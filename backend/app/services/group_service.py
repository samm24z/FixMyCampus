"""Grouping of repeat reports of one problem.

The oldest open ticket is the main ticket; later reports point at it through
``parent_ticket_id``. Members take on the main ticket's status, and the main ticket's
priority goes up as more people report (rules in ``app.core.permissions``).
"""

from typing import Optional
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import permissions as policy
from app.core.exceptions import ConflictException, ForbiddenException, NotFoundException
from app.models.enums import AuditActionEnum, TicketStatusEnum
from app.models.ticket import Ticket, TicketDuplicate
from app.models.user import User
from app.schemas.ticket_detail import TicketDetailRead
from app.services import ticket_service
from app.services.audit_service import record_audit

S = TicketStatusEnum

# History notes are read by reporters, so they never name other people's tickets.
GROUPED_NOTE = "Grouped with another report of the same problem"
FOLLOW_NOTE = "Updated together with the other reports of this problem"
SPLIT_NOTE = "Separated from the group by a coordinator"


def grouped_error(ticket: Ticket) -> ConflictException:
    main = ticket.parent.ticket_number if ticket.parent else "its main ticket"
    return ConflictException(f"This report is grouped with {main}; update that ticket instead")


async def _lock(db: AsyncSession, ticket_id: UUID) -> Optional[Ticket]:
    return await db.scalar(
        select(Ticket).where(Ticket.id == ticket_id).with_for_update().execution_options(populate_existing=True)
    )


async def _recount(db: AsyncSession, main: Ticket) -> None:
    await db.flush()
    members = await db.scalar(select(func.count()).select_from(Ticket).where(Ticket.parent_ticket_id == main.id))
    main.report_count = 1 + (members or 0)


async def find_link(db: AsyncSession, first: UUID, second: UUID) -> Optional[TicketDuplicate]:
    return await db.scalar(select(TicketDuplicate).where(or_(
        (TicketDuplicate.primary_ticket_id == first) & (TicketDuplicate.duplicate_ticket_id == second),
        (TicketDuplicate.primary_ticket_id == second) & (TicketDuplicate.duplicate_ticket_id == first),
    )))


def is_reviewed(link: TicketDuplicate) -> bool:
    """A coordinator (or the system) already decided on this pair."""
    return link.is_verified or link.verified_by is not None


async def apply_report_escalation(db: AsyncSession, main: Ticket) -> None:
    """Raise the main ticket's priority at 3 and again at 5 reports. Never lowers it."""
    target = policy.escalation_level_for(main.report_count)
    if target <= main.escalation_level:
        return
    raised = policy.raised_priority(main.priority, target - main.escalation_level)
    main.escalation_level = target
    if raised == main.priority:
        return
    old = {"priority": main.priority, "sla_deadline": main.sla_deadline.isoformat() if main.sla_deadline else None}
    main.priority = raised
    main.sla_deadline = await ticket_service._sla_deadline(db, main.category, raised, main.created_at)
    record_audit(
        db, user=None, action=AuditActionEnum.UPDATE, entity_type="ticket", entity_id=main.id, old_values=old,
        new_values={
            "priority": raised, "sla_deadline": main.sla_deadline.isoformat() if main.sla_deadline else None,
            "reason": f"Priority raised to {raised.title()}: reported by {main.report_count} people",
        },
    )


async def sync_member_priority(db: AsyncSession, main: Ticket) -> None:
    """Grouped reports show the group's priority and fix-by date, not the ones first given."""
    await db.flush()
    members = (await db.scalars(
        select(Ticket).where(Ticket.parent_ticket_id == main.id, Ticket.status != S.CLOSED.value)
        .with_for_update().execution_options(populate_existing=True)
    )).all()
    for member in members:
        member.priority, member.sla_deadline = main.priority, main.sla_deadline


async def join_group(
    db: AsyncSession, member: Ticket, main: Ticket, actor: Optional[User],
    *, link: Optional[TicketDuplicate] = None, similarity: float = 0.0,
) -> Ticket:
    """Group ``member`` under ``main`` (or under main's own main ticket). ``actor`` is None for automatic grouping."""
    root = await _lock(db, main.parent_ticket_id or main.id)
    assert root is not None
    if root.id == member.id:
        raise ConflictException("A report can't be grouped with itself")
    if member.parent_ticket_id == root.id:
        return root
    if member.parent_ticket_id is not None:
        raise ConflictException("This report is already grouped with another ticket. Split it from that group first")
    if root.status not in policy.GROUPABLE_STATUSES or member.status not in policy.GROUPABLE_STATUSES:
        raise ConflictException("Only tickets that are still open can be grouped")

    old_status = member.status
    for child in (await db.scalars(select(Ticket).where(Ticket.parent_ticket_id == member.id))).all():
        child.parent_ticket_id = root.id  # joining a group that has its own followers moves them too
    member.parent_ticket_id = root.id
    member.report_count = 1
    member.status = root.status
    ticket_service._record_status(db, member, actor, old_status, member.status, GROUPED_NOTE)

    link = link or await find_link(db, root.id, member.id)
    if link is None:
        link = TicketDuplicate(
            primary_ticket_id=root.id, duplicate_ticket_id=member.id, similarity_score=similarity,
            detected_by="AI_AUTO" if actor is None else "STAFF_MANUAL",
        )
        db.add(link)
    link.is_verified = True
    link.verified_by = actor.id if actor else None
    record_audit(
        db, user=actor, action=AuditActionEnum.UPDATE, entity_type="ticket", entity_id=member.id,
        old_values={"grouped_with": None},
        new_values={"grouped_with": root.ticket_number, "similarity": round(link.similarity_score, 3),
                    "by": "coordinator" if actor else "system"},
    )
    await _recount(db, root)
    await apply_report_escalation(db, root)
    await sync_member_priority(db, root)
    return root


