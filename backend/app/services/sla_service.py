"""The "due soon" and "overdue" alerts for open tickets, run by the background loop.

A ticket is warned once its deadline is closer than its SLA rule allows (the rule's
``escalation_threshold_hours`` counted from the start of the target window), and flagged once the
deadline passes. Each alert goes out once per deadline: changing the deadline resets both markers.
Only main tickets are checked; reports grouped under them share their deadline.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core import permissions as policy
from app.models.enums import AuditActionEnum, NotificationTypeEnum as N
from app.models.sla import SLARule
from app.models.ticket import Ticket
from app.services import notification_service
from app.services.audit_service import record_audit

logger = logging.getLogger("app.sla")


def _hours(delta: timedelta) -> str:
    hours = max(1, round(delta.total_seconds() / 3600))
    return "about 1 hour" if hours == 1 else f"about {hours} hours"


async def _warning_windows(db: AsyncSession) -> dict[tuple[str, str], timedelta]:
    """(category, priority) -> how long before the deadline the warning goes out.

    Uses the same rule ``ticket_service._sla_deadline`` picks: the oldest active one.
    """
    windows: dict[tuple[str, str], timedelta] = {}
    for rule in (await db.scalars(select(SLARule).where(SLARule.is_active.is_(True)).order_by(SLARule.created_at))).all():
        key = (rule.category, rule.priority)
        if key not in windows and rule.target_resolution_hours > rule.escalation_threshold_hours:
            windows[key] = timedelta(hours=rule.target_resolution_hours - rule.escalation_threshold_hours)
    return windows


async def check_deadlines(db: AsyncSession, now: Optional[datetime] = None) -> tuple[int, int]:
    """Send due-soon and overdue alerts. Returns (warned, breached)."""
    now = now or datetime.now(timezone.utc)
    tickets = (await db.scalars(
        select(Ticket)
        .where(
            Ticket.status.notin_(policy.DONE_STATUSES), Ticket.parent_ticket_id.is_(None),
            Ticket.sla_deadline.is_not(None), Ticket.sla_breached_at.is_(None),
        )
        .options(selectinload(Ticket.assignee))
        .with_for_update(of=Ticket, skip_locked=True)  # two workers never send the same alert
    )).all()
    if not tickets:
        await db.commit()
        return 0, 0
    windows = await _warning_windows(db)
    leads = await notification_service.coordinators(db)
    warned = breached = 0
    for ticket in tickets:
        assignee = ticket.assignee if ticket.assignee and ticket.assignee.is_active else None
        if ticket.sla_deadline <= now:
            ticket.sla_breached_at = now
            notification_service.notify(
                db, [assignee, *leads], ticket, N.SLA_BREACH, f"{ticket.ticket_number} is overdue",
                f"{ticket.title}. It was due to be fixed {_hours(now - ticket.sla_deadline)} ago.",
            )
            record_audit(
                db, user=None, action=AuditActionEnum.SLA_BREACH, entity_type="ticket", entity_id=ticket.id,
                new_values={"sla_deadline": ticket.sla_deadline.isoformat(), "assigned_to": str(ticket.assigned_to) if ticket.assigned_to else None},
            )
            breached += 1
            continue
        window = windows.get((ticket.category, ticket.priority))
        if ticket.sla_warned_at is None and window is not None and ticket.sla_deadline - window <= now:
            ticket.sla_warned_at = now
            notification_service.notify(
                db, [assignee] if assignee else leads, ticket, N.SLA_WARNING, f"{ticket.ticket_number} is due soon",
                f"{ticket.title}. It should be fixed within {_hours(ticket.sla_deadline - now)}.",
            )
            warned += 1
    await db.commit()
    return warned, breached
