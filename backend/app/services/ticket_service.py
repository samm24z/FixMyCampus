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
from app.models.ticket import (
    Ticket,
    TicketAssignment,
    TicketComment,
    TicketDuplicate,
    TicketFeedback,
    TicketStatusHistory,
)
from app.models.user import User
from app.schemas.ai import DuplicateCandidateSummary, TicketSuggestions
from app.schemas.assignment import AssignmentRead
from app.schemas.comment import CommentCreate, CommentRead
from app.schemas.duplicate import GroupMemberRead
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
from app.services import group_service, notification_service
from app.services import upload_service
from app.services.audit_service import record_audit

S = TicketStatusEnum


def _label(status: str) -> str:
    """Status as people read it: IN_PROGRESS -> 'in progress'."""
    return status.replace("_", " ").lower()


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------- queries

def _detail_query():
    return select(Ticket).options(
        selectinload(Ticket.creator),
        selectinload(Ticket.assignee),
        selectinload(Ticket.confirmed_department),
        selectinload(Ticket.suggested_department),
        selectinload(Ticket.parent),
        selectinload(Ticket.members),
        selectinload(Ticket.duplicates_as_duplicate).selectinload(TicketDuplicate.primary_ticket),
        selectinload(Ticket.duplicates_as_primary).selectinload(TicketDuplicate.duplicate_ticket),
        selectinload(Ticket.comments).selectinload(TicketComment.user),
        selectinload(Ticket.status_history),
        selectinload(Ticket.assignments),
        selectinload(Ticket.feedback),
        selectinload(Ticket.attachments),
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
        recent_tickets=[to_read(ticket, user) for ticket in recent.all()],
    )


# ------------------------------------------------------------ presentation

def to_read(ticket: Ticket, user: User) -> TicketRead:
    """The ticket as ``user`` may see it: suggestions are for coordinators and admins only."""
    read = TicketRead.model_validate(ticket)
    if policy.can_review_suggestions(user):
        return read
    return read.model_copy(update={"suggested_category": None, "suggested_department_id": None, "ai_confidence": None})


def _possible_duplicates(ticket: Ticket) -> list[DuplicateCandidateSummary]:
    """Open reports that may be the same problem and nobody has decided on yet."""
    own_group = ticket.parent_ticket_id or ticket.id
    found = []
    for link in [*ticket.duplicates_as_duplicate, *ticket.duplicates_as_primary]:
        if group_service.is_reviewed(link):
            continue
        other = link.primary_ticket if link.duplicate_ticket_id == ticket.id else link.duplicate_ticket
        if other.status in policy.DONE_STATUSES or (other.parent_ticket_id or other.id) == own_group:
            continue
        found.append(DuplicateCandidateSummary(
            ticket_id=other.id, ticket_number=other.ticket_number, title=other.title,
            similarity_score=round(link.similarity_score, 3), status=other.status,
        ))
    return sorted(found, key=lambda item: -item.similarity_score)


def build_detail(ticket: Ticket, user: User) -> TicketDetailRead:
    show_internal = policy.can_see_internal_notes(user)
    reviewer = policy.can_review_suggestions(user)
    base = to_read(ticket, user).model_dump()
    if reviewer and ticket.parent:
        base["parent_ticket_number"] = ticket.parent.ticket_number
    comments = [
        CommentRead.model_validate(comment).model_copy(
            update={"author_name": comment.user.full_name, "author_role": comment.user.role}
        )
        for comment in sorted(ticket.comments, key=lambda item: item.created_at)
        if show_internal or not comment.is_internal
    ]
    show_location = policy.can_see_media_location(user, ticket)
    return TicketDetailRead(
        **base,
        observed_at=ticket.observed_at,
        location_source=ticket.location_source,
        attachment_count=sum(1 for item in ticket.attachments if item.status == "ready"),
        report_lat=ticket.report_lat if show_location else None,
        report_lng=ticket.report_lng if show_location else None,
        report_accuracy_m=ticket.report_accuracy_m if show_location else None,
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
            can_review_suggestions=reviewer,
            can_split_group=policy.can_split_group(user, ticket),
            statuses_requiring_remarks=[
                status for status in S if policy.requires_remarks(ticket.status, status.value)
            ],
        ),
        suggestions=TicketSuggestions(
            status=ticket.ai_status, category=ticket.suggested_category, priority=ticket.suggested_priority,
            department_id=ticket.suggested_department_id,
            department_name=ticket.suggested_department.name if ticket.suggested_department else None,
            confidence=ticket.ai_confidence, reason=ticket.ai_reason, source=ticket.ai_source,
            analyzed_at=ticket.ai_analyzed_at,
        ) if reviewer and ticket.ai_status else None,
        duplicates=_possible_duplicates(ticket) if reviewer else [],
        group_members=[
            GroupMemberRead(ticket_id=m.id, ticket_number=m.ticket_number, title=m.title, status=m.status, created_at=m.created_at)
            for m in sorted(ticket.members, key=lambda item: item.created_at)
        ] if reviewer else [],
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
        raise UnprocessableException("That department doesn't exist or is no longer active")
    return department


