"""LLMTriage — the production path.

Talks to any OpenAI-compatible chat-completions endpoint: Groq (default),
Gemini's OpenAI-compatible endpoint, or OpenRouter. We use httpx directly
rather than a vendor SDK so that the timeout, and the mapping from HTTP status
to retryable / non-retryable error, are explicit and visible in this file.
"""

from __future__ import annotations

import httpx

from app.providers.triage.base import (
    MalformedTriageOutput,
    TriageBadRequest,
    TriageRateLimited,
    TriageResult,
    TriageServerError,
    TriageTimeout,
)
from app.providers.triage.prompt import build_messages, parse_triage_output


def raise_for_status(response: httpx.Response) -> None:
    """Translate an HTTP status into our error taxonomy."""
    code = response.status_code
    if code == 429:
        raise TriageRateLimited("HTTP 429")
    if code >= 500:
        raise TriageServerError(f"HTTP {code}")
    if code >= 400:
        # 400/401/403/404: our request is wrong. Retrying cannot fix it.
        raise TriageBadRequest(f"HTTP {code}")


class LLMTriage:
    def __init__(
        self,
        *,
        vendor: str,
        base_url: str,
        model: str,
        api_key: str,
        timeout_seconds: float = 10.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.name = f"llm:{vendor}"
        self._model = model
        # One client per provider instance: connection pooling to the vendor.
        # The key goes into a header here and is never logged anywhere.
        self._client = httpx.Client(
            base_url=base_url.rstrip("/"),
            timeout=httpx.Timeout(timeout_seconds),
            headers={"Authorization": f"Bearer {api_key}"},
            transport=transport,
        )

    def triage(self, text: str, location: str) -> TriageResult:
        body = {
            "model": self._model,
            "messages": build_messages(text, location),
            "temperature": 0,
            "max_tokens": 200,
            "response_format": {"type": "json_object"},  # JSON mode
        }
        try:
            response = self._client.post("/chat/completions", json=body)
        except httpx.TimeoutException as exc:
            raise TriageTimeout(type(exc).__name__) from exc
        except httpx.TransportError as exc:
            # DNS failure, connection refused: transient from our side.
            raise TriageServerError(type(exc).__name__) from exc
        raise_for_status(response)
        try:
            content = response.json()["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise MalformedTriageOutput("unexpected response envelope") from exc
        return parse_triage_output(content)

    def close(self) -> None:
        self._client.close()
