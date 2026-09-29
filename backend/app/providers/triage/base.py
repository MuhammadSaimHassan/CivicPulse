"""The triage contract.

Everything outside providers/triage/ depends on this file only — never on a
concrete provider. Swapping keyword rules for an LLM, or an LLM for a
fine-tuned classifier, is a change to factory.py and nothing else.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from app.domain import Category, Priority


class TriageResult(BaseModel):
    # extra="forbid": a model that invents fields ("urgency", "reasoning") is
    # not following the contract, and we would rather fall back than guess.
    model_config = ConfigDict(extra="forbid")

    category: Category
    priority: Priority
    summary: str = Field(min_length=1, max_length=140)
    confidence: float = Field(ge=0.0, le=1.0)


@runtime_checkable
class TriageProvider(Protocol):
    name: str

    def triage(self, text: str, location: str) -> TriageResult: ...


# --- Error taxonomy ---------------------------------------------------------
# The orchestrator decides retry/fallback from the *class* of error, so each
# provider must translate its transport's failures into one of these.


class TriageError(Exception):
    """Any failure to produce a valid TriageResult."""


class RetryableTriageError(TriageError):
    """Transient: timeout, HTTP 429, HTTP 5xx. Worth exactly one retry."""


class TriageTimeout(RetryableTriageError):
    pass


class TriageRateLimited(RetryableTriageError):
    pass


class TriageServerError(RetryableTriageError):
    pass


class NonRetryableTriageError(TriageError):
    """The request or the response was wrong and will be wrong again."""


class TriageBadRequest(NonRetryableTriageError):
    pass


class MalformedTriageOutput(NonRetryableTriageError):
    """The provider answered, but not with something our schema accepts."""
