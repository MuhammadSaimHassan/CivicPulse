# AI usage

Course policy (§5.5): honest attribution, not avoidance. This file says which tools
were used, what they produced, and what we changed afterwards and why.

## Tools

| tool | how it was used |
|---|---|
| Claude (Anthropic, Claude Opus 5.5, via claude.ai), 2026-09-27 | Generated the initial version of the whole repository from the assignment brief: backend, frontend, Dockerfiles, Compose files, Kubernetes manifests, GitHub Actions workflows, scripts and the first drafts of every document in `docs/`. |
| TODO(team) | Add any other assistant you use from here on (Copilot, ChatGPT, …) and for what. |

## What the assistant produced

Effectively all of the initial code and configuration, including:

- **Backend** (`backend/`): the four-layer structure, all endpoints, the triage providers
  and orchestration (retry/fallback/cache/guardrail), Redis cache and rate limiter, Alembic
  migration, idempotent seed and its complaint texts, graceful-shutdown server, JSON
  logging, Prometheus metrics, and the test suite.
- **Frontend** (`frontend/`): the three views, typed API client (types generated from the
  backend's OpenAPI by `openapi-typescript`), error boundary, validation, styles and tests.
- **Infrastructure**: both Dockerfiles, nginx config, `compose.yaml`, `compose.prod.yaml`,
  all of `k8s/`, the three workflows, `scripts/`, `load/`, `observability/`.
- **Docs**: README, ADRs 0001–0004, RUNBOOK, ENGINEERING-NOTES, TRIAGE, this file.
- **Evaluation labels** in `backend/tools/eval_triage.py` (the "correct" category/priority
  for each test complaint) were drafted by the assistant and must be reviewed by us.

## How it was verified before handover

The assistant ran, in its own Linux sandbox (Docker Hub was not reachable from it, so no
container images could be pulled or built there):

- Backend: `ruff`, `ruff format --check`, `mypy --strict` clean; **90 pytest tests passing
  against a real PostgreSQL 16 and Redis 7**, 93% coverage of `app/`; migrations up/down/up;
  seed run twice (second run inserts 0 rows).
- A live backend process: a request in flight while `SIGTERM` was sent completed with 201
  before the process closed its pools; an unreachable LLM produced one jittered retry, a
  `triage fallback` WARNING with the request id, and a 201 with `rules:fallback`.
- Frontend: `eslint`, `tsc --noEmit`, 13 Vitest tests, production build.
- nginx: the frontend's `nginx.conf` + rendered template were run with a local nginx against
  the live backend (proxying, SPA fallback, `/config.js`, caching and security headers).
  This caught a real bug: `add_header` inside a `location` block silently removed the
  server-level security headers; fixed with a `map` in `nginx.conf`.
- `docker compose config` for both Compose files; `kustomize build | kubeconform -strict`
  for both overlays (18/18 valid, incl. the VPA CRD); `actionlint` on all workflows;
  build-context sizes measured with and without `.dockerignore`.

**Not verified by the assistant** (needs Docker Hub and a real cluster — this is ours to do):
building and running the images, the Compose stack end to end, the k3d deployment, the HPA
load test, the VPA loop, the CD pipeline on GitHub, and every screenshot in `docs/evidence/`.

## What we changed afterwards, and why

TODO(team) — be specific; this is the part that shows the work is yours. For example:
*"Replaced the assistant's rate-limit default of 10/min with 20/min after measuring that our
demo script needs 15; see PR #12."* / *"Rewrote the Postgres StatefulSet securityContext
because the local-path volume was not writable as uid 70 on our cluster; see ENGINEERING-NOTES Q8."*

| file / area | what we changed | why | PR |
|---|---|---|---|
| | | | |

## Viva note to ourselves

The viva does not care who wrote a line, only whether we can defend it. Before the viva,
each of us must be able to explain — and modify live — at least: the triage retry/fallback
path, the state machine, the rate limiter and why it is in Redis, the two probes and why
they differ, why Postgres is a StatefulSet, the HPA/VPA interaction, the network
segmentation, and how the deploy uses a digest.
