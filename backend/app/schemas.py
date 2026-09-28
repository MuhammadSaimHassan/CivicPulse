"""HTTP request/response models — the API contract the frontend is typed against.

Changing anything here changes openapi.json; CI regenerates the frontend's
TypeScript types from it and fails if the committed types are stale.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.domain import Category, Priority, Status

ComplaintText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=10, max_length=2000)]
LocationText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=200)]
ContactText = Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)]


class ComplaintCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: ComplaintText = Field(description="What is wrong, in the citizen's own words.")
    location: LocationText
    reporter_contact: ContactText | None = None


class ComplaintOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    text: str
    location: str
    reporter_contact: str | None
    category: Category
    priority: Priority
    status: Status
    ai_summary: str | None
    triaged_by: str
    triage_latency_ms: int
    created_at: datetime
    updated_at: datetime
    allowed_transitions: list[Status] = Field(
        default_factory=list,
        description="Statuses this complaint may move to next. Computed by the server's state machine.",
    )


class TriageInfo(BaseModel):
    provider: str
    confidence: float
    fallback: bool
    cache_hit: bool
    guardrail_applied: bool


class ComplaintCreated(ComplaintOut):
    triage: TriageInfo


class ComplaintPage(BaseModel):
    items: list[ComplaintOut]
    total: int
    page: int
    page_size: int


class StatusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Status


class Stats(BaseModel):
    total: int
    by_category: dict[str, int]
    by_priority: dict[str, int]
    by_status: dict[str, int]
    generated_at: datetime


class TriageOutcomeOut(BaseModel):
    complaint_id: str
    provider: str
    latency_ms: int
    fallback: bool
    cache_hit: bool = False
    error: str | None = None
    at: str


class TriageCacheStats(BaseModel):
    hits: int
    misses: int
    hit_rate: float


class ProvidersMeta(BaseModel):
    active_provider: str
    fallback_provider: str
    triage_cache: TriageCacheStats
    recent: list[TriageOutcomeOut]


class FieldError(BaseModel):
    field: str
    message: str


class ErrorBody(BaseModel):
    detail: str
    errors: list[FieldError] | None = None


class ReadyBody(BaseModel):
    status: str
    checks: dict[str, bool]
    failed: list[str] = []
