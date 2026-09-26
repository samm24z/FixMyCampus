"""User and Role Repositories."""

from typing import Optional, Sequence
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import Role, User
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    """User data access operations."""

    def __init__(self):
        super().__init__(User)

    async def get_by_email(self, db: AsyncSession, email: str) -> Optional[User]:
        """Lookup active user by email."""
        result = await db.execute(select(User).where(User.email == email))
        return result.scalars().first()

    async def get_by_role(self, db: AsyncSession, role: str) -> Sequence[User]:
        """Fetch users by system role."""
        result = await db.execute(select(User).where(User.role == role))
        return result.scalars().all()


class RoleRepository(BaseRepository[Role]):
    """Role data access operations."""

    def __init__(self):
        super().__init__(Role)

    async def get_by_code(self, db: AsyncSession, code: str) -> Optional[Role]:
        """Lookup role by unique code."""
        result = await db.execute(select(Role).where(Role.code == code))
        return result.scalars().first()


user_repo = UserRepository()
role_repo = RoleRepository()
