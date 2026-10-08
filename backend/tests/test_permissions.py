"""Pure unit tests for the RBAC / lifecycle policy (no database)."""

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.core import permissions as policy


def user(role, *, department_id=None, uid=None):
    return SimpleNamespace(id=uid or uuid.uuid4(), role=role, department_id=department_id)


def ticket(status="NEW", *, created_by=None, assigned_to=None, department_id=None, resolved_at=None):
    return SimpleNamespace(
        status=status, created_by=created_by or uuid.uuid4(), assigned_to=assigned_to,
        confirmed_department_id=department_id, resolved_at=resolved_at,
    )


@pytest.mark.parametrize("role", ["STUDENT", "FACULTY", "STAFF", "COORDINATOR", "ADMIN"])
def test_everyone_can_view_their_own_ticket(role):
    me = user(role)
    assert policy.can_view_ticket(me, ticket(created_by=me.id))


def test_students_and_faculty_only_see_their_own_tickets():
    for role in ("STUDENT", "FACULTY"):
        assert not policy.can_view_ticket(user(role), ticket())


def test_staff_see_assigned_or_own_department_tickets_only():
    dept = uuid.uuid4()
    staff = user("STAFF", department_id=dept)
    assert policy.can_view_ticket(staff, ticket(assigned_to=staff.id))
    assert policy.can_view_ticket(staff, ticket(department_id=dept))
    assert not policy.can_view_ticket(staff, ticket(department_id=uuid.uuid4()))
    assert not policy.can_view_ticket(staff, ticket())  # unassigned, no department


def test_staff_without_department_never_matches_unassigned_tickets():
    # Regression: `department_id == NULL` must not make a department-less staff user see everything.
    assert not policy.can_view_ticket(user("STAFF"), ticket())


@pytest.mark.parametrize("role", ["COORDINATOR", "ADMIN"])
def test_triage_roles_see_everything(role):
    assert policy.can_view_ticket(user(role), ticket())


def test_internal_notes_are_staff_only():
    assert not policy.can_see_internal_notes(user("STUDENT"))
    assert not policy.can_see_internal_notes(user("FACULTY"))
    assert all(policy.can_see_internal_notes(user(r)) for r in ("STAFF", "COORDINATOR", "ADMIN"))


def test_staff_can_only_move_their_own_ticket_forward():
    staff = user("STAFF")
    assert policy.allowed_status_transitions(staff, ticket("ASSIGNED", assigned_to=staff.id)) == {"IN_PROGRESS"}
    assert policy.allowed_status_transitions(staff, ticket("IN_PROGRESS", assigned_to=staff.id)) == {"RESOLVED"}
    assert policy.allowed_status_transitions(staff, ticket("REOPENED", assigned_to=staff.id)) == {"IN_PROGRESS"}
    assert policy.allowed_status_transitions(staff, ticket("ASSIGNED", assigned_to=uuid.uuid4())) == set()


def test_reporters_cannot_change_status_through_the_status_endpoint():
    me = user("STUDENT")
    assert policy.allowed_status_transitions(me, ticket("RESOLVED", created_by=me.id)) == set()


def test_coordinator_cannot_set_assigned_without_an_assignee():
    coordinator = user("COORDINATOR")
    assert "ASSIGNED" not in policy.allowed_status_transitions(coordinator, ticket("NEW"))
    assert "ASSIGNED" in policy.allowed_status_transitions(coordinator, ticket("NEW", assigned_to=uuid.uuid4()))


def test_closed_tickets_are_terminal_for_triage_roles():
    assert policy.allowed_status_transitions(user("ADMIN"), ticket("CLOSED")) == set()


def test_status_graph_never_skips_straight_to_resolved():
    assert "RESOLVED" not in policy.allowed_status_transitions(user("COORDINATOR"), ticket("NEW"))


def test_only_the_reporter_can_reopen_a_finished_ticket():
    me = user("STUDENT")
    assert policy.can_reopen(me, ticket("RESOLVED", created_by=me.id))
    assert policy.can_reopen(me, ticket("CLOSED", created_by=me.id))
    assert not policy.can_reopen(me, ticket("IN_PROGRESS", created_by=me.id))
    assert not policy.can_reopen(me, ticket("RESOLVED"))
    assert not policy.can_reopen(user("ADMIN"), ticket("RESOLVED"))


def test_nobody_can_comment_on_a_closed_ticket():
    me = user("STUDENT")
    assert policy.can_comment(me, ticket("RESOLVED", created_by=me.id))
    assert not policy.can_comment(me, ticket("CLOSED", created_by=me.id))
    assert not policy.can_comment(user("ADMIN"), ticket("CLOSED"))
    assert not policy.can_comment_internal(user("ADMIN"), ticket("CLOSED"))


@pytest.mark.parametrize("old,new,expected", [
    ("IN_PROGRESS", "RESOLVED", True),
    ("NEW", "CLOSED", True),
    ("UNDER_REVIEW", "CLOSED", True),
    ("RESOLVED", "CLOSED", False),
    ("NEW", "UNDER_REVIEW", False),
    ("ASSIGNED", "IN_PROGRESS", False),
    ("RESOLVED", "REOPENED", False),
])
def test_requires_remarks(old, new, expected):
    assert policy.requires_remarks(old, new) is expected


def test_only_the_reporter_confirms_a_resolved_ticket():
    me = user("STUDENT")
    assert policy.can_confirm_resolution(me, ticket("RESOLVED", created_by=me.id))
    assert not policy.can_confirm_resolution(me, ticket("CLOSED", created_by=me.id))
    assert not policy.can_confirm_resolution(me, ticket("RESOLVED"))
    assert not policy.can_confirm_resolution(user("ADMIN"), ticket("RESOLVED"))


@pytest.mark.parametrize("status,expected", [
    ("NEW", True), ("UNDER_REVIEW", True), ("ASSIGNED", False), ("IN_PROGRESS", False),
    ("RESOLVED", False), ("REOPENED", False), ("CLOSED", False),
])
def test_reporter_withdraws_only_before_assignment(status, expected):
    me = user("STUDENT")
    assert policy.can_withdraw(me, ticket(status, created_by=me.id)) is expected
    assert not policy.can_withdraw(user("ADMIN"), ticket(status))


@pytest.mark.parametrize("status,expected", [
    ("NEW", False), ("IN_PROGRESS", False), ("REOPENED", False), ("RESOLVED", True), ("CLOSED", True),
])
def test_reporter_gives_feedback_only_on_done_tickets(status, expected):
    me, resolved = user("STUDENT"), datetime.now(timezone.utc)
    assert policy.can_give_feedback(me, ticket(status, created_by=me.id, resolved_at=resolved)) is expected
    assert not policy.can_give_feedback(user("ADMIN"), ticket(status, resolved_at=resolved))


def test_no_feedback_on_withdrawn_or_rejected_tickets():
    me = user("STUDENT")
    assert not policy.can_give_feedback(me, ticket("CLOSED", created_by=me.id))


def test_department_less_staff_filter_never_compiles_to_is_null():
    # The original list query compared `confirmed_department_id == NULL`, which SQL renders as
    # `IS NULL` and exposed every unassigned ticket to staff accounts without a department.
    sql = str(policy.ticket_visibility_filter(user("STAFF")).compile(compile_kwargs={"literal_binds": True}))
    assert "IS NULL" not in sql
