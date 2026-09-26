"""SLA Rule Repository."""

from typing import Optional, Sequence
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.sla import SLARule
from app.repositories.base import BaseRepository


class SLARuleRepository(BaseRepository[SLARule]):
    def __init__(self):
        super().__init__(SLARule)

    async def get_by_category_and_priority(
        self, db: AsyncSession, category: str, priority: str
    ) -> Optional[SLARule]:
        result = await db.execute(
            select(SLARule).where(
                SLARule.category == category,
                SLARule.priority == priority,
                SLARule.is_active.is_(True),
            )
        )
        return result.scalars().first()

    async def get_active_rules(self, db: AsyncSession) -> Sequence[SLARule]:
        result = await db.execute(select(SLARule).where(SLARule.is_active.is_(True)))
        return result.scalars().all()


sla_repo = SLARuleRepository()
