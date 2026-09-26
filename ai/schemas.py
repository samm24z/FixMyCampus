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


class SourceCitation(BaseModel):
    """Grounding citation for RAG policy answers."""
    document_title: str = Field(..., description="Name of approved campus document")
    page_number: Optional[int] = Field(None, description="Page number in document")
    section_heading: Optional[str] = Field(None, description="Section or chapter name")
    snippet: str = Field(..., description="Relevant text excerpt")
    similarity_score: float = Field(..., ge=0.0, le=1.0)


class RAGQueryRequest(BaseModel):
    """Incoming user question to campus policy assistant."""
    question: str = Field(..., min_length=3, max_length=1000)
    conversation_history: List[dict] = Field(default_factory=list)


class RAGQueryResponse(BaseModel):
    """Grounded answer from campus policy assistant with citations."""
    answer: str = Field(..., description="LLM generated answer grounded in approved docs")
    citations: List[SourceCitation] = Field(default_factory=list)
    is_grounded: bool = Field(True, description="False if answer fell back to generic guidance")
