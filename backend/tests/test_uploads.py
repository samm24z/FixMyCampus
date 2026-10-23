"""Photo uploads: signed-link flow, server-side sanitising, linking to tickets, gallery privacy, purge."""

import io
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from httpx import AsyncClient
from PIL import Image
from sqlalchemy import func, select, text

from app.core.config import settings
from app.core.database import AsyncSessionLocal, engine
from app.models import AuditLog, Department, Ticket, TicketAttachment
from app.services import upload_service
from app.services.storage import InMemoryStorage, set_storage

UPLOADS = "/api/v1/uploads"
TICKETS = "/api/v1/tickets"
BAD_LINK = "Some photos are missing or not yours — please remove and add them again"

NEW_TICKET = {
    "title": "Broken tap in the canteen",
    "description": "The tap next to the canteen counter has been leaking since this morning.",
    "category": "Water / Plumbing",
    "location": "Canteen",
    "priority": "MEDIUM",
}


@pytest.fixture(autouse=True)
def storage():
    store = InMemoryStorage()
    set_storage(store)
    upload_service.reset_rate_limits()
    yield store
    set_storage(None)
    upload_service.reset_rate_limits()


@pytest_asyncio.fixture(autouse=True)
async def clean_uploads():
    yield
    async with engine.begin() as conn:  # drafts have no ticket, so deleting tickets doesn't remove them
        await conn.execute(text("DELETE FROM ticket_attachments"))


def make_image(fmt: str = "JPEG", size=(64, 48), mode: str = "RGB", **save_kwargs) -> bytes:
    out = io.BytesIO()
    Image.new(mode, size, (200, 30, 30) if mode == "RGB" else None).save(out, fmt, **save_kwargs)
    return out.getvalue()


def jpeg_with_exif(size=(64, 48), orientation: int | None = None) -> bytes:
    exif = Image.Exif()
    exif[0x010F] = "SecretPhoneMaker"  # Make
    exif[0x0110] = "Model X"
    exif[0x9003] = "2026:10:20 10:00:00"  # DateTimeOriginal
    gps = exif.get_ifd(0x8825)
    gps[1], gps[2], gps[3], gps[4] = "N", (17.0, 23.0, 0.0), "E", (78.0, 28.0, 0.0)
    if orientation:
        exif[0x0112] = orientation
    return make_image("JPEG", size, exif=exif)


async def request_upload(client, headers, *, content_type="image/jpeg", size=1000, kind="image", name="photo.jpg"):
    return await client.post(
        UPLOADS, json={"kind": kind, "content_type": content_type, "size": size, "file_name": name}, headers=headers
    )


def put_in_storage(storage: InMemoryStorage, ticket: dict, data: bytes, content_type: str = "image/jpeg") -> str:
    key = ticket["upload_url"].removeprefix("memory://upload/")
    storage.objects[key] = (data, content_type)  # what the browser's PUT does
    return key


async def upload_photo(client, headers, storage, data: bytes | None = None, *, complete_body=None, declared="image/jpeg"):
    """Create, simulate the browser upload and complete. Returns the AttachmentRead JSON."""
    data = data if data is not None else make_image()
    created = await request_upload(client, headers, content_type=declared, size=len(data))
    assert created.status_code == 201, created.text
    ticket = created.json()
    put_in_storage(storage, ticket, data, declared)
    done = await client.post(f"{UPLOADS}/{ticket['upload_id']}/complete", json=complete_body or {}, headers=headers)
    assert done.status_code == 200, done.text
    return done.json()


