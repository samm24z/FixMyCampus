"""Mock AI services for development, testing, and offline baseline execution."""

from typing import List, Optional
from ai.interfaces import (
    BaseClassifierService,
    BaseDeduplicationService,
    BasePriorityService,
    BaseRAGService,
)
from ai.keyword_service import match_category, match_priority
from ai.schemas import (
    CategoryPrediction,
    DuplicateCandidate,
    PriorityRecommendation,
    RAGQueryResponse,
    SourceCitation,
)


_DEPARTMENTS = {
    "IT / Network": "Information Technology",
    "Electrical": "Electrical Maintenance",
    "Water / Plumbing": "Sanitation & Plumbing",
}


class MockClassifierService(BaseClassifierService):
    """Mock implementation of complaint classification (uses the keyword rules)."""

    async def classify(self, title: str, description: str) -> CategoryPrediction:
        category, words = match_category(f"{title} {description}")
        known = bool(words)
        return CategoryPrediction(
            suggested_category=category,
            category_confidence=0.9 if known else 0.55,
            suggested_department=_DEPARTMENTS.get(category, "General Administration"),
            department_confidence=0.88 if known else 0.5,
            confidence_warning=not known,
        )


class MockDeduplicationService(BaseDeduplicationService):
    """Mock implementation of vector embedding and duplicate search."""

    async def generate_embedding(self, text: str) -> List[float]:
        # Return deterministic 384-dimensional vector
        return [0.0] * 384

    async def find_duplicates(
        self, text: str, threshold: float = 0.82, top_k: int = 5
    ) -> List[DuplicateCandidate]:
        return []


_PRIORITY_SCORES = {
    "CRITICAL": (0.95, "Immediate safety hazard detected", 4),
    "HIGH": (0.85, "High-impact academic disruption", 24),
    "MEDIUM": (0.75, "Standard maintenance issue", 72),
    "LOW": (0.7, "Minor or cosmetic issue", 168),
}


class MockPriorityService(BasePriorityService):
    """Mock implementation of priority calculation (uses the keyword rules)."""

    async def recommend_priority(
        self, title: str, description: str, category: Optional[str] = None
    ) -> PriorityRecommendation:
        priority, _ = match_priority(f"{title} {description}")
        confidence, signal, hours = _PRIORITY_SCORES[priority]
        return PriorityRecommendation(
            suggested_priority=priority,
            priority_confidence=confidence,
            urgency_signals=[signal],
            recommended_sla_hours=hours,
        )


class MockRAGService(BaseRAGService):
    """Mock implementation of RAG campus policy assistant."""

    async def answer_policy_query(
        self, question: str, history: Optional[List[dict]] = None
    ) -> RAGQueryResponse:
        return RAGQueryResponse(
            answer="Based on the Campus Facilities Policy (Section 4.2), standard maintenance requests submitted by students are triaged within 24 hours.",
            citations=[
                SourceCitation(
                    document_title="Campus Facilities Policy & Grievance Guidelines 2026",
                    page_number=14,
                    section_heading="4.2 Maintenance SLAs and Triage Workflow",
                    snippet="All registered campus grievances undergo initial coordinator triage within 24 hours of submission.",
                    similarity_score=0.91,
                )
            ],
            is_grounded=True,
        )
