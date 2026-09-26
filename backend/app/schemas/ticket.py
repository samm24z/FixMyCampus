"""Ticket Pydantic schemas."""

import uuid
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field
from app.models.enums import PriorityEnum, TicketStatusEnum


class TicketBase(BaseModel):
    title: str = Field(..., min_length=5, max_length=255)
    description: str = Field(..., min_length=10)
    category: str = Field(..., min_length=2, max_length=100)
    location: str = Field(..., min_length=2, max_length=255)
    priority: PriorityEnum = Field(default=PriorityEnum.MEDIUM)


class TicketCreate(TicketBase):
    pass


class TicketUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=5, max_length=255)
    description: Optional[str] = Field(None, min_length=10)
    category: Optional[str] = None
    confirmed_category: Optional[str] = None
    confirmed_department_id: Optional[uuid.UUID] = None
    priority: Optional[PriorityEnum] = None
    location: Optional[str] = None
    status: Optional[TicketStatusEnum] = None
    assigned_to: Optional[uuid.UUID] = None
    sla_deadline: Optional[datetime] = None


class TicketRead(TicketBase):
    id: uuid.UUID
    ticket_number: str
    suggested_category: Optional[str] = None
    confirmed_category: Optional[str] = None
    suggested_department_id: Optional[uuid.UUID] = None
    confirmed_department_id: Optional[uuid.UUID] = None
    ai_confidence: Optional[float] = None
    status: TicketStatusEnum
    created_by: uuid.UUID
    assigned_to: Optional[uuid.UUID] = None
    sla_deadline: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    reopened_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TicketFilter(BaseModel):
    status: Optional[TicketStatusEnum] = None
    category: Optional[str] = None
    priority: Optional[PriorityEnum] = None
    department_id: Optional[uuid.UUID] = None
    assigned_to: Optional[uuid.UUID] = None
    created_by: Optional[uuid.UUID] = None
    search: Optional[str] = None


class TicketSummary(BaseModel):
    id: uuid.UUID
    ticket_number: str
    title: str
    category: str
    priority: PriorityEnum
    status: TicketStatusEnum
    location: str
    created_at: datetime
    sla_deadline: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
