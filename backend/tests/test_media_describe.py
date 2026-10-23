"""Describe it for me: photos to a draft ticket via Gemini (mocked), with ownership, safety and fail-soft rules."""

import base64
import json
import uuid
from datetime import datetime, timezone

import httpx
import pytest
from sqlalchemy import select

from ai.media_llm import GeminiMediaService
from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models import AuditLog
from app.models.ticket import TicketAttachment
from app.services import media_service
from app.services.storage import InMemoryStorage, set_storage
from scripts.demo_users import demo_user_id

URL = "/api/v1/uploads/describe"
THUMB = b"\xff\xd8\xff\xe0fake-jpeg-thumbnail"
ERROR_TEXT = "Couldn't describe it right now — please type a short description."


@pytest.fixture(autouse=True)
def storage():
    store = InMemoryStorage()
    set_storage(store)
    media_service.set_media_llm(None)
    media_service.reset_rate_limits()
    yield store
    set_storage(None)
    media_service.set_media_llm(None)
    media_service.reset_rate_limits()


def draft_reply(**fields) -> dict:
    draft = {
        "title": "Broken ceiling fan in classroom", "description": "The fan blade is bent and hangs low.",
        "category": "Electrical", "priority": "HIGH", "location_hint": None, "confidence": 0.9,
        "contains_people": False, "inappropriate": False, **fields,
    }
    return {"candidates": [{"content": {"parts": [{"text": json.dumps(draft)}]}}]}


