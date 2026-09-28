"""Shared fixtures.

Unit tests need nothing. Integration tests (marked `integration`) need a real
PostgreSQL and Redis, reached through TEST_DATABASE_URL / TEST_REDIS_URL. In CI
those are service containers and REQUIRE_INTEGRATION=1 turns "unreachable"
into a failure instead of a skip, so the suite can never go green by silently
testing less.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Iterator

import pytest
import redis
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError

from app.container import Container
from app.core.config import Settings
from app.db import build_engine, build_session_factory
from app.main import create_app
from app.migrate import ALEMBIC_INI
from app.providers.cache import RedisCache
from app.providers.rate_limiter import RedisRateLimiter
from app.providers.triage.base import TriageProvider
from app.providers.triage.simulated import SimulatedTriage
from app.services.triage_service import TriageService

TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL", "postgresql+psycopg://civicpulse:civicpulse@127.0.0.1:5432/civicpulse_test"
)
TEST_REDIS_URL = os.getenv("TEST_REDIS_URL", "redis://127.0.0.1:6379/15")


def _reachable() -> str | None:
    try:
        engine = create_engine(TEST_DATABASE_URL, connect_args={"connect_timeout": 2})
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        engine.dispose()
        redis.Redis.from_url(TEST_REDIS_URL, socket_connect_timeout=2).ping()
    except (OperationalError, redis.RedisError) as exc:
        return f"integration infrastructure unreachable: {type(exc).__name__}"
    return None


@pytest.fixture(scope="session")
def infra() -> None:
    problem = _reachable()
    if problem:
        if os.getenv("REQUIRE_INTEGRATION") == "1":
            pytest.fail(problem)
        pytest.skip(problem)
    cfg = Config(str(ALEMBIC_INI))
    cfg.set_main_option("script_location", str(ALEMBIC_INI.parent / "alembic"))
    cfg.attributes["database_url"] = TEST_DATABASE_URL
    command.downgrade(cfg, "base")  # prove the downgrade path works, every run
    command.upgrade(cfg, "head")


@pytest.fixture
def settings() -> Settings:
    return Settings(
        database_url=TEST_DATABASE_URL,
        redis_url=TEST_REDIS_URL,
        triage_provider="simulated",
        rate_limit_per_window=5,
        rate_limit_window_seconds=60,
        log_level="WARNING",
    )


@pytest.fixture
def clean(infra: None, settings: Settings) -> Iterator[None]:
    engine = create_engine(settings.database_url)
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE complaints"))
    engine.dispose()
    redis.Redis.from_url(settings.redis_url).flushdb()
    yield


ClientFactory = Callable[..., TestClient]


@pytest.fixture
def make_client(clean: None, settings: Settings) -> Iterator[ClientFactory]:
    """Build a TestClient whose container uses the given triage provider."""
    clients: list[TestClient] = []

    def factory(provider: TriageProvider | None = None, **overrides: object) -> TestClient:
        s = settings.model_copy(update=overrides)

        def build(st: Settings) -> Container:
            engine = build_engine(st)
            cache = RedisCache.from_url(st.redis_url)
            return Container(
                settings=st,
                engine=engine,
                session_factory=build_session_factory(engine),
                cache=cache,
                rate_limiter=RedisRateLimiter(
                    cache.client, limit=st.rate_limit_per_window, window_seconds=st.rate_limit_window_seconds
                ),
                triage=TriageService(
                    provider or SimulatedTriage(seed=st.simulated_seed),
                    cache,
                    retry_base_delay_seconds=0.0,  # no real sleeping in tests
                ),
            )

        client = TestClient(create_app(s, container_factory=build))
        client.__enter__()
        clients.append(client)
        return client

    yield factory
    for c in clients:
        c.__exit__(None, None, None)


@pytest.fixture
def client(make_client: ClientFactory) -> TestClient:
    return make_client()


VALID = {"text": "Burst water main flooding Street 12 since fajr", "location": "G-9/2, Islamabad"}
