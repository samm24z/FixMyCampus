"""Department and Category Repositories."""

from typing import Optional, Sequence
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.department import Category, Department
from app.repositories.base import BaseRepository


class DepartmentRepository(BaseRepository[Department]):
    """Department data access."""

    def __init__(self):
        super().__init__(Department)

    async def get_by_code(self, db: AsyncSession, code: str) -> Optional[Department]:
        result = await db.execute(select(Department).where(Department.code == code))
        return result.scalars().first()

    async def get_by_name(self, db: AsyncSession, name: str) -> Optional[Department]:
        result = await db.execute(select(Department).where(Department.name == name))
        return result.scalars().first()

    async def get_active(self, db: AsyncSession) -> Sequence[Department]:
        result = await db.execute(select(Department).where(Department.is_active.is_(True)))
        return result.scalars().all()


class CategoryRepository(BaseRepository[Category]):
    """Category data access."""

    def __init__(self):
        super().__init__(Category)

    async def get_by_code(self, db: AsyncSession, code: str) -> Optional[Category]:
        result = await db.execute(select(Category).where(Category.code == code))
        return result.scalars().first()

    async def get_by_name(self, db: AsyncSession, name: str) -> Optional[Category]:
        result = await db.execute(select(Category).where(Category.name == name))
        return result.scalars().first()


department_repo = DepartmentRepository()
category_repo = CategoryRepository()
