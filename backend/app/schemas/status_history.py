"""Ticket Status History schemas."""

import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict
from app.models.enums import TicketStatusEnum


class StatusChangeRequest(BaseModel):
    to_status: TicketStatusEnum
    remarks: Optional[str] = None


class StatusHistoryRead(BaseModel):
    id: uuid.UUID
    ticket_id: uuid.UUID
    changed_by: uuid.UUID
    from_status: Optional[TicketStatusEnum] = None
    to_status: TicketStatusEnum
    remarks: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
