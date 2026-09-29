"""Stats and observability endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Response

from app.deps import ContainerDep, StatsServiceDep
from app.schemas import ProvidersMeta, Stats, TriageCacheStats, TriageOutcomeOut

router = APIRouter(prefix="/api", tags=["stats"])


@router.get("/stats", response_model=Stats)
def get_stats(response: Response, service: StatsServiceDep) -> Stats:
    stats, hit = service.get()
    response.headers["X-Cache"] = "HIT" if hit else "MISS"
    # The browser must not add its own cache layer on top of ours, or the
    # X-Cache value the Stats view shows would be a lie.
    response.headers["Cache-Control"] = "no-store"
    return stats


@router.get("/meta/providers", response_model=ProvidersMeta)
def get_providers(container: ContainerDep) -> ProvidersMeta:
    triage = container.triage
    return ProvidersMeta(
        active_provider=triage.primary.name,
        fallback_provider=triage.fallback.name,
        triage_cache=TriageCacheStats.model_validate(triage.cache_stats()),
        recent=[TriageOutcomeOut.model_validate(o) for o in triage.recent_outcomes(20)],
    )
