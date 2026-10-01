"""Ticket Comment schemas."""

import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class CommentCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=5000)
    is_internal: bool = False


class CommentRead(BaseModel):
    id: uuid.UUID
    ticket_id: uuid.UUID
    user_id: uuid.UUID
    author_name: Optional[str] = None
    author_role: Optional[str] = None
    content: str
    is_internal: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
