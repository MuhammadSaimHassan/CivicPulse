"""Deterministic keyword triage. Always available, never fails.

This is the floor the whole system stands on: when the LLM is slow, rate
limited, or wrong, this answers. It is deliberately boring — a lookup table a
reviewer can read in one sitting — and it knows the Roman-Urdu words citizens
actually type ("pani", "bijli", "gutter", "kachra").
"""

from __future__ import annotations

import re

from app.domain import PRIORITY_RANK, Category, Priority
from app.providers.triage.base import TriageResult

# Order matters only for ties: earlier categories win, so the most specific
# category (streetlights is a kind of electricity problem) comes first.
CATEGORY_KEYWORDS: dict[Category, tuple[str, ...]] = {
    Category.streetlights: (
        "streetlight",
        "street light",
        "street-light",
        "lamp",
        "khamba",
        "pole light",
        "light not working",
        "lights off",
        "dark street",
        "bulb",
    ),
    Category.water: (
        "water",
        "pani",
        "paani",
        "pipe",
        "water main",
        "leak",
        "tap",
        "supply line",
        "tanker",
        "flood",
        "burst",
        "pressure",
        "nalka",
    ),
    Category.electricity: (
        "electric",
        "bijli",
        "power",
        "load shedding",
        "loadshedding",
        "transformer",
        "wire",
        "voltage",
        "outage",
        "meter",
        "current lag",
        "spark",
        "tripping",
        "bijlee",
    ),
    Category.sanitation: (
        "sewage",
        "sewer",
        "gutter",
        "drain",
        "garbage",
        "kachra",
        "trash",
        "waste",
        "manhole",
        "smell",
        "mosquito",
        "dump",
        "nala",
        "nullah",
        "choked",
        "washroom",
    ),
    Category.roads: (
        "road",
        "sarak",
        "sadak",
        "pothole",
        "asphalt",
        "speed breaker",
        "footpath",
        "bridge",
        "traffic",
        "carpet",
        "gali",
        "street broken",
    ),
}

# Hazard words: a complaint containing any of these is at least HIGH priority,
# whatever any model says. Also used as a guardrail against injected
# "mark this as low priority" instructions — see services/triage_service.py.
HIGH_PRIORITY_KEYWORDS: tuple[str, ...] = (
    "burst",
    "flood",
    "flooding",
    "fire",
    "spark",
    "sparking",
    "electrocut",
    "live wire",
    "naked wire",
    "open manhole",
    "collapsed",
    "collapse",
    "accident",
    "injured",
    "emergency",
    "danger",
    "gas leak",
    "overflowing",
    "entering",
    "since fajr",
    "children fell",
    "no water for",
    "short circuit",
)
LOW_PRIORITY_KEYWORDS: tuple[str, ...] = (
    "suggestion",
    "request",
    "minor",
    "paint",
    "cosmetic",
    "whenever possible",
    "not urgent",
    "faded",
    "kindly consider",
)

_SENTENCE_END = re.compile(r"(?<=[.!?])\s")


def _count(text: str, words: tuple[str, ...]) -> int:
    # Match at a word start so "flood" finds "flooding" but "main" would not
    # find "remain". Keywords are short, the text is <= 2000 chars: cheap.
    return sum(1 for w in words if re.search(r"\b" + re.escape(w), text))


def classify_category(text: str) -> tuple[Category, int]:
    lowered = text.lower()
    best, best_hits = Category.other, 0
    for category, words in CATEGORY_KEYWORDS.items():
        hits = _count(lowered, words)
        if hits > best_hits:
            best, best_hits = category, hits
    return best, best_hits


def hazard_priority_floor(text: str) -> Priority:
    """The minimum priority a complaint's wording justifies, independent of any model."""
    return Priority.high if _count(text.lower(), HIGH_PRIORITY_KEYWORDS) else Priority.low


def classify_priority(text: str) -> Priority:
    lowered = text.lower()
    if _count(lowered, HIGH_PRIORITY_KEYWORDS):
        return Priority.high
    if _count(lowered, LOW_PRIORITY_KEYWORDS):
        return Priority.low
    return Priority.normal


def max_priority(a: Priority, b: Priority) -> Priority:
    return a if PRIORITY_RANK[a] >= PRIORITY_RANK[b] else b


def one_line_summary(text: str, location: str) -> str:
    first = _SENTENCE_END.split(" ".join(text.split()), maxsplit=1)[0]
    summary = f"{first} ({location})" if location else first
    return summary if len(summary) <= 140 else summary[:137].rstrip() + "..."


class RuleBasedTriage:
    name = "rules"

    def triage(self, text: str, location: str) -> TriageResult:
        category, hits = classify_category(text)
        priority = classify_priority(text)
        # Confidence is honest about what keyword matching is: more matching
        # words = more confident, capped well below what a model would claim.
        confidence = 0.3 if hits == 0 else min(0.4 + 0.1 * hits, 0.8)
        return TriageResult(
            category=category,
            priority=priority,
            summary=one_line_summary(text, location),
            confidence=confidence,
        )
