"""`python -m app.migrate [--seed]` — apply migrations, optionally seed.

Runs as a one-shot Compose service and as a Kubernetes initContainer — never
inside application startup. With N backend replicas starting at once, N
initContainers race; a PostgreSQL advisory lock makes exactly one of them run
`alembic upgrade head` while the others wait and then find nothing to do.
"""

from __future__ import annotations

import argparse
import logging
import time
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError

from app.core.config import get_settings
from app.core.logging import configure_logging

log = logging.getLogger("civicpulse.migrate")
LOCK_ID = 727_001  # arbitrary, constant, shared by every replica
ALEMBIC_INI = Path(__file__).resolve().parent.parent / "alembic.ini"


def wait_for_database(url: str, attempts: int = 30) -> None:
    engine = create_engine(url)
    try:
        for attempt in range(1, attempts + 1):
            try:
                with engine.connect() as conn:
                    conn.execute(text("SELECT 1"))
                return
            except OperationalError:
                log.info("waiting for database", extra={"attempt": attempt})
                time.sleep(2)
        raise SystemExit("database never became reachable")
    finally:
        engine.dispose()


def upgrade(url: str) -> None:
    cfg = Config(str(ALEMBIC_INI))
    cfg.set_main_option("script_location", str(ALEMBIC_INI.parent / "alembic"))
    cfg.attributes["database_url"] = url
    engine = create_engine(url)
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT pg_advisory_lock(:id)"), {"id": LOCK_ID})
            try:
                command.upgrade(cfg, "head")
            finally:
                conn.execute(text("SELECT pg_advisory_unlock(:id)"), {"id": LOCK_ID})
                conn.commit()
    finally:
        engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", action="store_true", help="load seed data after migrating")
    args = parser.parse_args()
    settings = get_settings()
    configure_logging(settings.log_level)
    wait_for_database(settings.database_url)
    upgrade(settings.database_url)
    log.info("migrations at head")
    if args.seed:
        from app.seed import run as run_seed

        run_seed()


if __name__ == "__main__":
    main()
