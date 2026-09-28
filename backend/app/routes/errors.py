"""Map exceptions to HTTP responses with one consistent error body:

{"detail": "<human-readable message>", "errors": [{"field": ..., "message": ...}]}
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.services.errors import ConcurrentUpdate, NotFound
from app.services.state_machine import InvalidTransition

log = logging.getLogger(__name__)


def _field_name(loc: tuple[object, ...]) -> str:
    # ("body", "text") -> "text"; ("query", "page_size") -> "page_size"
    parts = [str(p) for p in loc if p not in ("body", "query", "path")]
    return ".".join(parts) or "body"


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        errors = [{"field": _field_name(tuple(e["loc"])), "message": e["msg"]} for e in exc.errors()]
        return JSONResponse(status_code=400, content={"detail": "Validation failed", "errors": errors})

    @app.exception_handler(NotFound)
    async def not_found(_: Request, exc: NotFound) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(InvalidTransition)
    async def invalid_transition(_: Request, exc: InvalidTransition) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @app.exception_handler(ConcurrentUpdate)
    async def concurrent_update(_: Request, exc: ConcurrentUpdate) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @app.exception_handler(StarletteHTTPException)
    async def http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail}, headers=exc.headers)

    @app.exception_handler(Exception)
    async def unhandled(_: Request, exc: Exception) -> JSONResponse:
        log.exception("unhandled error", extra={"error": type(exc).__name__})
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})
