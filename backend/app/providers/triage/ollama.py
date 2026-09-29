"""OllamaTriage — the fully offline path.

Same interface, same prompt, same validator; a 1B-parameter model running in
a container in the Compose stack. No key, no rate limit, no PII leaving the
machine. Slower on CPU and worse at classification — which is the measured
buy-versus-host trade-off (see docs/TRIAGE.md).
"""

from __future__ import annotations

import httpx

from app.providers.triage.base import (
    MalformedTriageOutput,
    TriageResult,
    TriageServerError,
    TriageTimeout,
)
from app.providers.triage.llm import raise_for_status
from app.providers.triage.prompt import build_messages, parse_triage_output


class OllamaTriage:
    name = "llm:ollama"

    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        timeout_seconds: float = 10.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._model = model
        self._client = httpx.Client(
            base_url=base_url.rstrip("/"),
            timeout=httpx.Timeout(timeout_seconds),
            transport=transport,
        )

    def triage(self, text: str, location: str) -> TriageResult:
        body = {
            "model": self._model,
            "messages": build_messages(text, location),
            "stream": False,
            # Ollama constrains decoding to this JSON schema — structured
            # output enforced at generation time, then validated again by us.
            "format": TriageResult.model_json_schema(),
            "options": {"temperature": 0},
        }
        try:
            response = self._client.post("/api/chat", json=body)
        except httpx.TimeoutException as exc:
            raise TriageTimeout(type(exc).__name__) from exc
        except httpx.TransportError as exc:
            raise TriageServerError(type(exc).__name__) from exc
        raise_for_status(response)
        try:
            content = response.json()["message"]["content"]
        except (ValueError, KeyError, TypeError) as exc:
            raise MalformedTriageOutput("unexpected response envelope") from exc
        return parse_triage_output(content)

    def close(self) -> None:
        self._client.close()
