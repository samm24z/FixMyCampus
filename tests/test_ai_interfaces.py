"""Test AI module interfaces and mock implementations."""

import pytest
from ai.mock_service import (
    MockClassifierService,
    MockDeduplicationService,
    MockPriorityService,
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
@pytest.mark.parametrize("title, description, category, priority", [
    ("Wi-Fi router down", "Nobody can connect to the internet.", "IT / Network", "MEDIUM"),
    ("Sparks from switchboard", "Sparks and a burning smell.", "Electrical", "CRITICAL"),
    ("Tap leaking", "Water is leaking from the tap in the washroom.", "Water / Plumbing", "MEDIUM"),
    ("Garbage not collected", "The dustbin near the canteen is overflowing.", "Sanitation", "HIGH"),
    ("Projector not working", "The projector in Room 204 does not turn on.", "Classroom Equipment", "HIGH"),
    ("Crack in the wall", "There is a big crack in the wall of the staircase.", "Civil Maintenance", "MEDIUM"),
    ("Library closed early", "The library was shut during exam week.", "Academic Facilities", "HIGH"),
    ("Something odd", "It is hard to describe what happened here.", "Other", "MEDIUM"),
])
async def test_keyword_service_covers_every_category(title, description, category, priority):
    from ai.keyword_service import MAX_CONFIDENCE, KeywordSuggestionService

    result = await KeywordSuggestionService().suggest(title, description, "Block A")
    assert (result.category, result.priority, result.source) == (category, priority, "keywords")
    assert 0 < result.confidence <= MAX_CONFIDENCE and result.reason


def _reply(text):
    return {"candidates": [{"content": {"parts": [{"text": text}]}}]}


def test_gemini_reply_parsing_accepts_fenced_json_and_clamps_confidence():
    from ai.gemini_service import parse_suggestion

    result = parse_suggestion(_reply('```json\n{"category": "Electrical", "priority": "high", "confidence": 7, "reason": "  Wiring\\nfault. "}\n```'))
    assert (result.category, result.priority, result.confidence, result.reason, result.source) == ("Electrical", "HIGH", 1.0, "Wiring fault.", "gemini")


@pytest.mark.parametrize("payload", [
    {}, {"candidates": []}, _reply("no json"), _reply('{"category": "Magic", "priority": "HIGH", "confidence": 1, "reason": "x"}'),
    _reply('{"category": "Other", "priority": "URGENT", "confidence": 1, "reason": "x"}'),
])
def test_gemini_reply_parsing_rejects_unusable_answers(payload):
    from ai.gemini_service import SuggestionError, parse_suggestion

    with pytest.raises(SuggestionError):
        parse_suggestion(payload)


@pytest.mark.asyncio
async def test_gemini_service_sends_only_the_report_text_and_reports_failures_as_suggestion_errors():
    import httpx
    from ai.gemini_service import GeminiSuggestionService, SuggestionError

    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(429, json={"error": {"message": "quota"}})

    service = GeminiSuggestionService("secret-key", "some-model", transport=httpx.MockTransport(handler))
    with pytest.raises(SuggestionError) as error:
        await service.suggest("Projector broken", "It does not turn on.", "Room 204")
    assert "secret-key" not in str(error.value) and "429" in str(error.value)
    assert calls[0].headers["x-goog-api-key"] == "secret-key" and "secret-key" not in str(calls[0].url)
    assert str(calls[0].url).endswith("/models/some-model:generateContent")