def _record_status(db: AsyncSession, ticket: Ticket, user: Optional[User], old: Optional[str], new: str, remarks: Optional[str] = None) -> None:
    db.add(TicketStatusHistory(ticket_id=ticket.id, changed_by=user.id if user else None, from_status=old, to_status=new, remarks=remarks))
    record_audit(
        db, user=user, action=AuditActionEnum.STATUS_CHANGE, entity_type="ticket", entity_id=ticket.id,
        old_values={"status": old}, new_values={"status": new, "remarks": remarks},
    )
    notification_service.status_changed(db, ticket, user, old, new, remarks)


# --------------------------------------------------------------- operations

async def create_ticket(db: AsyncSession, user: User, payload: TicketCreate) -> TicketDetailRead:
    photos = await upload_service.claim_for_ticket(db, user, payload.attachment_ids)  # 422 before anything is created
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
        ai_status="pending" if settings.AI_SUGGESTIONS_ENABLED else None,
        created_by=user.id,
        observed_at=payload.observed_at or now,
        report_lat=payload.report_lat,
        report_lng=payload.report_lng,
        report_accuracy_m=payload.report_accuracy_m,
        location_source=payload.location_source,
        sla_deadline=await _sla_deadline(db, payload.category, payload.priority.value, now),
    )
    db.add(ticket)
    await db.flush()
    upload_service.link_to_ticket(db, user, ticket, photos)
    _record_status(db, ticket, user, None, S.NEW.value)
    record_audit(
        db, user=user, action=AuditActionEnum.CREATE, entity_type="ticket", entity_id=ticket.id,
        new_values={"ticket_number": ticket.ticket_number, "category": ticket.category, "priority": ticket.priority},
    )
    await notification_service.ticket_filed(db, ticket, user)
    await db.commit()
    return await _detail_after_commit(db, user, ticket.id)


async def change_status(db: AsyncSession, user: User, ticket_ref: str, payload: TicketStatusChange) -> TicketDetailRead:
    ticket = await get_ticket_for_user(db, user, ticket_ref, for_update=True)
    if not policy.can_change_status(user, ticket):
        raise ForbiddenException("You can't change the status of this ticket")
    if policy.is_group_member(ticket):
        raise group_service.grouped_error(ticket)
    old, new = ticket.status, payload.status.value
    if new == old:
        raise ConflictException(f"This ticket is already {_label(old)}")
    if new not in policy.allowed_status_transitions(user, ticket):
        hint = ". Assign it to a staff member first" if new == S.ASSIGNED.value and ticket.assigned_to is None else ""
        raise ConflictException(f"A ticket can't go from {_label(old)} to {_label(new)}{hint}")
    if policy.requires_remarks(old, new) and not (payload.remarks and payload.remarks.strip()):
        what = "saying what was fixed" if new == S.RESOLVED.value else "saying why this ticket is being turned down"
        raise UnprocessableException(f"Please add a note {what}")
    ticket.status = new
    if new == S.RESOLVED.value:
        ticket.resolved_at = _now()
    _record_status(db, ticket, user, old, new, payload.remarks)
    await group_service.propagate_status(db, ticket, new, payload.remarks)
    await db.commit()
    return await _detail_after_commit(db, user, ticket.id)


