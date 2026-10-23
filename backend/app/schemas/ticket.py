"""Ticket Pydantic schemas."""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from app.core.config import settings
from app.models.enums import CategoryEnum, PriorityEnum, TicketStatusEnum
from app.schemas.attachment import LocationSource

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
    # Ready photos uploaded earlier through POST /uploads; linked to the ticket when it is created.
    attachment_ids: list[uuid.UUID] = Field(default_factory=list)
    # When the problem was seen (defaults to now), and where the reporter says it is.
    observed_at: Optional[datetime] = None
    report_lat: Optional[float] = Field(None, ge=-90, le=90)
    report_lng: Optional[float] = Field(None, ge=-180, le=180)
    report_accuracy_m: Optional[float] = Field(None, ge=0, le=100_000)
    location_source: Optional[LocationSource] = None

    @field_validator("category")
    @classmethod
    def category_must_be_known(cls, value: str) -> str:
        return validate_category(value)  # type: ignore[return-value]

    @field_validator("attachment_ids")
    @classmethod
    def limit_photos(cls, value: list[uuid.UUID]) -> list[uuid.UUID]:
        unique = list(dict.fromkeys(value))
        if len(unique) > settings.UPLOAD_MAX_PHOTOS:
            raise ValueError(f"You can attach up to {settings.UPLOAD_MAX_PHOTOS} photos")
        return unique

    @field_validator("observed_at")
    @classmethod
    def not_in_the_future(cls, value: Optional[datetime]) -> Optional[datetime]:
        if value is None:
            return value
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        if value > datetime.now(timezone.utc) + timedelta(minutes=5):
            raise ValueError("observed_at can't be in the future")
        return value

    @model_validator(mode="after")
    def position_needs_both_coordinates(self) -> "TicketCreate":
        if (self.report_lat is None) != (self.report_lng is None):
            raise ValueError("report_lat and report_lng must be given together")
        return self


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
    report_count: int = 1
    parent_ticket_id: Optional[uuid.UUID] = None
    parent_ticket_number: Optional[str] = None  # coordinators and admins only
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
