"""Describe it for me: Gemini drafts a report from uploaded photos.

The logic is in ``app.services.media_service``.
"""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.attachment import DescribeRequest, MediaDraft
from app.services import media_service

router = APIRouter(prefix="/uploads")

DbSession = Annotated[AsyncSession, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]


@router.post("/describe", response_model=MediaDraft)
async def describe(payload: DescribeRequest, db: DbSession, current_user: CurrentUser) -> MediaDraft:
    return await media_service.describe_uploads(db, current_user, payload)
