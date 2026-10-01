"""Ticket detail, dashboard, and action schemas."""

import uuid
from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict

from app.models.enums import TicketStatusEnum
from app.schemas.assignment import AssignmentRead
from app.schemas.comment import CommentRead
from app.schemas.status_history import StatusHistoryRead
from app.schemas.ticket import TicketRead


class TicketPermissions(BaseModel):
    """What the requesting user may do with this ticket (computed server-side).

    The UI renders controls from this instead of re-implementing the rules.
    """

    allowed_statuses: List[TicketStatusEnum] = []
    can_assign: bool = False
    can_edit_triage: bool = False
    can_comment: bool = False
    can_comment_internal: bool = False
    can_reopen: bool = False


class TicketDetailRead(TicketRead):
    created_by_name: str
    assigned_to_name: Optional[str] = None
    department_name: Optional[str] = None
    comments: List[CommentRead] = []
    history: List[StatusHistoryRead] = []
    assignments: List[AssignmentRead] = []
    permissions: TicketPermissions = TicketPermissions()


class DashboardSummary(BaseModel):
    total_tickets: int
    open_tickets: int
    resolved_tickets: int
    by_status: Dict[str, int] = {}
    recent_tickets: List[TicketRead] = []


class TicketAssignmentRequest(BaseModel):
    assigned_to: uuid.UUID
    department_id: Optional[uuid.UUID] = None
    notes: Optional[str] = None


class TicketDetailResponse(TicketDetailRead):
    model_config = ConfigDict(from_attributes=True)
