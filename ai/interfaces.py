"""Abstract Base Classes and Interfaces for FixMyCampus AI Subsystems."""

from abc import ABC, abstractmethod
from typing import List, Optional
from ai.schemas import (
    AssistantReply,
    CategoryPrediction,
    DuplicateCandidate,
    PriorityRecommendation,
    TicketSuggestion,
)


class BaseSuggestionService(ABC):
    """Interface for suggesting a category and priority for a new report."""

    @abstractmethod
    async def suggest(self, title: str, description: str, location: str) -> TicketSuggestion:
        """Suggest a category and priority. May raise; callers fall back to keywords."""
        pass


class BaseEmbeddingService(ABC):
    """Interface for turning text into a normalised 384-number vector."""

    @abstractmethod
    async def embed(self, text: str) -> List[float]:
        pass

    async def embed_many(self, texts: List[str]) -> List[List[float]]:
        return [await self.embed(text) for text in texts]


class BaseClassifierService(ABC):
    """Interface for classifying complaint text into category and department."""

    @abstractmethod
    async def classify(self, title: str, description: str) -> CategoryPrediction:
        """Predict category and department for given complaint text."""
        pass


class BaseDeduplicationService(ABC):
    """Interface for generating embeddings and detecting duplicate grievances."""

    @abstractmethod
    async def generate_embedding(self, text: str) -> List[float]:
        """Generate a 384-dimensional dense vector embedding."""
        pass

    @abstractmethod
    async def find_duplicates(
        self, text: str, threshold: float = 0.82, top_k: int = 5
    ) -> List[DuplicateCandidate]:
        """Retrieve candidate duplicates exceeding similarity threshold."""
        pass


class BasePriorityService(ABC):
    """Interface for evaluating grievance severity, priority, and SLA target."""

    @abstractmethod
    async def recommend_priority(
        self, title: str, description: str, category: Optional[str] = None
    ) -> PriorityRecommendation:
        """Calculate urgency score and recommended priority level."""
        pass


class BaseAssistantService(ABC):
    """Interface for the campus chat assistant: one call per message, answers only from the given sources."""

    @abstractmethod
    async def reply(
        self, message: str, sources: List[dict], tickets: List[dict], history: List[dict]
    ) -> AssistantReply:
        """May raise; callers fall back to showing the sources."""
        pass
