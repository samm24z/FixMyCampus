"""Ticket photo/video (attachment) schemas: upload flow, AI draft and gallery view."""

import uuid
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import PriorityEnum

MediaKind = Literal["image", "video"]
AttachmentStatus = Literal["draft", "ready", "rejected", "deleted"]
LocationSource = Literal["picker", "device", "photo"]


class GeoPoint(BaseModel):
    lat: float = Field(..., ge=-90, le=90)
    lng: float = Field(..., ge=-180, le=180)
    accuracy_m: Optional[float] = Field(None, ge=0, le=100_000)


class UploadCreate(BaseModel):
    """Ask for a signed upload link. ``size`` is the browser's file size after shrinking."""

    kind: MediaKind
    content_type: str = Field(..., max_length=100)
    size: int = Field(..., gt=0)
    file_name: str = Field(..., min_length=1, max_length=255)


class UploadTicket(BaseModel):
    """Where the browser sends the file: ``upload_method upload_url`` with ``upload_headers``, raw bytes as body."""

    upload_id: uuid.UUID
    upload_url: str
    upload_method: str
    upload_headers: dict[str, str]
    expires_at: datetime


class UploadComplete(BaseModel):
    """Details the browser read from the original file before shrinking it."""

    captured_at: Optional[datetime] = None
    gps: Optional[GeoPoint] = None
    duration_s: Optional[float] = Field(None, ge=0)


class AttachmentRead(BaseModel):
    """A finished upload, as returned to its uploader."""

    id: uuid.UUID
    ticket_id: Optional[uuid.UUID]
    kind: MediaKind
    status: AttachmentStatus
    file_name: str
    file_size: int
    mime_type: str
    width: Optional[int] = None
    height: Optional[int] = None
    duration_s: Optional[float] = None
    captured_at: Optional[datetime] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AttachmentView(BaseModel):
    """A ticket's photo/video for the gallery, with short-lived signed links.

    ``captured_at`` and ``gps_*`` are only filled for the uploader and for staff, coordinators
    and admins who can see the ticket.
    """

    id: uuid.UUID
    kind: MediaKind
    file_name: str
    mime_type: str
    width: Optional[int] = None
    height: Optional[int] = None
    duration_s: Optional[float] = None
    created_at: datetime
    view_url: Optional[str] = None
    thumb_url: Optional[str] = None
    captured_at: Optional[datetime] = None
    gps_lat: Optional[float] = None
    gps_lng: Optional[float] = None
    gps_accuracy_m: Optional[float] = None


class DescribeRequest(BaseModel):
    upload_ids: list[uuid.UUID] = Field(..., min_length=1, max_length=5)
    note: Optional[str] = Field(None, max_length=300)
    place: Optional[str] = Field(None, max_length=255)


class MediaDraft(BaseModel):
    """Gemini's draft report from the photos; the student reviews and edits it before sending."""

    title: str
    description: str
    category: str
    priority: PriorityEnum
    location_hint: Optional[str] = None
    confidence: float = Field(..., ge=0, le=1)
    contains_people: bool = False
