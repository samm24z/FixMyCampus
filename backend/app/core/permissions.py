"""Central RBAC and ticket-lifecycle policy.

This module is the single source of truth for who may see or do what. It holds
pure functions only (no database access) so the rules are easy to test and can
be reused by API routes, services, and later by the AI agent's tools.

Visibility exists twice on purpose: ``ticket_visibility_filter`` builds the SQL
used by list/summary queries and ``can_view_ticket`` checks a loaded ticket. A
test asserts both always agree.
"""

from typing import Any

from sqlalchemy import or_, true
from sqlalchemy.sql.elements import ColumnElement

from app.models.enums import RoleEnum, TicketStatusEnum
from app.models.ticket import Ticket
from app.models.user import User


ADMIN = RoleEnum.ADMIN.value
COORDINATOR = RoleEnum.COORDINATOR.value
STAFF = RoleEnum.STAFF.value

# Roles that see every ticket and run triage (assign, re-categorise, re-prioritise).
TRIAGE_ROLES = {COORDINATOR, ADMIN}
# Roles that work tickets and may read/write internal notes.
STAFF_ROLES = {STAFF, COORDINATOR, ADMIN}
# Roles that can register themselves; every role may still file tickets.
SELF_REGISTRATION_ROLES = {RoleEnum.STUDENT.value, RoleEnum.FACULTY.value}

S = TicketStatusEnum

# Status graph for coordinators/admins. ASSIGNED additionally needs an assignee
# (see allowed_status_transitions); reopening is reporter-only and handled apart.
_TRIAGE_TRANSITIONS: dict[str, set[str]] = {
    S.NEW.value: {S.UNDER_REVIEW.value, S.ASSIGNED.value, S.CLOSED.value},
    S.UNDER_REVIEW.value: {S.ASSIGNED.value, S.CLOSED.value},
    S.ASSIGNED.value: {S.IN_PROGRESS.value, S.UNDER_REVIEW.value},
    S.IN_PROGRESS.value: {S.RESOLVED.value, S.ASSIGNED.value, S.UNDER_REVIEW.value},
    S.RESOLVED.value: {S.CLOSED.value},
    S.REOPENED.value: {S.UNDER_REVIEW.value, S.ASSIGNED.value, S.IN_PROGRESS.value},
    S.CLOSED.value: set(),
}
# Assigned staff can only move work forward.
_STAFF_TRANSITIONS: dict[str, set[str]] = {
    S.ASSIGNED.value: {S.IN_PROGRESS.value},
    S.REOPENED.value: {S.IN_PROGRESS.value},
    S.IN_PROGRESS.value: {S.RESOLVED.value},
}

# Statuses in which a ticket can be (re)assigned, and those where assigning
# should also move the ticket to ASSIGNED.
ASSIGNABLE_STATUSES = {
    S.NEW.value, S.UNDER_REVIEW.value, S.ASSIGNED.value, S.IN_PROGRESS.value, S.REOPENED.value,
}
PROMOTE_TO_ASSIGNED_STATUSES = {S.NEW.value, S.UNDER_REVIEW.value, S.REOPENED.value}
REOPENABLE_STATUSES = {S.RESOLVED.value, S.CLOSED.value}
DONE_STATUSES = {S.RESOLVED.value, S.CLOSED.value}


def is_admin(user: User) -> bool:
    return user.role == ADMIN


def can_triage(user: User) -> bool:
    return user.role in TRIAGE_ROLES


def can_see_internal_notes(user: User) -> bool:
    return user.role in STAFF_ROLES


def ticket_visibility_filter(user: User) -> ColumnElement[bool]:
    """SQL predicate for the tickets ``user`` may see."""
    if user.role in TRIAGE_ROLES:
        return true()
    clauses: list[Any] = [Ticket.created_by == user.id]
    if user.role == STAFF:
        clauses.append(Ticket.assigned_to == user.id)
        if user.department_id is not None:
            clauses.append(Ticket.confirmed_department_id == user.department_id)
    return or_(*clauses)


def can_view_ticket(user: User, ticket: Ticket) -> bool:
    """Python mirror of ``ticket_visibility_filter``."""
    if user.role in TRIAGE_ROLES or ticket.created_by == user.id:
        return True
    if user.role == STAFF:
        if ticket.assigned_to == user.id:
            return True
        return user.department_id is not None and ticket.confirmed_department_id == user.department_id
    return False


def can_comment(user: User, ticket: Ticket) -> bool:
    return can_view_ticket(user, ticket)


def can_comment_internal(user: User, ticket: Ticket) -> bool:
    return can_comment(user, ticket) and can_see_internal_notes(user)


def can_assign(user: User, ticket: Ticket) -> bool:
    return can_triage(user) and ticket.status in ASSIGNABLE_STATUSES


def can_edit_triage(user: User, ticket: Ticket) -> bool:
    return can_triage(user) and ticket.status != S.CLOSED.value


def can_change_status(user: User, ticket: Ticket) -> bool:
    """True if the user works this ticket at all (whether or not a given transition is valid)."""
    return user.role in TRIAGE_ROLES or (user.role == STAFF and ticket.assigned_to == user.id)


def can_reopen(user: User, ticket: Ticket) -> bool:
    return ticket.created_by == user.id and ticket.status in REOPENABLE_STATUSES


def allowed_status_transitions(user: User, ticket: Ticket) -> set[str]:
    """Statuses ``user`` may move ``ticket`` to via the status endpoint."""
    if user.role in TRIAGE_ROLES:
        options = set(_TRIAGE_TRANSITIONS.get(ticket.status, set()))
    elif user.role == STAFF and ticket.assigned_to == user.id:
        options = set(_STAFF_TRANSITIONS.get(ticket.status, set()))
    else:
        return set()
    if ticket.assigned_to is None:
        options.discard(S.ASSIGNED.value)  # use the assign endpoint to pick an assignee
    return options
