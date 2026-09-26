"""Review-1 ticket, comment, assignment, and status endpoints."""

from datetime import datetime, timezone
from typing import Annotated, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.department import Department
from app.models.enums import RoleEnum, TicketStatusEnum
from app.models.ticket import Ticket, TicketAssignment, TicketComment, TicketStatusHistory
from app.models.user import User
from app.schemas.comment import CommentRead
from app.schemas.assignment import AssignmentRead
from app.schemas.status_history import StatusHistoryRead
from app.schemas.ticket import TicketCreate, TicketRead, TicketUpdate
from app.schemas.ticket_detail import (
    DashboardSummary,
    TicketAssignmentRequest,
    TicketCommentRequest,
    TicketDetailRead,
)


router = APIRouter(prefix="/tickets")
STAFF_ROLES = {RoleEnum.STAFF.value, RoleEnum.COORDINATOR.value, RoleEnum.ADMIN.value}
TRIAGE_ROLES = {RoleEnum.COORDINATOR.value, RoleEnum.ADMIN.value}


def is_admin(user: User) -> bool:
    return user.role == RoleEnum.ADMIN.value


def can_view_ticket(user: User, ticket: Ticket) -> bool:
    if is_admin(user):
        return True
    if user.role in {RoleEnum.STUDENT.value, RoleEnum.FACULTY.value}:
        return ticket.created_by == user.id
    if user.role == RoleEnum.STAFF.value:
        return ticket.assigned_to == user.id or (
            user.department_id is not None and ticket.confirmed_department_id == user.department_id
        )
    if user.role == RoleEnum.COORDINATOR.value:
        return ticket.confirmed_department_id is None or (
            user.department_id is not None and ticket.confirmed_department_id == user.department_id
        )
    return False


def can_comment(user: User, ticket: Ticket) -> bool:
    return can_view_ticket(user, ticket) or (
        user.role in STAFF_ROLES and ticket.assigned_to == user.id
    )


async def get_ticket(db: AsyncSession, ticket_ref: str) -> Ticket:
    query = select(Ticket).options(
        selectinload(Ticket.creator),
        selectinload(Ticket.assignee),
        selectinload(Ticket.confirmed_department),
        selectinload(Ticket.comments),
        selectinload(Ticket.status_history),
        selectinload(Ticket.assignments),
    )
    try:
        ticket_id = UUID(ticket_ref)
        query = query.where(Ticket.id == ticket_id)
    except ValueError:
        query = query.where(Ticket.ticket_number == ticket_ref)
    ticket = await db.scalar(query)
    if ticket is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")
    return ticket


def ticket_number(number: int) -> str:
    return f"TICK-{datetime.now(timezone.utc).year}-{number:04d}"


def detail_response(ticket: Ticket) -> TicketDetailRead:
    return TicketDetailRead(
        **TicketRead.model_validate(ticket).model_dump(),
        created_by_name=ticket.creator.full_name,
        assigned_to_name=ticket.assignee.full_name if ticket.assignee else None,
        department_name=ticket.confirmed_department.name if ticket.confirmed_department else None,
        comments=[CommentRead.model_validate(comment) for comment in sorted(ticket.comments, key=lambda item: item.created_at)],
        history=[StatusHistoryRead.model_validate(history) for history in sorted(ticket.status_history, key=lambda item: item.created_at)],
        assignments=[AssignmentRead.model_validate(assignment) for assignment in sorted(ticket.assignments, key=lambda item: item.created_at)],
    )


