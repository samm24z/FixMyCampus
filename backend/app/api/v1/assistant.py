"""Campus assistant endpoint. Business rules live in ``app.services.assistant_service``."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.assistant import AssistantChatRequest, AssistantChatResponse
from app.services import assistant_service

router = APIRouter(prefix="/assistant")

DbSession = Annotated[AsyncSession, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]


@router.post("/chat", response_model=AssistantChatResponse)
async def chat(payload: AssistantChatRequest, db: DbSession, current_user: CurrentUser) -> AssistantChatResponse:
    return await assistant_service.chat(db, current_user, payload)
