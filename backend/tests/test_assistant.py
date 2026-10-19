"""Campus assistant: answers with sources, fail-soft fallback, server-side checks of proposed actions (Gemini mocked)."""

import json

import httpx
import pytest

from ai.assistant_llm import GeminiAssistantService
from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models import AuditLog
from app.models.enums import AuditActionEnum
from app.services import assistant_service, knowledge_service
from sqlalchemy import select
from tests.helpers import FakeEmbedder
from tests.test_knowledge import page
from tests.test_tickets import assign, create_ticket, move, resolved_ticket, staff_id

CONTACT_PAGE = page(
    url="https://mvsrec.edu.in/contact", title="Contact Us", sha="e" * 64,
    text="## Contact Us\nEXAMINATION BRANCH\nEmail: exambranch@mvsrec.edu.in\nPhone No: 9441795375\nHead CSE Dept Email : hod_cse @mvsrec.edu.in",
)
FEES_PAGE = page(
    url="https://mvsrec.edu.in/fees", title="Fee payment", sha="f" * 64,
    text="## Fee payment\nTuition fees can be paid online through the college payment page.",
)


async def seed_knowledge() -> None:
    async with AsyncSessionLocal() as db:
        await knowledge_service.ingest(db, [CONTACT_PAGE, FEES_PAGE], FakeEmbedder())


def gemini_reply(**fields) -> dict:
    answer = {"answer": "Pay online [2].", "cited": [2], "status": "answered", "actions": [], **fields}
    return {"candidates": [{"content": {"parts": [{"text": json.dumps(answer)}]}}]}


