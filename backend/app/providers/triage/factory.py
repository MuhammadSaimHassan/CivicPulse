"""Select the triage provider from TRIAGE_PROVIDER. The only place that knows
the concrete classes exist."""

from __future__ import annotations

from app.core.config import Settings
from app.providers.triage.base import TriageProvider
from app.providers.triage.llm import LLMTriage
from app.providers.triage.ollama import OllamaTriage
from app.providers.triage.rules import RuleBasedTriage
from app.providers.triage.simulated import SimulatedTriage


def build_provider(settings: Settings) -> TriageProvider:
    match settings.triage_provider:
        case "llm":
            return LLMTriage(
                vendor=settings.llm_vendor,
                base_url=settings.llm_base_url,
                model=settings.llm_model,
                api_key=settings.llm_api_key.get_secret_value(),
                timeout_seconds=settings.triage_timeout_seconds,
            )
        case "ollama":
            return OllamaTriage(
                base_url=settings.ollama_base_url,
                model=settings.ollama_model,
                timeout_seconds=settings.triage_timeout_seconds,
            )
        case "simulated":
            return SimulatedTriage(
                seed=settings.simulated_seed,
                failure_rate=settings.simulated_failure_rate,
                failure_mode=settings.simulated_failure_mode,
            )
        case _:
            return RuleBasedTriage()
