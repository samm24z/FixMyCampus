"""Ticket lifecycle, scoping, and audit integration tests (real PostgreSQL)."""

import re
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models import AuditLog, Department, Ticket
from app.models.enums import AuditActionEnum
from app.services import ticket_service

DEMO_USER_PREFIXES = ["student", "student2", "faculty", "staff", "staff2", "coordinator", "admin"]

NEW_TICKET = {
    "title": "WiFi down in C Block",
    "description": "Nobody in C Block can connect to the campus WiFi since morning.",
    "category": "IT / Network",
    "location": "C Block, first floor",
    "priority": "HIGH",
}


async def create_ticket(client: AsyncClient, headers: dict, **overrides) -> dict:
    response = await client.post("/api/v1/tickets", json={**NEW_TICKET, **overrides}, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


async def department_id(code: str) -> str:
    async with AsyncSessionLocal() as session:
        return str(await session.scalar(select(Department.id).where(Department.code == code)))


async def staff_id(client: AsyncClient, coordinator_headers: dict, email: str) -> str:
    response = await client.get("/api/v1/users/staff", headers=coordinator_headers)
    assert response.status_code == 200
    return next(u["id"] for u in response.json() if u["email"] == email)


async def assign(client, headers, ticket_number, assignee_id, **extra):
    return await client.post(
        f"/api/v1/tickets/{ticket_number}/assign", json={"assigned_to": assignee_id, **extra}, headers=headers
    )


async def move(client, headers, ticket_number, status, **extra):
    return await client.post(
        f"/api/v1/tickets/{ticket_number}/status", json={"status": status, **extra}, headers=headers
    )


# ------------------------------------------------------------------ creation

async def test_create_ticket_returns_detail_with_number_history_and_sla(async_client, login):
    student = await login("student")
    ticket = await create_ticket(async_client, student)

    assert re.fullmatch(r"TICK-\d{4}-\d{4,}", ticket["ticket_number"])
    assert ticket["status"] == "NEW"
    assert ticket["sla_deadline"] is not None  # HIGH + IT / Network has a seeded SLA rule
    assert [h["to_status"] for h in ticket["history"]] == ["NEW"]
    assert ticket["created_by_name"] == "Demo Student"
    perms = ticket["permissions"]
    assert perms["can_comment"] and perms["can_reopen"] is False
    assert not perms["can_assign"] and not perms["can_edit_triage"] and perms["allowed_statuses"] == []


async def test_ticket_numbers_are_unique_and_survive_deletion(async_client, login):
    student = await login("student")
    numbers = [(await create_ticket(async_client, student))["ticket_number"] for _ in range(3)]
    assert len(set(numbers)) == 3
    # Deleting rows must not cause the next ticket to reuse a number (the old count+1 scheme did).
    from sqlalchemy import text
    async with AsyncSessionLocal() as session:
        await session.execute(text("DELETE FROM tickets"))
        await session.commit()
    assert (await create_ticket(async_client, student))["ticket_number"] not in numbers


async def test_unknown_category_is_rejected(async_client, login):
    response = await async_client.post(
        "/api/v1/tickets", json={**NEW_TICKET, "category": "Made Up"}, headers=await login("student")
    )
    assert response.status_code == 422


async def test_creating_a_ticket_writes_an_audit_row(async_client, login):
    ticket = await create_ticket(async_client, await login("student"))
    async with AsyncSessionLocal() as session:
        rows = (await session.scalars(select(AuditLog).where(AuditLog.entity_id == ticket["id"]))).all()
    assert AuditActionEnum.CREATE.value in {row.action for row in rows}


# ------------------------------------------------------------------- scoping

async def test_reporters_only_see_their_own_tickets(async_client, login):
    mine = await create_ticket(async_client, await login("student"))
    other = await login("student2")

    listing = await async_client.get("/api/v1/tickets", headers=other)
    assert listing.json()["total"] == 0
    assert (await async_client.get(f"/api/v1/tickets/{mine['ticket_number']}", headers=other)).status_code == 404


async def test_list_and_detail_visibility_always_agree(async_client, login):
    """Regression: list and detail used different rules, so a role could list tickets it could not open."""
    student = await login("student")
    coordinator = await login("coordinator")
    it_staff_id = await staff_id(async_client, coordinator, "staff@fixmycampus.dev")

    await create_ticket(async_client, student, title="Unassigned ticket")
    assigned = await create_ticket(async_client, student, title="Assigned to IT staff")
    assert (await assign(async_client, coordinator, assigned["ticket_number"], it_staff_id)).status_code == 200
    await create_ticket(async_client, await login("student2"), title="Someone else's ticket")

    for prefix in DEMO_USER_PREFIXES:
        headers = await login(prefix)
        listed = (await async_client.get("/api/v1/tickets?page_size=100", headers=headers)).json()["items"]
        listed_ids = {t["id"] for t in listed}
        for ticket_id in [t["id"] for t in listed]:
            assert (await async_client.get(f"/api/v1/tickets/{ticket_id}", headers=headers)).status_code == 200
        everything = (await async_client.get("/api/v1/tickets?page_size=100", headers=await login("admin"))).json()["items"]
        for ticket in everything:
            opened = (await async_client.get(f"/api/v1/tickets/{ticket['id']}", headers=headers)).status_code == 200
            assert opened == (ticket["id"] in listed_ids), f"{prefix} list/detail disagree on {ticket['ticket_number']}"


async def test_staff_are_scoped_to_their_department_or_assignment(async_client, login):
    student, coordinator = await login("student"), await login("coordinator")
    ticket = await create_ticket(async_client, student)
    it_staff = await staff_id(async_client, coordinator, "staff@fixmycampus.dev")
    assert (await assign(async_client, coordinator, ticket["ticket_number"], it_staff)).status_code == 200

    assert (await async_client.get(f"/api/v1/tickets/{ticket['ticket_number']}", headers=await login("staff"))).status_code == 200
    other_dept_staff = await login("staff2")
    assert (await async_client.get(f"/api/v1/tickets/{ticket['ticket_number']}", headers=other_dept_staff)).status_code == 404
    assert (await async_client.get("/api/v1/tickets", headers=other_dept_staff)).json()["total"] == 0


# ----------------------------------------------------------------- lifecycle

async def test_full_lifecycle_and_timeline(async_client, login):
    student, coordinator, staff = await login("student"), await login("coordinator"), await login("staff")
    ticket = await create_ticket(async_client, student)
    ref = ticket["ticket_number"]
    it_staff = await staff_id(async_client, coordinator, "staff@fixmycampus.dev")

    assigned = await assign(async_client, coordinator, ref, it_staff)
    assert assigned.status_code == 200
    body = assigned.json()
    assert body["status"] == "ASSIGNED" and body["department_name"] == "IT Department"
    assert body["assigned_to_name"] == "Demo Staff"

    assert (await move(async_client, staff, ref, "IN_PROGRESS")).status_code == 200
    resolved = await move(async_client, staff, ref, "RESOLVED", remarks="Replaced access point")
    assert resolved.status_code == 200 and resolved.json()["resolved_at"] is not None
    assert resolved.json()["permissions"]["can_reopen"] is False  # staff, not the reporter

    reopened = await async_client.post(f"/api/v1/tickets/{ref}/reopen", json={"reason": "Still down"}, headers=student)
    assert reopened.status_code == 200
    assert reopened.json()["status"] == "REOPENED" and reopened.json()["reopened_at"] is not None

    detail = (await async_client.get(f"/api/v1/tickets/{ref}", headers=student)).json()
    assert [h["to_status"] for h in detail["history"]] == ["NEW", "ASSIGNED", "IN_PROGRESS", "RESOLVED", "REOPENED"]
    assert detail["history"][-1]["remarks"] == "Still down"


async def test_every_status_change_is_audited(async_client, login):
    student, coordinator = await login("student"), await login("coordinator")
    ticket = await create_ticket(async_client, student)
    it_staff = await staff_id(async_client, coordinator, "staff@fixmycampus.dev")
    await assign(async_client, coordinator, ticket["ticket_number"], it_staff)
    async with AsyncSessionLocal() as session:
        actions = [r.action for r in (await session.scalars(select(AuditLog).where(AuditLog.entity_id == ticket["id"]))).all()]
    assert actions.count(AuditActionEnum.STATUS_CHANGE.value) == 2  # NEW, then ASSIGNED
    assert AuditActionEnum.ASSIGNMENT.value in actions


async def test_invalid_transitions_are_rejected(async_client, login):
    student, coordinator, staff = await login("student"), await login("coordinator"), await login("staff")
    ref = (await create_ticket(async_client, student))["ticket_number"]
    it_staff = await staff_id(async_client, coordinator, "staff@fixmycampus.dev")

    # No skipping straight to RESOLVED, and ASSIGNED needs an assignee.
    assert (await move(async_client, coordinator, ref, "RESOLVED")).status_code == 409
    assert (await move(async_client, coordinator, ref, "ASSIGNED")).status_code == 409
    assert (await move(async_client, coordinator, ref, "NEW")).status_code == 409  # no-op

    await assign(async_client, coordinator, ref, it_staff)
    assert (await move(async_client, staff, ref, "RESOLVED")).status_code == 409  # must start work first
    assert (await move(async_client, staff, ref, "CLOSED")).status_code == 409


async def test_reporters_cannot_drive_the_status_workflow(async_client, login):
    student = await login("student")
    ref = (await create_ticket(async_client, student))["ticket_number"]
    assert (await move(async_client, student, ref, "IN_PROGRESS")).status_code == 403
    assert (await move(async_client, await login("student2"), ref, "IN_PROGRESS")).status_code == 404


async def test_staff_of_another_department_cannot_act_on_the_ticket(async_client, login):
    student, coordinator = await login("student"), await login("coordinator")
    ref = (await create_ticket(async_client, student))["ticket_number"]
    it_staff = await staff_id(async_client, coordinator, "staff@fixmycampus.dev")
    await assign(async_client, coordinator, ref, it_staff)
    assert (await move(async_client, await login("staff2"), ref, "IN_PROGRESS")).status_code == 404


async def test_only_coordinators_and_admins_can_assign(async_client, login):
    student, coordinator = await login("student"), await login("coordinator")
    ref = (await create_ticket(async_client, student))["ticket_number"]
    it_staff = await staff_id(async_client, coordinator, "staff@fixmycampus.dev")
    assert (await assign(async_client, student, ref, it_staff)).status_code == 403
    assert (await assign(async_client, await login("staff"), ref, it_staff)).status_code == 404  # cannot even see it yet


async def test_assign_rejects_non_staff_assignees_and_unknown_departments(async_client, login):
    student, coordinator = await login("student"), await login("coordinator")
    ref = (await create_ticket(async_client, student))["ticket_number"]
    a_student_id = (await async_client.get("/api/v1/auth/me", headers=student)).json()["id"]
    assert (await assign(async_client, coordinator, ref, a_student_id)).status_code == 404
    it_staff = await staff_id(async_client, coordinator, "staff@fixmycampus.dev")
    bogus = "00000000-0000-0000-0000-000000000000"
    assert (await assign(async_client, coordinator, ref, it_staff, department_id=bogus)).status_code == 422


async def test_reassigning_an_in_progress_ticket_keeps_its_status(async_client, login):
    student, coordinator, staff = await login("student"), await login("coordinator"), await login("staff")
    ref = (await create_ticket(async_client, student))["ticket_number"]
    it_staff = await staff_id(async_client, coordinator, "staff@fixmycampus.dev")
    await assign(async_client, coordinator, ref, it_staff)
    await move(async_client, staff, ref, "IN_PROGRESS")
    electrical_staff = await staff_id(async_client, coordinator, "staff2@fixmycampus.dev")
    reassigned = await assign(async_client, coordinator, ref, electrical_staff, department_id=await department_id("ELECTRICAL"))
    assert reassigned.status_code == 200 and reassigned.json()["status"] == "IN_PROGRESS"
    assert reassigned.json()["assigned_to_name"] == "Demo Staff Electrical"


async def test_reopen_rules(async_client, login):
    student, other = await login("student"), await login("student2")
    ref = (await create_ticket(async_client, student))["ticket_number"]
    reopen = lambda headers: async_client.post(f"/api/v1/tickets/{ref}/reopen", json={}, headers=headers)  # noqa: E731
    assert (await reopen(student)).status_code == 409  # not resolved yet
    assert (await reopen(other)).status_code == 404


# -------------------------------------------------------------------- triage

async def test_triage_changes_are_coordinator_only_and_recompute_sla(async_client, login):
    student, coordinator = await login("student"), await login("coordinator")
    ticket = await create_ticket(async_client, student, priority="LOW")
    ref = ticket["ticket_number"]

    assert (await async_client.patch(f"/api/v1/tickets/{ref}", json={"priority": "CRITICAL"}, headers=student)).status_code == 403

    response = await async_client.patch(
        f"/api/v1/tickets/{ref}", json={"priority": "CRITICAL", "category": "Electrical"}, headers=coordinator
    )
    assert response.status_code == 200
    body = response.json()
    assert body["priority"] == "CRITICAL" and body["category"] == "Electrical"
    assert body["confirmed_category"] == "Electrical"
    assert body["sla_deadline"] != ticket["sla_deadline"]  # CRITICAL SLA is much shorter than LOW

    assert (await async_client.patch(f"/api/v1/tickets/{ref}", json={"category": "Nope"}, headers=coordinator)).status_code == 422
    async with AsyncSessionLocal() as session:
        rows = (await session.scalars(select(AuditLog).where(
            AuditLog.entity_id == ticket["id"], AuditLog.action == AuditActionEnum.UPDATE.value))).all()
    assert rows and rows[0].old_values["priority"] == "LOW" and rows[0].new_values["priority"] == "CRITICAL"


# ------------------------------------------------------------------ comments

async def test_internal_notes_are_hidden_from_reporters(async_client, login):
    student, coordinator = await login("student"), await login("coordinator")
    ref = (await create_ticket(async_client, student))["ticket_number"]
    url = f"/api/v1/tickets/{ref}/comments"

    assert (await async_client.post(url, json={"content": "Please hurry", "is_internal": False}, headers=student)).status_code == 201
    assert (await async_client.post(url, json={"content": "secret", "is_internal": True}, headers=student)).status_code == 403
    assert (await async_client.post(url, json={"content": "Escalating to vendor", "is_internal": True}, headers=coordinator)).status_code == 201

    student_view = (await async_client.get(f"/api/v1/tickets/{ref}", headers=student)).json()
    assert [c["content"] for c in student_view["comments"]] == ["Please hurry"]
    assert student_view["comments"][0]["author_name"] == "Demo Student"
    staff_view = (await async_client.get(f"/api/v1/tickets/{ref}", headers=coordinator)).json()
    assert len(staff_view["comments"]) == 2


async def test_users_cannot_comment_on_tickets_they_cannot_see(async_client, login):
    ref = (await create_ticket(async_client, await login("student")))["ticket_number"]
    response = await async_client.post(
        f"/api/v1/tickets/{ref}/comments", json={"content": "hi there"}, headers=await login("student2")
    )
    assert response.status_code == 404


# ----------------------------------------------------- listing and dashboards

async def test_pagination_search_and_filters(async_client, login):
    student = await login("student")
    for index in range(5):
        await create_ticket(async_client, student, title=f"Broken projector {index}", category="Classroom Equipment")
    await create_ticket(async_client, student, title="Leaking 100% pipe_x", category="Water / Plumbing", priority="LOW")

    page1 = (await async_client.get("/api/v1/tickets?page_size=4", headers=student)).json()
    assert page1["total"] == 6 and page1["total_pages"] == 2 and len(page1["items"]) == 4
    page2 = (await async_client.get("/api/v1/tickets?page_size=4&page=2", headers=student)).json()
    assert len(page2["items"]) == 2
    assert not {t["id"] for t in page1["items"]} & {t["id"] for t in page2["items"]}

    assert (await async_client.get("/api/v1/tickets?search=projector", headers=student)).json()["total"] == 5
    assert (await async_client.get("/api/v1/tickets?search=100%25", headers=student)).json()["total"] == 1  # '%' is literal
    assert (await async_client.get("/api/v1/tickets?category=Water / Plumbing", headers=student)).json()["total"] == 1
    assert (await async_client.get("/api/v1/tickets?priority=LOW", headers=student)).json()["total"] == 1
    assert (await async_client.get("/api/v1/tickets?status=RESOLVED", headers=student)).json()["total"] == 0
    assert (await async_client.get("/api/v1/tickets?open_only=true", headers=student)).json()["total"] == 6
    assert (await async_client.get("/api/v1/tickets?mine=true", headers=await login("coordinator"))).json()["total"] == 0
    assert (await async_client.get("/api/v1/tickets?page_size=500", headers=student)).status_code == 422


async def test_dashboard_summary_counts_by_status(async_client, login):
    student, coordinator = await login("student"), await login("coordinator")
    await create_ticket(async_client, student)
    second = await create_ticket(async_client, student)
    await move(async_client, coordinator, second["ticket_number"], "CLOSED", remarks="Duplicate request")

    summary = (await async_client.get("/api/v1/tickets/summary", headers=student)).json()
    assert summary["total_tickets"] == 2 and summary["open_tickets"] == 1 and summary["resolved_tickets"] == 1
    assert summary["by_status"] == {"NEW": 1, "CLOSED": 1}
    assert len(summary["recent_tickets"]) == 2
    assert (await async_client.get("/api/v1/tickets/summary", headers=await login("student2"))).json()["total_tickets"] == 0


async def test_unauthenticated_requests_are_rejected(async_client):
    assert (await async_client.get("/api/v1/tickets")).status_code == 401
    assert (await async_client.post("/api/v1/tickets", json=NEW_TICKET)).status_code == 401


# -------------------------------------------- remarks, confirm, withdraw, feedback

async def resolved_ticket(client, login) -> tuple[str, dict, dict]:
    """File a ticket and take it to RESOLVED; returns (ref, student headers, coordinator headers)."""
    student, coordinator, staff = await login("student"), await login("coordinator"), await login("staff")
    ref = (await create_ticket(client, student))["ticket_number"]
    await assign(client, coordinator, ref, await staff_id(client, coordinator, "staff@fixmycampus.dev"))
    await move(client, staff, ref, "IN_PROGRESS")
    assert (await move(client, staff, ref, "RESOLVED", remarks="Fixed")).status_code == 200
    return ref, student, coordinator


def post(client, headers, ref, action, **body):
    return client.post(f"/api/v1/tickets/{ref}/{action}", json=body, headers=headers)


async def test_resolving_and_rejecting_require_remarks(async_client, login):
    student, coordinator, staff = await login("student"), await login("coordinator"), await login("staff")
    ref = (await create_ticket(async_client, student))["ticket_number"]
    detail = (await async_client.get(f"/api/v1/tickets/{ref}", headers=coordinator)).json()
    assert detail["permissions"]["statuses_requiring_remarks"] == ["RESOLVED", "CLOSED"]

    for remarks in (None, "", "   "):
        extra = {} if remarks is None else {"remarks": remarks}
        assert (await move(async_client, coordinator, ref, "CLOSED", **extra)).status_code == 422
    assert (await move(async_client, coordinator, ref, "UNDER_REVIEW")).status_code == 200  # no remarks needed
    assert (await move(async_client, coordinator, ref, "CLOSED", remarks="Out of scope")).status_code == 200

    other = (await create_ticket(async_client, student))["ticket_number"]
    await assign(async_client, coordinator, other, await staff_id(async_client, coordinator, "staff@fixmycampus.dev"))
    assert (await move(async_client, staff, other, "IN_PROGRESS")).status_code == 200  # no remarks needed
    assert (await move(async_client, staff, other, "RESOLVED")).status_code == 422
    assert (await move(async_client, staff, other, "RESOLVED", remarks="  ")).status_code == 422
    assert (await move(async_client, staff, other, "RESOLVED", remarks="Rebooted router")).status_code == 200


async def test_reopen_clears_resolved_at(async_client, login):
    ref, student, _ = await resolved_ticket(async_client, login)
    assert (await async_client.get(f"/api/v1/tickets/{ref}", headers=student)).json()["resolved_at"] is not None
    reopened = await post(async_client, student, ref, "reopen", reason="Still broken")
    assert reopened.status_code == 200 and reopened.json()["resolved_at"] is None


async def test_reporter_confirms_a_resolved_ticket(async_client, login):
    ref, student, coordinator = await resolved_ticket(async_client, login)
    assert (await async_client.get(f"/api/v1/tickets/{ref}", headers=student)).json()["permissions"]["can_confirm"]
    assert (await post(async_client, coordinator, ref, "confirm")).status_code == 403
    assert (await post(async_client, await login("student2"), ref, "confirm")).status_code == 404

    confirmed = await post(async_client, student, ref, "confirm")
    assert confirmed.status_code == 200 and confirmed.json()["status"] == "CLOSED"
    last = confirmed.json()["history"][-1]
    assert (last["from_status"], last["to_status"]) == ("RESOLVED", "CLOSED")
    assert last["remarks"] == "Confirmed fixed by reporter" and last["changed_by"] == confirmed.json()["created_by"]
    assert (await post(async_client, student, ref, "confirm")).status_code == 409  # no longer RESOLVED


async def test_confirm_needs_a_resolved_ticket(async_client, login):
    student = await login("student")
    ref = (await create_ticket(async_client, student))["ticket_number"]
    assert (await post(async_client, student, ref, "confirm")).status_code == 409


async def test_reporter_can_withdraw_until_work_is_assigned(async_client, login):
    student, coordinator = await login("student"), await login("coordinator")
    ref = (await create_ticket(async_client, student))["ticket_number"]
    assert (await async_client.get(f"/api/v1/tickets/{ref}", headers=student)).json()["permissions"]["can_withdraw"]
    assert (await post(async_client, coordinator, ref, "withdraw")).status_code == 403
    assert (await post(async_client, await login("student2"), ref, "withdraw")).status_code == 404

    withdrawn = await post(async_client, student, ref, "withdraw", reason="Filed by mistake")
    assert withdrawn.status_code == 200 and withdrawn.json()["status"] == "CLOSED"
    assert withdrawn.json()["history"][-1]["remarks"] == "Withdrawn by reporter: Filed by mistake"
    assert (await post(async_client, student, ref, "withdraw")).status_code == 409

    plain = (await create_ticket(async_client, student))["ticket_number"]
    await move(async_client, coordinator, plain, "UNDER_REVIEW")
    result = await post(async_client, student, plain, "withdraw")
    assert result.status_code == 200 and result.json()["history"][-1]["remarks"] == "Withdrawn by reporter"

    assigned = (await create_ticket(async_client, student))["ticket_number"]
    await assign(async_client, coordinator, assigned, await staff_id(async_client, coordinator, "staff@fixmycampus.dev"))
    assert (await post(async_client, student, assigned, "withdraw")).status_code == 409


async def test_nobody_can_comment_on_a_closed_ticket(async_client, login):
    student, coordinator = await login("student"), await login("coordinator")
    ref = (await create_ticket(async_client, student))["ticket_number"]
    assert (await post(async_client, student, ref, "withdraw")).status_code == 200
    detail = (await async_client.get(f"/api/v1/tickets/{ref}", headers=student)).json()
    assert detail["permissions"]["can_comment"] is False
    for headers in (student, coordinator):
        assert (await post(async_client, headers, ref, "comments", content="Any update?")).status_code == 403


async def test_withdrawn_tickets_cannot_be_rated(async_client, login):
    student = await login("student")
    ref = (await create_ticket(async_client, student))["ticket_number"]
    withdrawn = await post(async_client, student, ref, "withdraw")
    assert withdrawn.status_code == 200 and withdrawn.json()["permissions"]["can_give_feedback"] is False
    assert (await post(async_client, student, ref, "feedback", rating=5)).status_code == 409


async def test_feedback_rules_and_upsert(async_client, login):
    student, coordinator = await login("student"), await login("coordinator")
    fresh = (await create_ticket(async_client, student))["ticket_number"]
    assert (await post(async_client, student, fresh, "feedback", rating=5)).status_code == 409  # not done yet

    ref, student, coordinator = await resolved_ticket(async_client, login)
    assert (await async_client.get(f"/api/v1/tickets/{ref}", headers=student)).json()["permissions"]["can_give_feedback"]
    assert (await post(async_client, coordinator, ref, "feedback", rating=5)).status_code == 403
    assert (await post(async_client, await login("student2"), ref, "feedback", rating=5)).status_code == 404
    for bad in (0, 6):
        assert (await post(async_client, student, ref, "feedback", rating=bad)).status_code == 422

    first = await post(async_client, student, ref, "feedback", rating=3, comments="Okay")
    assert first.status_code == 200 and first.json()["feedback"]["rating"] == 3
    second = await post(async_client, student, ref, "feedback", rating=5, comments="Great after all")
    feedback = second.json()["feedback"]
    assert feedback["rating"] == 5 and feedback["comments"] == "Great after all"
    assert feedback["id"] == first.json()["feedback"]["id"]  # one row per ticket

    assert (await async_client.get(f"/api/v1/tickets/{ref}", headers=coordinator)).json()["feedback"]["rating"] == 5
    async with AsyncSessionLocal() as session:
        rows = (await session.scalars(select(AuditLog).where(
            AuditLog.entity_id == second.json()["id"], AuditLog.action == AuditActionEnum.FEEDBACK_SUBMITTED.value
        ).order_by(AuditLog.created_at))).all()
    assert len(rows) == 2 and rows[0].old_values is None
    assert rows[1].old_values["rating"] == 3 and rows[1].new_values["rating"] == 5


async def test_stale_resolved_tickets_are_auto_closed(async_client, login):
    old_ref, student, _ = await resolved_ticket(async_client, login)
    fresh_ref, _, _ = await resolved_ticket(async_client, login)
    async with AsyncSessionLocal() as session:
        old = await session.scalar(select(Ticket).where(Ticket.ticket_number == old_ref))
        fresh = await session.scalar(select(Ticket).where(Ticket.ticket_number == fresh_ref))
        old.resolved_at = datetime.now(timezone.utc) - timedelta(days=8)
        fresh.resolved_at = datetime.now(timezone.utc) - timedelta(days=1)
        await session.commit()
    async with AsyncSessionLocal() as session:
        assert await ticket_service.auto_close_resolved_tickets(session) == 1

    closed = (await async_client.get(f"/api/v1/tickets/{old_ref}", headers=student)).json()
    assert closed["status"] == "CLOSED"
    assert closed["history"][-1]["changed_by"] is None
    assert closed["history"][-1]["remarks"].startswith("Auto-closed")
    assert (await async_client.get(f"/api/v1/tickets/{fresh_ref}", headers=student)).json()["status"] == "RESOLVED"
    async with AsyncSessionLocal() as session:
        audit = await session.scalars(select(AuditLog).where(AuditLog.entity_id == closed["id"], AuditLog.user_id.is_(None)))
        assert len(audit.all()) == 1


async def test_admin_sees_every_reporters_tickets_with_matching_status_counts(async_client, login):
    admin, coordinator = await login("admin"), await login("coordinator")
    first = await create_ticket(async_client, await login("student"))
    second = await create_ticket(async_client, await login("student2"))
    third = await create_ticket(async_client, await login("faculty"))
    await move(async_client, coordinator, second["ticket_number"], "UNDER_REVIEW")
    await move(async_client, coordinator, third["ticket_number"], "CLOSED", remarks="Out of scope")

    listing = (await async_client.get("/api/v1/tickets?page_size=100", headers=admin)).json()
    statuses = {t["ticket_number"]: t["status"] for t in listing["items"]}
    assert statuses == {first["ticket_number"]: "NEW", second["ticket_number"]: "UNDER_REVIEW", third["ticket_number"]: "CLOSED"}
    assert len({t["created_by"] for t in listing["items"]}) == 3

    summary = (await async_client.get("/api/v1/tickets/summary", headers=admin)).json()
    assert summary["total_tickets"] == listing["total"] == 3
    assert summary["by_status"] == {"NEW": 1, "UNDER_REVIEW": 1, "CLOSED": 1}
    closed_only = (await async_client.get("/api/v1/tickets?status=CLOSED", headers=admin)).json()
    assert closed_only["total"] == summary["by_status"]["CLOSED"]
