"""All SQLAlchemy models and enums."""

from app.models.base import Base, TimestampMixin, UUIDMixin
from app.models.types import VectorType
from app.models.enums import (
    RoleEnum,
    TicketStatusEnum,
    PriorityEnum,
    CategoryEnum,
    NotificationTypeEnum,
    AuditActionEnum,
)
from app.models.user import Role, User
from app.models.department import Department, Category
from app.models.ticket import (
    Ticket,
    TicketComment,
    TicketAttachment,
    TicketStatusHistory,
    TicketAssignment,
    TicketFeedback,
    TicketDuplicate,
)
from app.models.sla import SLARule
from app.models.notification import Notification
from app.models.audit import AuditLog
from app.models.knowledge import KnowledgeDocument, KnowledgeChunk

__all__ = [
    "Base",
    "TimestampMixin",
    "UUIDMixin",
    "VectorType",
    "RoleEnum",
    "TicketStatusEnum",
    "PriorityEnum",
    "CategoryEnum",
    "NotificationTypeEnum",
    "AuditActionEnum",
    "Role",
    "User",
    "Department",
    "Category",
    "Ticket",
    "TicketComment",
    "TicketAttachment",
    "TicketStatusHistory",
    "TicketAssignment",
    "TicketFeedback",
    "TicketDuplicate",
    "SLARule",
    "Notification",
    "AuditLog",
    "KnowledgeDocument",
    "KnowledgeChunk",
]
