# ADR 0004 — PII and data governance for LLM triage

- **Status:** Accepted
- **Date:** 2026-09-27

## Context

A complaint can contain personal data: the reporter's name, phone number, e-mail, house
number, sometimes a CNIC. Hosted LLM triage sends text to a third party:

- **Groq** (default): processes the request to serve it. Check their current data-use and
  retention terms before relying on them — record what you read and the date here.
- **Google AI Studio (Gemini) free tier**: Google may use free-tier inputs to improve its
  models. Sending raw complaints there would make citizens' personal data training data.
- **Ollama**: nothing leaves the machine.

## Decision

1. **Data minimisation — send only what classification needs.** The model receives the
   complaint body and the location string. `reporter_contact` is **never** sent: it is not a
   parameter of `TriageProvider.triage()` at all, so no provider can send it by accident.
2. **Redact before sending.** `redact_pii()` (`backend/app/providers/triage/prompt.py`)
   replaces Pakistani mobile numbers (`03xx-xxxxxxx`, `+92 3xx…`), other long digit runs,
   e-mail addresses and CNIC numbers with `[phone]`, `[email]`, `[cnic]` in both the text and
   the location, before the prompt is built. Covered by
   `tests/test_providers.py::test_pii_is_redacted_before_it_leaves_the_machine`.
3. **Default to Groq, not the Gemini free tier**, for the production path. Gemini remains
   supported (OpenAI-compatible endpoint) for experiments with synthetic or seed data.
4. **An offline path exists**: `TRIAGE_PROVIDER=ollama` keeps all data on our machine, at a
   measured cost in accuracy and latency (`docs/TRIAGE.md`).
5. **Logs never contain complaint text or contact details.** Log lines carry the complaint
   id, provider, error class and latency. The API key is a `SecretStr` and never logged;
   it comes from the environment, a Kubernetes Secret, or a GitHub Secret.
6. **Stored data**: complaints (including `reporter_contact`) live only in our PostgreSQL.
   The Redis triage cache stores the *model's answer* keyed by a SHA-256 of the normalised
   text — not the text itself.

## What still leaves the machine, and why that is acceptable

The redacted complaint body and location go to Groq over TLS. A name typed into free text
("my name is Ali, house 42") is not reliably detectable by regex and may still be sent.
We accept that residual exposure because: the text is needed to classify at all; the
highest-risk identifiers (phone, e-mail, CNIC) are removed; the provider is not a free
tier that trains on inputs; and a municipality that cannot accept it can switch to
`ollama` with one environment variable. Name detection (NER-based redaction) is the next
step if the risk assessment changes.

## Consequences

- Operators still see full contact details in the dashboard (they need them to follow up);
  the model never does.
- Redaction can over-match (e.g. a long meter number becomes `[phone]`). That costs a little
  context and nothing else: category and priority do not depend on the digits.
