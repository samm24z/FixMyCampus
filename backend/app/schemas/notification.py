"""Notification schemas."""

import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field
from app.models.enums import NotificationTypeEnum


class NotificationCreate(BaseModel):
    user_id: uuid.UUID
    ticket_id: Optional[uuid.UUID] = None
    title: str = Field(..., max_length=200)
    message: str
    type: NotificationTypeEnum = NotificationTypeEnum.STATUS_CHANGED


class NotificationRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    ticket_id: Optional[uuid.UUID] = None
    title: str
    message: str
    type: NotificationTypeEnum
    is_read: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class NotificationMarkRead(BaseModel):
    notification_ids: list[uuid.UUID]
