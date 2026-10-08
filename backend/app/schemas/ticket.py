"""Ticket Pydantic schemas."""

import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator
from app.models.enums import CategoryEnum, PriorityEnum, TicketStatusEnum

CATEGORY_VALUES = {category.value for category in CategoryEnum}


def validate_category(value: Optional[str]) -> Optional[str]:
    if value is not None and value not in CATEGORY_VALUES:
        raise ValueError(f"category must be one of: {', '.join(sorted(CATEGORY_VALUES))}")
    return value


class TicketBase(BaseModel):
    title: str = Field(..., min_length=5, max_length=255)
    description: str = Field(..., min_length=10)
    category: str = Field(..., min_length=2, max_length=100)
    location: str = Field(..., min_length=2, max_length=255)
    priority: PriorityEnum = Field(default=PriorityEnum.MEDIUM)


class TicketCreate(TicketBase):
    @field_validator("category")
    @classmethod
    def category_must_be_known(cls, value: str) -> str:
        return validate_category(value)  # type: ignore[return-value]


class TicketTriageUpdate(BaseModel):
    """Coordinator/admin edits to the classification of a ticket."""

    category: Optional[str] = None
    priority: Optional[PriorityEnum] = None
    confirmed_department_id: Optional[uuid.UUID] = None
    sla_deadline: Optional[datetime] = None

    @field_validator("category")
    @classmethod
    def category_must_be_known(cls, value: Optional[str]) -> Optional[str]:
        return validate_category(value)


class TicketStatusChange(BaseModel):
    status: TicketStatusEnum
    remarks: Optional[str] = Field(None, max_length=2000)


class TicketReopenRequest(BaseModel):
    reason: Optional[str] = Field(None, max_length=2000)


class TicketWithdrawRequest(BaseModel):
    reason: Optional[str] = Field(None, max_length=2000)


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
    mine: bool = False
    open_only: bool = False


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
