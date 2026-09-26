"""Ticket and related entities Repositories."""

import uuid
from typing import Optional, Sequence
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.ticket import (
    Ticket,
    TicketAssignment,
    TicketAttachment,
    TicketComment,
    TicketDuplicate,
    TicketFeedback,
    TicketStatusHistory,
)
from app.repositories.base import BaseRepository
from app.schemas.ticket import TicketFilter


class TicketRepository(BaseRepository[Ticket]):
    """Ticket data access."""

    def __init__(self):
        super().__init__(Ticket)

    async def get_by_ticket_number(self, db: AsyncSession, ticket_number: str) -> Optional[Ticket]:
        result = await db.execute(select(Ticket).where(Ticket.ticket_number == ticket_number))
        return result.scalars().first()

    async def get_filtered(
        self, db: AsyncSession, *, filter_params: TicketFilter, skip: int = 0, limit: int = 20
    ) -> Sequence[Ticket]:
        query = select(Ticket)
        
        if filter_params.status:
            query = query.where(Ticket.status == filter_params.status)
        if filter_params.category:
            query = query.where(Ticket.category == filter_params.category)
        if filter_params.priority:
            query = query.where(Ticket.priority == filter_params.priority)
        if filter_params.department_id:
            query = query.where(Ticket.confirmed_department_id == filter_params.department_id)
        if filter_params.assigned_to:
            query = query.where(Ticket.assigned_to == filter_params.assigned_to)
        if filter_params.created_by:
            query = query.where(Ticket.created_by == filter_params.created_by)
        if filter_params.search:
            search_pattern = f"%{filter_params.search}%"
            query = query.where(
                or_(
                    Ticket.title.ilike(search_pattern),
                    Ticket.description.ilike(search_pattern),
                    Ticket.location.ilike(search_pattern),
                    Ticket.ticket_number.ilike(search_pattern),
                )
            )

        query = query.order_by(Ticket.created_at.desc()).offset(skip).limit(limit)
        result = await db.execute(query)
        return result.scalars().all()

    async def count_filtered(self, db: AsyncSession, *, filter_params: TicketFilter) -> int:
        query = select(func.count()).select_from(Ticket)
        
        if filter_params.status:
            query = query.where(Ticket.status == filter_params.status)
        if filter_params.category:
            query = query.where(Ticket.category == filter_params.category)
        if filter_params.priority:
            query = query.where(Ticket.priority == filter_params.priority)
        if filter_params.department_id:
            query = query.where(Ticket.confirmed_department_id == filter_params.department_id)
        if filter_params.assigned_to:
            query = query.where(Ticket.assigned_to == filter_params.assigned_to)
        if filter_params.created_by:
            query = query.where(Ticket.created_by == filter_params.created_by)
        if filter_params.search:
            search_pattern = f"%{filter_params.search}%"
            query = query.where(
                or_(
                    Ticket.title.ilike(search_pattern),
                    Ticket.description.ilike(search_pattern),
                    Ticket.location.ilike(search_pattern),
                    Ticket.ticket_number.ilike(search_pattern),
                )
            )

        result = await db.execute(query)
        return result.scalar() or 0


class TicketCommentRepository(BaseRepository[TicketComment]):
    def __init__(self):
        super().__init__(TicketComment)

    async def get_by_ticket(self, db: AsyncSession, ticket_id: uuid.UUID) -> Sequence[TicketComment]:
        result = await db.execute(
            select(TicketComment).where(TicketComment.ticket_id == ticket_id).order_by(TicketComment.created_at.asc())
        )
        return result.scalars().all()


class TicketAttachmentRepository(BaseRepository[TicketAttachment]):
    def __init__(self):
        super().__init__(TicketAttachment)

    async def get_by_ticket(self, db: AsyncSession, ticket_id: uuid.UUID) -> Sequence[TicketAttachment]:
        result = await db.execute(select(TicketAttachment).where(TicketAttachment.ticket_id == ticket_id))
        return result.scalars().all()


class TicketStatusHistoryRepository(BaseRepository[TicketStatusHistory]):
    def __init__(self):
        super().__init__(TicketStatusHistory)

    async def get_by_ticket(self, db: AsyncSession, ticket_id: uuid.UUID) -> Sequence[TicketStatusHistory]:
        result = await db.execute(
            select(TicketStatusHistory)
            .where(TicketStatusHistory.ticket_id == ticket_id)
            .order_by(TicketStatusHistory.created_at.desc())
        )
        return result.scalars().all()


class TicketAssignmentRepository(BaseRepository[TicketAssignment]):
    def __init__(self):
        super().__init__(TicketAssignment)

    async def get_by_ticket(self, db: AsyncSession, ticket_id: uuid.UUID) -> Sequence[TicketAssignment]:
        result = await db.execute(
            select(TicketAssignment)
            .where(TicketAssignment.ticket_id == ticket_id)
            .order_by(TicketAssignment.created_at.desc())
        )
        return result.scalars().all()


class TicketFeedbackRepository(BaseRepository[TicketFeedback]):
    def __init__(self):
        super().__init__(TicketFeedback)

    async def get_by_ticket(self, db: AsyncSession, ticket_id: uuid.UUID) -> Optional[TicketFeedback]:
        result = await db.execute(select(TicketFeedback).where(TicketFeedback.ticket_id == ticket_id))
        return result.scalars().first()


class TicketDuplicateRepository(BaseRepository[TicketDuplicate]):
    def __init__(self):
        super().__init__(TicketDuplicate)

    async def get_duplicates_for_ticket(
        self, db: AsyncSession, ticket_id: uuid.UUID
    ) -> Sequence[TicketDuplicate]:
        result = await db.execute(
            select(TicketDuplicate).where(
                or_(
                    TicketDuplicate.primary_ticket_id == ticket_id,
                    TicketDuplicate.duplicate_ticket_id == ticket_id,
                )
            )
        )
        return result.scalars().all()


ticket_repo = TicketRepository()
comment_repo = TicketCommentRepository()
attachment_repo = TicketAttachmentRepository()
status_history_repo = TicketStatusHistoryRepository()
assignment_repo = TicketAssignmentRepository()
feedback_repo = TicketFeedbackRepository()
duplicate_repo = TicketDuplicateRepository()
