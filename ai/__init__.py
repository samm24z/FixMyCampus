"""FixMyCampus AI - Modular Machine Learning & Generative AI Subsystem."""

from ai.interfaces import (
    BaseClassifierService,
    BaseEmbeddingService,
    BaseSuggestionService,
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
    TicketSuggestion,
)

__all__ = [
    "BaseClassifierService",
    "BaseEmbeddingService",
    "BaseSuggestionService",
    "BaseDeduplicationService",
    "BasePriorityService",
    "BaseRAGService",
    "CategoryPrediction",
    "DuplicateCandidate",
    "PriorityRecommendation",
    "RAGQueryRequest",
    "RAGQueryResponse",
    "SourceCitation",
    "TicketSuggestion",
]
