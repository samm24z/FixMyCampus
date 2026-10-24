"""The signed-in person's notifications. Rules live in ``app.services.notification_service``."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.common import PaginatedResponse
from app.schemas.notification import NotificationMarkRead, NotificationRead, UnreadCount
from app.services import notification_service


router = APIRouter(prefix="/notifications")

DbSession = Annotated[AsyncSession, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]


@router.get("", response_model=PaginatedResponse[NotificationRead])
async def list_notifications(
    db: DbSession,
    current_user: CurrentUser,
    unread_only: bool = Query(default=False),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=50),
) -> PaginatedResponse[NotificationRead]:
    items, total, total_pages = await notification_service.list_for_user(
        db, current_user, unread_only=unread_only, page=page, page_size=page_size
    )
    return PaginatedResponse[NotificationRead](items=items, total=total, page=page, page_size=page_size, total_pages=total_pages)


@router.get("/unread-count", response_model=UnreadCount)
async def unread_count(db: DbSession, current_user: CurrentUser) -> UnreadCount:
    return UnreadCount(count=await notification_service.unread_count(db, current_user))


@router.post("/read", response_model=UnreadCount)
async def mark_read(payload: NotificationMarkRead, db: DbSession, current_user: CurrentUser) -> UnreadCount:
    return UnreadCount(count=await notification_service.mark_read(db, current_user, payload.ids, payload.all))
