"""Ticket lifecycle service.

Every rule-enforcing ticket operation lives here so the API routes stay thin and
the same behaviour can be reused by other callers (e.g. the AI agent's tools).
Authorization rules themselves come from ``app.core.permissions``.
"""

import math
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core import permissions as policy
from app.core.config import settings
from app.core.exceptions import (
    ConflictException,
    ForbiddenException,
    NotFoundException,
    UnprocessableException,
)
from app.models.department import Department
from app.models.enums import AuditActionEnum, RoleEnum, TicketStatusEnum
from app.models.sla import SLARule
from app.models.ticket import Ticket, TicketAssignment, TicketComment, TicketFeedback, TicketStatusHistory
from app.models.user import User
from app.schemas.assignment import AssignmentRead
from app.schemas.comment import CommentCreate, CommentRead
from app.schemas.feedback import FeedbackCreate, FeedbackRead
from app.schemas.status_history import StatusHistoryRead
from app.schemas.ticket import (
    TicketCreate,
    TicketFilter,
    TicketRead,
    TicketReopenRequest,
    TicketStatusChange,
    TicketTriageUpdate,
    TicketWithdrawRequest,
)
from app.schemas.ticket_detail import (
    DashboardSummary,
    TicketAssignmentRequest,
    TicketDetailRead,
    TicketPermissions,
)
from app.services.audit_service import record_audit

S = TicketStatusEnum


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------- queries

def _detail_query():
    return select(Ticket).options(
        selectinload(Ticket.creator),
        selectinload(Ticket.assignee),
        selectinload(Ticket.confirmed_department),
        selectinload(Ticket.comments).selectinload(TicketComment.user),
        selectinload(Ticket.status_history),
        selectinload(Ticket.assignments),
        selectinload(Ticket.feedback),
    )


async def _load_ticket(db: AsyncSession, ticket_ref: str, *, for_update: bool = False) -> Optional[Ticket]:
    query = _detail_query().execution_options(populate_existing=True)
    try:
        query = query.where(Ticket.id == UUID(ticket_ref))
    except ValueError:
        query = query.where(Ticket.ticket_number == ticket_ref)
    if for_update:
        query = query.with_for_update(of=Ticket)
    return await db.scalar(query)


async def get_ticket_for_user(db: AsyncSession, user: User, ticket_ref: str, *, for_update: bool = False) -> Ticket:
    """Load a ticket the user may see. Tickets they may not see are reported as missing."""
    ticket = await _load_ticket(db, ticket_ref, for_update=for_update)
    if ticket is None or not policy.can_view_ticket(user, ticket):
        raise NotFoundException("Ticket", ticket_ref)
    return ticket


def _escape_like(term: str) -> str:
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _filtered_query(user: User, filters: TicketFilter):
    query = select(Ticket).where(policy.ticket_visibility_filter(user))
    if filters.status:
        query = query.where(Ticket.status == filters.status.value)
    if filters.category:
        query = query.where(Ticket.category == filters.category)
    if filters.priority:
        query = query.where(Ticket.priority == filters.priority.value)
    if filters.department_id:
        query = query.where(Ticket.confirmed_department_id == filters.department_id)
    if filters.assigned_to:
        query = query.where(Ticket.assigned_to == filters.assigned_to)
    if filters.created_by:
        query = query.where(Ticket.created_by == filters.created_by)
    if filters.open_only:
        query = query.where(Ticket.status.notin_(policy.DONE_STATUSES))
    if filters.mine:
        query = query.where(Ticket.created_by == user.id)
    if filters.search:
        pattern = f"%{_escape_like(filters.search.strip())}%"
        query = query.where(or_(
            Ticket.title.ilike(pattern, escape="\\"),
            Ticket.description.ilike(pattern, escape="\\"),
            Ticket.ticket_number.ilike(pattern, escape="\\"),
            Ticket.location.ilike(pattern, escape="\\"),
        ))
    return query


