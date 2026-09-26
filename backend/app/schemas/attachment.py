"""Ticket Attachment schemas."""

import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class AttachmentCreate(BaseModel):
    ticket_id: uuid.UUID
    file_name: str
    file_path: str
    file_size: int
    mime_type: str


class AttachmentRead(BaseModel):
    id: uuid.UUID
    ticket_id: uuid.UUID
    uploaded_by: uuid.UUID
    file_name: str
    file_path: str
    file_size: int
    mime_type: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
