"""User profile helpers."""

import uuid
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import ForbiddenException
from app.core.permissions import SELF_REGISTRATION_ROLES
from app.models.enums import RoleEnum
from app.models.user import User


async def provision_user(db: AsyncSession, user_id: uuid.UUID, claims: dict[str, Any]) -> Optional[User]:
    """Create the application profile for someone who just signed up through Supabase Auth.

    Self-signups are always STUDENT or FACULTY: the requested role comes from user metadata,
    which anyone can set when signing up, so nothing beyond the self-registration roles is honoured.
    Elevated roles are only ever granted by an admin. Returns None when the token cannot yield a
    usable profile (no email, anonymous session, or the email belongs to another profile) and raises
    Forbidden when the email domain is not allowed to sign up.
    """
    email = claims.get("email")
    if not email or claims.get("is_anonymous"):
        return None
    if not settings.is_email_allowed(str(email)):
        domains = ", ".join(f"@{d}" for d in settings.allowed_email_domains)
        raise ForbiddenException(f"Sign-up is limited to {domains} email addresses.")
    metadata = claims.get("user_metadata") or {}
    requested = metadata.get("role")
    role = requested if requested in SELF_REGISTRATION_ROLES else RoleEnum.STUDENT.value
    full_name = str(metadata.get("full_name") or "").strip()[:150]
    if len(full_name) < 2:
        full_name = str(email).split("@")[0][:150]
    if len(full_name) < 2:  # e.g. "a@college.edu": the profile schema needs at least two characters
        full_name = str(email)[:150]

    db.add(User(id=user_id, email=str(email).lower(), full_name=full_name, role=role, is_active=True, is_verified=True))
    try:
        await db.commit()
    except IntegrityError:
        # Either a concurrent first request created it (fine), or the email is taken by another profile (None).
        await db.rollback()
        return await db.scalar(select(User).where(User.id == user_id))
    return await db.scalar(select(User).where(User.id == user_id))