async def detach(db: AsyncSession, member: Ticket, actor: Optional[User]) -> Optional[Ticket]:
    """Take ``member`` out of its group; the main ticket keeps its priority."""
    main = await _lock(db, member.parent_ticket_id) if member.parent_ticket_id else None
    member.parent_ticket_id = None
    if main is not None:
        await _recount(db, main)
        record_audit(
            db, user=actor, action=AuditActionEnum.UPDATE, entity_type="ticket", entity_id=member.id,
            old_values={"grouped_with": main.ticket_number}, new_values={"grouped_with": None},
        )
    return main


async def promote_new_main(db: AsyncSession, old_main: Ticket, actor: Optional[User]) -> None:
    """The main ticket is being cancelled: the oldest open follower takes over the group."""
    await db.flush()
    members = (await db.scalars(
        select(Ticket).where(Ticket.parent_ticket_id == old_main.id).order_by(Ticket.created_at, Ticket.id)
        .with_for_update().execution_options(populate_existing=True)
    )).all()
    successor = next((m for m in members if m.status != S.CLOSED.value), None)
    if successor is None:
        return
    for member in members:
        member.parent_ticket_id = None if member is successor else successor.id
    for field in ("priority", "escalation_level", "sla_deadline", "sla_warned_at", "sla_breached_at",
                  "assigned_to", "confirmed_department_id", "confirmed_category"):
        setattr(successor, field, getattr(old_main, field))
    old_main.report_count = 1
    await _recount(db, successor)
    record_audit(
        db, user=actor, action=AuditActionEnum.UPDATE, entity_type="ticket", entity_id=successor.id,
        old_values={"grouped_with": old_main.ticket_number}, new_values={"grouped_with": None, "now_main_ticket": True},
    )


async def propagate_status(db: AsyncSession, main: Ticket, new: str, remarks: Optional[str] = None) -> None:
    """Copy a status change of ``main`` onto the reports grouped under it that are not closed."""
    await db.flush()  # the query below must see (and must not overwrite) changes made earlier in this transaction
    members = (await db.scalars(
        select(Ticket).where(Ticket.parent_ticket_id == main.id, Ticket.status.notin_([S.CLOSED.value, new]))
        .with_for_update().execution_options(populate_existing=True)
    )).all()
    now = ticket_service._now()
    for member in members:
        old = member.status
        member.status = new
        if new == S.RESOLVED.value:
            member.resolved_at = main.resolved_at or now
        elif new == S.REOPENED.value:
            member.reopened_at, member.resolved_at = now, None
        elif old == S.RESOLVED.value:
            member.resolved_at = None
        ticket_service._record_status(db, member, None, old, new, remarks or FOLLOW_NOTE)


def _require_reviewer(user: User) -> None:
    if not policy.can_review_suggestions(user):
        raise ForbiddenException("Only coordinators and admins can do this")


async def split_from_group(db: AsyncSession, user: User, ticket_ref: str) -> TicketDetailRead:
    ticket = await ticket_service.get_ticket_for_user(db, user, ticket_ref, for_update=True)
    _require_reviewer(user)
    if not policy.is_group_member(ticket):
        raise ConflictException("This report isn't grouped with another one")
    if not policy.can_split_group(user, ticket):
        raise ConflictException("Closed tickets can't be changed")
    main_id = ticket.parent_ticket_id
    await detach(db, ticket, user)
    link = await find_link(db, main_id, ticket.id)
    if link is not None:
        link.is_verified, link.verified_by = False, user.id  # reviewed: not the same problem
    old = ticket.status
    ticket.status = S.UNDER_REVIEW.value
    ticket.resolved_at = None
    ticket_service._record_status(db, ticket, user, old, ticket.status, SPLIT_NOTE)
    await db.commit()
    return await ticket_service._detail_after_commit(db, user, ticket.id)


async def _load_pair(db: AsyncSession, user: User, ticket_ref: str, other_ref: str) -> tuple[Ticket, Ticket, TicketDuplicate]:
    ticket = await ticket_service.get_ticket_for_user(db, user, ticket_ref, for_update=True)
    _require_reviewer(user)
    other = await ticket_service.get_ticket_for_user(db, user, other_ref, for_update=True)
    link = await find_link(db, ticket.id, other.id)
    if link is None:
        raise NotFoundException("Possible duplicate", other_ref)
    return ticket, other, link


async def group_duplicate(db: AsyncSession, user: User, ticket_ref: str, other_ref: str) -> TicketDetailRead:
    """A coordinator confirms two reports are the same problem; the newer one joins the older."""
    ticket, other, link = await _load_pair(db, user, ticket_ref, other_ref)
    if link.is_verified:
        raise ConflictException("These reports are already grouped")
    member, main = (ticket, other) if link.duplicate_ticket_id == ticket.id else (other, ticket)
    await join_group(db, member, main, user, link=link)
    await db.commit()
    return await ticket_service._detail_after_commit(db, user, ticket.id)


async def dismiss_duplicate(db: AsyncSession, user: User, ticket_ref: str, other_ref: str) -> TicketDetailRead:
    """A coordinator says two reports are not the same problem. The decision is kept so it isn't suggested again."""
    ticket, other, link = await _load_pair(db, user, ticket_ref, other_ref)
    if link.is_verified:
        raise ConflictException("These reports are already grouped")
    link.verified_by = user.id
    record_audit(
        db, user=user, action=AuditActionEnum.UPDATE, entity_type="ticket", entity_id=ticket.id,
        new_values={"not_the_same_as": other.ticket_number},
    )
    await db.commit()
    return await ticket_service._detail_after_commit(db, user, ticket.id)
