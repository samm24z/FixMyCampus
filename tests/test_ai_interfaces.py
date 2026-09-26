"""Test AI module interfaces and mock implementations."""

import pytest
from ai.mock_service import (
    MockClassifierService,
    MockDeduplicationService,
    MockPriorityService,
    MockRAGService,
)


@pytest.mark.asyncio
async def test_mock_classifier():
    """Verify mock classifier categorizes IT issues correctly."""
    classifier = MockClassifierService()
    result = await classifier.classify(
        title="Wi-Fi router down",
        description="The internet in the computer lab is not working and nobody can login.",
    )
    assert result.suggested_category == "IT / Network"
    assert result.category_confidence >= 0.8
    assert result.suggested_department == "Information Technology"


@pytest.mark.asyncio
async def test_mock_deduplicator():
    """Verify mock deduplicator generates 384-dimensional vector."""
    deduplicator = MockDeduplicationService()
    embedding = await deduplicator.generate_embedding("Water leak in library bathroom")
    assert isinstance(embedding, list)
    assert len(embedding) == 384


@pytest.mark.asyncio
async def test_mock_priority_engine():
    """Verify priority engine flags critical hazards."""
    priority_engine = MockPriorityService()
    result = await priority_engine.recommend_priority(
        title="Emergency electrical spark",
        description="Sparks flying from main distribution switchboard in Block B.",
    )
    assert result.suggested_priority == "CRITICAL"
    assert result.recommended_sla_hours == 4


@pytest.mark.asyncio
async def test_mock_rag_service():
    """Verify RAG service returns grounded answer with citation."""
    rag_service = MockRAGService()
    result = await rag_service.answer_policy_query("What is the resolution SLA for standard complaints?")
    assert result.is_grounded is True
    assert len(result.citations) > 0
    assert result.citations[0].page_number == 14
