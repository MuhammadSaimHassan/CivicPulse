"""FastAPI dependencies. Routes ask for a *service*; they never see a session."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from app.container import Container
from app.core import metrics
from app.repositories.complaint_repository import ComplaintRepository
from app.services.complaint_service import ComplaintService
from app.services.stats_service import StatsService


def get_container(request: Request) -> Container:
    return request.app.state.container  # type: ignore[no-any-return]


ContainerDep = Annotated[Container, Depends(get_container)]


def get_session(container: ContainerDep) -> Iterator[Session]:
    # A unit of work per request. The connection is checked out lazily on the
    # first query and returned when the request ends, whatever happened.
    session = container.session_factory()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


SessionDep = Annotated[Session, Depends(get_session)]


def get_stats_service(container: ContainerDep, session: SessionDep) -> StatsService:
    return StatsService(
        ComplaintRepository(session), container.cache, ttl_seconds=container.settings.stats_cache_ttl_seconds
    )


StatsServiceDep = Annotated[StatsService, Depends(get_stats_service)]


def get_complaint_service(container: ContainerDep, session: SessionDep, stats: StatsServiceDep) -> ComplaintService:
    return ComplaintService(ComplaintRepository(session), container.triage, stats, session.commit)


ComplaintServiceDep = Annotated[ComplaintService, Depends(get_complaint_service)]


def client_ip(request: Request) -> str:
    # Uvicorn runs with --proxy-headers, so request.client is the address nginx
    # or the Ingress put in X-Forwarded-For, not the proxy's own address.
    return request.client.host if request.client else "unknown"


def enforce_rate_limit(request: Request, response: Response, container: ContainerDep) -> None:
    decision = container.rate_limiter.hit(client_ip(request))
    response.headers["X-RateLimit-Limit"] = str(decision.limit)
    response.headers["X-RateLimit-Remaining"] = str(decision.remaining)
    if not decision.allowed:
        metrics.RATE_LIMITED.inc()
        raise HTTPException(
            status_code=429,
            detail=f"Too many complaints from this address. Try again in {decision.retry_after_seconds} s.",
            headers={"Retry-After": str(decision.retry_after_seconds)},
        )