async def file_ticket(client, headers, **extra) -> dict:
    response = await client.post(TICKETS, json={**NEW_TICKET, **extra}, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


async def attachment_row(upload_id: str) -> TicketAttachment | None:
    async with AsyncSessionLocal() as session:
        return await session.get(TicketAttachment, uuid.UUID(upload_id))


async def ticket_count() -> int:
    async with AsyncSessionLocal() as session:
        return await session.scalar(select(func.count()).select_from(Ticket))


# ------------------------------------------------------------- happy path

async def test_upload_flow_makes_a_clean_ready_photo(async_client: AsyncClient, login, storage):
    student = await login("student")
    created = await request_upload(async_client, student, size=2000)
    assert created.status_code == 201
    ticket = created.json()
    assert ticket["upload_method"] == "PUT"
    assert ticket["upload_url"].startswith("memory://upload/tickets/")

    original = jpeg_with_exif((200, 100))
    source_exif = Image.open(io.BytesIO(original)).getexif()
    assert source_exif[0x010F] == "SecretPhoneMaker" and source_exif.get_ifd(0x8825)  # the test input really has EXIF + GPS
    key = put_in_storage(storage, ticket, original)
    assert key.endswith("/original.jpg")

    done = await async_client.post(
        f"{UPLOADS}/{ticket['upload_id']}/complete",
        json={"captured_at": "2026-10-20T10:00:00Z", "gps": {"lat": 17.39, "lng": 78.49, "accuracy_m": 12}},
        headers=student,
    )
    assert done.status_code == 200, done.text
    body = done.json()
    assert body["status"] == "ready"
    assert body["ticket_id"] is None
    assert (body["width"], body["height"]) == (200, 100)
    assert body["mime_type"] == "image/jpeg"
    assert body["captured_at"].startswith("2026-10-20T10:00:00")

    row = await attachment_row(ticket["upload_id"])
    assert row.sha256 is not None and len(row.sha256) == 64
    assert row.file_size == len(storage.objects[row.storage_key][0])
    assert row.gps_lat == pytest.approx(17.39) and row.gps_accuracy_m == 12
    thumb, thumb_type = storage.objects[row.thumb_key]
    assert thumb_type == "image/jpeg" and row.thumb_key.endswith("/thumb.jpg")
    assert Image.open(io.BytesIO(thumb)).format == "JPEG"

    # Neither the stored original nor the thumbnail may keep any EXIF (GPS, make, timestamps).
    for stored_key in (row.storage_key, row.thumb_key):
        image = Image.open(io.BytesIO(storage.objects[stored_key][0]))
        assert len(image.getexif()) == 0
        assert b"SecretPhoneMaker" not in storage.objects[stored_key][0]
    assert storage.objects[key][0] != original


async def test_exif_orientation_is_applied_before_metadata_is_dropped(async_client: AsyncClient, login, storage):
    student = await login("student")
    body = await upload_photo(async_client, student, storage, jpeg_with_exif((64, 48), orientation=6))
    assert (body["width"], body["height"]) == (48, 64)
    row = await attachment_row(body["id"])
    assert len(Image.open(io.BytesIO(storage.objects[row.storage_key][0])).getexif()) == 0


async def test_thumbnail_is_at_most_1024_pixels(async_client: AsyncClient, login, storage):
    student = await login("student")
    body = await upload_photo(async_client, student, storage, make_image("JPEG", (2400, 1200)))
    assert (body["width"], body["height"]) == (2400, 1200)
    row = await attachment_row(body["id"])
    assert Image.open(io.BytesIO(storage.objects[row.thumb_key][0])).size == (1024, 512)


async def test_declared_type_is_not_trusted_real_format_is_stored(async_client: AsyncClient, login, storage):
    student = await login("student")
    body = await upload_photo(async_client, student, storage, make_image("PNG"), declared="image/jpeg")
    assert body["mime_type"] == "image/png"
    row = await attachment_row(body["id"])
    # The sanitised copy overwrites the upload under the same key, so no stray un-sanitised object
    # can be parked under a freed key with the still-valid signed upload link.
    assert row.storage_key.endswith("/original.jpg")
    data, content_type = storage.objects[row.storage_key]
    assert content_type == "image/png"
    assert Image.open(io.BytesIO(data)).format == "PNG"
    assert [key for key in storage.objects if "/original." in key] == [row.storage_key]


@pytest.mark.parametrize(
    "fmt,mode,mime",
    [("PNG", "RGBA", "image/png"), ("WEBP", "RGB", "image/webp"), ("PNG", "P", "image/png")],
)
async def test_png_webp_and_palette_images_are_accepted(async_client, login, storage, fmt, mode, mime):
    student = await login("student")
    data = make_image(fmt, mode=mode) if mode != "P" else _palette_png()
    body = await upload_photo(async_client, student, storage, data, declared=mime)
    assert body["mime_type"] == mime and body["status"] == "ready"
    row = await attachment_row(body["id"])
    assert Image.open(io.BytesIO(storage.objects[row.thumb_key][0])).mode == "RGB"  # JPEG thumbnail


def _palette_png() -> bytes:
    out = io.BytesIO()
    Image.new("P", (20, 20), 3).save(out, "PNG", transparency=0)
    return out.getvalue()


# ----------------------------------------------------------- limits & types

async def test_create_rejects_bad_requests(async_client: AsyncClient, login):
    student = await login("student")
    too_big = await request_upload(async_client, student, size=settings.UPLOAD_MAX_IMAGE_BYTES + 1)
    assert too_big.status_code == 422
    assert too_big.json()["error"]["message"] == "Photos can be up to 5 MB after shrinking"

    assert (await request_upload(async_client, student, content_type="image/gif")).status_code == 422
    assert (await request_upload(async_client, student, content_type="image/svg+xml")).status_code == 422
    assert (await request_upload(async_client, student, content_type="application/pdf")).status_code == 422
    assert (await request_upload(async_client, student, size=0)).status_code == 422


async def test_video_is_not_available_yet(async_client: AsyncClient, login):
    response = await request_upload(
        async_client, await login("student"), kind="video", content_type="video/mp4", name="clip.mp4"
    )
    assert response.status_code == 422
    assert response.json()["error"]["message"] == "Video uploads are coming soon"


async def test_uploads_need_login(async_client: AsyncClient):
    assert (await request_upload(async_client, {})).status_code == 401


async def test_at_most_ten_open_drafts(async_client: AsyncClient, login):
    student = await login("student")
    for _ in range(10):
        assert (await request_upload(async_client, student)).status_code == 201
    eleventh = await request_upload(async_client, student)
    assert eleventh.status_code == 422
    assert (await request_upload(async_client, await login("student2"))).status_code == 201  # per user


async def test_rate_limit(async_client: AsyncClient, login, monkeypatch):
    monkeypatch.setattr(settings, "UPLOADS_PER_10_MINUTES", 3)
    student = await login("student")
    for _ in range(3):
        assert (await request_upload(async_client, student)).status_code == 201
    limited = await request_upload(async_client, student)
    assert limited.status_code == 429
    assert limited.json()["error"]["code"] == "RATE_LIMITED"
    assert (await request_upload(async_client, await login("student2"))).status_code == 201


# ------------------------------------------------------------ complete errors

async def test_complete_without_the_file_arriving(async_client: AsyncClient, login):
    student = await login("student")
    ticket = (await request_upload(async_client, student)).json()
    response = await async_client.post(f"{UPLOADS}/{ticket['upload_id']}/complete", json={}, headers=student)
    assert response.status_code == 422
    assert response.json()["error"]["message"] == "The upload didn't arrive — please try again"
    assert (await attachment_row(ticket["upload_id"])).status == "draft"  # can still be retried


async def test_complete_rejects_an_oversized_object(async_client: AsyncClient, login, storage):
    student = await login("student")
    ticket = (await request_upload(async_client, student)).json()
    key = put_in_storage(storage, ticket, b"\0" * (settings.UPLOAD_MAX_IMAGE_BYTES + 1))
    response = await async_client.post(f"{UPLOADS}/{ticket['upload_id']}/complete", json={}, headers=student)
    assert response.status_code == 422
    assert key not in storage.objects
    assert (await attachment_row(ticket["upload_id"])).status == "rejected"


@pytest.mark.parametrize(
    "payload",
    [
        b"just some text, not a picture",
        b"<html><script>alert(1)</script></html>",
        b'<svg xmlns="http://www.w3.org/2000/svg" width="5" height="5"><rect width="5" height="5"/></svg>',
        b"GIF89a\x01\x00\x01\x00\x00\x00\x00;",  # a real GIF: decodable but not an allowed type
        make_image("JPEG")[:40],  # truncated
    ],
)
async def test_non_photos_are_rejected_and_their_files_deleted(async_client, login, storage, payload):
    student = await login("student")
    ticket = (await request_upload(async_client, student)).json()  # declared as image/jpeg
    put_in_storage(storage, ticket, payload)
    response = await async_client.post(f"{UPLOADS}/{ticket['upload_id']}/complete", json={}, headers=student)
    assert response.status_code == 422
    assert response.json()["error"]["message"] == "That file doesn't look like a photo."
    assert storage.objects == {}
    row = await attachment_row(ticket["upload_id"])
    assert row.status == "rejected" and row.thumb_key is None
    async with AsyncSessionLocal() as session:
        audits = (await session.scalars(select(AuditLog).where(AuditLog.entity_id == row.id))).all()
    assert any(a.new_values and a.new_values.get("status") == "rejected" for a in audits)


async def test_decompression_bomb_is_rejected(async_client: AsyncClient, login, storage, monkeypatch):
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 1000)
    student = await login("student")
    ticket = (await request_upload(async_client, student)).json()
    put_in_storage(storage, ticket, make_image("PNG", (100, 100)), "image/png")
    response = await async_client.post(f"{UPLOADS}/{ticket['upload_id']}/complete", json={}, headers=student)
    assert response.status_code == 422
    assert storage.objects == {}


