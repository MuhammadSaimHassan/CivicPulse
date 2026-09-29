"""Triage orchestration: cache → provider → (retry once) → fallback.

The rule this file exists to enforce: a citizen never sees a 500 because a
third party was slow, rate-limited or wrong. Whatever the provider does —
times out, returns 429, returns prose, raises something we never anticipated —
the complaint is still triaged (by rules) and still saved.
"""

from __future__ import annotations

import hashlib
import logging
import random
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime

from pydantic import ValidationError

from app.core import metrics
from app.providers.cache import Cache
from app.providers.triage.base import RetryableTriageError, TriageProvider, TriageResult
from app.providers.triage.rules import RuleBasedTriage, hazard_priority_floor, max_priority

log = logging.getLogger(__name__)

OUTCOMES_KEY = "triage:outcomes"
CACHE_HITS_KEY = "triage:cache:hits"
CACHE_MISSES_KEY = "triage:cache:misses"
CACHE_KEY_VERSION = "v1"  # bump when the prompt changes, to invalidate old answers


@dataclass(frozen=True)
class TriageOutcome:
    result: TriageResult
    triaged_by: str
    latency_ms: int
    fallback: bool
    cache_hit: bool
    error: str | None = None
    guardrail_applied: bool = False


def content_hash(text: str) -> str:
    """Normalise case and whitespace so trivially different duplicates share a key."""
    normalised = " ".join(text.lower().split())
    return hashlib.sha256(normalised.encode()).hexdigest()


class TriageService:
    def __init__(
        self,
        primary: TriageProvider,
        cache: Cache,
        *,
        cache_ttl_seconds: int = 24 * 3600,
        retry_base_delay_seconds: float = 0.5,
        sleep: Callable[[float], None] = time.sleep,
        jitter: Callable[[], float] = random.random,
        clock: Callable[[], float] = time.perf_counter,
    ) -> None:
        self.primary = primary
        self.fallback = RuleBasedTriage()
        self._cache = cache
        self._ttl = cache_ttl_seconds
        self._base_delay = retry_base_delay_seconds
        self._sleep = sleep
        self._jitter = jitter
        self._clock = clock

    @property
    def uses_model(self) -> bool:
        return self.primary.name != "rules"

    # ------------------------------------------------------------------ API
    def triage(self, complaint_id: uuid.UUID, text: str, location: str) -> TriageOutcome:
        start = self._clock()
        if not self.uses_model:
            outcome = TriageOutcome(self.fallback.triage(text, location), "rules", 0, False, False)
        else:
            outcome = self._triage_with_model(complaint_id, text, location)
        latency_ms = int((self._clock() - start) * 1000)
        outcome = replace(outcome, latency_ms=latency_ms)
        metrics.TRIAGE_LATENCY.labels(outcome.triaged_by).observe(latency_ms / 1000)
        self._record(complaint_id, outcome)
        return outcome

    def cache_stats(self) -> dict[str, float | int]:
        hits = self._cache.get_int(CACHE_HITS_KEY)
        misses = self._cache.get_int(CACHE_MISSES_KEY)
        total = hits + misses
        return {"hits": hits, "misses": misses, "hit_rate": round(hits / total, 3) if total else 0.0}

    def recent_outcomes(self, limit: int = 20) -> list[dict[str, object]]:
        return self._cache.list_json(OUTCOMES_KEY, limit)

    # ------------------------------------------------------------ internals
    def _triage_with_model(self, complaint_id: uuid.UUID, text: str, location: str) -> TriageOutcome:
        key = f"triage:{CACHE_KEY_VERSION}:{self.primary.name}:{content_hash(text)}"
        cached = self._from_cache(key)
        if cached is not None:
            metrics.TRIAGE_CACHE.labels("hit").inc()
            self._cache.incr(CACHE_HITS_KEY)
            return self._guard(cached, text, self.primary.name, cache_hit=True)
        metrics.TRIAGE_CACHE.labels("miss").inc()
        self._cache.incr(CACHE_MISSES_KEY)

        try:
            result = self._call_with_retry(text, location)
        except Exception as exc:  # noqa: BLE001 — deliberately total: never a 500
            return self._fall_back(complaint_id, text, location, exc)

        # Only model answers are cached. Caching a fallback would pin a
        # keyword guess in place for 24 h after the model recovered.
        self._cache.set_json(key, result.model_dump(mode="json"), self._ttl)
        return self._guard(result, text, self.primary.name, cache_hit=False)

    def _call_with_retry(self, text: str, location: str) -> TriageResult:
        try:
            return self.primary.triage(text, location)
        except RetryableTriageError as exc:
            # Exactly one retry, only for timeout / 429 / 5xx, with jitter so
            # N pods that were throttled together do not retry in lock-step.
            delay = self._base_delay * (1 + self._jitter())
            log.info(
                "triage retry",
                extra={"provider": self.primary.name, "error": type(exc).__name__, "delay_s": round(delay, 3)},
            )
            self._sleep(delay)
            return self.primary.triage(text, location)
        # NonRetryableTriageError (400, malformed output) propagates at once.

    def _from_cache(self, key: str) -> TriageResult | None:
        raw = self._cache.get_json(key)
        if raw is None:
            return None
        try:
            # Validate again: the cache is outside the process, so treat it as untrusted too.
            return TriageResult.model_validate(raw)
        except ValidationError:
            self._cache.delete(key)
            return None

    def _guard(self, result: TriageResult, text: str, triaged_by: str, *, cache_hit: bool) -> TriageOutcome:
        """Hazard floor: a schema can constrain the *shape* of an answer but not
        its truth. If the wording contains a hazard ("burst", "live wire", ...)
        no model answer — honest mistake or obeyed injection — may rank it below high."""
        floor = hazard_priority_floor(text)
        guarded = max_priority(result.priority, floor)
        applied = guarded != result.priority
        if applied:
            result = result.model_copy(update={"priority": guarded})
        return TriageOutcome(result, triaged_by, 0, False, cache_hit, None, applied)

    def _fall_back(self, complaint_id: uuid.UUID, text: str, location: str, exc: Exception) -> TriageOutcome:
        error = type(exc).__name__
        metrics.TRIAGE_FALLBACK.labels(self.primary.name, error).inc()
        log.warning(
            "triage fallback",
            extra={"complaint_id": str(complaint_id), "provider": self.primary.name, "error": error},
        )
        return TriageOutcome(self.fallback.triage(text, location), "rules:fallback", 0, True, False, error)

    def _record(self, complaint_id: uuid.UUID, outcome: TriageOutcome) -> None:
        self._cache.push_capped(
            OUTCOMES_KEY,
            {
                "complaint_id": str(complaint_id),
                "provider": outcome.triaged_by,
                "latency_ms": outcome.latency_ms,
                "fallback": outcome.fallback,
                "cache_hit": outcome.cache_hit,
                "error": outcome.error,
                "at": datetime.now(UTC).isoformat(),
            },
            cap=20,
        )
