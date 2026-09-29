"""Aggregate statistics with a read-through Redis cache.

Why both a TTL *and* explicit invalidation:
- Invalidation on write makes a new complaint show up in the stats at once.
- The 30 s TTL is the safety net for writes that bypass this service (a psql
  session, a seed run, a missed invalidation after a crash between commit and
  delete). Invalidation alone would make one missed delete a permanent lie;
  TTL alone would make every submission look lost for up to 30 s.
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.providers.cache import Cache
from app.repositories.complaint_repository import ComplaintRepository
from app.schemas import Stats

STATS_KEY = "stats:v1"


class StatsService:
    def __init__(self, repo: ComplaintRepository, cache: Cache, *, ttl_seconds: int = 30) -> None:
        self._repo = repo
        self._cache = cache
        self._ttl = ttl_seconds

    def get(self) -> tuple[Stats, bool]:
        cached = self._cache.get_json(STATS_KEY)
        if cached is not None:
            return Stats.model_validate(cached), True
        stats = Stats(
            total=self._repo.total(),
            by_category=self._repo.counts_by("category"),
            by_priority=self._repo.counts_by("priority"),
            by_status=self._repo.counts_by("status"),
            generated_at=datetime.now(UTC),
        )
        self._cache.set_json(STATS_KEY, stats.model_dump(mode="json"), self._ttl)
        return stats, False

    def invalidate(self) -> None:
        self._cache.delete(STATS_KEY)
