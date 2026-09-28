"""Readiness check for the database. Still SQL, so still a repository."""

from __future__ import annotations

from sqlalchemy import Engine, text
from sqlalchemy.exc import SQLAlchemyError


class HealthRepository:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def ping(self) -> bool:
        try:
            with self._engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return True
        except SQLAlchemyError:
            return False
