"""Department and Category SQLAlchemy models."""

import uuid
from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.ticket import Ticket, TicketAssignment
    from app.models.sla import SLARule


class Department(Base, UUIDMixin, TimestampMixin):
    """Campus Operational Department (e.g., IT, Sanitation, Electrical)."""

    __tablename__ = "departments"

    name: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    code: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    head_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    head_user: Mapped[Optional["User"]] = relationship("User", foreign_keys=[head_user_id], post_update=True)
    members: Mapped[List["User"]] = relationship("User", foreign_keys="User.department_id", back_populates="department")
    categories: Mapped[List["Category"]] = relationship("Category", back_populates="default_department")
    tickets_suggested: Mapped[List["Ticket"]] = relationship("Ticket", foreign_keys="Ticket.suggested_department_id", back_populates="suggested_department")
    tickets_confirmed: Mapped[List["Ticket"]] = relationship("Ticket", foreign_keys="Ticket.confirmed_department_id", back_populates="confirmed_department")
    sla_rules: Mapped[List["SLARule"]] = relationship("SLARule", back_populates="department")
    assignments: Mapped[List["TicketAssignment"]] = relationship("TicketAssignment", back_populates="department")


class Category(Base, UUIDMixin, TimestampMixin):
    """Grievance Category (e.g., IT / Network, Electrical, Sanitation)."""

    __tablename__ = "categories"

    name: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    code: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    default_department_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("departments.id", ondelete="SET NULL"), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    default_department: Mapped[Optional["Department"]] = relationship("Department", back_populates="categories")
