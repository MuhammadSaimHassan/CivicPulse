"""Complaint business rules: validate → triage → persist; status changes."""

from __future__ import annotations

import uuid
from collections.abc import Callable

from app.domain import Status
from app.repositories.complaint_repository import ComplaintFilter, ComplaintRepository
from app.repositories.models import ComplaintRow
from app.schemas import ComplaintCreate, ComplaintCreated, ComplaintOut, ComplaintPage, TriageInfo
from app.services.errors import ConcurrentUpdate, NotFound
from app.services.state_machine import allowed_next, check_transition
from app.services.stats_service import StatsService
from app.services.triage_service import TriageService


def to_out(row: ComplaintRow) -> ComplaintOut:
    out = ComplaintOut.model_validate(row)
    out.allowed_transitions = allowed_next(row.status)
    return out


class ComplaintService:
    def __init__(
        self,
        repo: ComplaintRepository,
        triage: TriageService,
        stats: StatsService,
        commit: Callable[[], None],
    ) -> None:
        self._repo = repo
        self._triage = triage
        self._stats = stats
        self._commit = commit

    def create(self, payload: ComplaintCreate) -> ComplaintCreated:
        complaint_id = uuid.uuid4()
        # Triage happens BEFORE the first query, so no database connection is
        # held open while we wait up to 10 s (x2) on a third party.
        outcome = self._triage.triage(complaint_id, payload.text, payload.location)
        row = self._repo.add(
            id=complaint_id,
            text=payload.text,
            location=payload.location,
            reporter_contact=payload.reporter_contact or None,
            category=outcome.result.category,
            priority=outcome.result.priority,
            ai_summary=outcome.result.summary,
            triaged_by=outcome.triaged_by,
            triage_latency_ms=outcome.latency_ms,
        )
        self._commit()
        # Invalidate after commit: invalidating first would let a concurrent
        # /api/stats re-cache the pre-commit numbers for 30 s.
        self._stats.invalidate()
        base = to_out(row)
        return ComplaintCreated(
            **base.model_dump(),
            triage=TriageInfo(
                provider=outcome.triaged_by,
                confidence=outcome.result.confidence,
                fallback=outcome.fallback,
                cache_hit=outcome.cache_hit,
                guardrail_applied=outcome.guardrail_applied,
            ),
        )

    def get(self, complaint_id: uuid.UUID) -> ComplaintOut:
        row = self._repo.get(complaint_id)
        if row is None:
            raise NotFound(complaint_id)
        return to_out(row)

    def list(self, flt: ComplaintFilter, *, page: int, page_size: int) -> ComplaintPage:
        rows, total = self._repo.search(flt, page=page, page_size=page_size)
        return ComplaintPage(items=[to_out(r) for r in rows], total=total, page=page, page_size=page_size)

    def change_status(self, complaint_id: uuid.UUID, new_status: Status) -> ComplaintOut:
        row = self._repo.get(complaint_id)
        if row is None:
            raise NotFound(complaint_id)
        check_transition(row.status, new_status)  # raises InvalidTransition -> 409
        updated = self._repo.transition_status(complaint_id, expected=row.status, new=new_status)
        if updated is None:
            raise ConcurrentUpdate(complaint_id)
        self._commit()
        self._stats.invalidate()
        return to_out(updated)
