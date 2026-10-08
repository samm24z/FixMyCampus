"""Ticket and related grievance entities SQLAlchemy models."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin, UUIDMixin
from app.models.enums import PriorityEnum, TicketStatusEnum
from app.models.types import VectorType

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.department import Department
    from app.models.notification import Notification


class Ticket(Base, UUIDMixin, TimestampMixin):
    """Core Grievance Ticket Model."""

    __tablename__ = "tickets"

    ticket_number: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Classification & Department fields (AI + Human in the loop)
    category: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    suggested_category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    confirmed_category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    
    suggested_department_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("departments.id", ondelete="SET NULL"), nullable=True, index=True
    )
    confirmed_department_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("departments.id", ondelete="SET NULL"), nullable=True, index=True
    )

    priority: Mapped[PriorityEnum] = mapped_column(
        String(20), default=PriorityEnum.MEDIUM, index=True, nullable=False
    )
    ai_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    location: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    status: Mapped[TicketStatusEnum] = mapped_column(
        String(30), default=TicketStatusEnum.NEW, index=True, nullable=False
    )
    
    # User ownership
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    assigned_to: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True
    )

    # pgvector 384-dimensional dense semantic embedding
    embedding: Mapped[Optional[List[float]]] = mapped_column(VectorType(384), nullable=True)

    # Timelines and SLA
    sla_deadline: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    reopened_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    creator: Mapped["User"] = relationship("User", foreign_keys=[created_by], back_populates="tickets_created")
    assignee: Mapped[Optional["User"]] = relationship("User", foreign_keys=[assigned_to], back_populates="tickets_assigned")
    suggested_department: Mapped[Optional["Department"]] = relationship(
        "Department", foreign_keys=[suggested_department_id], back_populates="tickets_suggested"
    )
    confirmed_department: Mapped[Optional["Department"]] = relationship(
        "Department", foreign_keys=[confirmed_department_id], back_populates="tickets_confirmed"
    )
    
    comments: Mapped[List["TicketComment"]] = relationship("TicketComment", back_populates="ticket", cascade="all, delete-orphan")
    attachments: Mapped[List["TicketAttachment"]] = relationship("TicketAttachment", back_populates="ticket", cascade="all, delete-orphan")
    status_history: Mapped[List["TicketStatusHistory"]] = relationship("TicketStatusHistory", back_populates="ticket", cascade="all, delete-orphan")
    assignments: Mapped[List["TicketAssignment"]] = relationship("TicketAssignment", back_populates="ticket", cascade="all, delete-orphan")
    feedback: Mapped[Optional["TicketFeedback"]] = relationship("TicketFeedback", back_populates="ticket", uselist=False, cascade="all, delete-orphan")
    
    duplicates_as_primary: Mapped[List["TicketDuplicate"]] = relationship(
        "TicketDuplicate", foreign_keys="TicketDuplicate.primary_ticket_id", back_populates="primary_ticket", cascade="all, delete-orphan"
    )
    duplicates_as_duplicate: Mapped[List["TicketDuplicate"]] = relationship(
        "TicketDuplicate", foreign_keys="TicketDuplicate.duplicate_ticket_id", back_populates="duplicate_ticket", cascade="all, delete-orphan"
    )
    notifications: Mapped[List["Notification"]] = relationship("Notification", back_populates="ticket", cascade="all, delete-orphan")


class TicketComment(Base, UUIDMixin, TimestampMixin):
    """Discussion and staff internal notes on tickets."""

    __tablename__ = "ticket_comments"

    ticket_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tickets.id", ondelete="CASCADE"), index=True, nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    is_internal: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relationships
    ticket: Mapped["Ticket"] = relationship("Ticket", back_populates="comments")
    user: Mapped["User"] = relationship("User", back_populates="comments")


class TicketAttachment(Base, UUIDMixin, TimestampMixin):
    """Uploaded attachments and image evidence."""

    __tablename__ = "ticket_attachments"

    ticket_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tickets.id", ondelete="CASCADE"), index=True, nullable=False
    )
    uploaded_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)

    # Relationships
    ticket: Mapped["Ticket"] = relationship("Ticket", back_populates="attachments")
    uploader: Mapped["User"] = relationship("User", back_populates="attachments")


class TicketStatusHistory(Base, UUIDMixin, TimestampMixin):
    """Audit log of ticket lifecycle status transitions."""

    __tablename__ = "ticket_status_history"

    ticket_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tickets.id", ondelete="CASCADE"), index=True, nullable=False
    )
    changed_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=True
    )
    from_status: Mapped[Optional[TicketStatusEnum]] = mapped_column(String(30), nullable=True)
    to_status: Mapped[TicketStatusEnum] = mapped_column(String(30), nullable=False)
    remarks: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    ticket: Mapped["Ticket"] = relationship("Ticket", back_populates="status_history")
    user: Mapped["User"] = relationship("User", back_populates="status_history")


class TicketAssignment(Base, UUIDMixin, TimestampMixin):
    """Records of staff and coordinator assignment history."""

    __tablename__ = "ticket_assignments"

    ticket_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tickets.id", ondelete="CASCADE"), index=True, nullable=False
    )
    assigned_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    assigned_to: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    department_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("departments.id", ondelete="SET NULL"), nullable=True
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    ticket: Mapped["Ticket"] = relationship("Ticket", back_populates="assignments")
    assigner: Mapped["User"] = relationship("User", foreign_keys=[assigned_by], back_populates="assigned_by_records")
    assignee: Mapped["User"] = relationship("User", foreign_keys=[assigned_to], back_populates="assigned_to_records")
    department: Mapped[Optional["Department"]] = relationship("Department", back_populates="assignments")


class TicketFeedback(Base, UUIDMixin, TimestampMixin):
    """User satisfaction rating & feedback upon ticket resolution."""

    __tablename__ = "ticket_feedback"
    __table_args__ = (UniqueConstraint("ticket_id", name="uq_ticket_feedback_ticket_id"),)

    ticket_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tickets.id", ondelete="CASCADE"), unique=True, index=True, nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    comments: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    ticket: Mapped["Ticket"] = relationship("Ticket", back_populates="feedback")
    user: Mapped["User"] = relationship("User", back_populates="feedbacks")


class TicketDuplicate(Base, UUIDMixin, TimestampMixin):
    """Linkage between primary ticket and detected duplicates."""

    __tablename__ = "ticket_duplicates"

    primary_ticket_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tickets.id", ondelete="CASCADE"), index=True, nullable=False
    )
    duplicate_ticket_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tickets.id", ondelete="CASCADE"), index=True, nullable=False
    )
    similarity_score: Mapped[float] = mapped_column(Float, nullable=False)
    detected_by: Mapped[str] = mapped_column(String(50), default="AI_AUTO", nullable=False)
    verified_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relationships
    primary_ticket: Mapped["Ticket"] = relationship("Ticket", foreign_keys=[primary_ticket_id], back_populates="duplicates_as_primary")
    duplicate_ticket: Mapped["Ticket"] = relationship("Ticket", foreign_keys=[duplicate_ticket_id], back_populates="duplicates_as_duplicate")
    verifier: Mapped[Optional["User"]] = relationship("User", foreign_keys=[verified_by])
