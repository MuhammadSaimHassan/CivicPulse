"""SimulatedTriage — the deterministic fake CI runs against.

No network, no clock, no randomness that is not seeded. The same (seed, text)
always yields the same result or the same failure, so a red test is a real
regression and never a coin toss.

Failure injection: SIMULATED_FAILURE_RATE of inputs (chosen by hash, so the
*same* inputs fail every run) raise the error named by SIMULATED_FAILURE_MODE.
"""

from __future__ import annotations

import hashlib

from app.providers.triage.base import (
    TriageRateLimited,
    TriageResult,
    TriageServerError,
    TriageTimeout,
)
from app.providers.triage.prompt import parse_triage_output
from app.providers.triage.rules import RuleBasedTriage


class SimulatedTriage:
    name = "simulated"

    def __init__(self, *, seed: int = 42, failure_rate: float = 0.0, failure_mode: str = "timeout") -> None:
        self._seed = seed
        self._failure_rate = failure_rate
        self._failure_mode = failure_mode
        self._rules = RuleBasedTriage()

    def _unit(self, text: str) -> float:
        digest = hashlib.sha256(f"{self._seed}:{text}".encode()).digest()
        return int.from_bytes(digest[:8], "big") / 2**64

    def triage(self, text: str, location: str) -> TriageResult:
        u = self._unit(text)
        if u < self._failure_rate:
            self._fail()
        base = self._rules.triage(text, location)
        # Deterministic, plausible confidence in [0.6, 0.95).
        return base.model_copy(update={"confidence": round(0.6 + 0.35 * u, 3)})

    def _fail(self) -> None:
        mode = self._failure_mode
        if mode == "timeout":
            raise TriageTimeout("simulated timeout")
        if mode == "rate_limit":
            raise TriageRateLimited("simulated HTTP 429")
        if mode == "server_error":
            raise TriageServerError("simulated HTTP 503")
        # "malformed": go through the real validator, exactly as a model's
        # prose answer would.
        parse_triage_output("Sure! The category is probably water.")
