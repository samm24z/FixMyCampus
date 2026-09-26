"""SLA Rule SQLAlchemy model."""

import uuid
from typing import TYPE_CHECKING, Optional
from sqlalchemy import Boolean, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin, UUIDMixin
from app.models.enums import PriorityEnum

if TYPE_CHECKING:
    from app.models.department import Department


class SLARule(Base, UUIDMixin, TimestampMixin):
    """SLA Target configuration per Category and Priority."""

    __tablename__ = "sla_rules"
    __table_args__ = (
        UniqueConstraint("category", "priority", "department_id", name="uq_sla_rule_cat_prio_dept"),
    )

    category: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    priority: Mapped[PriorityEnum] = mapped_column(String(20), index=True, nullable=False)
    
    department_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("departments.id", ondelete="CASCADE"), nullable=True, index=True
    )
    
    target_resolution_hours: Mapped[int] = mapped_column(Integer, nullable=False)
    escalation_threshold_hours: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    department: Mapped[Optional["Department"]] = relationship("Department", back_populates="sla_rules")
