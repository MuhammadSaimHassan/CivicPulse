"""Liveness, readiness and metrics.

/health  — liveness. "Is the process alive?" Touches nothing external. If this
           checked the database, a slow database would make Kubernetes restart
           every backend pod at once: a DB hiccup becomes a full outage.
/ready   — readiness. "Should traffic be sent here?" Checks Postgres and Redis.
           Failing it only removes the pod from the Service's endpoints.
"""

from __future__ import annotations

from fastapi import APIRouter, Response
from fastapi.responses import JSONResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from app.deps import ContainerDep
from app.schemas import ReadyBody

router = APIRouter(tags=["ops"])


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "alive"}


@router.get("/ready", response_model=ReadyBody, responses={503: {"model": ReadyBody}})
def ready(container: ContainerDep) -> JSONResponse:
    ok, checks, failed = container.health.readiness()
    body = ReadyBody(status="ready" if ok else "not_ready", checks=checks, failed=failed)
    return JSONResponse(status_code=200 if ok else 503, content=body.model_dump())


@router.get("/metrics", include_in_schema=False)
def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
