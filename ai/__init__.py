"""FixMyCampus AI - Modular Machine Learning & Generative AI Subsystem."""

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
    RAGQueryRequest,
    RAGQueryResponse,
    SourceCitation,
)

__all__ = [
    "BaseClassifierService",
    "BaseDeduplicationService",
    "BasePriorityService",
    "BaseRAGService",
    "CategoryPrediction",
    "DuplicateCandidate",
    "PriorityRecommendation",
    "RAGQueryRequest",
    "RAGQueryResponse",
    "SourceCitation",
]