def use_llm(monkeypatch, handler) -> list[httpx.Request]:
    seen: list[httpx.Request] = []

    def record(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return handler(request)

    monkeypatch.setattr(settings, "GEMINI_API_KEY", "test-key")
    assistant_service.set_llm(GeminiAssistantService("test-key", settings.GEMINI_MODEL, transport=httpx.MockTransport(record)))
    return seen


def ok(**fields):
    return lambda request: httpx.Response(200, json=gemini_reply(**fields))


async def ask(client, headers, message="How do I pay my fees?", history=None):
    return await client.post("/api/v1/assistant/chat", json={"message": message, "history": history or []}, headers=headers)


def prompt_of(request: httpx.Request) -> str:
    return json.loads(request.content)["contents"][0]["parts"][0]["text"]


def source_numbers(prompt: str, url: str) -> int:
    return int(prompt.split(f"({url})")[0].rsplit("[", 1)[1].split("]")[0])


async def test_needs_sign_in(async_client):
    response = await async_client.post("/api/v1/assistant/chat", json={"message": "hello"})
    assert response.status_code == 401


async def test_answer_comes_back_with_its_sources(async_client, login, monkeypatch):
    await seed_knowledge()
    seen = use_llm(monkeypatch, lambda request: httpx.Response(200, json=gemini_reply(answer="Pay online [1].", cited=[1])))
    response = await ask(async_client, await login("student"), "Tuition fees payment online")
    body = response.json()
    assert response.status_code == 200 and body["status"] == "answered" and body["answer"] == "Pay online [1]."
    assert [s["n"] for s in body["sources"]] == [1] and body["sources"][0]["url"].startswith("https://mvsrec.edu.in/")
    request = seen[0]
    assert request.headers["x-goog-api-key"] == "test-key" and "test-key" not in str(request.url)
    sent = json.loads(request.content)
    assert sent["generationConfig"]["responseMimeType"] == "application/json" and "responseSchema" in sent["generationConfig"]
    assert "data" in sent["systemInstruction"]["parts"][0]["text"] and "student@fixmycampus.dev" not in json.dumps(sent)


async def test_not_found_is_passed_on_without_made_up_sources(async_client, login, monkeypatch):
    await seed_knowledge()
    use_llm(monkeypatch, ok(answer="That is not on the website. Try the academic section.", cited=[], status="not_found"))
    body = (await ask(async_client, await login("student"), "What is the canteen menu?")).json()
    assert body["status"] == "not_found" and body["sources"] == []


@pytest.mark.parametrize("handler", [
    lambda request: (_ for _ in ()).throw(httpx.ReadTimeout("slow")),
    lambda request: httpx.Response(429, json={"error": {"message": "quota"}}),
    lambda request: httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": "not json"}]}}]}),
])
async def test_falls_back_to_sources_when_the_model_fails(async_client, login, monkeypatch, handler):
    await seed_knowledge()
    use_llm(monkeypatch, handler)
    response = await ask(async_client, await login("student"), "Tuition fees payment online")
    body = response.json()
    assert response.status_code == 200 and body["status"] == "fallback"
    assert body["answer"].startswith("I can't write a full answer right now") and body["sources"]
    assert len(body["sources"]) <= 3 and all(s["url"].startswith("https://mvsrec.edu.in/") for s in body["sources"])


async def test_falls_back_when_no_key_and_offers_a_report_card_for_a_problem(async_client, login):
    await seed_knowledge()
    body = (await ask(async_client, await login("student"), "The fan in Room 204 is broken and not working")).json()
    assert body["status"] == "fallback"
    card = body["actions"][0]
    assert card["type"] == "report_problem" and card["category"] == "Electrical" and "Room 204" in card["description"]
    assert (await ask(async_client, await login("student"), "How do I pay my fees?")).json()["actions"] == []


async def test_contact_details_must_appear_in_the_sources(async_client, login, monkeypatch):
    await seed_knowledge()
    use_llm(monkeypatch, ok(cited=[1], actions=[
        {"type": "contact", "label": "Exam branch", "email": "exambranch@mvsrec.edu.in", "phone": "9441795375"},
        {"type": "contact", "label": "CSE head", "email": "hod_cse@mvsrec.edu.in"},
        {"type": "contact", "label": "Made up", "email": "dean@mvsrec.edu.in", "phone": "9000000000"},
        {"type": "contact", "label": "Half real", "email": "nobody@mvsrec.edu.in", "phone": "94417 95375"},
        {"type": "open_link", "label": "Contacts", "url": "https://mvsrec.edu.in/contact"},
        {"type": "open_link", "label": "Elsewhere", "url": "https://evil.example/phish"},
    ]))
    actions = (await ask(async_client, await login("student"), "exam branch contact email phone")).json()["actions"]
    assert len(actions) == 3  # at most three, the made-up card and the foreign link are dropped
    assert actions[0] == {"type": "contact", "label": "Exam branch", "email": "exambranch@mvsrec.edu.in", "phone": "9441795375"}
    assert actions[1]["email"] == "hod_cse@mvsrec.edu.in" and actions[1]["phone"] is None
    assert actions[2]["email"] is None and actions[2]["phone"] == "9441795375"


async def test_link_outside_the_sources_is_dropped(async_client, login, monkeypatch):
    await seed_knowledge()
    use_llm(monkeypatch, ok(cited=[1], actions=[{"type": "open_link", "label": "Elsewhere", "url": "https://evil.example/phish"}]))
    assert (await ask(async_client, await login("student"), "fees")).json()["actions"] == []


async def test_report_problem_is_clamped_to_the_ticket_rules(async_client, login, monkeypatch):
    await seed_knowledge()
    use_llm(monkeypatch, ok(cited=[], actions=[
        {"type": "report_problem", "title": "Fan broken", "description": "The fan is broken in Room 204.", "category": "Magic", "priority": "URGENT", "location": "Room 204"},
        {"type": "report_problem", "title": "x", "description": "y", "category": "Other"},
    ]))
    actions = (await ask(async_client, await login("student"), "the fan in Room 204 is broken")).json()["actions"]
    assert actions[0]["category"] == "Other" and actions[0]["priority"] == "MEDIUM" and actions[0]["location"] == "Room 204"
    assert len(actions) == 1  # the card whose title and description are too short to be a ticket is dropped


async def test_ticket_actions_follow_the_users_real_permissions(async_client, login, monkeypatch):
    ref, student, coordinator = await resolved_ticket(async_client, login)
    other = await create_ticket(async_client, await login("student2"), title="Other student's leak", description="A tap is leaking in the hostel.")
    open_ref = (await create_ticket(async_client, student, title="Projector flickers", description="The projector in Room 9 flickers."))["ticket_number"]
    await seed_knowledge()
    seen = use_llm(monkeypatch, ok(cited=[], actions=[
        {"type": "confirm_fixed", "ticket_number": ref},
        {"type": "reopen_ticket", "ticket_number": ref},
        {"type": "confirm_fixed", "ticket_number": open_ref},  # not resolved yet
        {"type": "reopen_ticket", "ticket_number": other["ticket_number"]},  # somebody else's
        {"type": "add_comment", "ticket_number": open_ref, "text": "Still flickering today."},
    ]))
    actions = (await ask(async_client, student, "Is my projector ticket fixed?")).json()["actions"]
    assert [(a["type"], a["ticket_number"]) for a in actions] == [("confirm_fixed", ref), ("reopen_ticket", ref), ("add_comment", open_ref)]
    assert actions[2]["text"] == "Still flickering today." and actions[0]["ticket_title"]

    prompt = prompt_of(seen[0])
    assert ref in prompt and open_ref in prompt and "resolved" in prompt
    assert other["ticket_number"] not in prompt and "Other student's leak" not in prompt


async def test_cancel_only_before_assignment_and_nothing_executes_by_itself(async_client, login, monkeypatch):
    student = await login("student")
    new_ref = (await create_ticket(async_client, student))["ticket_number"]
    await seed_knowledge()
    use_llm(monkeypatch, ok(cited=[], actions=[{"type": "cancel_ticket", "ticket_number": new_ref.lower()}]))
    actions = (await ask(async_client, student, "please cancel my wifi report")).json()["actions"]
    assert actions[0]["type"] == "cancel_ticket" and actions[0]["ticket_number"] == new_ref
    detail = await async_client.get(f"/api/v1/tickets/{new_ref}", headers=student)
    assert detail.json()["status"] == "NEW"

    coordinator = await login("coordinator")
    staff = await login("staff")
    await assign(async_client, coordinator, new_ref, await staff_id(async_client, coordinator, "staff@fixmycampus.dev"))
    assert (await ask(async_client, student, "cancel it again")).json()["actions"] == []
    assert (await move(async_client, staff, new_ref, "IN_PROGRESS")).status_code == 200


async def test_staff_prompt_lists_only_tickets_they_reported(async_client, login, monkeypatch):
    await create_ticket(async_client, await login("student"), title="Student's own ticket", description="Something broken in block A.")
    await seed_knowledge()
    seen = use_llm(monkeypatch, ok(cited=[]))
    await ask(async_client, await login("coordinator"), "Check my tickets")
    assert "Student's own ticket" not in prompt_of(seen[0])


async def test_history_is_trimmed_and_used_for_follow_up_search(async_client, login, monkeypatch):
    await seed_knowledge()
    seen = use_llm(monkeypatch, ok(cited=[]))
    history = [{"role": "user" if i % 2 == 0 else "assistant", "text": f"turn {i} " + "z" * 1200} for i in range(8)]
    history[0] = {"role": "user", "text": "exam branch email"}
    response = await ask(async_client, await login("student"), "and the phone?", history=history)
    assert response.status_code == 200
    prompt = prompt_of(seen[0])
    assert prompt.count("z" * 1200) <= 3 and "turn 7" in prompt
    too_many = await ask(async_client, await login("student"), "hi", history=history + history[:1])
    assert too_many.status_code == 422


async def test_a_follow_up_finds_pages_through_the_previous_question(async_client, login, monkeypatch):
    await seed_knowledge()
    seen = use_llm(monkeypatch, ok(cited=[]))
    history = [{"role": "user", "text": "How do I contact the examination branch?"}, {"role": "assistant", "text": "Email them."}]
    await ask(async_client, await login("student"), "and their phone?", history=history)
    assert "exambranch@mvsrec.edu.in" in prompt_of(seen[0])


async def test_rate_limit_and_audit_without_the_text(async_client, login, monkeypatch):
    monkeypatch.setattr(settings, "ASSISTANT_MESSAGES_PER_MINUTE", 3)
    student = await login("student")
    for _ in range(3):
        assert (await ask(async_client, student, "secret question about fees")).status_code == 200
    limited = await ask(async_client, student, "one more")
    assert limited.status_code == 429 and "sending messages quickly" in limited.json()["error"]["message"]
    assert (await ask(async_client, await login("student2"))).status_code == 200  # limits are per person

    async with AsyncSessionLocal() as db:
        rows = (await db.scalars(select(AuditLog).where(AuditLog.action == AuditActionEnum.ASSISTANT_CHAT.value))).all()
    assert len(rows) == 4
    assert all(set(r.new_values) == {"message_length", "status"} for r in rows)
    assert "secret" not in json.dumps([r.new_values for r in rows])


async def test_message_must_be_one_to_a_thousand_characters(async_client, login):
    student = await login("student")
    assert (await ask(async_client, student, "")).status_code == 422
    assert (await ask(async_client, student, "x" * 1001)).status_code == 422
