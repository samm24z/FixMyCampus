"""Ticket Feedback schemas."""

import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class FeedbackCreate(BaseModel):
    rating: int = Field(..., ge=1, le=5, description="Satisfaction rating from 1 to 5")
    comments: Optional[str] = Field(None, max_length=2000)


class FeedbackRead(BaseModel):
    id: uuid.UUID
    ticket_id: uuid.UUID
    user_id: uuid.UUID
    rating: int
    comments: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
