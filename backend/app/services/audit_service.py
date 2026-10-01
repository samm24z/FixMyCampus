"""Append-only audit trail helper."""

import uuid
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog
from app.models.enums import AuditActionEnum
from app.models.user import User


def record_audit(
    db: AsyncSession,
    *,
    user: Optional[User],
    action: AuditActionEnum,
    entity_type: str,
    entity_id: uuid.UUID,
    old_values: Optional[dict[str, Any]] = None,
    new_values: Optional[dict[str, Any]] = None,
) -> None:
    """Stage an audit row in the caller's transaction (committed with the change itself)."""
    db.add(AuditLog(
        user_id=user.id if user else None,
        action=action.value,
        entity_type=entity_type,
        entity_id=entity_id,
        old_values=old_values,
        new_values=new_values,
    ))