async def list_tickets(
    db: AsyncSession, user: User, filters: TicketFilter, page: int, page_size: int
) -> tuple[list[Ticket], int, int]:
    """Return (tickets, total, total_pages) for one page of the user's visible tickets."""
    query = _filtered_query(user, filters)
    total = await db.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = await db.scalars(
        query.order_by(Ticket.created_at.desc(), Ticket.id).offset((page - 1) * page_size).limit(page_size)
    )
    return list(rows.all()), total, math.ceil(total / page_size) if total else 0


async def dashboard_summary(db: AsyncSession, user: User) -> DashboardSummary:
    visible = policy.ticket_visibility_filter(user)
    counts = await db.execute(select(Ticket.status, func.count()).where(visible).group_by(Ticket.status))
    by_status = {status: count for status, count in counts.all()}
    total = sum(by_status.values())
    done = sum(by_status.get(status, 0) for status in policy.DONE_STATUSES)
    recent = await db.scalars(select(Ticket).where(visible).order_by(Ticket.created_at.desc()).limit(5))
    return DashboardSummary(
        total_tickets=total,
        open_tickets=total - done,
        resolved_tickets=done,
        by_status=by_status,
        recent_tickets=[TicketRead.model_validate(ticket) for ticket in recent.all()],
    )


# ------------------------------------------------------------ presentation

def build_detail(ticket: Ticket, user: User) -> TicketDetailRead:
    show_internal = policy.can_see_internal_notes(user)
    comments = [
        CommentRead.model_validate(comment).model_copy(
            update={"author_name": comment.user.full_name, "author_role": comment.user.role}
        )
        for comment in sorted(ticket.comments, key=lambda item: item.created_at)
        if show_internal or not comment.is_internal
    ]
    return TicketDetailRead(
        **TicketRead.model_validate(ticket).model_dump(),
        created_by_name=ticket.creator.full_name,
        assigned_to_name=ticket.assignee.full_name if ticket.assignee else None,
        department_name=ticket.confirmed_department.name if ticket.confirmed_department else None,
        comments=comments,
        history=[StatusHistoryRead.model_validate(h) for h in sorted(ticket.status_history, key=lambda item: item.created_at)],
        assignments=[AssignmentRead.model_validate(a) for a in sorted(ticket.assignments, key=lambda item: item.created_at)],
        feedback=FeedbackRead.model_validate(ticket.feedback) if ticket.feedback else None,
        permissions=TicketPermissions(
            allowed_statuses=sorted(policy.allowed_status_transitions(user, ticket)),
            can_assign=policy.can_assign(user, ticket),
            can_edit_triage=policy.can_edit_triage(user, ticket),
            can_comment=policy.can_comment(user, ticket),
            can_comment_internal=policy.can_comment_internal(user, ticket),
            can_reopen=policy.can_reopen(user, ticket),
            can_confirm=policy.can_confirm_resolution(user, ticket),
            can_withdraw=policy.can_withdraw(user, ticket),
            can_give_feedback=policy.can_give_feedback(user, ticket),
            statuses_requiring_remarks=[
                status for status in S if policy.requires_remarks(ticket.status, status.value)
            ],
        ),
    )


async def _detail_after_commit(db: AsyncSession, user: User, ticket_id: UUID) -> TicketDetailRead:
    ticket = await _load_ticket(db, str(ticket_id))
    assert ticket is not None
    return build_detail(ticket, user)


# ------------------------------------------------------------------- helpers

async def _sla_deadline(db: AsyncSession, category: str, priority: str, start: datetime) -> Optional[datetime]:
    rule = await db.scalar(
        select(SLARule).where(
            SLARule.category == category, SLARule.priority == priority, SLARule.is_active.is_(True)
        ).order_by(SLARule.created_at).limit(1)
    )
    return start + timedelta(hours=rule.target_resolution_hours) if rule else None


async def _require_department(db: AsyncSession, department_id: UUID) -> Department:
    department = await db.scalar(select(Department).where(Department.id == department_id, Department.is_active.is_(True)))
    if department is None:
        raise UnprocessableException("Department not found or inactive")
    return department


