"""Authentication endpoints.

Sign-up, login, password reset and token refresh are handled by Supabase Auth directly from the
browser. The backend only exposes the signed-in user's profile (and, on first sight of a new
Supabase account, creates that profile - see ``app.api.deps.get_current_user``), and lets users
edit their own name and phone number. Role, department, email and active status stay admin-only.
"""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.enums import AuditActionEnum
from app.models.user import User
from app.schemas.user import SelfProfileUpdate, UserRead
from app.services.audit_service import record_audit


router = APIRouter(prefix="/auth")


@router.get("/me", response_model=UserRead)
async def current_user(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Return the authenticated user's profile, including role and department."""
    return current_user


@router.patch("/me", response_model=UserRead)
async def update_current_user(
    payload: SelfProfileUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """Update the signed-in user's own name and/or phone number."""
    given = payload.model_dump(exclude_unset=True)
    old = {field: getattr(current_user, field) for field in given}
    for field, value in given.items():
        setattr(current_user, field, value)
    new = {field: getattr(current_user, field) for field in given}
    if new != old:
        record_audit(
            db, user=current_user, action=AuditActionEnum.UPDATE, entity_type="user", entity_id=current_user.id,
            old_values=old, new_values=new,
        )
        await db.commit()
        await db.refresh(current_user)
    return current_user
