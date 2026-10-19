"""AI Service schemas for backend endpoints."""

import uuid
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field
from app.models.enums import PriorityEnum


class TriageAnalysisRequest(BaseModel):
    title: str = Field(..., min_length=3)
    description: str = Field(..., min_length=5)


class DuplicateCandidateSummary(BaseModel):
    ticket_id: uuid.UUID
    ticket_number: str
    title: str
    similarity_score: float
    status: str


class TriageAnalysisResponse(BaseModel):
    suggested_category: str
    category_confidence: float
    suggested_department_id: Optional[uuid.UUID] = None
    suggested_department_name: Optional[str] = None
    department_confidence: float
    suggested_priority: PriorityEnum
    priority_confidence: float
    recommended_sla_hours: int
    duplicate_candidates: List[DuplicateCandidateSummary] = Field(default_factory=list)
    confidence_warning: bool = False


class TicketSuggestions(BaseModel):
    """What the system suggests for a ticket. Coordinators and admins only."""

    status: str  # pending, done or failed
    category: Optional[str] = None
    priority: Optional[PriorityEnum] = None
    department_id: Optional[uuid.UUID] = None
    department_name: Optional[str] = None
    confidence: Optional[float] = None
    reason: Optional[str] = None
    source: Optional[str] = None  # "gemini" or "keywords"
    analyzed_at: Optional[datetime] = None
