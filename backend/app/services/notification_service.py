"""In-app notifications.

Rows are staged in the caller's transaction, like audit rows, so a change that rolls back never
notifies anyone. Nobody is told about their own action, and a notification only ever points at a
ticket its recipient can already see; the text never quotes staff-only notes to a reporter.
"""

import math
from datetime import datetime, timedelta, timezone
from typing import Iterable, Optional
from uuid import UUID

from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import permissions as policy
from app.core.config import settings
from app.models.enums import NotificationTypeEnum as N, RoleEnum, TicketStatusEnum as S
from app.models.notification import Notification
from app.models.ticket import Ticket
from app.models.user import User
from app.schemas.notification import NotificationRead

SNIPPET = 140

# What a reporter reads when their ticket moves: "TICK-2026-1001 is being worked on".
STATUS_TEXT = {
    S.NEW.value: "is waiting to be reviewed",
    S.UNDER_REVIEW.value: "is being reviewed",
    S.ASSIGNED.value: "has been given to a staff member",
    S.IN_PROGRESS.value: "is being worked on",
    S.RESOLVED.value: "has been marked as fixed",
    S.REOPENED.value: "has been reopened",
    S.CLOSED.value: "has been closed",
}


def _snippet(text: str) -> str:
    text = " ".join(text.split())
    return text if len(text) <= SNIPPET else text[: SNIPPET - 1].rstrip() + "…"


def _stage(db: AsyncSession, user_id: UUID, ticket: Ticket, kind: N, title: str, message: str) -> None:
    db.add(Notification(user_id=user_id, ticket_id=ticket.id, type=kind.value, title=title[:200], message=message))


def notify(
    db: AsyncSession, recipients: Iterable[Optional[User]], ticket: Ticket, kind: N, title: str, message: str,
    *, actor: Optional[User] = None,
) -> int:
    """Stage one notification per distinct, active recipient who may see ``ticket``, except ``actor``."""
    seen: set[UUID] = set()
    for user in recipients:
        if user is None or user.id in seen or (actor is not None and user.id == actor.id):
            continue
        seen.add(user.id)
        if user.is_active and policy.can_view_ticket(user, ticket):
            _stage(db, user.id, ticket, kind, title, message)
    return len(seen)


async def coordinators(db: AsyncSession) -> list[User]:
    return list((await db.scalars(
        select(User).where(User.role == RoleEnum.COORDINATOR.value, User.is_active.is_(True))
    )).all())


async def _user(db: AsyncSession, user_id: Optional[UUID]) -> Optional[User]:
    return await db.get(User, user_id) if user_id else None


# ------------------------------------------------------------------ events

def status_changed(
    db: AsyncSession, ticket: Ticket, actor: Optional[User], old: Optional[str], new: str, remarks: Optional[str] = None,
) -> None:
    """Tell the reporter. Called from every status change, including group follow-ons and auto-close.

    This runs inside synchronous code, so it uses the reporter's id directly: a reporter can always
    see their own ticket, which is the visibility rule ``notify`` would otherwise check.
    """
    if old is None or old == new or (actor is not None and actor.id == ticket.created_by):
        return
    if new == S.RESOLVED.value:
        message = f"{ticket.title}. Please confirm it's fixed, or reopen it if it isn't."
        kind = N.FEEDBACK_REQUEST
    else:
        message = ticket.title
        kind = N.STATUS_CHANGED
    if remarks and remarks.strip() and new in (S.RESOLVED.value, S.CLOSED.value):
        message = message.rstrip(".") + f". Note: {_snippet(remarks)}"
    _stage(db, ticket.created_by, ticket, kind, f"{ticket.ticket_number} {STATUS_TEXT.get(new, 'was updated')}", message)


async def ticket_filed(db: AsyncSession, ticket: Ticket, actor: User) -> None:
    notify(
        db, await coordinators(db), ticket, N.TICKET_CREATED,
        f"New report {ticket.ticket_number}", f"{ticket.title} ({ticket.location})", actor=actor,
    )


def assigned(db: AsyncSession, ticket: Ticket, assignee: User, actor: User) -> None:
    notify(
        db, [assignee], ticket, N.ASSIGNED,
        f"{ticket.ticket_number} was given to you", f"{ticket.title} ({ticket.location})", actor=actor,
    )