def use_llm(monkeypatch, handler) -> list[httpx.Request]:
    seen: list[httpx.Request] = []

    def record(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return handler(request)

    monkeypatch.setattr(settings, "GEMINI_API_KEY", "test-key")
    media_service.set_media_llm(GeminiMediaService("test-key", settings.GEMINI_MODEL, transport=httpx.MockTransport(record)))
    return seen


def ok(**fields):
    return lambda request: httpx.Response(200, json=draft_reply(**fields))


async def add_photo(storage: InMemoryStorage, owner: str = "student", **overrides) -> uuid.UUID:
    """A ready draft upload whose thumbnail is in storage, as the upload endpoints would leave it."""
    attachment_id = uuid.uuid4()
    key = f"tickets/2026/10/{attachment_id}"
    storage.objects[f"{key}/original.jpg"] = (b"original", "image/jpeg")
    storage.objects[f"{key}/thumb.jpg"] = (THUMB, "image/jpeg")
    values = dict(
        id=attachment_id, uploaded_by=demo_user_id(owner), file_name="fan.jpg", storage_key=f"{key}/original.jpg",
        thumb_key=f"{key}/thumb.jpg", file_size=8, mime_type="image/jpeg", kind="image", status="ready",
        width=800, height=600, captured_at=datetime(2026, 10, 1, tzinfo=timezone.utc), gps_lat=17.3871, gps_lng=78.3911,
    )
    async with AsyncSessionLocal() as db:
        db.add(TicketAttachment(**{**values, **overrides}))
        await db.commit()
    return attachment_id


async def status_of(attachment_id) -> str:
    async with AsyncSessionLocal() as db:
        return (await db.get(TicketAttachment, attachment_id)).status


async def describe(client, headers, ids, **body):
    return await client.post(URL, json={"upload_ids": [str(i) for i in ids], **body}, headers=headers)


async def test_needs_sign_in(async_client):
    assert (await async_client.post(URL, json={"upload_ids": [str(uuid.uuid4())]})).status_code == 401


async def test_draft_comes_back_and_only_photos_and_text_are_sent(async_client, login, storage, monkeypatch):
    seen = use_llm(monkeypatch, ok(location_hint="CSE Block"))
    ids = [await add_photo(storage), await add_photo(storage)]
    response = await describe(async_client, await login("student"), ids, note="the fan is wobbling", place="CSE Block, Room 204")
    assert response.status_code == 200
    assert response.json() == {
        "title": "Broken ceiling fan in classroom", "description": "The fan blade is bent and hangs low.",
        "category": "Electrical", "priority": "HIGH", "location_hint": "CSE Block", "confidence": 0.9, "contains_people": False,
    }
    assert len(seen) == 1
    request = seen[0]
    assert request.headers["x-goog-api-key"] == "test-key" and "test-key" not in str(request.url)
    sent = json.loads(request.content)
    parts = sent["contents"][0]["parts"]
    images = [p["inline_data"] for p in parts if "inline_data" in p]
    assert len(images) == 2 and all(i["mime_type"] == "image/jpeg" and base64.b64decode(i["data"]) == THUMB for i in images)
    assert "the fan is wobbling" in parts[-1]["text"] and "CSE Block, Room 204" in parts[-1]["text"]
    assert sent["generationConfig"]["responseMimeType"] == "application/json" and "responseSchema" in sent["generationConfig"]
    assert "CAMPUS PLACES" in sent["systemInstruction"]["parts"][0]["text"]
    body = request.content.decode()
    for private in ("student@fixmycampus.dev", "Demo Student", str(demo_user_id("student")), "17.3871", "78.3911", "gps", "lat", "lng"):
        assert private not in body


async def test_schema_refused_retries_without_it(async_client, login, storage, monkeypatch):
    def handler(request):
        if "responseSchema" in json.loads(request.content)["generationConfig"]:
            return httpx.Response(400, json={"error": {"message": "bad schema"}})
        return httpx.Response(200, json=draft_reply())

    seen = use_llm(monkeypatch, handler)
    response = await describe(async_client, await login("student"), [await add_photo(storage)])
    assert response.status_code == 200 and response.json()["category"] == "Electrical"
    assert len(seen) == 2 and "responseSchema" not in json.loads(seen[1].content)["generationConfig"]
    assert any("inline_data" in p for p in json.loads(seen[1].content)["contents"][0]["parts"])


@pytest.mark.parametrize("handler", [
    lambda request: httpx.Response(500, json={"error": {"message": "boom"}}),
    lambda request: (_ for _ in ()).throw(httpx.ReadTimeout("slow")),
    lambda request: httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": "not json"}]}}]}),
])
async def test_gemini_failure_is_a_503_and_photos_stay_usable(async_client, login, storage, monkeypatch, handler):
    use_llm(monkeypatch, handler)
    photo = await add_photo(storage)
    response = await describe(async_client, await login("student"), [photo])
    assert response.status_code == 503
    assert response.json()["error"] == {"code": "AI_UNAVAILABLE", "message": ERROR_TEXT, "details": {}}
    assert await status_of(photo) == "ready" and len(storage.objects) == 2


async def test_slow_gemini_times_out_into_a_503(async_client, login, storage, monkeypatch):
    import asyncio

    class Slow:
        async def describe(self, *args):
            await asyncio.sleep(5)

    monkeypatch.setattr(settings, "GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(settings, "MEDIA_DESCRIBE_TIMEOUT_SECONDS", 0.05)
    media_service.set_media_llm(Slow())
    response = await describe(async_client, await login("student"), [await add_photo(storage)])
    assert response.status_code == 503 and response.json()["error"]["code"] == "AI_UNAVAILABLE"


async def test_no_key_is_a_503(async_client, login, storage):
    response = await describe(async_client, await login("student"), [await add_photo(storage)])
    assert response.status_code == 503 and response.json()["error"]["code"] == "AI_UNAVAILABLE"


async def test_inappropriate_photos_are_rejected_and_deleted(async_client, login, storage, monkeypatch):
    use_llm(monkeypatch, ok(inappropriate=True))
    keep = await add_photo(storage)
    ids = [await add_photo(storage), await add_photo(storage)]
    response = await describe(async_client, await login("student"), ids)
    assert response.status_code == 422
    assert response.json()["error"]["message"] == "These photos can't be used. Please upload a photo of the problem only."
    assert [await status_of(i) for i in ids] == ["rejected", "rejected"] and await status_of(keep) == "ready"
    assert not any(str(i) in key for i in ids for key in storage.objects) and len(storage.objects) == 2
    async with AsyncSessionLocal() as db:
        logs = (await db.scalars(select(AuditLog).where(AuditLog.entity_type == "attachment"))).all()
    assert {log.entity_id for log in logs} == set(ids)
    assert all(log.action == "UPDATE" and log.new_values == {"status": "rejected", "reason": "inappropriate"} for log in logs)


@pytest.mark.parametrize("overrides, owner", [
    ({}, "student2"),
    ({"status": "draft"}, "student"),
    ({"status": "rejected"}, "student"),
])
async def test_only_your_own_ready_photos_can_be_described(async_client, login, storage, monkeypatch, overrides, owner):
    seen = use_llm(monkeypatch, ok())
    photo = await add_photo(storage, owner=owner, **overrides)
    response = await describe(async_client, await login("student"), [photo])
    assert response.status_code == 422
    assert response.json()["error"]["message"] == "Some photos are missing or not yours — please remove and add them again"
    assert seen == []


async def test_unknown_or_attached_photos_are_refused(async_client, login, storage, monkeypatch):
    from tests.test_tickets import create_ticket

    seen = use_llm(monkeypatch, ok())
    headers = await login("student")
    ticket = await create_ticket(async_client, headers)
    attached = await add_photo(storage, ticket_id=uuid.UUID(ticket["id"]))
    mine = await add_photo(storage)
    assert (await describe(async_client, headers, [uuid.uuid4()])).status_code == 422
    assert (await describe(async_client, headers, [attached])).status_code == 422
    assert (await describe(async_client, headers, [mine, uuid.uuid4()])).status_code == 422
    assert seen == []


async def test_unknown_category_priority_and_confidence_are_cleaned(async_client, login, storage, monkeypatch):
    use_llm(monkeypatch, ok(category="Furniture", priority="URGENT", confidence=7, title="T" * 300, description="D" * 5000))
    body = (await describe(async_client, await login("student"), [await add_photo(storage)])).json()
    assert body["category"] == "Other" and body["priority"] == "MEDIUM" and body["confidence"] == 1.0
    assert len(body["title"]) == 120 and len(body["description"]) == 2000


async def test_location_hint_must_be_a_real_campus_place(async_client, login, storage, monkeypatch):
    headers = await login("student")
    use_llm(monkeypatch, ok(location_hint="Moon Base Alpha, Room 7"))
    assert (await describe(async_client, headers, [await add_photo(storage)])).json()["location_hint"] is None
    use_llm(monkeypatch, ok(location_hint="the first year block, room 12"))
    assert (await describe(async_client, headers, [await add_photo(storage)])).json()["location_hint"] == "AS&H Block (First-year block)"


async def test_describing_is_rate_limited_per_user(async_client, login, storage, monkeypatch):
    use_llm(monkeypatch, ok())
    monkeypatch.setattr(settings, "MEDIA_DESCRIBE_PER_MINUTE", 2)
    headers = await login("student")
    photo = await add_photo(storage)
    assert [(await describe(async_client, headers, [photo])).status_code for _ in range(2)] == [200, 200]
    limited = await describe(async_client, headers, [photo])
    assert limited.status_code == 429 and limited.json()["error"]["code"] == "RATE_LIMITED"
    other = await add_photo(storage, owner="student2")
    assert (await describe(async_client, await login("student2"), [other])).status_code == 200
