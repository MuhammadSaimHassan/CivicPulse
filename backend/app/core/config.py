"""Application settings, read once from the environment.

Every value here can be overridden by an environment variable of the same
name (case-insensitive). Nothing secret has a real default: the LLM key comes
from the environment, a Kubernetes Secret, or a GitHub Secret — never a file
in the repository.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

ProviderName = Literal["llm", "ollama", "rules", "simulated"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, extra="ignore")

    app_env: str = "dev"
    log_level: str = "INFO"

    # --- Data layer -------------------------------------------------------
    # Service names, never localhost: inside Compose/Kubernetes "localhost" is
    # the container itself, not the database.
    database_url: str = "postgresql+psycopg://civicpulse:civicpulse@postgres:5432/civicpulse"
    db_pool_size: int = 5
    db_max_overflow: int = 5

    # --- Cache layer ------------------------------------------------------
    redis_url: str = "redis://redis:6379/0"
    stats_cache_ttl_seconds: int = 30
    triage_cache_ttl_seconds: int = 24 * 60 * 60
    rate_limit_per_window: int = 10
    rate_limit_window_seconds: int = 60

    # --- AI layer ---------------------------------------------------------
    triage_provider: ProviderName = "rules"
    triage_timeout_seconds: float = 10.0
    triage_retry_base_delay_seconds: float = 0.5

    # OpenAI-compatible endpoint (Groq by default; Gemini/OpenRouter also work).
    llm_vendor: Literal["groq", "gemini", "openrouter"] = "groq"
    llm_base_url: str = "https://api.groq.com/openai/v1"
    llm_model: str = "llama-3.1-8b-instant"
    llm_api_key: SecretStr = SecretStr("")

    ollama_base_url: str = "http://ollama:11434"
    ollama_model: str = "llama3.2:1b"

    # Deterministic fake for CI.
    simulated_seed: int = 42
    simulated_failure_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    simulated_failure_mode: Literal["timeout", "rate_limit", "server_error", "malformed"] = "timeout"

    # --- Shutdown ---------------------------------------------------------
    shutdown_grace_seconds: int = 20


@lru_cache
def get_settings() -> Settings:
    return Settings()
