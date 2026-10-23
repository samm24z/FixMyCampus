"""Photo uploads: signed upload links, completion checks, drafts, linking to tickets, clean-up.

The browser sends the file straight to storage. ``complete_upload`` then reads it back, decides
what it really is by decoding it, and writes a metadata-free copy plus a thumbnail, so nothing
stored ever carries the EXIF (GPS, device, timestamps) of the original. Capture time and GPS
that the browser read before shrinking live only in database columns, and are shown only to
people allowed by ``permissions.can_see_media_location``.
"""

import asyncio
import hashlib
import logging
import time
import uuid
from collections import deque
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import and_, delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import permissions as policy
from app.core.config import settings
from app.core.exceptions import AppException, ConflictException, NotFoundException, UnprocessableException
from app.models.enums import AuditActionEnum
from app.models.ticket import Ticket, TicketAttachment
from app.models.user import User
from app.schemas.attachment import AttachmentRead, AttachmentView, UploadComplete, UploadCreate, UploadTicket
from app.services.audit_service import record_audit
from app.services.image_processing import ImageRejected, sanitise_image
from app.services.storage import Storage, StorageError, get_storage

logger = logging.getLogger("app.uploads")

ALLOWED_CONTENT_TYPES = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}
MAX_OPEN_DRAFTS = 10
RATE_WINDOW_SECONDS = 600
VIEW_URL_SECONDS = 300
REJECTED_KEEP = timedelta(days=1)
PURGE_BATCH = 200

NOT_A_PHOTO = "That file doesn't look like a photo."
TOO_BIG = "Photos can be up to 5 MB after shrinking"
NOT_ARRIVED = "The upload didn't arrive — please try again"
BAD_LINK = "Some photos are missing or not yours — please remove and add them again"

_recent: dict[uuid.UUID, deque] = {}
# Decoding is memory-heavy; keep at most two photos in flight per process.
_image_slots = asyncio.Semaphore(2)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _utc(value: Optional[datetime]) -> Optional[datetime]:
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def reset_rate_limits() -> None:
    _recent.clear()


def check_rate_limit(user: User) -> None:
    now = time.monotonic()
    stamps = _recent.setdefault(user.id, deque())
    while stamps and now - stamps[0] > RATE_WINDOW_SECONDS:
        stamps.popleft()
    if len(stamps) >= settings.UPLOADS_PER_10_MINUTES:
        raise AppException("You're uploading photos too quickly — please wait a few minutes.", 429, "RATE_LIMITED")
    stamps.append(now)


def _folder(attachment: TicketAttachment) -> str:
    return attachment.storage_key.rsplit("/", 1)[0]


def _object_keys(attachment: TicketAttachment) -> list[str]:
    keys = {attachment.storage_key, f"{_folder(attachment)}/thumb.jpg"}
    if attachment.thumb_key:
        keys.add(attachment.thumb_key)
    return sorted(keys)


async def _own_unattached(db: AsyncSession, user: User, upload_id: uuid.UUID) -> TicketAttachment:
    """The caller's own draft or ready upload, locked. Anyone else's reads as missing, never forbidden."""
    attachment = await db.scalar(
        select(TicketAttachment)
        .where(
            TicketAttachment.id == upload_id,
            TicketAttachment.uploaded_by == user.id,
            TicketAttachment.ticket_id.is_(None),
        )
        .with_for_update()
    )
    if attachment is None:
        raise NotFoundException("Upload", upload_id)
    return attachment


# ------------------------------------------------------------------ create

async def create_upload(
    db: AsyncSession, user: User, payload: UploadCreate, storage: Optional[Storage] = None
) -> UploadTicket:
    storage = storage or get_storage()
    if payload.kind != "image":
        raise UnprocessableException("Video uploads are coming soon")
    content_type = payload.content_type.strip().lower()
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise UnprocessableException("Please choose a JPEG, PNG or WebP photo")
    if payload.size > settings.UPLOAD_MAX_IMAGE_BYTES:
        raise UnprocessableException(TOO_BIG)
    check_rate_limit(user)

    now = _now()
    open_count = await db.scalar(
        select(func.count()).select_from(TicketAttachment).where(
            TicketAttachment.uploaded_by == user.id,
            TicketAttachment.ticket_id.is_(None),
            TicketAttachment.status.in_(("draft", "ready")),
            TicketAttachment.expires_at > now,
        )
    )
    if (open_count or 0) >= MAX_OPEN_DRAFTS:
        raise UnprocessableException("You have too many photos waiting to be sent — remove some and try again")

    upload_id = uuid.uuid4()
    key = f"tickets/{now:%Y}/{now:%m}/{upload_id}/original.{ALLOWED_CONTENT_TYPES[content_type]}"
    target = await storage.create_upload_url(key, content_type)
    attachment = TicketAttachment(
        id=upload_id, ticket_id=None, uploaded_by=user.id,
        file_name=payload.file_name.replace("\\", "/").rsplit("/", 1)[-1][:255] or "photo",
        storage_key=key, file_size=payload.size, mime_type=content_type,
        kind="image", status="draft", expires_at=now + timedelta(hours=settings.UPLOAD_DRAFT_HOURS),
    )
    db.add(attachment)
    record_audit(
        db, user=user, action=AuditActionEnum.CREATE, entity_type="attachment", entity_id=upload_id,
        new_values={"kind": "image", "status": "draft", "declared_type": content_type, "size": payload.size},
    )
    await db.commit()
    return UploadTicket(
        upload_id=upload_id, upload_url=target.url, upload_method=target.method,
        upload_headers=target.headers, expires_at=attachment.expires_at,
    )


