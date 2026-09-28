"""FastAPI application factory."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI

from app.container import Container, build_container
from app.core.config import Settings, get_settings
from app.core.logging import configure_logging
from app.middleware import RequestContextMiddleware
from app.routes import complaints, health, stats
from app.routes.errors import install_error_handlers

log = logging.getLogger(__name__)


def create_app(
    settings: Settings | None = None,
    container_factory: Callable[[Settings], Container] = build_container,
) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        container = container_factory(settings)
        app.state.container = container
        provider = container.triage.primary.name
        if settings.triage_provider == "llm" and not settings.llm_api_key.get_secret_value():
            log.warning("TRIAGE_PROVIDER=llm but LLM_API_KEY is empty; every call will fall back to rules")
        log.info("startup", extra={"env": settings.app_env, "triage_provider": provider})
        yield
        # Runs after uvicorn has stopped accepting connections and drained
        # in-flight requests (see app/server.py): now release the pools.
        log.info("shutdown: closing database pool and redis connections")
        container.close()
        log.info("shutdown complete")

    app = FastAPI(
        title="CivicPulse API",
        version="1.0.0",
        description="Municipal complaint intake, AI triage and operations.",
        lifespan=lifespan,
    )
    app.add_middleware(RequestContextMiddleware)
    install_error_handlers(app)
    app.include_router(complaints.router)
    app.include_router(stats.router)
    app.include_router(health.router)
    _document_400_not_422(app)
    return app


def _document_400_not_422(app: FastAPI) -> None:
    """We answer validation errors with 400 + ErrorBody (routes/errors.py), so
    remove FastAPI's default 422 entries: the published contract — and the
    TypeScript client generated from it — must describe what we actually send."""
    original = app.openapi

    def openapi() -> dict[str, Any]:
        if app.openapi_schema:
            return app.openapi_schema
        schema = original()
        for path in schema.get("paths", {}).values():
            for operation in path.values():
                operation.get("responses", {}).pop("422", None)
        for name in ("HTTPValidationError", "ValidationError"):
            schema.get("components", {}).get("schemas", {}).pop(name, None)
        app.openapi_schema = schema
        return schema

    app.openapi = openapi  # type: ignore[method-assign]
