"""Notification schemas."""

import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, model_validator
from app.models.enums import NotificationTypeEnum


class NotificationRead(BaseModel):
    id: uuid.UUID
    ticket_id: Optional[uuid.UUID] = None
    ticket_number: Optional[str] = None
    title: str
    message: str
    type: NotificationTypeEnum
    is_read: bool
    created_at: datetime


class NotificationMarkRead(BaseModel):
    """Either some of the caller's notifications (``ids``) or all of them (``all``)."""

    ids: list[uuid.UUID] = Field(default_factory=list, max_length=100)
    all: bool = False

    @model_validator(mode="after")
    def _one_of(self) -> "NotificationMarkRead":
        if not self.all and not self.ids:
            raise ValueError("Say which notifications to mark as read, or all of them")
        return self


class UnreadCount(BaseModel):
    count: int
