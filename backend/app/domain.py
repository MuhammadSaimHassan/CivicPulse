"""Domain vocabulary shared by every layer.

These are values, not rules. The rules that use them (the state machine,
triage orchestration) live in services/.
"""

from __future__ import annotations

from enum import StrEnum


class Category(StrEnum):
    water = "water"
    electricity = "electricity"
    sanitation = "sanitation"
    roads = "roads"
    streetlights = "streetlights"
    other = "other"


class Priority(StrEnum):
    high = "high"
    normal = "normal"
    low = "low"


class Status(StrEnum):
    open = "open"
    in_progress = "in_progress"
    resolved = "resolved"
    rejected = "rejected"


PRIORITY_RANK: dict[Priority, int] = {Priority.low: 0, Priority.normal: 1, Priority.high: 2}

# Values allowed in complaints.triaged_by (also enforced by a DB CHECK).
TRIAGED_BY_VALUES = (
    "llm:groq",
    "llm:gemini",
    "llm:openrouter",
    "llm:ollama",
    "rules",
    "rules:fallback",
    "simulated",
)
