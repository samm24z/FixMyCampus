"""Authentication endpoints.

Sign-up, login, password reset and token refresh are handled by Supabase Auth directly from the
browser. The backend only exposes the signed-in user's profile (and, on first sight of a new
Supabase account, creates that profile - see ``app.api.deps.get_current_user``).
"""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.user import UserRead


router = APIRouter(prefix="/auth")


@router.get("/me", response_model=UserRead)
async def current_user(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Return the authenticated user's profile, including role and department."""
    return current_user