async def reopened(db: AsyncSession, ticket: Ticket, actor: User, reason: Optional[str]) -> None:
    """The work wasn't finished for the reporter: tell whoever did it, or the coordinators."""
    assignee = await _user(db, ticket.assigned_to)
    recipients = [assignee] if assignee and assignee.is_active else await coordinators(db)
    message = ticket.title + (f". Reason: {_snippet(reason)}" if reason and reason.strip() else "")
    notify(db, recipients, ticket, N.STATUS_CHANGED, f"{ticket.ticket_number} was reopened by the reporter", message, actor=actor)


async def confirmed_fixed(db: AsyncSession, ticket: Ticket, actor: User) -> None:
    notify(
        db, [await _user(db, ticket.assigned_to)], ticket, N.STATUS_CHANGED,
        f"{ticket.ticket_number} was confirmed fixed", ticket.title, actor=actor,
    )


async def comment_added(db: AsyncSession, ticket: Ticket, actor: User, content: str, internal: bool) -> None:
    """Public comments reach the reporter and the assignee; staff-only notes reach the assignee only."""
    recipients = [await _user(db, ticket.assigned_to)]
    if not internal:
        recipients.append(await _user(db, ticket.created_by))
    what = "staff note" if internal else "comment"
    notify(
        db, recipients, ticket, N.COMMENT_ADDED,
        f"New {what} on {ticket.ticket_number}", f"{actor.full_name}: {_snippet(content)}", actor=actor,
    )


async def feedback_received(db: AsyncSession, ticket: Ticket, actor: User, rating: int, comments: Optional[str]) -> None:
    message = ticket.title + (f". “{_snippet(comments)}”" if comments and comments.strip() else "")
    notify(
        db, [await _user(db, ticket.assigned_to)], ticket, N.FEEDBACK_RECEIVED,
        f"{ticket.ticket_number} was rated {rating}/5", message, actor=actor,
    )


# ------------------------------------------------------------------ reading

def _visible(user: User):
    """Only notifications about tickets the person can still see (e.g. not after being taken off one)."""
    return (Notification.user_id == user.id) & or_(Notification.ticket_id.is_(None), policy.ticket_visibility_filter(user))


def _base(user: User):
    return select(Notification).outerjoin(Ticket, Ticket.id == Notification.ticket_id).where(_visible(user))


async def list_for_user(
    db: AsyncSession, user: User, *, unread_only: bool, page: int, page_size: int,
) -> tuple[list[NotificationRead], int, int]:
    query = _base(user)
    if unread_only:
        query = query.where(Notification.is_read.is_(False))
    total = await db.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = await db.execute(
        query.add_columns(Ticket.ticket_number)
        .order_by(Notification.created_at.desc(), Notification.id)
        .offset((page - 1) * page_size).limit(page_size)
    )
    items = [
        NotificationRead(
            id=n.id, ticket_id=n.ticket_id, ticket_number=number, title=n.title, message=n.message,
            type=n.type, is_read=n.is_read, created_at=n.created_at,
        )
        for n, number in rows.all()
    ]
    return items, total, math.ceil(total / page_size) if total else 0


async def unread_count(db: AsyncSession, user: User) -> int:
    query = _base(user).where(Notification.is_read.is_(False))
    return await db.scalar(select(func.count()).select_from(query.subquery())) or 0


async def mark_read(db: AsyncSession, user: User, ids: list[UUID], everything: bool) -> int:
    """Mark the caller's own notifications as read (others' ids are ignored) and return what's left unread."""
    query = update(Notification).where(Notification.user_id == user.id, Notification.is_read.is_(False))
    if not everything:
        query = query.where(Notification.id.in_(ids))
    await db.execute(query.values(is_read=True))
    await db.commit()
    return await unread_count(db, user)


async def purge_old(db: AsyncSession, now: Optional[datetime] = None) -> int:
    """Delete read notifications older than NOTIFICATION_RETENTION_DAYS."""
    cutoff = (now or datetime.now(timezone.utc)) - timedelta(days=settings.NOTIFICATION_RETENTION_DAYS)
    result = await db.execute(delete(Notification).where(Notification.is_read.is_(True), Notification.created_at < cutoff))
    await db.commit()
    return result.rowcount or 0