def _record_status(db: AsyncSession, ticket: Ticket, user: Optional[User], old: Optional[str], new: str, remarks: Optional[str] = None) -> None:
    db.add(TicketStatusHistory(ticket_id=ticket.id, changed_by=user.id if user else None, from_status=old, to_status=new, remarks=remarks))
    record_audit(
        db, user=user, action=AuditActionEnum.STATUS_CHANGE, entity_type="ticket", entity_id=ticket.id,
        old_values={"status": old}, new_values={"status": new, "remarks": remarks},
    )


# --------------------------------------------------------------- operations

async def create_ticket(db: AsyncSession, user: User, payload: TicketCreate) -> TicketDetailRead:
    sequence = await db.scalar(text("SELECT nextval('ticket_number_seq')"))
    now = _now()
    ticket = Ticket(
        ticket_number=f"TICK-{now.year}-{sequence:04d}",
        title=payload.title,
        description=payload.description,
        category=payload.category,
        priority=payload.priority.value,
        location=payload.location,
        status=S.NEW.value,
        created_by=user.id,
        sla_deadline=await _sla_deadline(db, payload.category, payload.priority.value, now),
    )
    db.add(ticket)
    await db.flush()
    _record_status(db, ticket, user, None, S.NEW.value)
    record_audit(
        db, user=user, action=AuditActionEnum.CREATE, entity_type="ticket", entity_id=ticket.id,
        new_values={"ticket_number": ticket.ticket_number, "category": ticket.category, "priority": ticket.priority},
    )
    await db.commit()
    return await _detail_after_commit(db, user, ticket.id)


async def change_status(db: AsyncSession, user: User, ticket_ref: str, payload: TicketStatusChange) -> TicketDetailRead:
    ticket = await get_ticket_for_user(db, user, ticket_ref, for_update=True)
    if not policy.can_change_status(user, ticket):
        raise ForbiddenException("You cannot change the status of this ticket")
    old, new = ticket.status, payload.status.value
    if new == old:
        raise ConflictException(f"Ticket is already {old}")
    if new not in policy.allowed_status_transitions(user, ticket):
        hint = " (assign the ticket to a staff member first)" if new == S.ASSIGNED.value and ticket.assigned_to is None else ""
        raise ConflictException(f"Cannot move a ticket from {old} to {new}{hint}")
    if policy.requires_remarks(old, new) and not (payload.remarks and payload.remarks.strip()):
        what = "a resolution note" if new == S.RESOLVED.value else "a reason for rejecting the ticket"
        raise UnprocessableException(f"Remarks are required: please give {what}")
    ticket.status = new
    if new == S.RESOLVED.value:
        ticket.resolved_at = _now()
    _record_status(db, ticket, user, old, new, payload.remarks)
    await db.commit()
    return await _detail_after_commit(db, user, ticket.id)


async def assign_ticket(db: AsyncSession, user: User, ticket_ref: str, payload: TicketAssignmentRequest) -> TicketDetailRead:
    ticket = await get_ticket_for_user(db, user, ticket_ref, for_update=True)
    if not policy.can_triage(user):
        raise ForbiddenException("Only coordinators and admins can assign tickets")
    if ticket.status not in policy.ASSIGNABLE_STATUSES:
        raise ConflictException(f"A {ticket.status} ticket cannot be assigned")
    assignee = await db.scalar(select(User).where(
        User.id == payload.assigned_to, User.is_active.is_(True), User.role == RoleEnum.STAFF.value
    ))
    if assignee is None:
        raise NotFoundException("Staff member", payload.assigned_to)
    department_id = payload.department_id or assignee.department_id
    if department_id is None:
        raise UnprocessableException("A department is required: the staff member has none on record")
    await _require_department(db, department_id)

    old_status = ticket.status
    old = {"assigned_to": str(ticket.assigned_to) if ticket.assigned_to else None,
           "confirmed_department_id": str(ticket.confirmed_department_id) if ticket.confirmed_department_id else None}
    ticket.assigned_to = assignee.id
    ticket.confirmed_department_id = department_id
    if old_status in policy.PROMOTE_TO_ASSIGNED_STATUSES:
        ticket.status = S.ASSIGNED.value
        _record_status(db, ticket, user, old_status, ticket.status)
    db.add(TicketAssignment(
        ticket_id=ticket.id, assigned_by=user.id, assigned_to=assignee.id,
        department_id=department_id, notes=payload.notes,
    ))
    record_audit(
        db, user=user, action=AuditActionEnum.ASSIGNMENT, entity_type="ticket", entity_id=ticket.id,
        old_values=old, new_values={"assigned_to": str(assignee.id), "confirmed_department_id": str(department_id)},
    )
    await db.commit()
    return await _detail_after_commit(db, user, ticket.id)


