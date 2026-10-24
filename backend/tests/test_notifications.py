"""Notifications: who hears about what, privacy, reading and marking as read (real PostgreSQL)."""

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update

from app.core.database import AsyncSessionLocal
from app.models import AuditLog, Notification, Ticket
from app.services import notification_service, sla_service
from scripts.demo_users import demo_user_id
from tests.test_tickets import assign, create_ticket, move, staff_id


async def rows(prefix: str) -> list[Notification]:
    async with AsyncSessionLocal() as session:
        return list((await session.scalars(
            select(Notification).where(Notification.user_id == demo_user_id(prefix)).order_by(Notification.created_at)
        )).all())


async def types(prefix: str) -> list[str]:
    return [n.type for n in await rows(prefix)]


async def assigned_ticket(client, login) -> tuple[dict, dict, dict, dict]:
    """A student's ticket given to the IT staff member. Returns (ticket, student, staff, coordinator) headers."""
    student, staff, coordinator = await login("student"), await login("staff"), await login("coordinator")
    ticket = await create_ticket(client, student)
    response = await assign(client, coordinator, ticket["ticket_number"], await staff_id(client, coordinator, "staff@fixmycampus.dev"))
    assert response.status_code == 200, response.text
    return ticket, student, staff, coordinator


# ------------------------------------------------------------------ who hears about what

async def test_filing_tells_coordinators_but_not_the_reporter(async_client, login):
    ticket = await create_ticket(async_client, await login("student"))
    [note] = await rows("coordinator")
    assert note.type == "TICKET_CREATED" and ticket["ticket_number"] in note.title
    assert await rows("student") == []
    assert await rows("admin") == []


async def test_assignment_tells_assignee_and_reporter(async_client, login):
    ticket, *_ = await assigned_ticket(async_client, login)
    assert await types("staff") == ["ASSIGNED"]
    [note] = await rows("student")
    assert note.type == "STATUS_CHANGED" and note.title == f"{ticket['ticket_number']} has been given to a staff member"
    assert await rows("staff2") == []


async def test_reassigning_tells_only_the_new_assignee(async_client, login):
    ticket, _, _, coordinator = await assigned_ticket(async_client, login)
    other = await staff_id(async_client, coordinator, "staff2@fixmycampus.dev")
    assert (await assign(async_client, coordinator, ticket["ticket_number"], other)).status_code == 200
    assert await types("staff2") == ["ASSIGNED"]
    assert await types("staff") == ["ASSIGNED"]
    assert await types("student") == ["STATUS_CHANGED"]  # status didn't change again


async def test_resolving_asks_reporter_to_confirm_and_quotes_the_fix(async_client, login):
    ticket, _, staff, _ = await assigned_ticket(async_client, login)
    number = ticket["ticket_number"]
    assert (await move(async_client, staff, number, "IN_PROGRESS")).status_code == 200
    assert (await move(async_client, staff, number, "RESOLVED", remarks="Replaced the access point")).status_code == 200
    notes = await rows("student")
    assert [n.type for n in notes] == ["STATUS_CHANGED", "STATUS_CHANGED", "FEEDBACK_REQUEST"]
    assert "Replaced the access point" in notes[-1].message
    assert await types("staff") == ["ASSIGNED"]  # never told about their own changes


async def test_reporter_actions_tell_the_assignee(async_client, login):
    ticket, student, staff, _ = await assigned_ticket(async_client, login)
    number = ticket["ticket_number"]
    await move(async_client, staff, number, "IN_PROGRESS")
    await move(async_client, staff, number, "RESOLVED", remarks="Fixed")
    response = await async_client.post(f"/api/v1/tickets/{number}/reopen", json={"reason": "Still down"}, headers=student)
    assert response.status_code == 200, response.text
    reopen = (await rows("staff"))[-1]
    assert reopen.title == f"{number} was reopened by the reporter" and "Still down" in reopen.message
    assert (await rows("student"))[-1].type == "FEEDBACK_REQUEST"  # nothing about their own reopen

    await move(async_client, staff, number, "IN_PROGRESS")
    await move(async_client, staff, number, "RESOLVED", remarks="Fixed again")
    assert (await async_client.post(f"/api/v1/tickets/{number}/confirm", headers=student)).status_code == 200
    response = await async_client.post(f"/api/v1/tickets/{number}/feedback", json={"rating": 4, "comments": "Quick"}, headers=student)
    assert response.status_code == 200, response.text
    titles = [n.title for n in await rows("staff")]
    assert titles[-2:] == [f"{number} was confirmed fixed", f"{number} was rated 4/5"]


