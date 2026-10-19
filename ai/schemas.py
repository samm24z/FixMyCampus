"""Pydantic schemas for AI input, output, and recommendation payloads."""

from typing import List, Optional
from pydantic import BaseModel, Field


class CategoryPrediction(BaseModel):
    """Result of AI complaint classification."""
    suggested_category: str = Field(..., description="Predicted category name")
    category_confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score")
    suggested_department: Optional[str] = Field(None, description="Mapped department name")
    department_confidence: float = Field(0.0, ge=0.0, le=1.0)
    confidence_warning: bool = Field(False, description="True if confidence is below threshold")


class TicketSuggestion(BaseModel):
    """Suggested category and priority for a new report."""
    category: str = Field(..., description="One of the campus categories")
    priority: str = Field(..., description="LOW, MEDIUM, HIGH, or CRITICAL")
    confidence: float = Field(..., ge=0.0, le=1.0)
    reason: str = Field(..., description="One plain sentence explaining the suggestion")
    source: str = Field(..., description="'gemini' or 'keywords'")


class DuplicateCandidate(BaseModel):
    """Candidate duplicate complaint detected via vector similarity."""
    complaint_id: str = Field(..., description="UUID of existing complaint")
    ticket_number: str = Field(..., description="Human-readable ticket code e.g. TICK-2026-0001")
    title: str = Field(..., description="Title of existing complaint")
    similarity_score: float = Field(..., ge=0.0, le=1.0, description="Cosine similarity score")
    status: str = Field(..., description="Current status of existing ticket")
    created_at: str = Field(..., description="Creation ISO timestamp")


class PriorityRecommendation(BaseModel):
    """Result of AI urgency and SLA calculation."""
    suggested_priority: str = Field(..., description="LOW, MEDIUM, HIGH, or CRITICAL")
    priority_confidence: float = Field(..., ge=0.0, le=1.0)
    urgency_signals: List[str] = Field(default_factory=list, description="Keywords/patterns detected")
    recommended_sla_hours: int = Field(..., description="Suggested resolution SLA target in hours")


class AssistantReply(BaseModel):
    """What the model said, before the server checks it. Actions are only proposals."""
    answer: str
    cited: List[int] = Field(default_factory=list, description="Numbers of the sources used")
    status: str = Field("answered", description="'answered' or 'not_found'")
    actions: List[dict] = Field(default_factory=list)
