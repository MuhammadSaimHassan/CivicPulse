"""Composition root: builds the long-lived objects once per process.

This is the only module that knows which concrete Engine, Redis client and
triage provider the app runs with. Tests build their own Container with fakes.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field

from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.db import build_engine, build_session_factory
from app.providers.cache import RedisCache
from app.providers.rate_limiter import RedisRateLimiter
from app.providers.triage.factory import build_provider
from app.repositories.health_repository import HealthRepository
from app.services.health_service import HealthService
from app.services.triage_service import TriageService


@dataclass
class Container:
    settings: Settings
    engine: Engine
    session_factory: sessionmaker[Session]
    cache: RedisCache
    rate_limiter: RedisRateLimiter
    triage: TriageService
    draining: threading.Event = field(default_factory=threading.Event)

    @property
    def health(self) -> HealthService:
        return HealthService(HealthRepository(self.engine), self.cache, self.draining.is_set)

    def close(self) -> None:
        close = getattr(self.triage.primary, "close", None)
        if callable(close):
            close()
        self.cache.close()
        self.engine.dispose()


def build_container(settings: Settings) -> Container:
    engine = build_engine(settings)
    cache = RedisCache.from_url(settings.redis_url)
    return Container(
        settings=settings,
        engine=engine,
        session_factory=build_session_factory(engine),
        cache=cache,
        rate_limiter=RedisRateLimiter(
            cache.client,
            limit=settings.rate_limit_per_window,
            window_seconds=settings.rate_limit_window_seconds,
        ),
        triage=TriageService(
            build_provider(settings),
            cache,
            cache_ttl_seconds=settings.triage_cache_ttl_seconds,
            retry_base_delay_seconds=settings.triage_retry_base_delay_seconds,
        ),
    )
