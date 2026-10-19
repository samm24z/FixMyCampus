"""FixMyCampus AI - Modular Machine Learning & Generative AI Subsystem."""

from ai.interfaces import (
    BaseClassifierService,
    BaseEmbeddingService,
    BaseSuggestionService,
    BaseDeduplicationService,
    BasePriorityService,
    BaseAssistantService,
)
from ai.schemas import (
    AssistantReply,
    CategoryPrediction,
    DuplicateCandidate,
    PriorityRecommendation,
    TicketSuggestion,
)

__all__ = [
    "AssistantReply",
    "BaseClassifierService",
    "BaseEmbeddingService",
    "BaseSuggestionService",
    "BaseDeduplicationService",
    "BasePriorityService",
    "BaseAssistantService",
    "CategoryPrediction",
    "DuplicateCandidate",
    "PriorityRecommendation",
    "TicketSuggestion",
]
