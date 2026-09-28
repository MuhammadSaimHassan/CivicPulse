"""Readiness: is this pod able to serve real traffic right now?"""

from __future__ import annotations

from collections.abc import Callable

from app.providers.cache import Cache
from app.repositories.health_repository import HealthRepository


class HealthService:
    def __init__(self, db: HealthRepository, cache: Cache, is_draining: Callable[[], bool]) -> None:
        self._db = db
        self._cache = cache
        self._is_draining = is_draining

    def readiness(self) -> tuple[bool, dict[str, bool], list[str]]:
        checks = {"postgres": self._db.ping(), "redis": self._cache.ping()}
        failed = [name for name, ok in checks.items() if not ok]
        if self._is_draining():
            # After SIGTERM, report not-ready so the endpoint controller stops
            # routing to us while in-flight requests finish.
            failed.append("shutting_down")
        return not failed, checks, failed
