"""Ticket Duplicate schemas."""

import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class DuplicateCreate(BaseModel):
    primary_ticket_id: uuid.UUID
    duplicate_ticket_id: uuid.UUID
    similarity_score: float = Field(..., ge=0.0, le=1.0)
    detected_by: str = "STAFF_MANUAL"


class DuplicateRead(BaseModel):
    id: uuid.UUID
    primary_ticket_id: uuid.UUID
    duplicate_ticket_id: uuid.UUID
    similarity_score: float
    detected_by: str
    verified_by: Optional[uuid.UUID] = None
    is_verified: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