async def update_triage(db: AsyncSession, user: User, ticket_ref: str, payload: TicketTriageUpdate) -> TicketDetailRead:
    ticket = await get_ticket_for_user(db, user, ticket_ref, for_update=True)
    if not policy.can_triage(user):
        raise ForbiddenException("Only coordinators and admins can edit triage fields")
    if not policy.can_edit_triage(user, ticket):
        raise ConflictException("Closed tickets cannot be edited")

    given = payload.model_dump(exclude_unset=True)
    old: dict = {}
    new: dict = {}
    classification_changed = False
    if given.get("category") and given["category"] != ticket.category:
        old["category"], new["category"] = ticket.category, given["category"]
        ticket.category = ticket.confirmed_category = given["category"]
        classification_changed = True
    if given.get("priority") and given["priority"].value != ticket.priority:
        old["priority"], new["priority"] = ticket.priority, given["priority"].value
        ticket.priority = given["priority"].value
        classification_changed = True
    if given.get("confirmed_department_id") and given["confirmed_department_id"] != ticket.confirmed_department_id:
        await _require_department(db, given["confirmed_department_id"])
        old["confirmed_department_id"] = str(ticket.confirmed_department_id) if ticket.confirmed_department_id else None
        new["confirmed_department_id"] = str(given["confirmed_department_id"])
        ticket.confirmed_department_id = given["confirmed_department_id"]
    if "sla_deadline" in given:
        old["sla_deadline"] = ticket.sla_deadline.isoformat() if ticket.sla_deadline else None
        ticket.sla_deadline = given["sla_deadline"]
        new["sla_deadline"] = given["sla_deadline"].isoformat() if given["sla_deadline"] else None
    elif classification_changed:
        ticket.sla_deadline = await _sla_deadline(db, ticket.category, ticket.priority, ticket.created_at)
        new["sla_deadline"] = ticket.sla_deadline.isoformat() if ticket.sla_deadline else None

    if new:
        record_audit(
            db, user=user, action=AuditActionEnum.UPDATE, entity_type="ticket", entity_id=ticket.id,
            old_values=old, new_values=new,
        )
    await db.commit()
    return await _detail_after_commit(db, user, ticket.id)


async def add_comment(db: AsyncSession, user: User, ticket_ref: str, payload: CommentCreate) -> TicketDetailRead:
    ticket = await get_ticket_for_user(db, user, ticket_ref)
    if not policy.can_comment(user, ticket):
        raise ForbiddenException("You cannot comment on this ticket")
    if payload.is_internal and not policy.can_comment_internal(user, ticket):
        raise ForbiddenException("Only staff can post internal notes")
    db.add(TicketComment(ticket_id=ticket.id, user_id=user.id, content=payload.content, is_internal=payload.is_internal))
    await db.commit()
    return await _detail_after_commit(db, user, ticket.id)


