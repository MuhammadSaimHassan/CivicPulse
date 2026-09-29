"""Migrations and seed."""

from __future__ import annotations

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, text

from app.core.config import Settings
from app.repositories.models import Base
from app.seed import SEED_COMPLAINTS, run

pytestmark = pytest.mark.integration


def test_orm_model_matches_the_migrated_schema(infra: None, settings: Settings) -> None:
    engine = create_engine(settings.database_url)
    with engine.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)
    engine.dispose()
    assert diff == [], f"models.py and alembic/versions disagree: {diff}"


def test_seed_is_idempotent(clean: None, settings: Settings, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", settings.database_url)
    from app.core.config import get_settings

    get_settings.cache_clear()
    try:
        assert run() == len(SEED_COMPLAINTS) >= 30
        assert run() == 0  # second run changes nothing
    finally:
        get_settings.cache_clear()
    engine = create_engine(settings.database_url)
    with engine.connect() as conn:
        total = conn.execute(text("SELECT count(*) FROM complaints")).scalar_one()
        categories = conn.execute(text("SELECT count(DISTINCT category) FROM complaints")).scalar_one()
    engine.dispose()
    assert total == len(SEED_COMPLAINTS)
    assert categories == 6  # every category represented
