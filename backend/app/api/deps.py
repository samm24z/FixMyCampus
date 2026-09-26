"""Common API dependencies, including authentication and RBAC."""

from collections.abc import Callable
from typing import Annotated, AsyncGenerator
from uuid import UUID
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose.exceptions import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.security import decode_token
from app.models.enums import RoleEnum
from app.models.user import User


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


async def get_current_user(
	token: Annotated[str, Depends(oauth2_scheme)],
	db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
	"""Resolve an active user from a valid access token."""
	credentials_exception = HTTPException(
		status_code=status.HTTP_401_UNAUTHORIZED,
		detail="Could not validate credentials",
		headers={"WWW-Authenticate": "Bearer"},
	)
	try:
		payload = decode_token(token, expected_type="access")
		user_id = UUID(payload["sub"])
	except (JWTError, ValueError, KeyError):
		raise credentials_exception from None

	user = await db.scalar(select(User).where(User.id == user_id))
	if user is None or not user.is_active:
		raise credentials_exception
	return user


def require_role(*roles: RoleEnum) -> Callable:
	"""Create a dependency that permits only the supplied roles."""
	allowed_roles = {role.value for role in roles}

	async def role_dependency(
		current_user: Annotated[User, Depends(get_current_user)],
	) -> User:
		if current_user.role not in allowed_roles:
			raise HTTPException(
				status_code=status.HTTP_403_FORBIDDEN,
				detail="Insufficient permissions",
			)
		return current_user

	return role_dependency

__all__ = ["get_db", "AsyncSession", "get_current_user", "require_role"]