@router.get("/summary", response_model=DashboardSummary)
async def dashboard_summary(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> DashboardSummary:
    tickets = await list_visible_tickets(db, current_user)
    resolved = sum(ticket.status in {TicketStatusEnum.RESOLVED.value, TicketStatusEnum.CLOSED.value} for ticket in tickets)
    return DashboardSummary(
        total_tickets=len(tickets),
        open_tickets=len(tickets) - resolved,
        resolved_tickets=resolved,
        recent_tickets=[TicketRead.model_validate(ticket) for ticket in tickets[:5]],
    )


async def list_visible_tickets(db: AsyncSession, current_user: User, search: Optional[str] = None) -> list[Ticket]:
    query = select(Ticket).order_by(Ticket.created_at.desc())
    if current_user.role in {RoleEnum.STUDENT.value, RoleEnum.FACULTY.value}:
        query = query.where(Ticket.created_by == current_user.id)
    elif current_user.role == RoleEnum.STAFF.value:
        query = query.where(or_(Ticket.assigned_to == current_user.id, Ticket.confirmed_department_id == current_user.department_id))
    elif current_user.role == RoleEnum.COORDINATOR.value:
        query = query.where(
            or_(
                Ticket.confirmed_department_id.is_(None),
                Ticket.confirmed_department_id == current_user.department_id,
            )
        )
    if search:
        pattern = f"%{search}%"
        query = query.where(or_(Ticket.title.ilike(pattern), Ticket.description.ilike(pattern), Ticket.ticket_number.ilike(pattern)))
    result = await db.scalars(query)
    return list(result.all())


@router.get("", response_model=list[TicketRead])
async def list_tickets(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    search: Optional[str] = Query(default=None),
    ticket_status: Optional[TicketStatusEnum] = Query(default=None, alias="status"),
) -> list[TicketRead]:
    tickets = await list_visible_tickets(db, current_user, search)
    if ticket_status:
        tickets = [ticket for ticket in tickets if ticket.status == ticket_status.value]
    return [TicketRead.model_validate(ticket) for ticket in tickets]


@router.post("", response_model=TicketRead, status_code=status.HTTP_201_CREATED)
async def create_ticket(
    payload: TicketCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> Ticket:
    count = await db.scalar(select(func.count()).select_from(Ticket))
    ticket = Ticket(
        ticket_number=ticket_number((count or 0) + 1),
        title=payload.title,
        description=payload.description,
        category=payload.category,
        priority=payload.priority.value,
        location=payload.location,
        status=TicketStatusEnum.NEW.value,
        created_by=current_user.id,
        ai_confidence=None,
    )
    db.add(ticket)
    await db.flush()
    db.add(TicketStatusHistory(ticket_id=ticket.id, changed_by=current_user.id, to_status=TicketStatusEnum.NEW.value))
    await db.commit()
    await db.refresh(ticket)
    return ticket


@router.get("/{ticket_ref}", response_model=TicketDetailRead)
async def read_ticket(
    ticket_ref: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> TicketDetailRead:
    ticket = await get_ticket(db, ticket_ref)
    if not can_view_ticket(current_user, ticket):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You cannot view this ticket")
    return detail_response(ticket)


@router.post("/{ticket_ref}/comments", response_model=CommentRead, status_code=status.HTTP_201_CREATED)
async def add_comment(
    ticket_ref: str,
    payload: TicketCommentRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> TicketComment:
    ticket = await get_ticket(db, ticket_ref)
    if not can_comment(current_user, ticket):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You cannot comment on this ticket")
    comment = TicketComment(ticket_id=ticket.id, user_id=current_user.id, content=payload.content, is_internal=payload.is_internal)
    db.add(comment)
    await db.commit()
    await db.refresh(comment)
    return comment


@router.post("/{ticket_ref}/reopen", response_model=TicketRead)
async def reopen_ticket(
    ticket_ref: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> Ticket:
    ticket = await get_ticket(db, ticket_ref)
    if ticket.created_by != current_user.id or current_user.role not in {RoleEnum.STUDENT.value, RoleEnum.FACULTY.value}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the reporter can reopen this ticket")
    if ticket.status not in {TicketStatusEnum.RESOLVED.value, TicketStatusEnum.CLOSED.value}:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only resolved or closed tickets can be reopened")
    old_status = ticket.status
    ticket.status = TicketStatusEnum.REOPENED.value
    ticket.reopened_at = datetime.now(timezone.utc)
    db.add(TicketStatusHistory(ticket_id=ticket.id, changed_by=current_user.id, from_status=old_status, to_status=ticket.status))
    await db.commit()
    await db.refresh(ticket)
    return ticket


@router.patch("/{ticket_ref}", response_model=TicketRead)
async def update_ticket(
    ticket_ref: str,
    payload: TicketUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> Ticket:
    ticket = await get_ticket(db, ticket_ref)
    if current_user.role not in TRIAGE_ROLES and not (current_user.role == RoleEnum.STAFF.value and ticket.assigned_to == current_user.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You cannot update this ticket")
    changes = payload.model_dump(exclude_unset=True)
    if current_user.role == RoleEnum.STAFF.value:
        changes = {key: value for key, value in changes.items() if key in {"status"}}
    old_status = ticket.status
    for field, value in changes.items():
        if hasattr(ticket, field):
            setattr(ticket, field, value.value if hasattr(value, "value") else value)
    if "status" in changes and ticket.status != old_status:
        db.add(TicketStatusHistory(ticket_id=ticket.id, changed_by=current_user.id, from_status=old_status, to_status=ticket.status))
        if ticket.status == TicketStatusEnum.RESOLVED.value:
            ticket.resolved_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(ticket)
    return ticket


@router.post("/{ticket_ref}/assign", response_model=TicketRead)
async def assign_ticket(
    ticket_ref: str,
    payload: TicketAssignmentRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> Ticket:
    ticket = await get_ticket(db, ticket_ref)
    if current_user.role not in TRIAGE_ROLES:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only coordinators and admins can assign tickets")
    assignee = await db.scalar(select(User).where(User.id == payload.assigned_to, User.is_active.is_(True)))
    if assignee is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignee not found")
    previous_status = ticket.status
    ticket.assigned_to = assignee.id
    ticket.confirmed_department_id = payload.department_id or assignee.department_id
    ticket.status = TicketStatusEnum.ASSIGNED.value
    db.add(TicketAssignment(ticket_id=ticket.id, assigned_by=current_user.id, assigned_to=assignee.id, department_id=ticket.confirmed_department_id, notes=payload.notes))
    if previous_status != TicketStatusEnum.ASSIGNED.value:
        db.add(TicketStatusHistory(ticket_id=ticket.id, changed_by=current_user.id, from_status=previous_status, to_status=ticket.status))
    await db.commit()
    await db.refresh(ticket)
    return ticket