async def assign_ticket(db: AsyncSession, user: User, ticket_ref: str, payload: TicketAssignmentRequest) -> TicketDetailRead:
    ticket = await get_ticket_for_user(db, user, ticket_ref, for_update=True)
    if not policy.can_triage(user):
        raise ForbiddenException("Only coordinators and admins can assign tickets")
    if policy.is_group_member(ticket):
        raise group_service.grouped_error(ticket)
    if ticket.status not in policy.ASSIGNABLE_STATUSES:
        raise ConflictException(f"A ticket that is {_label(ticket.status)} can't be assigned")
    assignee = await db.scalar(select(User).where(
        User.id == payload.assigned_to, User.is_active.is_(True), User.role == RoleEnum.STAFF.value
    ))
    if assignee is None:
        raise NotFoundException("Staff member", payload.assigned_to)
    department_id = payload.department_id or assignee.department_id
    if department_id is None:
        raise UnprocessableException("Please choose a department: this staff member doesn't belong to one")
    await _require_department(db, department_id)

    old_status = ticket.status
    old = {"assigned_to": str(ticket.assigned_to) if ticket.assigned_to else None,
           "confirmed_department_id": str(ticket.confirmed_department_id) if ticket.confirmed_department_id else None}
    ticket.assigned_to = assignee.id
    ticket.confirmed_department_id = department_id
    if old_status in policy.PROMOTE_TO_ASSIGNED_STATUSES:
        ticket.status = S.ASSIGNED.value
        _record_status(db, ticket, user, old_status, ticket.status)
        await group_service.propagate_status(db, ticket, ticket.status)
    db.add(TicketAssignment(
        ticket_id=ticket.id, assigned_by=user.id, assigned_to=assignee.id,
        department_id=department_id, notes=payload.notes,
    ))
    record_audit(
        db, user=user, action=AuditActionEnum.ASSIGNMENT, entity_type="ticket", entity_id=ticket.id,
        old_values=old, new_values={"assigned_to": str(assignee.id), "confirmed_department_id": str(department_id)},
    )
    if old["assigned_to"] != str(assignee.id):
        notification_service.assigned(db, ticket, assignee, user)
    await db.commit()
    return await _detail_after_commit(db, user, ticket.id)


async def update_triage(db: AsyncSession, user: User, ticket_ref: str, payload: TicketTriageUpdate) -> TicketDetailRead:
    ticket = await get_ticket_for_user(db, user, ticket_ref, for_update=True)
    if not policy.can_triage(user):
        raise ForbiddenException("Only coordinators and admins can change the category or priority")
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

    if "sla_deadline" in new:
        ticket.sla_warned_at = ticket.sla_breached_at = None  # a new deadline gets its own alerts
    if new:
        record_audit(
            db, user=user, action=AuditActionEnum.UPDATE, entity_type="ticket", entity_id=ticket.id,
            old_values=old, new_values=new,
        )
    if ("priority" in new or "sla_deadline" in new) and ticket.report_count > 1:
        await group_service.sync_member_priority(db, ticket)
    suggested = {"category": ticket.suggested_category, "priority": ticket.suggested_priority}
    overridden = {key: suggested[key] for key in ("category", "priority") if key in new and suggested[key] and new[key] != suggested[key]}
    if overridden:  # a person chose something other than what the system suggested
        record_audit(
            db, user=user, action=AuditActionEnum.AI_OVERRIDE, entity_type="ticket", entity_id=ticket.id,
            old_values=overridden, new_values={key: new[key] for key in overridden},
        )
    await db.commit()
    return await _detail_after_commit(db, user, ticket.id)


async def add_comment(db: AsyncSession, user: User, ticket_ref: str, payload: CommentCreate) -> TicketDetailRead:
    ticket = await get_ticket_for_user(db, user, ticket_ref)
    if not policy.can_comment(user, ticket):
        raise ForbiddenException("You cannot comment on this ticket")
    if payload.is_internal and not policy.can_comment_internal(user, ticket):
        raise ForbiddenException("Only staff can add staff-only notes")
    db.add(TicketComment(ticket_id=ticket.id, user_id=user.id, content=payload.content, is_internal=payload.is_internal))
    await notification_service.comment_added(db, ticket, user, payload.content, payload.is_internal)
    await db.commit()
    return await _detail_after_commit(db, user, ticket.id)


