"""Notification Repository."""

import uuid
from typing import Sequence
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.notification import Notification
from app.repositories.base import BaseRepository


class NotificationRepository(BaseRepository[Notification]):
    def __init__(self):
        super().__init__(Notification)

    async def get_by_user(
        self, db: AsyncSession, user_id: uuid.UUID, unread_only: bool = False, limit: int = 50
    ) -> Sequence[Notification]:
        query = select(Notification).where(Notification.user_id == user_id)
        if unread_only:
            query = query.where(Notification.is_read.is_(False))
        query = query.order_by(Notification.created_at.desc()).limit(limit)
        result = await db.execute(query)
        return result.scalars().all()

    async def mark_as_read(self, db: AsyncSession, notification_ids: list[uuid.UUID]) -> int:
        query = (
            update(Notification)
            .where(Notification.id.in_(notification_ids))
            .values(is_read=True)
        )
        result = await db.execute(query)
        await db.commit()
        return result.rowcount


notification_repo = NotificationRepository()
