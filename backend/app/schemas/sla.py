"""SLA Rule schemas."""

import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field
from app.models.enums import PriorityEnum


class SLARuleBase(BaseModel):
    category: str = Field(..., max_length=100)
    priority: PriorityEnum
    department_id: Optional[uuid.UUID] = None
    target_resolution_hours: int = Field(..., ge=1, le=1000)
    escalation_threshold_hours: int = Field(..., ge=1, le=1000)
    is_active: bool = True


class SLARuleCreate(SLARuleBase):
    pass


class SLARuleUpdate(BaseModel):
    target_resolution_hours: Optional[int] = Field(None, ge=1, le=1000)
    escalation_threshold_hours: Optional[int] = Field(None, ge=1, le=1000)
    is_active: Optional[bool] = None


class SLARuleRead(SLARuleBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
