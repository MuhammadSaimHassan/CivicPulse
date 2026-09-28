"""Test doubles. Deterministic, no network, no sleeping."""

from __future__ import annotations

import json
from typing import Any

from app.domain import Category, Priority
from app.providers.triage.base import TriageError, TriageResult


class InMemoryCache:
    """Implements app.providers.cache.Cache without Redis."""

    def __init__(self) -> None:
        self.data: dict[str, Any] = {}
        self.lists: dict[str, list[str]] = {}

    def get_json(self, key: str) -> Any | None:
        raw = self.data.get(key)
        return None if raw is None else json.loads(raw)

    def set_json(self, key: str, value: Any, ttl_seconds: int) -> None:
        self.data[key] = json.dumps(value, default=str)

    def delete(self, *keys: str) -> None:
        for k in keys:
            self.data.pop(k, None)

    def incr(self, key: str) -> int:
        self.data[key] = str(int(self.data.get(key, "0")) + 1)
        return int(self.data[key])

    def get_int(self, key: str) -> int:
        return int(self.data.get(key, "0"))

    def push_capped(self, key: str, value: Any, cap: int) -> None:
        items = self.lists.setdefault(key, [])
        items.insert(0, json.dumps(value, default=str))
        del items[cap:]

    def list_json(self, key: str, limit: int) -> list[Any]:
        return [json.loads(i) for i in self.lists.get(key, [])[:limit]]

    def ping(self) -> bool:
        return True


class ScriptedProvider:
    """Plays back a script of results/exceptions, one per call, and counts calls."""

    def __init__(self, *script: TriageResult | Exception, name: str = "llm:groq") -> None:
        self.name = name
        self._script = list(script)
        self.calls = 0

    def triage(self, text: str, location: str) -> TriageResult:
        self.calls += 1
        item = self._script[min(self.calls - 1, len(self._script) - 1)]
        if isinstance(item, Exception):
            raise item
        return item


class AlwaysRaises:
    def __init__(self, exc: Exception, name: str = "llm:groq") -> None:
        self.name = name
        self.exc = exc
        self.calls = 0

    def triage(self, text: str, location: str) -> TriageResult:
        self.calls += 1
        raise self.exc


def result(
    category: Category = Category.water,
    priority: Priority = Priority.normal,
    summary: str = "Water problem reported",
    confidence: float = 0.9,
) -> TriageResult:
    return TriageResult(category=category, priority=priority, summary=summary, confidence=confidence)


__all__ = ["AlwaysRaises", "InMemoryCache", "ScriptedProvider", "TriageError", "result"]
