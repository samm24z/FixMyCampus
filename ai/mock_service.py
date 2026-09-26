"""Mock AI services for development, testing, and offline baseline execution."""

from typing import List, Optional
from ai.interfaces import (
    BaseClassifierService,
    BaseDeduplicationService,
    BasePriorityService,
    BaseRAGService,
)
from ai.schemas import (
    CategoryPrediction,
    DuplicateCandidate,
    PriorityRecommendation,
    RAGQueryResponse,
    SourceCitation,
)


class MockClassifierService(BaseClassifierService):
    """Mock implementation of complaint classification."""

    async def classify(self, title: str, description: str) -> CategoryPrediction:
        full_text = f"{title} {description}".lower()
        if any(w in full_text for w in ["wifi", "internet", "network", "router", "login"]):
            return CategoryPrediction(
                suggested_category="IT / Network",
                category_confidence=0.92,
                suggested_department="Information Technology",
                department_confidence=0.90,
                confidence_warning=False,
            )
        elif any(w in full_text for w in ["light", "power", "fan", "spark", "switch", "wire"]):
            return CategoryPrediction(
                suggested_category="Electrical",
                category_confidence=0.88,
                suggested_department="Electrical Maintenance",
                department_confidence=0.87,
                confidence_warning=False,
            )
        elif any(w in full_text for w in ["leak", "tap", "pipe", "toilet", "washroom", "water"]):
            return CategoryPrediction(
                suggested_category="Water / Plumbing",
                category_confidence=0.89,
                suggested_department="Sanitation & Plumbing",
                department_confidence=0.86,
                confidence_warning=False,
            )
        return CategoryPrediction(
            suggested_category="Other",
            category_confidence=0.55,
            suggested_department="General Administration",
            department_confidence=0.50,
            confidence_warning=True,
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


class MockPriorityService(BasePriorityService):
    """Mock implementation of priority calculation."""

    async def recommend_priority(
        self, title: str, description: str, category: Optional[str] = None
    ) -> PriorityRecommendation:
        full_text = f"{title} {description}".lower()
        if any(w in full_text for w in ["emergency", "fire", "spark", "hazard", "flood"]):
            return PriorityRecommendation(
                suggested_priority="CRITICAL",
                priority_confidence=0.95,
                urgency_signals=["Immediate safety hazard detected"],
                recommended_sla_hours=4,
            )
        elif any(w in full_text for w in ["urgent", "exam", "blackout", "broken"]):
            return PriorityRecommendation(
                suggested_priority="HIGH",
                priority_confidence=0.85,
                urgency_signals=["High-impact academic disruption"],
                recommended_sla_hours=24,
            )
        return PriorityRecommendation(
            suggested_priority="MEDIUM",
            priority_confidence=0.75,
            urgency_signals=["Standard maintenance issue"],
            recommended_sla_hours=72,
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
