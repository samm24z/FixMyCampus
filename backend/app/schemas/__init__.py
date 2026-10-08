"""Schemas package exports."""

from app.schemas.common import APIResponse, PaginationParams, PaginatedResponse
from app.schemas.user import RoleBase, RoleCreate, RoleRead, UserBase, UserCreate, UserUpdate, UserRead
from app.schemas.department import (
    DepartmentBase, DepartmentCreate, DepartmentUpdate, DepartmentRead,
    CategoryBase, CategoryCreate, CategoryRead
)
from app.schemas.ticket import TicketBase, TicketCreate, TicketTriageUpdate, TicketStatusChange, TicketReopenRequest, TicketWithdrawRequest, TicketRead, TicketFilter, TicketSummary
from app.schemas.comment import CommentCreate, CommentRead
from app.schemas.attachment import AttachmentCreate, AttachmentRead
from app.schemas.status_history import StatusChangeRequest, StatusHistoryRead
from app.schemas.assignment import AssignmentCreate, AssignmentRead
from app.schemas.feedback import FeedbackCreate, FeedbackRead
from app.schemas.duplicate import DuplicateCreate, DuplicateRead
from app.schemas.sla import SLARuleBase, SLARuleCreate, SLARuleUpdate, SLARuleRead
from app.schemas.notification import NotificationCreate, NotificationRead, NotificationMarkRead
from app.schemas.audit import AuditLogRead, AuditLogFilter
from app.schemas.knowledge import KnowledgeDocumentBase, KnowledgeDocumentCreate, KnowledgeDocumentRead, KnowledgeChunkRead
from app.schemas.analytics import (
    CategoryBreakdownItem, StatusBreakdownItem, SLAComplianceStats, AnalyticsSummary
)
from app.schemas.ai import TriageAnalysisRequest, TriageAnalysisResponse, DuplicateCandidateSummary
from app.schemas.assistant import PolicyCitation, PolicyQueryRequest, PolicyQueryResponse
from app.schemas.health import HealthResponse

__all__ = [
    "APIResponse",
    "PaginationParams",
    "PaginatedResponse",
    "RoleBase",
    "RoleCreate",
    "RoleRead",
    "UserBase",
    "UserCreate",
    "UserUpdate",
    "UserRead",
    "DepartmentBase",
    "DepartmentCreate",
    "DepartmentUpdate",
    "DepartmentRead",
    "CategoryBase",
    "CategoryCreate",
    "CategoryRead",
    "TicketBase",
    "TicketCreate",
    "TicketTriageUpdate",
    "TicketStatusChange",
    "TicketReopenRequest",
    "TicketWithdrawRequest",
    "TicketRead",
    "TicketFilter",
    "TicketSummary",
    "CommentCreate",
    "CommentRead",
    "AttachmentCreate",
    "AttachmentRead",
    "StatusChangeRequest",
    "StatusHistoryRead",
    "AssignmentCreate",
    "AssignmentRead",
    "FeedbackCreate",
    "FeedbackRead",
    "DuplicateCreate",
    "DuplicateRead",
    "SLARuleBase",
    "SLARuleCreate",
    "SLARuleUpdate",
    "SLARuleRead",
    "NotificationCreate",
    "NotificationRead",
    "NotificationMarkRead",
    "AuditLogRead",
    "AuditLogFilter",
    "KnowledgeDocumentBase",
    "KnowledgeDocumentCreate",
    "KnowledgeDocumentRead",
    "KnowledgeChunkRead",
    "CategoryBreakdownItem",
    "StatusBreakdownItem",
    "SLAComplianceStats",
    "AnalyticsSummary",
    "TriageAnalysisRequest",
    "TriageAnalysisResponse",
    "DuplicateCandidateSummary",
    "PolicyCitation",
    "PolicyQueryRequest",
    "PolicyQueryResponse",
    "HealthResponse",
]
