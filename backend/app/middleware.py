"""Request middleware: request_id propagation, JSON access log, Prometheus."""

from __future__ import annotations

import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.core import metrics
from app.core.logging import request_id_var

log = logging.getLogger("civicpulse.access")

_QUIET_PATHS = {"/health", "/ready", "/metrics"}


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Accept the caller's id (nginx, the Ingress, another service) so one
        # request can be followed across every hop; mint one if absent.
        incoming = request.headers.get("x-request-id", "")
        request_id = incoming if 0 < len(incoming) <= 128 else uuid.uuid4().hex
        token = request_id_var.set(request_id)
        start = time.perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            elapsed = time.perf_counter() - start
            route = request.scope.get("route")
            # Label by route template (/api/complaints/{complaint_id}), never by
            # raw path — raw paths would give Prometheus one series per UUID.
            route_label = getattr(route, "path", "unmatched")
            metrics.REQUEST_COUNT.labels(request.method, route_label, str(status)).inc()
            metrics.REQUEST_LATENCY.labels(request.method, route_label).observe(elapsed)
            if request.url.path not in _QUIET_PATHS:
                log.info(
                    "request",
                    extra={
                        "method": request.method,
                        "path": request.url.path,
                        "status": status,
                        "duration_ms": round(elapsed * 1000, 1),
                        "client": request.client.host if request.client else None,
                    },
                )
            request_id_var.reset(token)