async def reopen_ticket(db: AsyncSession, user: User, ticket_ref: str, payload: TicketReopenRequest) -> TicketDetailRead:
    ticket = await get_ticket_for_user(db, user, ticket_ref, for_update=True)
    if ticket.created_by != user.id:
        raise ForbiddenException("Only the person who reported this ticket can reopen it")
    if ticket.status not in policy.REOPENABLE_STATUSES:
        raise ConflictException("Only resolved or closed tickets can be reopened")
    if policy.is_group_member(ticket):
        await group_service.detach(db, ticket, user)  # not fixed for this person: it goes back to a coordinator on its own
    old = ticket.status
    ticket.status = S.REOPENED.value
    ticket.reopened_at = _now()
    ticket.resolved_at = None
    _record_status(db, ticket, user, old, ticket.status, payload.reason)
    await group_service.propagate_status(db, ticket, ticket.status)
    await notification_service.reopened(db, ticket, user, payload.reason)
    await db.commit()
    return await _detail_after_commit(db, user, ticket.id)


async def confirm_resolution(db: AsyncSession, user: User, ticket_ref: str) -> TicketDetailRead:
    ticket = await get_ticket_for_user(db, user, ticket_ref, for_update=True)
    if ticket.created_by != user.id:
        raise ForbiddenException("Only the person who reported this ticket can confirm the fix")
    if not policy.can_confirm_resolution(user, ticket):
        raise ConflictException("Only resolved tickets can be confirmed")
    old = ticket.status
    ticket.status = S.CLOSED.value
    _record_status(db, ticket, user, old, ticket.status, "Confirmed fixed by the reporter")
    await notification_service.confirmed_fixed(db, ticket, user)
    await db.commit()
    return await _detail_after_commit(db, user, ticket.id)


async def withdraw_ticket(db: AsyncSession, user: User, ticket_ref: str, payload: TicketWithdrawRequest) -> TicketDetailRead:
    ticket = await get_ticket_for_user(db, user, ticket_ref, for_update=True)
    if ticket.created_by != user.id:
        raise ForbiddenException("Only the person who reported this ticket can cancel it")
    if not policy.can_withdraw(user, ticket):
        raise ConflictException("A ticket can only be cancelled before it is assigned to someone")
    if policy.is_group_member(ticket):
        await group_service.detach(db, ticket, user)
    else:
        await group_service.promote_new_main(db, ticket, user)
    old = ticket.status
    ticket.status = S.CLOSED.value
    reason = payload.reason.strip() if payload.reason else ""
    _record_status(db, ticket, user, old, ticket.status, f"Cancelled by the reporter: {reason}" if reason else "Cancelled by the reporter")
    await db.commit()
    return await _detail_after_commit(db, user, ticket.id)


async def submit_feedback(db: AsyncSession, user: User, ticket_ref: str, payload: FeedbackCreate) -> TicketDetailRead:
    ticket = await get_ticket_for_user(db, user, ticket_ref, for_update=True)
    if ticket.created_by != user.id:
        raise ForbiddenException("Only the person who reported this ticket can rate it")
    if not policy.can_give_feedback(user, ticket):
        raise ConflictException("You can only rate a ticket after it has been fixed")
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
    await notification_service.feedback_received(db, ticket, user, payload.rating, payload.comments)
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
    note = f"Closed automatically: no reply from the reporter within {days} days"
    closed = 0
    for ticket in tickets:
        if ticket.status != S.RESOLVED.value:
            continue  # already closed along with its main ticket
        ticket.status = S.CLOSED.value
        _record_status(db, ticket, None, S.RESOLVED.value, S.CLOSED.value, note)
        await group_service.propagate_status(db, ticket, S.CLOSED.value, note)
        closed += 1
    await db.commit()
    return closed
