"""User and Role SQLAlchemy models."""

import uuid
from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin, UUIDMixin
from app.models.enums import RoleEnum

if TYPE_CHECKING:
    from app.models.department import Department
    from app.models.ticket import (
        Ticket,
        TicketComment,
        TicketAttachment,
        TicketStatusHistory,
        TicketAssignment,
        TicketFeedback,
    )
    from app.models.notification import Notification
    from app.models.audit import AuditLog


class Role(Base, UUIDMixin, TimestampMixin):
    """System Role model."""

    __tablename__ = "roles"

    name: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    code: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    permissions: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict, nullable=True)


class User(Base, UUIDMixin, TimestampMixin):
    """Application profile of a Supabase Auth account (``id`` equals the Supabase user id).

    Credentials live in Supabase; this table holds the role, department and active flag."""

    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    role: Mapped[RoleEnum] = mapped_column(String(50), default=RoleEnum.STUDENT, index=True, nullable=False)
    
    department_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("departments.id", ondelete="SET NULL"), nullable=True, index=True
    )
    phone_number: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relationships
    department: Mapped[Optional["Department"]] = relationship("Department", foreign_keys=[department_id], back_populates="members")
    
    tickets_created: Mapped[List["Ticket"]] = relationship(
        "Ticket", foreign_keys="Ticket.created_by", back_populates="creator", cascade="all, delete-orphan"
    )
    tickets_assigned: Mapped[List["Ticket"]] = relationship(
        "Ticket", foreign_keys="Ticket.assigned_to", back_populates="assignee"
    )
    comments: Mapped[List["TicketComment"]] = relationship("TicketComment", back_populates="user")
    attachments: Mapped[List["TicketAttachment"]] = relationship("TicketAttachment", back_populates="uploader")
    status_history: Mapped[List["TicketStatusHistory"]] = relationship("TicketStatusHistory", back_populates="user")
    assigned_by_records: Mapped[List["TicketAssignment"]] = relationship("TicketAssignment", foreign_keys="TicketAssignment.assigned_by", back_populates="assigner")
    assigned_to_records: Mapped[List["TicketAssignment"]] = relationship("TicketAssignment", foreign_keys="TicketAssignment.assigned_to", back_populates="assignee")
    feedbacks: Mapped[List["TicketFeedback"]] = relationship("TicketFeedback", back_populates="user")
    notifications: Mapped[List["Notification"]] = relationship("Notification", back_populates="user", cascade="all, delete-orphan")
    audit_logs: Mapped[List["AuditLog"]] = relationship("AuditLog", back_populates="user")