async def test_complete_twice_is_a_conflict(async_client: AsyncClient, login, storage):
    student = await login("student")
    body = await upload_photo(async_client, student, storage)
    again = await async_client.post(f"{UPLOADS}/{body['id']}/complete", json={}, headers=student)
    assert again.status_code == 409


# ------------------------------------------------------- ownership (404s)

async def test_other_users_drafts_are_not_found(async_client: AsyncClient, login, storage):
    student, other = await login("student"), await login("student2")
    ticket = (await request_upload(async_client, student)).json()
    put_in_storage(storage, ticket, make_image())
    upload_id = ticket["upload_id"]

    assert (await async_client.post(f"{UPLOADS}/{upload_id}/complete", json={}, headers=other)).status_code == 404
    assert (await async_client.delete(f"{UPLOADS}/{upload_id}", headers=other)).status_code == 404
    coordinator = await login("coordinator")
    assert (await async_client.post(f"{UPLOADS}/{upload_id}/complete", json={}, headers=coordinator)).status_code == 404
    assert (await async_client.delete(f"{UPLOADS}/{upload_id}", headers=coordinator)).status_code == 404
    unknown = uuid.uuid4()
    assert (await async_client.post(f"{UPLOADS}/{unknown}/complete", json={}, headers=student)).status_code == 404

    assert (await attachment_row(upload_id)).status == "draft"  # untouched
    assert (await async_client.post(f"{UPLOADS}/{upload_id}/complete", json={}, headers=student)).status_code == 200


