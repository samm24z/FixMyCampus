"""Ticket Assignment schemas."""

import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


class AssignmentCreate(BaseModel):
    ticket_id: uuid.UUID
    assigned_to: uuid.UUID
    department_id: Optional[uuid.UUID] = None
    notes: Optional[str] = None


class AssignmentRead(BaseModel):
    id: uuid.UUID
    ticket_id: uuid.UUID
    assigned_by: uuid.UUID
    assigned_to: uuid.UUID
    department_id: Optional[uuid.UUID] = None
    notes: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
