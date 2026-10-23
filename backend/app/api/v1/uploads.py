"""Photo and video uploads: signed upload links, completion checks, and a ticket's gallery.

Owned by the uploads worker; see ``upload_service`` for the logic.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.attachment import AttachmentRead, AttachmentView, UploadComplete, UploadCreate, UploadTicket
from app.services import ticket_service, upload_service

router = APIRouter(prefix="/uploads")
# GET /tickets/{ref}/attachments lives here so the tickets router stays untouched.
ticket_router = APIRouter(prefix="/tickets")

DbSession = Annotated[AsyncSession, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]


@router.post("", response_model=UploadTicket, status_code=status.HTTP_201_CREATED)
async def create_upload(payload: UploadCreate, db: DbSession, current_user: CurrentUser) -> UploadTicket:
    return await upload_service.create_upload(db, current_user, payload)


@router.post("/{upload_id}/complete", response_model=AttachmentRead)
async def complete_upload(
    upload_id: uuid.UUID, payload: UploadComplete, db: DbSession, current_user: CurrentUser
) -> AttachmentRead:
    return await upload_service.complete_upload(db, current_user, upload_id, payload)


@router.delete("/{upload_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_upload(upload_id: uuid.UUID, db: DbSession, current_user: CurrentUser) -> Response:
    await upload_service.delete_upload(db, current_user, upload_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@ticket_router.get("/{ticket_ref}/attachments", response_model=list[AttachmentView])
async def ticket_attachments(ticket_ref: str, db: DbSession, current_user: CurrentUser) -> list[AttachmentView]:
    ticket = await ticket_service.get_ticket_for_user(db, current_user, ticket_ref)
    return await upload_service.gallery_for_ticket(db, current_user, ticket)
