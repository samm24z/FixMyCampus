"""Abstract Base Classes and Interfaces for FixMyCampus AI Subsystems."""

from abc import ABC, abstractmethod
from typing import List, Optional
from ai.schemas import (
    CategoryPrediction,
    DuplicateCandidate,
    PriorityRecommendation,
    RAGQueryResponse,
)


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


class BaseRAGService(ABC):
    """Interface for campus policy Q&A assistant with source citations."""

    @abstractmethod
    async def answer_policy_query(
        self, question: str, history: Optional[List[dict]] = None
    ) -> RAGQueryResponse:
        """Answer policy query with source document citations."""
        pass
