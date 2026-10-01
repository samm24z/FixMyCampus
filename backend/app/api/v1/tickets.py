"""Ticket endpoints. Business rules live in ``app.services.ticket_service``."""

import uuid
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.enums import PriorityEnum, TicketStatusEnum
from app.models.user import User
from app.schemas.comment import CommentCreate
from app.schemas.common import PaginatedResponse
from app.schemas.ticket import (
    TicketCreate,
    TicketFilter,
    TicketRead,
    TicketReopenRequest,
    TicketStatusChange,
    TicketTriageUpdate,
)
from app.schemas.ticket_detail import DashboardSummary, TicketAssignmentRequest, TicketDetailRead
from app.services import ticket_service


router = APIRouter(prefix="/tickets")

DbSession = Annotated[AsyncSession, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]


@router.get("/summary", response_model=DashboardSummary)
async def dashboard_summary(db: DbSession, current_user: CurrentUser) -> DashboardSummary:
    return await ticket_service.dashboard_summary(db, current_user)


@router.get("", response_model=PaginatedResponse[TicketRead])
async def list_tickets(
    db: DbSession,
    current_user: CurrentUser,
    search: Optional[str] = Query(default=None, max_length=100),
    ticket_status: Optional[TicketStatusEnum] = Query(default=None, alias="status"),
    category: Optional[str] = Query(default=None, max_length=100),
    priority: Optional[PriorityEnum] = Query(default=None),
    department_id: Optional[uuid.UUID] = Query(default=None),
    assigned_to: Optional[uuid.UUID] = Query(default=None),
    mine: bool = Query(default=False, description="Only tickets I reported"),
    open_only: bool = Query(default=False, description="Exclude RESOLVED and CLOSED tickets"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> PaginatedResponse[TicketRead]:
    filters = TicketFilter(
        status=ticket_status, category=category, priority=priority, department_id=department_id,
        assigned_to=assigned_to, search=search, mine=mine, open_only=open_only,
    )
    tickets, total, total_pages = await ticket_service.list_tickets(db, current_user, filters, page, page_size)
    return PaginatedResponse[TicketRead](
        items=[TicketRead.model_validate(ticket) for ticket in tickets],
        total=total, page=page, page_size=page_size, total_pages=total_pages,
    )


@router.post("", response_model=TicketDetailRead, status_code=status.HTTP_201_CREATED)
async def create_ticket(payload: TicketCreate, db: DbSession, current_user: CurrentUser) -> TicketDetailRead:
    return await ticket_service.create_ticket(db, current_user, payload)


@router.get("/{ticket_ref}", response_model=TicketDetailRead)
async def read_ticket(ticket_ref: str, db: DbSession, current_user: CurrentUser) -> TicketDetailRead:
    ticket = await ticket_service.get_ticket_for_user(db, current_user, ticket_ref)
    return ticket_service.build_detail(ticket, current_user)


@router.patch("/{ticket_ref}", response_model=TicketDetailRead)
async def update_triage(
    ticket_ref: str, payload: TicketTriageUpdate, db: DbSession, current_user: CurrentUser
) -> TicketDetailRead:
    """Coordinator/admin edits to category, priority, department, or SLA deadline."""
    return await ticket_service.update_triage(db, current_user, ticket_ref, payload)


@router.post("/{ticket_ref}/status", response_model=TicketDetailRead)
async def change_status(
    ticket_ref: str, payload: TicketStatusChange, db: DbSession, current_user: CurrentUser
) -> TicketDetailRead:
    return await ticket_service.change_status(db, current_user, ticket_ref, payload)


@router.post("/{ticket_ref}/assign", response_model=TicketDetailRead)
async def assign_ticket(
    ticket_ref: str, payload: TicketAssignmentRequest, db: DbSession, current_user: CurrentUser
) -> TicketDetailRead:
    return await ticket_service.assign_ticket(db, current_user, ticket_ref, payload)


@router.post("/{ticket_ref}/comments", response_model=TicketDetailRead, status_code=status.HTTP_201_CREATED)
async def add_comment(
    ticket_ref: str, payload: CommentCreate, db: DbSession, current_user: CurrentUser
) -> TicketDetailRead:
    return await ticket_service.add_comment(db, current_user, ticket_ref, payload)


@router.post("/{ticket_ref}/reopen", response_model=TicketDetailRead)
async def reopen_ticket(
    ticket_ref: str, payload: TicketReopenRequest, db: DbSession, current_user: CurrentUser
) -> TicketDetailRead:
    return await ticket_service.reopen_ticket(db, current_user, ticket_ref, payload)
