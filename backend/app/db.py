"""Database engine and session factory. Imported only by the composition root
(app/deps.py, app/main.py) and by repositories — never by routes."""

from __future__ import annotations

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings


def build_engine(settings: Settings) -> Engine:
    return create_engine(
        settings.database_url,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_pre_ping=True,  # a restarted Postgres pod should not poison the pool
        pool_timeout=5,
        connect_args={"connect_timeout": 3},
    )


def build_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False)
