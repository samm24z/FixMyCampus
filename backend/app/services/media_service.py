"""Describe it for me: Gemini drafts a ticket from the student's uploaded photos.

The photos' thumbnails go to Gemini with the student's note and chosen place (never GPS, names or
emails). The draft is only a suggestion: every field is checked here before it reaches the form.
A photo Gemini flags as inappropriate is rejected and deleted on the spot.
"""

import asyncio
import logging
import time
import uuid
from collections import deque
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ai.media_llm import GeminiMediaService
from app.core import campus
from app.core.config import settings
from app.core.exceptions import AppException, UnprocessableException
from app.models.enums import AuditActionEnum, CategoryEnum, PriorityEnum
from app.models.ticket import TicketAttachment
from app.models.user import User
from app.schemas.attachment import DescribeRequest, MediaDraft
from app.services.audit_service import record_audit
from app.services.storage import get_storage

logger = logging.getLogger("app.media")

MAX_THUMB_BYTES = 2 * 1024 * 1024
RATE_LIMIT_TEXT = "You're asking quickly; try again in a minute"
UNAVAILABLE_TEXT = "Couldn't describe it right now — please type a short description."
REJECTED_TEXT = "These photos can't be used. Please upload a photo of the problem only."
NOT_YOURS_TEXT = "Some photos are missing or not yours — please remove and add them again"

CATEGORY_VALUES = {c.value for c in CategoryEnum}
PRIORITY_VALUES = {p.value for p in PriorityEnum}

_llm: Optional[GeminiMediaService] = None
_recent: dict[uuid.UUID, deque] = {}


def get_media_llm() -> Optional[GeminiMediaService]:
    global _llm
    if _llm is None and settings.GEMINI_API_KEY:
        _llm = GeminiMediaService(settings.GEMINI_API_KEY, settings.GEMINI_MODEL, settings.MEDIA_DESCRIBE_TIMEOUT_SECONDS)
    return _llm if settings.GEMINI_API_KEY else None


def set_media_llm(service: Optional[GeminiMediaService]) -> None:
    global _llm
    _llm = service


def reset_rate_limits() -> None:
    _recent.clear()


def check_rate_limit(user: User) -> None:
    now = time.monotonic()
    stamps = _recent.setdefault(user.id, deque())
    while stamps and now - stamps[0] > 60:
        stamps.popleft()
    if len(stamps) >= settings.MEDIA_DESCRIBE_PER_MINUTE:
        raise AppException(RATE_LIMIT_TEXT, 429, "RATE_LIMITED")
    stamps.append(now)


def _unavailable() -> AppException:
    return AppException(UNAVAILABLE_TEXT, 503, "AI_UNAVAILABLE")


def sanitise_draft(raw: dict[str, Any]) -> MediaDraft:
    """Only values the ticket form accepts: unknown categories become Other, places must be real campus places."""
    category = str(raw.get("category") or "").strip()
    priority = str(raw.get("priority") or "").strip().upper()
    try:
        confidence = min(1.0, max(0.0, float(raw.get("confidence"))))
    except (TypeError, ValueError):
        confidence = 0.0
    hint = raw.get("location_hint")
    place = campus.match_place(hint) if isinstance(hint, str) and hint.strip() else None
    return MediaDraft(
        title=" ".join(str(raw.get("title") or "").split())[:120],
        description=str(raw.get("description") or "").strip()[:2000],
        category=category if category in CATEGORY_VALUES else CategoryEnum.OTHER.value,
        priority=PriorityEnum(priority if priority in PRIORITY_VALUES else PriorityEnum.MEDIUM.value),
        location_hint=place.name if place else None,
        confidence=confidence,
        contains_people=bool(raw.get("contains_people")),
    )


async def _reject(db: AsyncSession, user: User, attachments: list[TicketAttachment]) -> None:
    keys: list[str] = []
    for attachment in attachments:
        attachment.status = "rejected"
        keys += [key for key in (attachment.storage_key, attachment.thumb_key) if key]
        record_audit(
            db, user=user, action=AuditActionEnum.UPDATE, entity_type="attachment", entity_id=attachment.id,
            new_values={"status": "rejected", "reason": "inappropriate"},
        )
    await db.commit()
    try:
        await get_storage().delete(keys)
    except Exception as exc:  # the hourly clean-up removes rejected rows and any objects left behind
        logger.warning("Could not delete rejected photos (%s)", type(exc).__name__)


async def describe_uploads(db: AsyncSession, user: User, payload: DescribeRequest) -> MediaDraft:
    check_rate_limit(user)
    ids = list(dict.fromkeys(payload.upload_ids))
    rows = (await db.scalars(select(TicketAttachment).where(TicketAttachment.id.in_(ids)))).all()
    if len(rows) != len(ids) or any(
        row.uploaded_by != user.id or row.status != "ready" or row.ticket_id is not None or not row.thumb_key for row in rows
    ):
        raise UnprocessableException(NOT_YOURS_TEXT)
    by_id = {row.id: row for row in rows}
    attachments = [by_id[i] for i in ids]

    llm = get_media_llm()
    if llm is None:
        raise _unavailable()
    storage = get_storage()
    images = [await storage.read(attachment.thumb_key, MAX_THUMB_BYTES) for attachment in attachments]

    try:
        raw = await asyncio.wait_for(
            llm.describe(images, payload.note, payload.place, [p.name for p in campus.PLACES]),
            timeout=settings.MEDIA_DESCRIBE_TIMEOUT_SECONDS,
        )
    except Exception as exc:  # fail soft: the student can type the description themselves
        logger.warning("Photo description failed (%s)", type(exc).__name__)
        raise _unavailable() from None

    if raw.get("inappropriate") is True:
        await _reject(db, user, attachments)
        raise UnprocessableException(REJECTED_TEXT)
    return sanitise_draft(raw)