async def reopen_ticket(db: AsyncSession, user: User, ticket_ref: str, payload: TicketReopenRequest) -> TicketDetailRead:
    ticket = await get_ticket_for_user(db, user, ticket_ref, for_update=True)
    if ticket.created_by != user.id:
        raise ForbiddenException("Only the reporter can reopen this ticket")
    if ticket.status not in policy.REOPENABLE_STATUSES:
        raise ConflictException("Only resolved or closed tickets can be reopened")
    old = ticket.status
    ticket.status = S.REOPENED.value
    ticket.reopened_at = _now()
    ticket.resolved_at = None
    _record_status(db, ticket, user, old, ticket.status, payload.reason)
    await db.commit()
    return await _detail_after_commit(db, user, ticket.id)


async def confirm_resolution(db: AsyncSession, user: User, ticket_ref: str) -> TicketDetailRead:
    ticket = await get_ticket_for_user(db, user, ticket_ref, for_update=True)
    if ticket.created_by != user.id:
        raise ForbiddenException("Only the reporter can confirm the fix")
    if not policy.can_confirm_resolution(user, ticket):
        raise ConflictException("Only resolved tickets can be confirmed")
    old = ticket.status
    ticket.status = S.CLOSED.value
    _record_status(db, ticket, user, old, ticket.status, "Confirmed fixed by reporter")
    await db.commit()
    return await _detail_after_commit(db, user, ticket.id)


async def withdraw_ticket(db: AsyncSession, user: User, ticket_ref: str, payload: TicketWithdrawRequest) -> TicketDetailRead:
    ticket = await get_ticket_for_user(db, user, ticket_ref, for_update=True)
    if ticket.created_by != user.id:
        raise ForbiddenException("Only the reporter can withdraw this ticket")
    if not policy.can_withdraw(user, ticket):
        raise ConflictException("Only tickets that are not yet assigned can be withdrawn")
    old = ticket.status
    ticket.status = S.CLOSED.value
    reason = payload.reason.strip() if payload.reason else ""
    _record_status(db, ticket, user, old, ticket.status, f"Withdrawn by reporter: {reason}" if reason else "Withdrawn by reporter")
    await db.commit()
    return await _detail_after_commit(db, user, ticket.id)


async def submit_feedback(db: AsyncSession, user: User, ticket_ref: str, payload: FeedbackCreate) -> TicketDetailRead:
    ticket = await get_ticket_for_user(db, user, ticket_ref, for_update=True)
    if ticket.created_by != user.id:
        raise ForbiddenException("Only the reporter can rate this ticket")
    if not policy.can_give_feedback(user, ticket):
        raise ConflictException("Feedback can only be given on a ticket that was resolved")
    feedback = ticket.feedback
    old = {"rating": feedback.rating, "comments": feedback.comments} if feedback else None
    if feedback is None:
        db.add(TicketFeedback(ticket_id=ticket.id, user_id=user.id, rating=payload.rating, comments=payload.comments))
    else:
        feedback.rating, feedback.comments = payload.rating, payload.comments
    record_audit(
        db, user=user, action=AuditActionEnum.FEEDBACK_SUBMITTED, entity_type="ticket", entity_id=ticket.id,
        old_values=old, new_values={"rating": payload.rating, "comments": payload.comments},
    )
    await db.commit()
    return await _detail_after_commit(db, user, ticket.id)


async def auto_close_resolved_tickets(db: AsyncSession, now: Optional[datetime] = None) -> int:
    """Close RESOLVED tickets the reporter has not answered for AUTO_CLOSE_RESOLVED_AFTER_DAYS days."""
    days = settings.AUTO_CLOSE_RESOLVED_AFTER_DAYS
    cutoff = (now or _now()) - timedelta(days=days)
    tickets = (await db.scalars(
        select(Ticket)
        .where(Ticket.status == S.RESOLVED.value, Ticket.resolved_at < cutoff)
        .with_for_update(skip_locked=True)
    )).all()
    for ticket in tickets:
        ticket.status = S.CLOSED.value
        _record_status(db, ticket, None, S.RESOLVED.value, S.CLOSED.value,
                       f"Auto-closed: no response from reporter within {days} days")
    await db.commit()
    return len(tickets)