# ---------------------------------------------------------------- complete

async def _reject(
    db: AsyncSession, user: User, attachment: TicketAttachment, storage: Storage, reason: str, message: str
) -> None:
    keys = _object_keys(attachment)
    attachment.status = "rejected"
    attachment.thumb_key = None
    record_audit(
        db, user=user, action=AuditActionEnum.UPDATE, entity_type="attachment", entity_id=attachment.id,
        old_values={"status": "draft"}, new_values={"status": "rejected", "reason": reason},
    )
    await db.commit()
    try:
        await storage.delete(keys)
    except StorageError:
        logger.warning("Couldn't delete rejected upload %s now; the purge will retry", attachment.id)
    raise UnprocessableException(message)


async def complete_upload(
    db: AsyncSession, user: User, upload_id: uuid.UUID, payload: UploadComplete, storage: Optional[Storage] = None
) -> AttachmentRead:
    storage = storage or get_storage()
    attachment = await _own_unattached(db, user, upload_id)
    if attachment.status != "draft":
        raise ConflictException("This upload is already finished")
    if attachment.expires_at is not None and attachment.expires_at < _now():
        raise NotFoundException("Upload", upload_id)

    stored = await storage.head(attachment.storage_key)
    if stored is None:
        raise UnprocessableException(NOT_ARRIVED)
    if stored.size > settings.UPLOAD_MAX_IMAGE_BYTES:
        await _reject(db, user, attachment, storage, "too_large", TOO_BIG)
    original = await storage.read(attachment.storage_key, settings.UPLOAD_MAX_IMAGE_BYTES)
    digest = hashlib.sha256(original).hexdigest()

    try:
        async with _image_slots:
            processed = await asyncio.to_thread(sanitise_image, original)
    except ImageRejected as error:
        await _reject(db, user, attachment, storage, error.reason, NOT_A_PHOTO)
    del original

    # The sanitised copy overwrites the upload under the SAME key, even when the real format differs
    # from the declared one (mime_type records the truth). A new key would free the old one, and the
    # browser's signed upload link (valid for hours, no overwrite) could then park an un-sanitised
    # file there that nothing tracks.
    thumb_key = f"{_folder(attachment)}/thumb.jpg"
    await storage.put(attachment.storage_key, processed.data, processed.mime_type)
    await storage.put(thumb_key, processed.thumbnail, "image/jpeg")

    gps = payload.gps
    attachment.thumb_key = thumb_key
    attachment.mime_type = processed.mime_type
    attachment.file_size = len(processed.data)
    attachment.width, attachment.height = processed.width, processed.height
    attachment.sha256 = digest
    attachment.captured_at = _utc(payload.captured_at)
    attachment.gps_lat = gps.lat if gps else None
    attachment.gps_lng = gps.lng if gps else None
    attachment.gps_accuracy_m = gps.accuracy_m if gps else None
    attachment.status = "ready"
    record_audit(
        db, user=user, action=AuditActionEnum.UPDATE, entity_type="attachment", entity_id=attachment.id,
        old_values={"status": "draft"},
        new_values={"status": "ready", "mime_type": processed.mime_type, "has_gps": gps is not None},
    )
    await db.commit()
    await db.refresh(attachment)
    return AttachmentRead.model_validate(attachment)


# ------------------------------------------------------------------ delete

