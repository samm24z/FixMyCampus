"""Keyword rules: the always-available fallback when Gemini is off or fails."""

import re
from typing import List, Tuple

from ai.interfaces import BaseSuggestionService
from ai.schemas import TicketSuggestion

CATEGORY_KEYWORDS: dict[str, List[str]] = {
    "IT / Network": ["wifi", "wi-fi", "internet", "network", "router", "login", "password", "server", "computer", "lan", "printer", "website"],
    "Electrical": ["light", "lights", "power", "fan", "spark", "sparks", "switch", "switchboard", "wire", "wiring", "socket", "electric", "bulb", "tubelight", "ac"],
    "Sanitation": ["garbage", "dustbin", "trash", "waste", "dirty", "smell", "cleaning", "sweeping", "mosquito", "unclean"],
    "Water / Plumbing": ["leak", "leaking", "tap", "pipe", "toilet", "washroom", "water", "drain", "flush", "sink", "drinking"],
    "Classroom Equipment": ["projector", "board", "whiteboard", "blackboard", "bench", "desk", "chair", "mic", "microphone", "speaker", "podium"],
    "Civil Maintenance": ["ceiling", "wall", "crack", "roof", "door", "window", "paint", "floor", "stairs", "gate", "glass"],
    "Academic Facilities": ["library", "lab", "laboratory", "exam", "seminar", "timetable", "books", "classroom"],
}
PRIORITY_KEYWORDS: List[Tuple[str, List[str]]] = [
    ("CRITICAL", ["emergency", "fire", "spark", "sparks", "hazard", "flood", "shock", "short circuit", "gas"]),
    ("HIGH", ["urgent", "exam", "blackout", "broken", "not working", "no power", "overflowing"]),
    ("LOW", ["minor", "cosmetic", "suggestion", "whenever"]),
]
MAX_CONFIDENCE = 0.6


def _hits(text: str, words: List[str]) -> List[str]:
    return [w for w in words if re.search(rf"(?<![a-z0-9]){re.escape(w)}(?![a-z0-9])", text)]


def match_category(text: str) -> Tuple[str, List[str]]:
    """Best category and the words that matched; ('Other', []) when nothing matches."""
    text = text.lower()
    best, best_hits = "Other", []
    for category, words in CATEGORY_KEYWORDS.items():
        found = _hits(text, words)
        if len(found) > len(best_hits):
            best, best_hits = category, found
    return best, best_hits


def match_priority(text: str) -> Tuple[str, List[str]]:
    text = text.lower()
    for priority, words in PRIORITY_KEYWORDS:
        found = _hits(text, words)
        if found:
            return priority, found
    return "MEDIUM", []


class KeywordSuggestionService(BaseSuggestionService):
    async def suggest(self, title: str, description: str, location: str = "") -> TicketSuggestion:
        text = f"{title} {description}"
        category, category_words = match_category(text)
        priority, priority_words = match_priority(text)
        confidence = min(MAX_CONFIDENCE, 0.3 + 0.1 * len(category_words)) if category_words else 0.2
        if category_words:
            reason = f"The report mentions {', '.join(repr(w) for w in category_words[:3])}."
        else:
            reason = "No clear match, so it was left as Other."
        if priority_words:
            reason += f" Words like {priority_words[0]!r} suggest {priority.lower()} priority."
        return TicketSuggestion(category=category, priority=priority, confidence=confidence, reason=reason, source="keywords")
