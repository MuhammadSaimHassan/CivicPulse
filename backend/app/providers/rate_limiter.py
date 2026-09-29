"""Distributed fixed-window rate limiter in Redis.

Why Redis and not a dict in this process: the HPA runs 2..10 backend pods. An
in-process counter gives every pod its own budget, so four pods would let a
client through four times the limit — and our free LLM tier is measured in
tens of requests per minute. A shared counter in Redis gives one budget per
client IP no matter how many pods answer.

Algorithm: one key per (client, window). INCR it; set its expiry on first use;
reject once it exceeds the limit. INCR is atomic, so two pods racing on the
same key can never both see "under the limit" for the same slot.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

import redis

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class RateLimitDecision:
    allowed: bool
    limit: int
    remaining: int
    retry_after_seconds: int


class RedisRateLimiter:
    def __init__(self, client: redis.Redis, *, limit: int, window_seconds: int, prefix: str = "ratelimit") -> None:
        self._r = client
        self._limit = limit
        self._window = window_seconds
        self._prefix = prefix

    def hit(self, client_id: str, now: float | None = None) -> RateLimitDecision:
        now = time.time() if now is None else now
        window_start = int(now // self._window) * self._window
        key = f"{self._prefix}:{client_id}:{window_start}"
        retry_after = max(1, int(window_start + self._window - now))
        try:
            pipe = self._r.pipeline()
            pipe.incr(key)
            pipe.expire(key, self._window + 1, nx=True)
            count = int(pipe.execute()[0])
        except redis.RedisError as exc:
            # Fail open: a Redis outage should not stop citizens reporting a
            # flood. The LLM layer still has its own fallback, so the worst
            # case is spending quota, not an outage. See docs/RUNBOOK.md.
            log.warning("rate limiter unavailable, failing open", extra={"error": type(exc).__name__})
            return RateLimitDecision(True, self._limit, self._limit, 0)
        remaining = max(0, self._limit - count)
        return RateLimitDecision(count <= self._limit, self._limit, remaining, retry_after)