async def delete_upload(
    db: AsyncSession, user: User, upload_id: uuid.UUID, storage: Optional[Storage] = None
) -> None:
    storage = storage or get_storage()
    attachment = await _own_unattached(db, user, upload_id)
    if attachment.status not in ("draft", "ready"):
        raise NotFoundException("Upload", upload_id)
    await storage.delete(_object_keys(attachment))
    record_audit(
        db, user=user, action=AuditActionEnum.DELETE, entity_type="attachment", entity_id=attachment.id,
        old_values={"status": attachment.status},
    )
    # Keep the row for a day instead of deleting it: the signed upload link is still valid for a
    # while, and the purge must still know this key to sweep anything uploaded to it afterwards.
    attachment.status = "deleted"
    attachment.thumb_key = None
    await db.commit()


# ------------------------------------------------------- linking to a ticket

async def claim_for_ticket(db: AsyncSession, user: User, upload_ids: list[uuid.UUID]) -> list[TicketAttachment]:
    """The caller's own ready, unattached photos, locked for linking; anything else is a 422."""
    if not upload_ids:
        return []
    rows = (await db.scalars(
        select(TicketAttachment).where(TicketAttachment.id.in_(upload_ids)).with_for_update()
    )).all()
    now = _now()
    usable = [
        row for row in rows
        if row.uploaded_by == user.id and row.status == "ready" and row.kind == "image"
        and row.ticket_id is None and (row.expires_at is None or row.expires_at > now)
    ]
    if len(usable) != len(set(upload_ids)):
        raise UnprocessableException(BAD_LINK)
    order = {upload_id: index for index, upload_id in enumerate(upload_ids)}
    return sorted(usable, key=lambda row: order[row.id])


def link_to_ticket(db: AsyncSession, user: User, ticket: Ticket, attachments: list[TicketAttachment]) -> None:
    """Attach claimed photos to the (flushed) ticket in the caller's transaction."""
    for attachment in attachments:
        attachment.ticket_id = ticket.id
        attachment.expires_at = None
        record_audit(
            db, user=user, action=AuditActionEnum.UPDATE, entity_type="attachment", entity_id=attachment.id,
            old_values={"ticket_id": None}, new_values={"ticket_id": str(ticket.id)},
        )


# ----------------------------------------------------------------- gallery

async def gallery_for_ticket(
    db: AsyncSession, user: User, ticket: Ticket, storage: Optional[Storage] = None
) -> list[AttachmentView]:
    """Ready photos of a ticket the caller can already see, with short-lived links."""
    storage = storage or get_storage()
    rows = (await db.scalars(
        select(TicketAttachment)
        .where(TicketAttachment.ticket_id == ticket.id, TicketAttachment.status == "ready")
        .order_by(TicketAttachment.created_at, TicketAttachment.id)
    )).all()
    if not rows:
        return []
    keys = [key for row in rows for key in (row.storage_key, row.thumb_key) if key]
    urls = await storage.create_view_urls(keys, VIEW_URL_SECONDS)
    show_location = policy.can_see_media_location(user, ticket)
    return [
        AttachmentView(
            id=row.id, kind=row.kind, file_name=row.file_name, mime_type=row.mime_type,
            width=row.width, height=row.height, duration_s=row.duration_s, created_at=row.created_at,
            view_url=urls.get(row.storage_key), thumb_url=urls.get(row.thumb_key) if row.thumb_key else None,
            captured_at=row.captured_at if show_location else None,
            gps_lat=row.gps_lat if show_location else None,
            gps_lng=row.gps_lng if show_location else None,
            gps_accuracy_m=row.gps_accuracy_m if show_location else None,
        )
        for row in rows
    ]


# ------------------------------------------------------------------- purge

async def purge_expired_drafts(db: AsyncSession, storage: Optional[Storage] = None) -> int:
    """Delete unattached uploads past their expiry, and rejected or deleted ones after a day, with their files."""
    storage = storage or get_storage()
    now = _now()
    rows = (await db.scalars(
        select(TicketAttachment)
        .where(
            TicketAttachment.ticket_id.is_(None),
            or_(
                and_(TicketAttachment.expires_at.is_not(None), TicketAttachment.expires_at < now),
                and_(
                    TicketAttachment.status.in_(("rejected", "deleted")),
                    TicketAttachment.created_at < now - REJECTED_KEEP,
                ),
            ),
        )
        .limit(PURGE_BATCH)
        .with_for_update(skip_locked=True)
    )).all()
    purged = 0
    for attachment in rows:
        try:
            await storage.delete(_object_keys(attachment))
        except StorageError:
            logger.warning("Couldn't delete files of upload %s; will retry next pass", attachment.id)
            continue
        record_audit(
            db, user=None, action=AuditActionEnum.DELETE, entity_type="attachment", entity_id=attachment.id,
            old_values={"status": attachment.status, "reason": "expired"},
        )
        await db.execute(delete(TicketAttachment).where(TicketAttachment.id == attachment.id))
        purged += 1
    await db.commit()
    return purged
