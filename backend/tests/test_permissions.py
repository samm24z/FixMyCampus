"""Pure unit tests for the RBAC / lifecycle policy (no database)."""

import uuid
from types import SimpleNamespace

import pytest

from app.core import permissions as policy


def user(role, *, department_id=None, uid=None):
    return SimpleNamespace(id=uid or uuid.uuid4(), role=role, department_id=department_id)


def ticket(status="NEW", *, created_by=None, assigned_to=None, department_id=None):
    return SimpleNamespace(
        status=status, created_by=created_by or uuid.uuid4(), assigned_to=assigned_to,
        confirmed_department_id=department_id,
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


def test_department_less_staff_filter_never_compiles_to_is_null():
    # The original list query compared `confirmed_department_id == NULL`, which SQL renders as
    # `IS NULL` and exposed every unassigned ticket to staff accounts without a department.
    sql = str(policy.ticket_visibility_filter(user("STAFF")).compile(compile_kwargs={"literal_binds": True}))
    assert "IS NULL" not in sql
