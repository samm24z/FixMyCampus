"""Grouping of repeat reports: automatic and confirmed grouping, priority rises, following the main ticket."""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select, text

from app.core.database import AsyncSessionLocal
from app.models import AuditLog
from app.services import ticket_service
from tests.test_tickets import assign, create_ticket, move, staff_id

pytestmark = pytest.mark.usefixtures("embeddings_on")

PROJECTOR = {
    "title": "Projector not working in Room 204",
    "description": "The projector in Room 204 does not turn on during lectures.",
    "location": "Room 204",
    "category": "Classroom Equipment",
    "priority": "MEDIUM",
}
# Same wording except the description: similar enough to suggest, not enough to group on its own.
PROJECTOR_WEAK = {**PROJECTOR, "description": "The projector in Room 204 does not turn on at all."}
WASHROOM = {
    "title": "Water leaking in library washroom",
    "description": "A tap keeps leaking near the library washroom.",
    "location": "Library, ground floor",
    "category": "Water / Plumbing",
    "priority": "MEDIUM",
}


async def get(client, headers, ref) -> dict:
    response = await client.get(f"/api/v1/tickets/{ref}", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


async def post(client, headers, path, **json):
    return await client.post(f"/api/v1/tickets{path}", json=json, headers=headers)


async def file_reports(client, login, who: list[str], payload=PROJECTOR) -> list[dict]:
    return [await create_ticket(client, await login(name), **payload) for name in who]


async def test_a_near_identical_report_joins_the_main_ticket_automatically(async_client, login):
    main, repeat = await file_reports(async_client, login, ["student", "student2"])
    coordinator = await login("coordinator")

    mine = await get(async_client, await login("student2"), repeat["ticket_number"])
    assert mine["parent_ticket_id"] == main["id"]
    assert mine["history"][-1]["remarks"] == "Grouped with another report of the same problem"

    detail = await get(async_client, coordinator, main["ticket_number"])
    assert detail["report_count"] == 2
    assert [m["ticket_number"] for m in detail["group_members"]] == [repeat["ticket_number"]]
    member = await get(async_client, coordinator, repeat["ticket_number"])
    assert member["parent_ticket_number"] == main["ticket_number"]
    assert member["permissions"]["can_split_group"] is True

    async with AsyncSessionLocal() as db:
        stored = await db.scalar(text("SELECT embedding IS NOT NULL FROM tickets WHERE id = :id"), {"id": uuid.UUID(repeat["id"])})
        assert stored
        audit = (await db.scalars(select(AuditLog).where(AuditLog.entity_id == uuid.UUID(mine["id"]), AuditLog.user_id.is_(None)))).all()
        assert any((a.new_values or {}).get("grouped_with") == main["ticket_number"] for a in audit)


async def test_students_never_see_other_tickets_or_suggestions_of_a_group(async_client, login):
    main, repeat = await file_reports(async_client, login, ["student", "student2"])
    for who, own in (("student", main), ("student2", repeat)):
        body = await get(async_client, await login(who), own["ticket_number"])
        other = repeat if own is main else main
        assert other["ticket_number"] not in str(body)
        assert body["parent_ticket_number"] is None
        assert body["group_members"] == [] and body["duplicates"] == [] and body["suggestions"] is None
        assert body["suggested_category"] is None and body["ai_confidence"] is None
    assert (await async_client.get(f"/api/v1/tickets/{main['ticket_number']}", headers=await login("student2"))).status_code == 404


async def test_a_weaker_match_is_only_offered_to_coordinators(async_client, login):
    first, second = await file_reports(async_client, login, ["student", "student2"])
    weak = await create_ticket(async_client, await login("student2"), **PROJECTOR_WEAK)
    coordinator = await login("coordinator")

    detail = await get(async_client, coordinator, weak["ticket_number"])
    assert detail["parent_ticket_id"] is None
    candidates = {c["ticket_number"]: c for c in detail["duplicates"]}
    assert first["ticket_number"] in candidates
    assert 0.75 <= candidates[first["ticket_number"]]["similarity_score"] < 0.9
    assert (await get(async_client, coordinator, first["ticket_number"]))["report_count"] == 2  # only the identical one joined
    assert (await get(async_client, await login("student2"), weak["ticket_number"]))["duplicates"] == []


async def test_unrelated_and_finished_tickets_are_not_matched(async_client, login):
    coordinator = await login("coordinator")
    first = await create_ticket(async_client, await login("student"), **PROJECTOR)
    await create_ticket(async_client, await login("student2"), **WASHROOM)
    assert (await get(async_client, coordinator, first["ticket_number"]))["report_count"] == 1

    assert (await move(async_client, coordinator, first["ticket_number"], "CLOSED", remarks="Not a real problem")).status_code == 200
    again = await create_ticket(async_client, await login("faculty"), **PROJECTOR)
    detail = await get(async_client, coordinator, again["ticket_number"])
    assert detail["parent_ticket_id"] is None and detail["duplicates"] == []


async def test_priority_rises_at_three_and_five_reports_and_the_fix_by_date_follows(async_client, login):
    users = ["student", "student2", "faculty", "staff", "staff2", "admin"]
    coordinator = await login("coordinator")
    main = (await file_reports(async_client, login, users[:1]))[0]
    seen = [await get(async_client, coordinator, main["ticket_number"])]
    for who in users[1:]:
        await file_reports(async_client, login, [who])
        seen.append(await get(async_client, coordinator, main["ticket_number"]))
    assert [(t["report_count"], t["priority"]) for t in seen] == [
        (1, "MEDIUM"), (2, "MEDIUM"), (3, "HIGH"), (4, "HIGH"), (5, "CRITICAL"), (6, "CRITICAL"),
    ]
    deadlines = [datetime.fromisoformat(t["sla_deadline"]) for t in seen]
    assert deadlines[2] < deadlines[1] and deadlines[4] < deadlines[3] and deadlines[5] == deadlines[4]

    async with AsyncSessionLocal() as db:
        raised = (await db.scalars(select(AuditLog).where(AuditLog.entity_id == uuid.UUID(main["id"]), AuditLog.user_id.is_(None)))).all()
    assert [a.new_values["reason"] for a in raised] == [
        "Priority raised to High: reported by 3 people", "Priority raised to Critical: reported by 5 people",
    ]


async def test_grouped_reports_show_the_groups_priority_and_fix_by_date(async_client, login):
    tickets = await file_reports(async_client, login, ["student", "student2", "faculty"])
    coordinator = await login("coordinator")
    main_ref = tickets[0]["ticket_number"]
    main = await get(async_client, coordinator, main_ref)
    assert main["priority"] == "HIGH"
    member = await get(async_client, await login("student2"), tickets[1]["ticket_number"])
    assert (member["priority"], member["sla_deadline"]) == (main["priority"], main["sla_deadline"])

    changed = await async_client.patch(f"/api/v1/tickets/{main_ref}", json={"priority": "CRITICAL"}, headers=coordinator)
    assert changed.status_code == 200
    member = await get(async_client, await login("faculty"), tickets[2]["ticket_number"])
    assert (member["priority"], member["sla_deadline"]) == ("CRITICAL", changed.json()["sla_deadline"])


async def test_the_main_ticket_drives_every_report_in_the_group(async_client, login):
    tickets = await file_reports(async_client, login, ["student", "student2", "faculty"])
    coordinator, staff = await login("coordinator"), await login("staff")
    main_ref = tickets[0]["ticket_number"]

    assert (await assign(async_client, coordinator, main_ref, await staff_id(async_client, coordinator, "staff@fixmycampus.dev"))).status_code == 200
    assert (await move(async_client, staff, main_ref, "IN_PROGRESS")).status_code == 200
    for ticket, who in zip(tickets[1:], ("student2", "faculty")):
        assert (await get(async_client, await login(who), ticket["ticket_number"]))["status"] == "IN_PROGRESS"

    assert (await move(async_client, staff, main_ref, "RESOLVED", remarks="Replaced the bulb")).status_code == 200
    for ticket, who in zip(tickets[1:], ("student2", "faculty")):
        mine = await get(async_client, await login(who), ticket["ticket_number"])
        assert mine["status"] == "RESOLVED" and mine["resolved_at"]
        assert mine["history"][-1]["remarks"] == "Replaced the bulb" and mine["history"][-1]["changed_by"] is None
        assert mine["permissions"]["can_confirm"] and mine["permissions"]["can_reopen"] and mine["permissions"]["can_give_feedback"]

    confirmed = await post(async_client, await login("student2"), f"/{tickets[1]['ticket_number']}/confirm")
    assert confirmed.status_code == 200 and confirmed.json()["status"] == "CLOSED"
    assert (await get(async_client, await login("faculty"), tickets[2]["ticket_number"]))["status"] == "RESOLVED"
    assert (await get(async_client, coordinator, main_ref))["status"] == "RESOLVED"


async def test_members_cannot_be_updated_or_assigned_directly(async_client, login):
    main, member = await file_reports(async_client, login, ["student", "student2"])
    coordinator = await login("coordinator")
    detail = await get(async_client, coordinator, member["ticket_number"])
    assert detail["permissions"]["allowed_statuses"] == [] and detail["permissions"]["can_assign"] is False

    moved = await move(async_client, coordinator, member["ticket_number"], "UNDER_REVIEW")
    assert moved.status_code == 409 and main["ticket_number"] in moved.json()["error"]["message"]
    assigned = await assign(async_client, coordinator, member["ticket_number"], await staff_id(async_client, coordinator, "staff@fixmycampus.dev"))
    assert assigned.status_code == 409 and "update that ticket instead" in assigned.json()["error"]["message"]


async def test_reopening_a_grouped_report_takes_it_out_of_the_group_without_lowering_priority(async_client, login):
    tickets = await file_reports(async_client, login, ["student", "student2", "faculty"])
    coordinator, staff = await login("coordinator"), await login("staff")
    main_ref = tickets[0]["ticket_number"]
    await assign(async_client, coordinator, main_ref, await staff_id(async_client, coordinator, "staff@fixmycampus.dev"))
    await move(async_client, staff, main_ref, "IN_PROGRESS")
    await move(async_client, staff, main_ref, "RESOLVED", remarks="Fixed")

    reopened = await post(async_client, await login("student2"), f"/{tickets[1]['ticket_number']}/reopen", reason="Still dark")
    assert reopened.status_code == 200
    body = reopened.json()
    assert body["status"] == "REOPENED" and body["parent_ticket_id"] is None

    main = await get(async_client, coordinator, main_ref)
    assert main["report_count"] == 2 and main["priority"] == "HIGH" and main["status"] == "RESOLVED"
    assert [m["ticket_number"] for m in main["group_members"]] == [tickets[2]["ticket_number"]]
    assert (await get(async_client, await login("faculty"), tickets[2]["ticket_number"]))["status"] == "RESOLVED"


async def test_a_coordinator_can_split_a_wrong_grouping(async_client, login):
    main, member = await file_reports(async_client, login, ["student", "student2"])
    coordinator = await login("coordinator")
    path = f"/{member['ticket_number']}/group/split"

    assert (await post(async_client, await login("student2"), path)).status_code == 403
    assert (await post(async_client, await login("staff"), path)).status_code in (403, 404)
    split = await post(async_client, coordinator, path)
    assert split.status_code == 200
    assert split.json()["status"] == "UNDER_REVIEW" and split.json()["parent_ticket_id"] is None
    assert (await get(async_client, coordinator, main["ticket_number"]))["report_count"] == 1
    assert (await post(async_client, coordinator, path)).status_code == 409  # no longer grouped
    # The pair is remembered as "not the same", so it is not offered again
    again = await post(async_client, coordinator, f"/{member['ticket_number']}/suggestions/refresh")
    assert again.status_code == 200
    detail = await get(async_client, coordinator, member["ticket_number"])
    assert detail["parent_ticket_id"] is None and detail["duplicates"] == []


async def test_same_problem_groups_a_weaker_match_from_either_ticket(async_client, login):
    coordinator = await login("coordinator")
    older = await create_ticket(async_client, await login("student"), **PROJECTOR)
    newer = await create_ticket(async_client, await login("student2"), **PROJECTOR_WEAK)

    older_view = await get(async_client, coordinator, older["ticket_number"])
    assert [c["ticket_number"] for c in older_view["duplicates"]] == [newer["ticket_number"]]  # offered from both sides

    grouped = await post(async_client, coordinator, f"/{older['ticket_number']}/duplicates/{newer['ticket_number']}/group")
    assert grouped.status_code == 200
    assert grouped.json()["report_count"] == 2 and grouped.json()["duplicates"] == []
    member = await get(async_client, coordinator, newer["ticket_number"])
    assert member["parent_ticket_number"] == older["ticket_number"]
    assert (await post(async_client, coordinator, f"/{older['ticket_number']}/duplicates/{newer['ticket_number']}/group")).status_code == 409


async def test_not_the_same_hides_the_candidate_for_good(async_client, login):
    coordinator = await login("coordinator")
    older = await create_ticket(async_client, await login("student"), **PROJECTOR)
    newer = await create_ticket(async_client, await login("student2"), **PROJECTOR_WEAK)

    dismissed = await post(async_client, coordinator, f"/{newer['ticket_number']}/duplicates/{older['ticket_number']}/dismiss")
    assert dismissed.status_code == 200 and dismissed.json()["duplicates"] == []
    await post(async_client, coordinator, f"/{newer['ticket_number']}/suggestions/refresh")  # looks again
    assert (await get(async_client, coordinator, newer["ticket_number"]))["duplicates"] == []
    assert (await get(async_client, coordinator, older["ticket_number"]))["report_count"] == 1


async def test_only_coordinators_and_admins_can_confirm_or_reject_matches(async_client, login):
    older = await create_ticket(async_client, await login("student"), **PROJECTOR)
    newer = await create_ticket(async_client, await login("student2"), **PROJECTOR_WEAK)
    path = f"/{newer['ticket_number']}/duplicates/{older['ticket_number']}"
    student2 = await login("student2")
    assert (await post(async_client, student2, f"{path}/group")).status_code == 403
    assert (await post(async_client, student2, f"{path}/dismiss")).status_code == 403
    admin = await login("admin")
    assert (await post(async_client, admin, f"{path}/group")).status_code == 200


async def test_cancelling_the_main_ticket_hands_the_group_to_the_next_report(async_client, login):
    tickets = await file_reports(async_client, login, ["student", "student2", "faculty"])
    coordinator = await login("coordinator")
    cancelled = await post(async_client, await login("student"), f"/{tickets[0]['ticket_number']}/withdraw")
    assert cancelled.status_code == 200 and cancelled.json()["status"] == "CLOSED"

    new_main = await get(async_client, coordinator, tickets[1]["ticket_number"])
    assert new_main["parent_ticket_id"] is None and new_main["report_count"] == 2
    assert new_main["priority"] == "HIGH"
    assert [m["ticket_number"] for m in new_main["group_members"]] == [tickets[2]["ticket_number"]]
    assert (await get(async_client, coordinator, tickets[0]["ticket_number"]))["report_count"] == 1

    # A member cancelling just leaves the group
    left = await post(async_client, await login("faculty"), f"/{tickets[2]['ticket_number']}/withdraw")
    assert left.status_code == 200 and left.json()["parent_ticket_id"] is None
    assert (await get(async_client, coordinator, tickets[1]["ticket_number"]))["report_count"] == 1


async def test_turning_down_the_main_ticket_closes_the_whole_group(async_client, login):
    main, member = await file_reports(async_client, login, ["student", "student2"])
    coordinator = await login("coordinator")
    assert (await move(async_client, coordinator, main["ticket_number"], "CLOSED", remarks="Not our job")).status_code == 200
    mine = await get(async_client, await login("student2"), member["ticket_number"])
    assert mine["status"] == "CLOSED" and mine["history"][-1]["remarks"] == "Not our job"


async def test_auto_close_reaches_the_grouped_reports(async_client, login):
    tickets = await file_reports(async_client, login, ["student", "student2", "faculty"])
    coordinator, staff = await login("coordinator"), await login("staff")
    main_ref = tickets[0]["ticket_number"]
    await assign(async_client, coordinator, main_ref, await staff_id(async_client, coordinator, "staff@fixmycampus.dev"))
    await move(async_client, staff, main_ref, "IN_PROGRESS")
    await move(async_client, staff, main_ref, "RESOLVED", remarks="Fixed")

    async with AsyncSessionLocal() as db:
        closed = await ticket_service.auto_close_resolved_tickets(db, datetime.now(timezone.utc) + timedelta(days=30))
    assert closed == 3
    for ticket, who in zip(tickets[1:], ("student2", "faculty")):
        mine = await get(async_client, await login(who), ticket["ticket_number"])
        assert mine["status"] == "CLOSED" and [h["to_status"] for h in mine["history"]].count("CLOSED") == 1


async def test_ticket_creation_survives_a_broken_embedder(async_client, login, monkeypatch):
    from app.services import suggestion_service

    class Broken:
        async def embed(self, text):
            raise RuntimeError("model missing")

    suggestion_service.set_embedder(Broken())
    created = await create_ticket(async_client, await login("student"), **PROJECTOR)
    detail = await get(async_client, await login("coordinator"), created["ticket_number"])
    assert detail["suggestions"]["status"] == "done" and detail["duplicates"] == []