async def test_delete_removes_files_and_hides_the_upload(async_client: AsyncClient, login, storage):
    student = await login("student")
    body = await upload_photo(async_client, student, storage)
    assert len(storage.objects) == 2
    response = await async_client.delete(f"{UPLOADS}/{body['id']}", headers=student)
    assert response.status_code == 204
    assert storage.objects == {}
    row = await attachment_row(body["id"])
    assert row.status == "deleted"  # kept for the purge, which still needs its key
    assert (await async_client.delete(f"{UPLOADS}/{body['id']}", headers=student)).status_code == 404
    assert (await async_client.post(f"{UPLOADS}/{body['id']}/complete", json={}, headers=student)).status_code in (404, 409)
    assert (await async_client.post("/api/v1/tickets", json={
        "title": "Broken fan", "description": "The fan in the room does not spin.", "category": "Other",
        "location": "CSE Block", "attachment_ids": [body["id"]],
    }, headers=student)).status_code == 422


async def test_purge_sweeps_files_uploaded_to_a_deleted_drafts_key(async_client: AsyncClient, login, storage):
    student = await login("student")
    ticket = (await request_upload(async_client, student)).json()
    assert (await async_client.delete(f"{UPLOADS}/{ticket['upload_id']}", headers=student)).status_code == 204
    put_in_storage(storage, ticket, make_image())  # the signed link was used after the delete
    async with AsyncSessionLocal() as session:
        row = await session.get(TicketAttachment, uuid.UUID(ticket["upload_id"]))
        row.created_at = datetime.now(timezone.utc) - timedelta(days=2)
        row.expires_at = None
        await session.commit()
    async with AsyncSessionLocal() as session:
        assert await upload_service.purge_expired_drafts(session, storage) == 1
    assert storage.objects == {}
    assert await attachment_row(ticket["upload_id"]) is None


