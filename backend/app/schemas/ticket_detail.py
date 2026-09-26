"""Review-1 ticket detail and dashboard response schemas."""

import uuid
from typing import List, Optional

from pydantic import BaseModel, ConfigDict

from app.schemas.assignment import AssignmentRead
from app.schemas.comment import CommentRead
from app.schemas.status_history import StatusHistoryRead
from app.schemas.ticket import TicketRead


class TicketDetailRead(TicketRead):
    created_by_name: str
    assigned_to_name: Optional[str] = None
    department_name: Optional[str] = None
    comments: List[CommentRead] = []
    history: List[StatusHistoryRead] = []
    assignments: List[AssignmentRead] = []


class DashboardSummary(BaseModel):
    total_tickets: int
    open_tickets: int
    resolved_tickets: int
    recent_tickets: List[TicketRead] = []


class TicketCommentRequest(BaseModel):
    content: str
    is_internal: bool = False


class TicketAssignmentRequest(BaseModel):
    assigned_to: uuid.UUID
    department_id: Optional[uuid.UUID] = None
    notes: Optional[str] = None


class TicketDetailResponse(TicketDetailRead):
    model_config = ConfigDict(from_attributes=True)