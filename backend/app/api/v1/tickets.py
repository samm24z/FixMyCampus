"""Ticket endpoints. Business rules live in ``app.services.ticket_service``."""

import uuid
from typing import Annotated, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.enums import PriorityEnum, TicketStatusEnum
from app.models.user import User
from app.schemas.comment import CommentCreate
from app.schemas.feedback import FeedbackCreate
from app.schemas.common import PaginatedResponse
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
    CheckDuplicatesRequest,
    DashboardSummary,
    DuplicateCandidateResult,
    DuplicateClusterItem,
    MergeTicketsRequest,
    TicketAssignmentRequest,
    TicketDetailRead,
)
from app.services import deduplication_service, group_service, suggestion_service, ticket_service


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
        items=[ticket_service.to_read(ticket, current_user) for ticket in tickets],
        total=total, page=page, page_size=page_size, total_pages=total_pages,
    )


@router.post("", response_model=TicketDetailRead, status_code=status.HTTP_201_CREATED)
async def create_ticket(
    payload: TicketCreate, background_tasks: BackgroundTasks, db: DbSession, current_user: CurrentUser
) -> TicketDetailRead:
    detail = await ticket_service.create_ticket(db, current_user, payload)
    background_tasks.add_task(suggestion_service.analyze_ticket, detail.id)  # after the response: never delays the student
    return detail


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


@router.post("/{ticket_ref}/confirm", response_model=TicketDetailRead)
async def confirm_resolution(ticket_ref: str, db: DbSession, current_user: CurrentUser) -> TicketDetailRead:
    return await ticket_service.confirm_resolution(db, current_user, ticket_ref)


@router.post("/{ticket_ref}/withdraw", response_model=TicketDetailRead)
async def withdraw_ticket(
    ticket_ref: str, payload: TicketWithdrawRequest, db: DbSession, current_user: CurrentUser
) -> TicketDetailRead:
    return await ticket_service.withdraw_ticket(db, current_user, ticket_ref, payload)


@router.post("/{ticket_ref}/feedback", response_model=TicketDetailRead)
async def submit_feedback(
    ticket_ref: str, payload: FeedbackCreate, db: DbSession, current_user: CurrentUser
) -> TicketDetailRead:
    return await ticket_service.submit_feedback(db, current_user, ticket_ref, payload)


@router.post("/{ticket_ref}/suggestions/accept", response_model=TicketDetailRead)
async def accept_suggestions(ticket_ref: str, db: DbSession, current_user: CurrentUser) -> TicketDetailRead:
    return await suggestion_service.accept_suggestions(db, current_user, ticket_ref)


@router.post("/{ticket_ref}/suggestions/refresh", response_model=TicketDetailRead)
async def refresh_suggestions(
    ticket_ref: str, background_tasks: BackgroundTasks, db: DbSession, current_user: CurrentUser
) -> TicketDetailRead:
    detail = await suggestion_service.request_refresh(db, current_user, ticket_ref)
    background_tasks.add_task(suggestion_service.analyze_ticket, detail.id)
    return detail


@router.post("/{ticket_ref}/duplicates/{other_ref}/group", response_model=TicketDetailRead)
async def group_duplicate(ticket_ref: str, other_ref: str, db: DbSession, current_user: CurrentUser) -> TicketDetailRead:
    return await group_service.group_duplicate(db, current_user, ticket_ref, other_ref)


@router.post("/{ticket_ref}/duplicates/{other_ref}/dismiss", response_model=TicketDetailRead)
async def dismiss_duplicate(ticket_ref: str, other_ref: str, db: DbSession, current_user: CurrentUser) -> TicketDetailRead:
    return await group_service.dismiss_duplicate(db, current_user, ticket_ref, other_ref)


@router.post("/{ticket_ref}/group/split", response_model=TicketDetailRead)
async def split_from_group(ticket_ref: str, db: DbSession, current_user: CurrentUser) -> TicketDetailRead:
    return await group_service.split_from_group(db, current_user, ticket_ref)


@router.post("/check-duplicates", response_model=list[DuplicateCandidateResult])
async def check_duplicates(
    payload: CheckDuplicatesRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> list[DuplicateCandidateResult]:
    """Check for active duplicate complaints matching incoming title/description/location."""
    exclude_id = None
    if payload.exclude_ticket_ref:
        try:
            exclude_ticket = await ticket_service.get_ticket_by_number(db, payload.exclude_ticket_ref)
            if exclude_ticket:
                exclude_id = exclude_ticket.id
        except Exception:
            pass
    return await deduplication_service.find_duplicate_candidates(
        db,
        title=payload.title,
        description=payload.description,
        location=payload.location,
        category=payload.category,
        exclude_ticket_id=exclude_id,
    )


@router.get("/duplicates/clusters", response_model=list[DuplicateClusterItem])
async def get_duplicate_clusters(
    db: DbSession,
    current_user: CurrentUser,
) -> list[DuplicateClusterItem]:
    """Retrieve consolidated issue clusters where multiple students reported similar grievances across blocks."""
    return await deduplication_service.get_duplicate_clusters(db)


@router.post("/{ticket_ref}/merge", response_model=TicketDetailRead)
async def merge_tickets(
    ticket_ref: str,
    payload: MergeTicketsRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> TicketDetailRead:
    """Merge duplicate student complaints into this primary master ticket."""
    return await deduplication_service.merge_tickets(
        db,
        current_user,
        primary_ref=ticket_ref,
        duplicate_refs=payload.duplicate_ticket_refs,
        notes=payload.notes,
    )


@router.post("/{ticket_ref}/unmerge/{duplicate_ref}", response_model=TicketDetailRead)
async def unmerge_ticket(
    ticket_ref: str,
    duplicate_ref: str,
    db: DbSession,
    current_user: CurrentUser,
) -> TicketDetailRead:
    """Detach a previously merged duplicate ticket and restore it to independent status."""
    return await deduplication_service.unmerge_ticket(
        db,
        current_user,
        primary_ref=ticket_ref,
        duplicate_ref=duplicate_ref,
    )


@router.post("/{ticket_ref}/dismiss-duplicate/{duplicate_ref}", response_model=TicketDetailRead)
async def dismiss_duplicate_candidate(
    ticket_ref: str,
    duplicate_ref: str,
    db: DbSession,
    current_user: CurrentUser,
) -> TicketDetailRead:
    """Dismiss a duplicate suggestion and mark complaints as unrelated."""
    return await deduplication_service.dismiss_duplicate_candidate(
        db,
        current_user,
        primary_ref=ticket_ref,
        duplicate_ref=duplicate_ref,
    )