async def test_reopen_without_assignee_tells_coordinators(async_client, login):
    student, coordinator = await login("student"), await login("coordinator")
    ticket = await create_ticket(async_client, student)
    number = ticket["ticket_number"]
    assert (await move(async_client, coordinator, number, "CLOSED", remarks="Not a campus issue")).status_code == 200
    closed = (await rows("student"))[-1]
    assert closed.title == f"{number} has been closed" and "Not a campus issue" in closed.message
    assert (await async_client.post(f"/api/v1/tickets/{number}/reopen", json={}, headers=student)).status_code == 200
    assert (await rows("coordinator"))[-1].title == f"{number} was reopened by the reporter"


async def test_comments_reach_the_other_side_and_staff_notes_stay_internal(async_client, login):
    ticket, student, staff, _ = await assigned_ticket(async_client, login)
    number = ticket["ticket_number"]
    url = f"/api/v1/tickets/{number}/comments"
    assert (await async_client.post(url, json={"content": "Which room exactly?"}, headers=staff)).status_code == 201
    assert (await async_client.post(url, json={"content": "Secret ladder location", "is_internal": True}, headers=staff)).status_code == 201
    assert (await async_client.post(url, json={"content": "Room 104"}, headers=student)).status_code == 201

    student_notes = [n for n in await rows("student") if n.type == "COMMENT_ADDED"]
    assert len(student_notes) == 1 and "Which room exactly?" in student_notes[0].message
    assert all("Secret" not in n.message for n in await rows("student"))
    staff_notes = [n for n in await rows("staff") if n.type == "COMMENT_ADDED"]
    assert len(staff_notes) == 1 and "Room 104" in staff_notes[0].message


async def test_coordinator_note_reaches_assignee(async_client, login):
    ticket, _, _, coordinator = await assigned_ticket(async_client, login)
    url = f"/api/v1/tickets/{ticket['ticket_number']}/comments"
    response = await async_client.post(url, json={"content": "Please prioritise", "is_internal": True}, headers=coordinator)
    assert response.status_code == 201
    assert (await rows("staff"))[-1].title == f"New staff note on {ticket['ticket_number']}"


async def test_auto_close_tells_the_reporter(async_client, login):
    ticket, _, staff, _ = await assigned_ticket(async_client, login)
    number = ticket["ticket_number"]
    await move(async_client, staff, number, "IN_PROGRESS")
    await move(async_client, staff, number, "RESOLVED", remarks="Fixed")
    async with AsyncSessionLocal() as session:
        from app.services import ticket_service
        assert await ticket_service.auto_close_resolved_tickets(session, now=datetime.now(timezone.utc) + timedelta(days=30)) == 1
    assert (await rows("student"))[-1].title == f"{number} has been closed"


# ------------------------------------------------------------------ reading

async def test_list_count_and_mark_read(async_client, login):
    ticket, student, staff, _ = await assigned_ticket(async_client, login)
    await move(async_client, staff, ticket["ticket_number"], "IN_PROGRESS")

    response = await async_client.get("/api/v1/notifications", headers=student)
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2 and body["items"][0]["title"].endswith("is being worked on")  # newest first
    assert body["items"][0]["ticket_number"] == ticket["ticket_number"]
    assert (await async_client.get("/api/v1/notifications/unread-count", headers=student)).json() == {"count": 2}

    first = body["items"][0]["id"]
    response = await async_client.post("/api/v1/notifications/read", json={"ids": [first]}, headers=student)
    assert response.json() == {"count": 1}
    unread = (await async_client.get("/api/v1/notifications", params={"unread_only": True}, headers=student)).json()
    assert [n["id"] for n in unread["items"]] == [body["items"][1]["id"]]
    assert (await async_client.post("/api/v1/notifications/read", json={"all": True}, headers=student)).json() == {"count": 0}


async def test_nobody_can_read_or_mark_someone_elses_notifications(async_client, login):
    await create_ticket(async_client, await login("student"))
    coordinator, student = await login("coordinator"), await login("student")
    [note] = (await async_client.get("/api/v1/notifications", headers=coordinator)).json()["items"]
    assert (await async_client.get("/api/v1/notifications", headers=student)).json()["total"] == 0
    response = await async_client.post("/api/v1/notifications/read", json={"ids": [note["id"]]}, headers=student)
    assert response.status_code == 200
    assert (await async_client.get("/api/v1/notifications/unread-count", headers=coordinator)).json() == {"count": 1}


async def test_mark_read_needs_ids_or_all(async_client, login):
    response = await async_client.post("/api/v1/notifications/read", json={}, headers=await login("student"))
    assert response.status_code == 422


