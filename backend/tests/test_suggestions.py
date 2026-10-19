"""Suggested category, priority and department; Gemini with a keyword fallback; accepting and overriding."""

import json
import uuid

import httpx
import pytest
from sqlalchemy import select

from ai.gemini_service import GeminiSuggestionService
from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models import AuditLog
from app.models.enums import AuditActionEnum
from app.services import suggestion_service
from tests.test_tickets import NEW_TICKET, create_ticket

SPARKS = {
    "title": "Sparks coming from the switchboard",
    "description": "Sparks and a burning smell near the main switchboard in the corridor.",
    "category": "Other",
    "location": "Block B corridor",
    "priority": "LOW",
}


async def get(client, headers, ref) -> dict:
    response = await client.get(f"/api/v1/tickets/{ref}", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def gemini_reply(**fields) -> dict:
    answer = {"category": "Classroom Equipment", "priority": "HIGH", "confidence": 0.82, "reason": "A projector is classroom equipment.", **fields}
    return {"candidates": [{"content": {"parts": [{"text": json.dumps(answer)}]}}]}


def use_gemini(monkeypatch, handler) -> list[httpx.Request]:
    """Install a Gemini client whose HTTP calls go to ``handler`` instead of Google."""
    seen: list[httpx.Request] = []

    def record(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return handler(request)

    monkeypatch.setattr(settings, "GEMINI_API_KEY", "test-key")
    suggestion_service.set_gemini(GeminiSuggestionService("test-key", settings.GEMINI_MODEL, transport=httpx.MockTransport(record)))
    return seen


async def test_keyword_suggestions_include_category_priority_and_department(async_client, login):
    created = await create_ticket(async_client, await login("student"))
    detail = await get(async_client, await login("coordinator"), created["ticket_number"])
    suggestions = detail["suggestions"]
    assert suggestions["status"] == "done" and suggestions["source"] == "keywords"
    assert suggestions["category"] == "IT / Network" and suggestions["priority"] in {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
    assert suggestions["department_name"] == "IT Department"
    assert 0 < suggestions["confidence"] <= 0.6 and suggestions["reason"]
    assert detail["suggested_category"] == "IT / Network"


async def test_gemini_suggestions_are_used_when_it_answers(async_client, login, monkeypatch):
    seen = use_gemini(monkeypatch, lambda request: httpx.Response(200, json=gemini_reply()))
    created = await create_ticket(async_client, await login("student"), title="Projector flickers badly", description="The projector in Room 204 flickers and then switches off.", category="Other")
    suggestions = (await get(async_client, await login("coordinator"), created["ticket_number"]))["suggestions"]
    assert suggestions["source"] == "gemini" and suggestions["category"] == "Classroom Equipment"
    assert suggestions["priority"] == "HIGH" and suggestions["confidence"] == 0.82
    assert suggestions["reason"] == "A projector is classroom equipment."

    request = seen[0]
    assert request.url.path.endswith(f"/models/{settings.GEMINI_MODEL}:generateContent")
    assert request.headers["x-goog-api-key"] == "test-key" and "test-key" not in str(request.url)
    body = json.loads(request.content)
    assert body["generationConfig"]["responseMimeType"] == "application/json" and "responseSchema" in body["generationConfig"]
    sent = json.dumps(body)
    assert "Projector flickers badly" in sent and "student@fixmycampus.dev" not in sent and "Student" not in body["contents"][0]["parts"][0]["text"]


@pytest.mark.parametrize("handler", [
    lambda request: (_ for _ in ()).throw(httpx.ReadTimeout("slow")),
    lambda request: httpx.Response(429, json={"error": {"message": "quota"}}),
    lambda request: httpx.Response(500, text="boom"),
    lambda request: httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": "not json at all"}]}}]}),
    lambda request: httpx.Response(200, json=gemini_reply(category="Space Travel")),
    lambda request: httpx.Response(200, json={"promptFeedback": {"blockReason": "SAFETY"}}),
], ids=["timeout", "rate-limited", "server-error", "garbage", "unknown-category", "blocked"])
async def test_ticket_is_created_with_keyword_suggestions_when_gemini_fails(async_client, login, monkeypatch, handler):
    use_gemini(monkeypatch, handler)
    created = await create_ticket(async_client, await login("student"))
    suggestions = (await get(async_client, await login("coordinator"), created["ticket_number"]))["suggestions"]
    assert suggestions["status"] == "done" and suggestions["source"] == "keywords"


async def test_gemini_reply_wrapped_in_text_or_a_rejected_schema_still_works(async_client, login, monkeypatch):
    calls = []

    def handler(request):
        body = json.loads(request.content)
        calls.append("responseSchema" in body["generationConfig"])
        if calls[-1]:
            return httpx.Response(400, json={"error": {"message": "schema not supported"}})
        wrapped = "Here you go:\n```json\n" + json.dumps(gemini_reply()["candidates"][0]["content"]["parts"][0]["text"] and json.loads(gemini_reply()["candidates"][0]["content"]["parts"][0]["text"])) + "\n```"
        return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": wrapped}]}}]})

    use_gemini(monkeypatch, handler)
    created = await create_ticket(async_client, await login("student"))
    suggestions = (await get(async_client, await login("coordinator"), created["ticket_number"]))["suggestions"]
    assert calls == [True, False] and suggestions["source"] == "gemini"


async def test_accepting_suggestions_applies_them_and_recalculates_the_fix_by_date(async_client, login):
    created = await create_ticket(async_client, await login("student"), **SPARKS)
    coordinator = await login("coordinator")
    before = await get(async_client, coordinator, created["ticket_number"])
    assert before["category"] == "Other" and before["suggestions"]["category"] == "Electrical"

    response = await async_client.post(f"/api/v1/tickets/{created['ticket_number']}/suggestions/accept", headers=coordinator)
    assert response.status_code == 200, response.text
    after = response.json()
    assert (after["category"], after["priority"], after["department_name"]) == ("Electrical", "CRITICAL", "Electrical Maintenance")
    assert after["sla_deadline"] != before["sla_deadline"]

    async with AsyncSessionLocal() as db:
        actions = (await db.scalars(select(AuditLog.action).where(AuditLog.entity_id == uuid.UUID(created["id"])))).all()
    assert AuditActionEnum.AI_OVERRIDE.value not in actions  # nothing was overridden


async def test_choosing_something_else_records_an_override(async_client, login):
    created = await create_ticket(async_client, await login("student"), **SPARKS)
    coordinator = await login("coordinator")
    response = await async_client.patch(
        f"/api/v1/tickets/{created['ticket_number']}", json={"category": "Civil Maintenance", "priority": "CRITICAL"}, headers=coordinator
    )
    assert response.status_code == 200

    async with AsyncSessionLocal() as db:
        overrides = (await db.scalars(select(AuditLog).where(
            AuditLog.entity_id == uuid.UUID(created["id"]), AuditLog.action == AuditActionEnum.AI_OVERRIDE.value
        ))).all()
    assert len(overrides) == 1
    # Only the category differs from the suggestion (Electrical / Critical)
    assert overrides[0].old_values == {"category": "Electrical"} and overrides[0].new_values == {"category": "Civil Maintenance"}


async def test_students_and_staff_never_get_suggestions(async_client, login):
    created = await create_ticket(async_client, await login("student"))
    ref = created["ticket_number"]
    student = await login("student")

    body = await get(async_client, student, ref)
    assert body["suggestions"] is None and body["suggested_category"] is None and body["ai_confidence"] is None
    assert body["suggested_department_id"] is None and body["duplicates"] == []
    listed = (await async_client.get("/api/v1/tickets", headers=student)).json()["items"][0]
    assert listed["suggested_category"] is None and listed["ai_confidence"] is None
    assert (await get(async_client, await login("coordinator"), ref))["suggested_category"] == "IT / Network"

    for path in ("suggestions/accept", "suggestions/refresh"):
        assert (await async_client.post(f"/api/v1/tickets/{ref}/{path}", headers=student)).status_code == 403
        assert (await async_client.post(f"/api/v1/tickets/{ref}/{path}", headers=await login("student2"))).status_code == 404
    assert (await async_client.post(f"/api/v1/tickets/{ref}/suggestions/refresh", headers=await login("staff"))).status_code in (403, 404)


async def test_refreshing_suggestions_redoes_them(async_client, login, monkeypatch):
    created = await create_ticket(async_client, await login("student"))
    coordinator = await login("coordinator")
    assert (await get(async_client, coordinator, created["ticket_number"]))["suggestions"]["source"] == "keywords"

    use_gemini(monkeypatch, lambda request: httpx.Response(200, json=gemini_reply(category="IT / Network", reason="It is a network problem.")))
    response = await async_client.post(f"/api/v1/tickets/{created['ticket_number']}/suggestions/refresh", headers=coordinator)
    assert response.status_code == 200 and response.json()["suggestions"]["status"] == "pending"
    after = (await get(async_client, coordinator, created["ticket_number"]))["suggestions"]
    assert after["status"] == "done" and after["source"] == "gemini" and after["reason"] == "It is a network problem."


async def test_ticket_is_created_even_if_the_analysis_itself_breaks(async_client, login, monkeypatch):
    async def explode(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(suggestion_service, "suggest", explode)
    created = await create_ticket(async_client, await login("student"), **NEW_TICKET)
    detail = await get(async_client, await login("coordinator"), created["ticket_number"])
    assert detail["suggestions"]["status"] == "failed" and detail["suggestions"]["category"] is None
    assert (await async_client.post(f"/api/v1/tickets/{created['ticket_number']}/suggestions/accept", headers=await login("coordinator"))).status_code == 409
