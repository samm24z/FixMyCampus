"""Campus Policy Assistant schemas."""

from typing import List, Optional
from pydantic import BaseModel, Field


class PolicyCitation(BaseModel):
    document_title: str
    page_number: Optional[int] = None
    section_heading: Optional[str] = None
    snippet: str
    similarity_score: float


class PolicyQueryRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=1000)


class PolicyQueryResponse(BaseModel):
    answer: str
    citations: List[PolicyCitation] = Field(default_factory=list)
    is_grounded: bool = True
