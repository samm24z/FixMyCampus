"""Ticket Comment schemas."""

import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class CommentCreate(BaseModel):
    ticket_id: uuid.UUID
    content: str = Field(..., min_length=1)
    is_internal: bool = False


class CommentRead(BaseModel):
    id: uuid.UUID
    ticket_id: uuid.UUID
    user_id: uuid.UUID
    content: str
    is_internal: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