async def test_delete_a_draft_that_never_completed(async_client: AsyncClient, login, storage):
    student = await login("student")
    ticket = (await request_upload(async_client, student)).json()
    put_in_storage(storage, ticket, make_image())
    assert (await async_client.delete(f"{UPLOADS}/{ticket['upload_id']}", headers=student)).status_code == 204
    assert storage.objects == {}


async def test_attached_photo_cannot_be_deleted_through_uploads(async_client: AsyncClient, login, storage):
    student = await login("student")
    body = await upload_photo(async_client, student, storage)
    await file_ticket(async_client, student, attachment_ids=[body["id"]])
    assert (await async_client.delete(f"{UPLOADS}/{body['id']}", headers=student)).status_code == 404
    assert len(storage.objects) == 2


# ------------------------------------------------------- linking to tickets

async def test_ticket_links_photos_and_detail_counts_them(async_client: AsyncClient, login, storage):
    student = await login("student")
    first = await upload_photo(async_client, student, storage)
    second = await upload_photo(async_client, student, storage)
    detail = await file_ticket(async_client, student, attachment_ids=[first["id"], second["id"]])
    assert detail["attachment_count"] == 2

    for upload in (first, second):
        row = await attachment_row(upload["id"])
        assert str(row.ticket_id) == detail["id"] and row.expires_at is None

    fetched = await async_client.get(f"{TICKETS}/{detail['ticket_number']}", headers=student)
    assert fetched.json()["attachment_count"] == 2
    gallery = await async_client.get(f"{TICKETS}/{detail['id']}/attachments", headers=student)
    assert [item["id"] for item in gallery.json()] == [first["id"], second["id"]]

    async with AsyncSessionLocal() as session:
        audits = (await session.scalars(
            select(AuditLog).where(AuditLog.entity_type == "attachment", AuditLog.entity_id == uuid.UUID(first["id"]))
        )).all()
    assert any(a.new_values and a.new_values.get("ticket_id") == detail["id"] for a in audits)


async def test_ticket_without_photos_has_zero_count_and_defaults(async_client: AsyncClient, login):
    before = datetime.now(timezone.utc)
    detail = await file_ticket(async_client, await login("student"))
    assert detail["attachment_count"] == 0
    assert datetime.fromisoformat(detail["observed_at"]) >= before - timedelta(seconds=1)
    assert detail["location_source"] is None and detail["report_lat"] is None


async def test_ticket_stores_observed_time_and_reported_position(async_client: AsyncClient, login):
    student = await login("student")
    seen = (datetime.now(timezone.utc) - timedelta(days=1)).replace(microsecond=0)
    detail = await file_ticket(
        async_client, student, observed_at=seen.isoformat(), report_lat=17.3, report_lng=78.4,
        report_accuracy_m=25, location_source="device",
    )
    assert datetime.fromisoformat(detail["observed_at"]) == seen
    assert (detail["report_lat"], detail["report_lng"], detail["report_accuracy_m"]) == (17.3, 78.4, 25)
    assert detail["location_source"] == "device"


@pytest.mark.parametrize("scenario", ["someone_elses", "unfinished", "already_attached", "unknown", "rejected"])
async def test_bad_attachment_ids_fail_with_no_ticket_created(async_client, login, storage, scenario):
    student, other = await login("student"), await login("student2")
    if scenario == "someone_elses":
        attachment_id = (await upload_photo(async_client, other, storage))["id"]
    elif scenario == "unfinished":
        attachment_id = (await request_upload(async_client, student)).json()["upload_id"]
    elif scenario == "already_attached":
        attachment_id = (await upload_photo(async_client, student, storage))["id"]
        await file_ticket(async_client, student, attachment_ids=[attachment_id])
    elif scenario == "rejected":
        ticket = (await request_upload(async_client, student)).json()
        put_in_storage(storage, ticket, b"not an image")
        await async_client.post(f"{UPLOADS}/{ticket['upload_id']}/complete", json={}, headers=student)
        attachment_id = ticket["upload_id"]
    else:
        attachment_id = str(uuid.uuid4())

    before = await ticket_count()
    response = await async_client.post(TICKETS, json={**NEW_TICKET, "attachment_ids": [attachment_id]}, headers=student)
    assert response.status_code == 422
    assert response.json()["error"]["message"] == BAD_LINK
    assert await ticket_count() == before