async def test_notifications_about_tickets_no_longer_visible_are_hidden(async_client, login):
    ticket, _, staff, coordinator = await assigned_ticket(async_client, login)
    assert (await async_client.get("/api/v1/notifications/unread-count", headers=staff)).json() == {"count": 1}
    # Moved to another department's staff member: IT staff can no longer open the ticket.
    other = await staff_id(async_client, coordinator, "staff2@fixmycampus.dev")
    async with AsyncSessionLocal() as session:
        await session.execute(update(Ticket).where(Ticket.ticket_number == ticket["ticket_number"]).values(assigned_to=uuid.UUID(other), confirmed_department_id=None))
        await session.commit()
    assert (await async_client.get(f"/api/v1/tickets/{ticket['ticket_number']}", headers=staff)).status_code == 404
    assert (await async_client.get("/api/v1/notifications/unread-count", headers=staff)).json() == {"count": 0}
    assert (await async_client.get("/api/v1/notifications", headers=staff)).json()["items"] == []


async def test_requires_sign_in(async_client):
    assert (await async_client.get("/api/v1/notifications")).status_code in (401, 403)


async def test_purge_deletes_only_old_read_notifications(async_client, login):
    await create_ticket(async_client, await login("student"))
    coordinator = await login("coordinator")
    await async_client.post("/api/v1/notifications/read", json={"all": True}, headers=coordinator)
    await create_ticket(async_client, await login("student2"), title="Projector broken")
    async with AsyncSessionLocal() as session:
        assert await notification_service.purge_old(session) == 0
        assert await notification_service.purge_old(session, now=datetime.now(timezone.utc) + timedelta(days=365)) == 1
    [left] = await rows("coordinator")
    assert not left.is_read


# ------------------------------------------------------------------ SLA alerts

async def set_deadline(number: str, deadline: datetime) -> None:
    async with AsyncSessionLocal() as session:
        await session.execute(update(Ticket).where(Ticket.ticket_number == number).values(sla_deadline=deadline))
        await session.commit()


async def check(now: datetime) -> tuple[int, int]:
    async with AsyncSessionLocal() as session:
        return await sla_service.check_deadlines(session, now=now)


async def test_due_soon_then_overdue_alerts_go_out_once(async_client, login):
    ticket, *_ = await assigned_ticket(async_client, login)  # HIGH: 24 h target, warning after 12 h
    number, now = ticket["ticket_number"], datetime.now(timezone.utc)
    await set_deadline(number, now + timedelta(hours=20))
    assert await check(now) == (0, 0)

    assert await check(now + timedelta(hours=9)) == (1, 0)
    warning = (await rows("staff"))[-1]
    assert warning.type == "SLA_WARNING" and warning.title == f"{number} is due soon"
    assert not any(n.type == "SLA_WARNING" for n in await rows("coordinator"))  # assigned: only the assignee
    assert await check(now + timedelta(hours=10)) == (0, 0)

    assert await check(now + timedelta(hours=21)) == (0, 1)
    assert (await rows("staff"))[-1].type == "SLA_BREACH"
    assert (await rows("coordinator"))[-1].title == f"{number} is overdue"
    assert await check(now + timedelta(hours=30)) == (0, 0)
    assert not any(n.type.startswith("SLA") for n in await rows("student"))
    async with AsyncSessionLocal() as session:
        assert await session.scalar(select(AuditLog).where(AuditLog.action == "SLA_BREACH")) is not None


async def test_unassigned_warning_goes_to_coordinators(async_client, login):
    ticket = await create_ticket(async_client, await login("student"))
    now = datetime.now(timezone.utc)
    await set_deadline(ticket["ticket_number"], now + timedelta(hours=2))
    assert await check(now) == (1, 0)
    assert (await rows("coordinator"))[-1].type == "SLA_WARNING"


async def test_new_deadline_gets_new_alerts_and_done_tickets_are_skipped(async_client, login):
    ticket, _, staff, coordinator = await assigned_ticket(async_client, login)
    number, now = ticket["ticket_number"], datetime.now(timezone.utc)
    await set_deadline(number, now - timedelta(hours=1))
    assert await check(now) == (0, 1)

    later = (now + timedelta(days=3)).isoformat()
    assert (await async_client.patch(f"/api/v1/tickets/{number}", json={"sla_deadline": later}, headers=coordinator)).status_code == 200
    assert await check(now + timedelta(days=4)) == (0, 1)

    await move(async_client, staff, number, "IN_PROGRESS")
    await move(async_client, staff, number, "RESOLVED", remarks="Done")
    await set_deadline(number, now - timedelta(hours=1))
    async with AsyncSessionLocal() as session:
        await session.execute(update(Ticket).where(Ticket.ticket_number == number).values(sla_breached_at=None))
        await session.commit()
    assert await check(now) == (0, 0)
