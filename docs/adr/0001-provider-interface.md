# ADR 0001 — Triage behind a provider interface, with a rules fallback

- **Status:** Accepted
- **Date:** 2026-09-27

## Context

Complaint text has to be read to be routed: a dropdown fails because citizens pick
"Other" and cannot judge urgency. The reader will change over the life of the system —
keyword rules today, a hosted LLM now, perhaps a fine-tuned classifier later — and the
current reader is a third party we do not control. It will be slow, rate-limited
(HTTP 429), down (5xx), or simply wrong (prose instead of JSON, an invented category,
a 400-character "one-line" summary).

## Decision

1. **One interface.** `TriageProvider` (`backend/app/providers/triage/base.py`) is a
   `Protocol` with a `name` and `triage(text, location) -> TriageResult`. `TriageResult`
   is a Pydantic model with `extra="forbid"`, enum-typed `category`/`priority`,
   `summary ≤ 140`, `0 ≤ confidence ≤ 1`.
2. **Four implementations**, chosen only in `factory.py` by `TRIAGE_PROVIDER`:
   `LLMTriage` (any OpenAI-compatible endpoint: Groq default, Gemini, OpenRouter),
   `OllamaTriage` (offline, in Compose), `RuleBasedTriage` (deterministic, never fails),
   `SimulatedTriage` (seeded fake with failure injection, for CI).
3. **A typed error taxonomy.** Providers translate transport failures into
   `RetryableTriageError` (timeout, 429, 5xx) or `NonRetryableTriageError`
   (400/401/403, malformed output). The orchestrator decides from the class, not from
   provider-specific details.
4. **Orchestration lives in one service** (`services/triage_service.py`): content-hash
   cache → provider (10 s timeout) → one jittered retry on retryable errors only →
   fallback to `RuleBasedTriage` with `triaged_by = "rules:fallback"`, a WARNING log line
   and a Prometheus counter. The catch is deliberately total (`except Exception`): no
   third-party failure may turn into a 500 for a citizen.
5. **A hazard guardrail** after the model: if the text contains hazard words
   (burst, live wire, open manhole…), priority is at least `high` whatever the model said.

## Consequences

- Swapping the model is a configuration change; adding a new kind of reader is one new
  class plus one `case` in the factory. Nothing in routes/, repositories/ or the frontend
  changes.
- CI is deterministic by construction (`TRIAGE_PROVIDER=simulated`, fakes injected in
  tests) — no `sleep()`, no re-runs.
- The rules fallback is worse than the model (see `docs/TRIAGE.md`), so a long provider
  outage degrades classification quality. That is visible, not silent: `/api/meta/providers`,
  the `civicpulse_triage_fallback_total` metric, and the dashboard's provider column.
- Fallback answers are **not** cached, so the system returns to model answers as soon as
  the provider recovers.

## Alternatives considered

- **Call the LLM SDK directly from the route.** Four lines, and the entire failure surface
  of a third party inside our request handler. Rejected.
- **Retry until success.** Multiplies load on a provider that is already rate-limiting us
  and keeps a citizen waiting; one retry with jitter is the compromise.
- **Fail the request when the model fails.** A burst water main is still a burst water main
  when Groq is down.