async def test_one_bad_photo_among_good_ones_links_nothing(async_client: AsyncClient, login, storage):
    student, other = await login("student"), await login("student2")
    mine = (await upload_photo(async_client, student, storage))["id"]
    theirs = (await upload_photo(async_client, other, storage))["id"]
    before = await ticket_count()
    response = await async_client.post(TICKETS, json={**NEW_TICKET, "attachment_ids": [mine, theirs]}, headers=student)
    assert response.status_code == 422
    assert await ticket_count() == before
    row = await attachment_row(mine)
    assert row.ticket_id is None and row.expires_at is not None  # still a draft, can be used again
    assert (await async_client.post(TICKETS, json={**NEW_TICKET, "attachment_ids": [mine]}, headers=student)).status_code == 201


async def test_at_most_five_photos_per_ticket(async_client: AsyncClient, login):
    ids = [str(uuid.uuid4()) for _ in range(settings.UPLOAD_MAX_PHOTOS + 1)]
    response = await async_client.post(
        TICKETS, json={**NEW_TICKET, "attachment_ids": ids}, headers=await login("student")
    )
    assert response.status_code == 422


async def test_same_photo_listed_twice_is_linked_once(async_client: AsyncClient, login, storage):
    student = await login("student")
    photo = (await upload_photo(async_client, student, storage))["id"]
    detail = await file_ticket(async_client, student, attachment_ids=[photo, photo])
    assert detail["attachment_count"] == 1


