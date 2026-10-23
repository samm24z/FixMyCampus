"""Ticket detail, dashboard, and action schemas."""

import uuid
from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel

from app.models.enums import TicketStatusEnum
from app.schemas.attachment import LocationSource
from app.schemas.ai import DuplicateCandidateSummary, TicketSuggestions
from app.schemas.assignment import AssignmentRead
from app.schemas.comment import CommentRead
from app.schemas.duplicate import GroupMemberRead
from app.schemas.feedback import FeedbackRead
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
    can_confirm: bool = False
    can_withdraw: bool = False
    can_give_feedback: bool = False
    can_review_suggestions: bool = False
    can_split_group: bool = False
    statuses_requiring_remarks: List[TicketStatusEnum] = []


class TicketDetailRead(TicketRead):
    created_by_name: str
    assigned_to_name: Optional[str] = None
    department_name: Optional[str] = None
    comments: List[CommentRead] = []
    history: List[StatusHistoryRead] = []
    assignments: List[AssignmentRead] = []
    feedback: Optional[FeedbackRead] = None
    permissions: TicketPermissions = TicketPermissions()
    # Coordinators and admins only; empty for everyone else.
    suggestions: Optional[TicketSuggestions] = None
    duplicates: List[DuplicateCandidateSummary] = []
    group_members: List[GroupMemberRead] = []
    observed_at: Optional[datetime] = None
    location_source: Optional[LocationSource] = None
    attachment_count: int = 0
    # Where the reporter said the problem is: the reporter and staff only, empty for everyone else.
    report_lat: Optional[float] = None
    report_lng: Optional[float] = None
    report_accuracy_m: Optional[float] = None


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