@pytest.mark.parametrize(
    "extra",
    [
        {"observed_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()},
        {"report_lat": 17.3},
        {"report_lng": 78.4},
        {"report_lat": 91, "report_lng": 78.4},
        {"report_lat": 17.3, "report_lng": 181},
        {"report_lat": 17.3, "report_lng": 78.4, "report_accuracy_m": -1},
        {"location_source": "telepathy"},
    ],
)
async def test_invalid_time_and_position_are_rejected(async_client: AsyncClient, login, extra):
    before = await ticket_count()
    response = await async_client.post(TICKETS, json={**NEW_TICKET, **extra}, headers=await login("student"))
    assert response.status_code == 422
    assert await ticket_count() == before


async def test_observed_time_a_few_minutes_ahead_is_tolerated(async_client: AsyncClient, login):
    soon = (datetime.now(timezone.utc) + timedelta(minutes=2)).isoformat()
    await file_ticket(async_client, await login("student"), observed_at=soon)


# ------------------------------------------------------------------ gallery

async def ticket_with_located_photo(client, login, storage):
    student = await login("student")
    photo = await upload_photo(
        client, student, storage,
        complete_body={"captured_at": "2026-10-20T10:00:00Z", "gps": {"lat": 17.39, "lng": 78.49, "accuracy_m": 8}},
    )
    detail = await file_ticket(
        client, student, attachment_ids=[photo["id"]], report_lat=17.4, report_lng=78.5, location_source="photo"
    )
    return detail, photo


async def assign_to(client, login, ticket_number: str, staff_email: str) -> None:
    coordinator = await login("coordinator")
    staff = next(u for u in (await client.get("/api/v1/users/staff", headers=coordinator)).json() if u["email"] == staff_email)
    response = await client.post(
        f"{TICKETS}/{ticket_number}/assign", json={"assigned_to": staff["id"]}, headers=coordinator
    )
    assert response.status_code == 200, response.text


def assert_location_visible(item: dict) -> None:
    assert item["gps_lat"] == pytest.approx(17.39) and item["gps_lng"] == pytest.approx(78.49)
    assert item["gps_accuracy_m"] == 8 and item["captured_at"].startswith("2026-10-20T10:00:00")


async def test_reporter_and_coordinator_see_photo_location(async_client: AsyncClient, login, storage):
    detail, photo = await ticket_with_located_photo(async_client, login, storage)
    for who in ("student", "coordinator", "admin"):
        headers = await login(who)
        response = await async_client.get(f"{TICKETS}/{detail['ticket_number']}/attachments", headers=headers)
        assert response.status_code == 200
        [item] = response.json()
        assert item["id"] == photo["id"]
        assert_location_visible(item)
        assert item["view_url"].startswith("memory://view/") and item["thumb_url"].endswith("thumb.jpg?expires_in=300")
        shown = (await async_client.get(f"{TICKETS}/{detail['id']}", headers=headers)).json()
        assert shown["report_lat"] == 17.4 and shown["location_source"] == "photo"


async def test_assigned_staff_see_location_but_other_departments_get_404(async_client: AsyncClient, login, storage):
    detail, _ = await ticket_with_located_photo(async_client, login, storage)
    await assign_to(async_client, login, detail["ticket_number"], "staff@fixmycampus.dev")

    staff = await login("staff")
    [item] = (await async_client.get(f"{TICKETS}/{detail['id']}/attachments", headers=staff)).json()
    assert_location_visible(item)
    assert (await async_client.get(f"{TICKETS}/{detail['id']}", headers=staff)).json()["report_lat"] == 17.4

    other_dept = await login("staff2")
    assert (await async_client.get(f"{TICKETS}/{detail['id']}/attachments", headers=other_dept)).status_code == 404


async def test_department_staff_who_are_not_assigned_see_location(async_client: AsyncClient, login, storage):
    detail, _ = await ticket_with_located_photo(async_client, login, storage)
    async with AsyncSessionLocal() as session:
        electrical = await session.scalar(select(Department).where(Department.code == "ELECTRICAL"))
        ticket = await session.get(Ticket, uuid.UUID(detail["id"]))
        ticket.confirmed_department_id = electrical.id
        await session.commit()
    [item] = (await async_client.get(f"{TICKETS}/{detail['id']}/attachments", headers=await login("staff2"))).json()
    assert_location_visible(item)


async def test_other_students_and_faculty_get_404(async_client: AsyncClient, login, storage):
    detail, _ = await ticket_with_located_photo(async_client, login, storage)
    for who in ("student2", "faculty"):
        headers = await login(who)
        assert (await async_client.get(f"{TICKETS}/{detail['id']}/attachments", headers=headers)).status_code == 404
        assert (await async_client.get(f"{TICKETS}/{detail['ticket_number']}/attachments", headers=headers)).status_code == 404
    unknown = await async_client.get(f"{TICKETS}/TICK-1999-0001/attachments", headers=await login("student"))
    assert unknown.status_code == 404
    assert (await async_client.get(f"{TICKETS}/{detail['id']}/attachments")).status_code == 401


async def test_gallery_lists_only_ready_photos_in_upload_order(async_client: AsyncClient, login, storage):
    student = await login("student")
    first = await upload_photo(async_client, student, storage)
    second = await upload_photo(async_client, student, storage)
    detail = await file_ticket(async_client, student, attachment_ids=[second["id"], first["id"]])
    # Something stuck on the ticket that never became ready must not be listed or counted.
    async with AsyncSessionLocal() as session:
        stray = await session.get(TicketAttachment, uuid.UUID(first["id"]))
        session.add(TicketAttachment(
            ticket_id=uuid.UUID(detail["id"]), uploaded_by=stray.uploaded_by, file_name="x.jpg",
            storage_key="tickets/x/original.jpg", file_size=1, mime_type="image/jpeg", status="draft",
        ))
        await session.commit()
    gallery = (await async_client.get(f"{TICKETS}/{detail['id']}/attachments", headers=student)).json()
    assert [item["id"] for item in gallery] == [first["id"], second["id"]]  # by created_at
    shown = (await async_client.get(f"{TICKETS}/{detail['id']}", headers=student)).json()
    assert shown["attachment_count"] == 2


async def test_detail_hides_report_position_from_non_staff(async_client: AsyncClient, login, storage):
    detail, _ = await ticket_with_located_photo(async_client, login, storage)
    # Faculty can't view this ticket at all; the position is only ever returned to the reporter and staff.
    from app.core import permissions as policy
    from app.models import User

    async with AsyncSessionLocal() as session:
        ticket = await session.get(Ticket, uuid.UUID(detail["id"]))
        users = {u.email.split("@")[0]: u for u in (await session.scalars(select(User))).all()}
        assert policy.can_see_media_location(users["student"], ticket)
        assert policy.can_see_media_location(users["coordinator"], ticket)
        assert policy.can_see_media_location(users["admin"], ticket)
        assert not policy.can_see_media_location(users["student2"], ticket)
        assert not policy.can_see_media_location(users["faculty"], ticket)
        assert not policy.can_see_media_location(users["staff"], ticket)  # staff outside the ticket's department
        assert policy.can_see_media_location(users["staff"], _with_department(ticket, users["staff"].department_id))


def _with_department(ticket: Ticket, department_id):
    ticket.confirmed_department_id = department_id  # in-memory only, never committed
    return ticket


# -------------------------------------------------------------------- purge

async def test_purge_removes_expired_drafts_and_their_files(async_client: AsyncClient, login, storage):
    student = await login("student")
    expired = await upload_photo(async_client, student, storage)
    fresh = await upload_photo(async_client, student, storage)
    attached = await upload_photo(async_client, student, storage)
    await file_ticket(async_client, student, attachment_ids=[attached["id"]])
    never_finished = (await request_upload(async_client, student)).json()
    put_in_storage(storage, never_finished, make_image())

    past = datetime.now(timezone.utc) - timedelta(minutes=1)
    async with AsyncSessionLocal() as session:
        for upload_id in (expired["id"], never_finished["upload_id"]):
            (await session.get(TicketAttachment, uuid.UUID(upload_id))).expires_at = past
        await session.commit()
    expired_row = await attachment_row(expired["id"])
    expired_keys = {expired_row.storage_key, expired_row.thumb_key}
    assert expired_keys <= storage.objects.keys()

    async with AsyncSessionLocal() as session:
        assert await upload_service.purge_expired_drafts(session, storage) == 2

    assert await attachment_row(expired["id"]) is None
    assert await attachment_row(never_finished["upload_id"]) is None
    assert not (expired_keys & storage.objects.keys())
    assert len(storage.objects) == 4  # the fresh and the attached photo, original + thumbnail each
    assert await attachment_row(fresh["id"]) is not None
    assert await attachment_row(attached["id"]) is not None

    async with AsyncSessionLocal() as session:
        assert await upload_service.purge_expired_drafts(session, storage) == 0


async def test_purge_removes_old_rejected_rows_only(async_client: AsyncClient, login, storage):
    student = await login("student")
    old, recent = [], []
    for bucket in (old, recent):
        ticket = (await request_upload(async_client, student)).json()
        put_in_storage(storage, ticket, b"nope")
        await async_client.post(f"{UPLOADS}/{ticket['upload_id']}/complete", json={}, headers=student)
        bucket.append(ticket["upload_id"])
    async with AsyncSessionLocal() as session:
        row = await session.get(TicketAttachment, uuid.UUID(old[0]))
        row.created_at = datetime.now(timezone.utc) - timedelta(days=2)
        row.expires_at = None  # purged because it is rejected and old, not because it expired
        await session.commit()
    async with AsyncSessionLocal() as session:
        assert await upload_service.purge_expired_drafts(session, storage) == 1
    assert await attachment_row(old[0]) is None
    assert await attachment_row(recent[0]) is not None


async def test_expired_photo_can_no_longer_be_attached(async_client: AsyncClient, login, storage):
    student = await login("student")
    photo = await upload_photo(async_client, student, storage)
    async with AsyncSessionLocal() as session:
        (await session.get(TicketAttachment, uuid.UUID(photo["id"]))).expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
        await session.commit()
    # Past its expiry a photo is as good as gone: it can no longer be attached.
    response = await async_client.post(TICKETS, json={**NEW_TICKET, "attachment_ids": [photo["id"]]}, headers=student)
    assert response.status_code == 422
