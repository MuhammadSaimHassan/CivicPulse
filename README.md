# CivicPulse

[![ci](https://github.com/MuhammadSaimHassan/CivicPulse/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/MuhammadSaimHassan/CivicPulse/actions/workflows/ci.yml)
[![cd](https://github.com/MuhammadSaimHassan/CivicPulse/actions/workflows/cd.yml/badge.svg?branch=main)](https://github.com/MuhammadSaimHassan/CivicPulse/actions/workflows/cd.yml)
![python](https://img.shields.io/badge/python-3.12-blue)
![react](https://img.shields.io/badge/react-18-61dafb)
![license](https://img.shields.io/badge/license-MIT-green)

**Municipal complaint intake, AI triage and operations.** A citizen writes
*"Burst water main flooding Street 12 since fajr, water entering ground floors"* in their own
words — English, Urdu or both. CivicPulse validates it, has a language model decide the
**category**, **priority** and a **one-line summary**, stores it durably, and puts it on a live
operations dashboard — so the burst main is at the top of Monday's queue instead of behind
three streetlight complaints.

The model is replaceable and untrusted. Triage sits behind a `TriageProvider` interface
(hosted LLM, local Ollama, keyword rules, deterministic fake), its output is validated
against a schema, and when the provider is slow, rate-limited or wrong the complaint is still
triaged — by rules — and still saved. A citizen never sees a 500 because a third party failed.

![Submit view](docs/evidence/screenshot-submit.png)
![Dashboard](docs/evidence/screenshot-dashboard.png)
![Stats with X-Cache](docs/evidence/screenshot-stats.png)

<sub>TODO(team): take these three screenshots from your running stack and save them under
`docs/evidence/` with these names.</sub>

## Architecture

```mermaid
flowchart TB
    user([Citizen / Operator]) -- HTTP :8080 --> fe

    subgraph edge["docker network: edge"]
        fe["frontend<br/>React 18 + Vite → nginx (non-root)<br/>serves SPA, proxies /api"]
        be["backend<br/>FastAPI + Pydantic v2<br/>routes → services → repositories / providers"]
    end
    subgraph internal["docker network: internal (internal: true — no route out)"]
        pg[("postgres:16<br/>volume pgdata")]
        rd[("redis:7<br/>stats cache · rate limiter<br/>triage cache · AOF on redisdata")]
    end

    fe -- "/api (same origin)" --> be
    be --> pg
    be --> rd
    be -- "TriageProvider" --> tp{{TRIAGE_PROVIDER}}
    tp -- llm --> groq["Groq / Gemini<br/>JSON mode, 10 s timeout"]
    tp -- ollama --> ol["Ollama 1B<br/>(internal network)"]
    tp -- simulated --> sim["SimulatedTriage<br/>deterministic (CI)"]
    groq -. "timeout · 429 · 5xx (retry once) · bad JSON" .-> rules["RuleBasedTriage<br/>fallback: rules:fallback"]
```

The frontend is on `edge` only, so it cannot reach the database (`make isolation` proves it —
the command is *supposed* to fail). The backend is the only service on both networks; its
calls to Groq leave through `edge` (ENGINEERING-NOTES Q7). In Kubernetes the same shape is:
Ingress `/` → frontend, `/api` → backend, ClusterIP Services, Postgres as a StatefulSet with a
PVC, NetworkPolicies allowing only backend pods to reach Postgres and Redis.

## Quickstart — one command

Requirements: Docker with Compose v2, `make` (Linux/macOS/WSL/Git Bash).

```bash
git clone https://github.com/MuhammadSaimHassan/CivicPulse.git && cd civicpulse
make up
```

`make up` copies `.env.example` to `.env` if you have none, builds both images, starts
Postgres and Redis, runs the Alembic migrations and loads 34 seed complaints (a one-shot
`migrate` service), starts the backend and frontend, and waits until every healthcheck
passes. Then open **http://localhost:8080**. API docs: http://localhost:8000/docs.

Without `make`: `cp .env.example .env && docker compose up -d --build --wait`.

It works offline out of the box with `TRIAGE_PROVIDER=rules`. To use the LLM, get a free key
at [console.groq.com](https://console.groq.com) (no card), then in `.env`:

```bash
TRIAGE_PROVIDER=llm
LLM_API_KEY=gsk_...          # .env is gitignored — never commit it
```

and `docker compose up -d backend`. Fully offline model instead:
`TRIAGE_PROVIDER=ollama` and `docker compose --profile ollama up -d` (downloads ~1.3 GB once).

| command | what it does |
|---|---|
| `make up` / `make down` / `make reset` | start / stop (keep data) / stop and delete volumes |
| `make logs` | follow backend JSON logs |
| `make isolation` | prove the frontend cannot reach Postgres or Redis |
| `make persistence` | prove rows survive `docker compose down` + `up` |
| `make k8s-up` | **second command:** k3d cluster + VPA + images + deploy `k8s/overlays/dev` → http://civicpulse.localhost:8081 |
| `make load` / `make hpa-watch` | k6 load test / watch the HPA scale |
| `docker compose --profile observability up -d` | Prometheus (:9090) + Grafana (:3000) with a provisioned dashboard |

## API

| method | path | behaviour |
|---|---|---|
| `POST` | `/api/complaints` | validate → triage → persist. **201**. **400** with `{"detail", "errors":[{"field","message"}]}`. **429** + `Retry-After` over the per-IP rate limit (10/min, in Redis). |
| `GET` | `/api/complaints/{id}` | **200** / **404** |
| `GET` | `/api/complaints` | filter `category`, `priority`, `status`; paginate `page`, `page_size ≤ 100`; returns `total` |
| `PATCH` | `/api/complaints/{id}/status` | state machine `open → in_progress → resolved`, `open → rejected`, `in_progress → rejected`; anything else **409** naming the transition |
| `GET` | `/api/stats` | counts by category, priority, status. Redis read-through, TTL 30 s, invalidated on every write. `X-Cache: HIT \| MISS` |
| `GET` | `/api/meta/providers` | active provider, triage cache hit rate, last 20 outcomes (provider, latency ms, fallback, error) |
| `GET` | `/health` | liveness — process alive; touches nothing external |
| `GET` | `/ready` | readiness — 200 only if Postgres and Redis answer; 503 naming the failed one (and during shutdown drain) |
| `GET` | `/metrics` | Prometheus: request count, request latency histogram, triage latency, fallback counter, cache hits, 429s |

Every response carries `X-Request-ID` (yours, if you sent one). OpenAPI: `/docs`, `/openapi.json`.

## How the pieces map to the brief

| requirement | where |
|---|---|
| Four layers, one-way dependencies | `backend/app/{routes,services,repositories,providers}` — routes never see a DB session (`app/deps.py` injects services) |
| Provider interface + 4 implementations | `backend/app/providers/triage/` · ADR 0001 · `docs/TRIAGE.md` |
| Structured output, timeout, retry-once-with-jitter, fallback, content-hash cache, injection guardrail | `providers/triage/prompt.py`, `services/triage_service.py` |
| The fallback test | `backend/tests/test_api.py::test_fallback_when_provider_always_raises` |
| State machine as a transition table | `backend/app/services/state_machine.py` |
| SIGTERM drain | `backend/app/server.py` + `preStop` in `k8s/base/backend.yaml` |
| Alembic, idempotent seed | `backend/alembic/versions/`, `backend/app/seed.py`, `backend/app/migrate.py` |
| Distributed rate limiter | `backend/app/providers/rate_limiter.py` (+ test with two app instances sharing one budget) |
| Runtime frontend config | `frontend/default.conf.template`, `frontend/docker-entrypoint.d/40-runtime-config.sh` · ADR 0002 |
| Typed API client from OpenAPI | `frontend/src/api/schema.d.ts` (generated), `frontend/src/api/client.ts`; CI fails if stale |
| Two networks, three volumes, healthchecks, prod file | `compose.yaml`, `compose.prod.yaml` |
| Kubernetes (Kustomize), probes, HPA, VPA, PDB | `k8s/base`, `k8s/overlays/{dev,prod}` |
| CI / CD / release | `.github/workflows/` · ADR 0003 |
| PII decision | ADR 0004 |

## Development

```bash
# backend (needs Postgres 16 + Redis 7 locally for the integration tests)
cd backend && python -m venv .venv && . .venv/bin/activate && pip install -r requirements-dev.txt
TEST_DATABASE_URL=postgresql+psycopg://civicpulse:civicpulse@127.0.0.1:5432/civicpulse_test \
TEST_REDIS_URL=redis://127.0.0.1:6379/15 python -m pytest --cov=app
ruff check . && ruff format --check . && mypy app

# frontend
cd frontend && npm ci && npm test && npm run lint && npx tsc --noEmit
npm run dev          # Vite on :5173, proxies /api to 127.0.0.1:8000

# after changing a backend schema: regenerate the contract the frontend is typed against
cd backend && python -m app.export_openapi ../frontend/openapi.json && cd ../frontend && npm run gen:api
```

Without local Postgres/Redis the integration tests are **skipped** locally and **fail** in CI
(`REQUIRE_INTEGRATION=1`), so CI can never go green by testing less.

Before submitting: `python scripts/check_submission.py` and `python scripts/check_refs.py`.

## Measured

| | value | how |
|---|---|---|
| build context, backend | 25.95 MB → 98.5 kB | `.dockerignore`; measured with `FROM scratch / COPY .` on the dev workspace (includes `.venv`/caches) |
| build context, frontend | 189.8 MB → 231.7 kB | `.dockerignore` (excludes `node_modules`, `dist`, tests) |
| image size, backend (builder / final) | TODO(team) | `docker image ls`; builder: `docker build --target builder -t cp-builder backend` |
| image size, frontend (build / final) | TODO(team) — must be < ~60 MB | `docker build --target build -t cp-fe-build frontend` |
| backend tests / coverage | 90 tests / 93% | `pytest --cov=app` against real Postgres + Redis |
| frontend tests | 13 | `npm test` |
| triage accuracy, rules | 77% fully correct (39 cases) | `python -m tools.eval_triage` — see `docs/TRIAGE.md` for LLM/Ollama rows |
| HPA lag | TODO(team) | `docs/ENGINEERING-NOTES.md` Q5 |

## Deviations from the brief (and why)

- **nginx 1.30.5 instead of 1.27.** Upstream no longer patches 1.27; with it the required
  Trivy gate (fail on fixable HIGH/CRITICAL) would fail on the base image. Same image family
  and configuration.
- **`triaged_by` has three extra values** besides `llm:groq · llm:ollama · rules · rules:fallback`:
  `llm:gemini`, `llm:openrouter` (same `LLMTriage`, other vendors) and `simulated` (CI). All are
  enforced by a CHECK constraint.
- **Compose publishes the backend on `127.0.0.1:8000` in dev** for `/docs` and the CI
  integration test. `compose.prod.yaml` publishes only the frontend.

## Repository layout

```
backend/     FastAPI app (app/{routes,services,repositories,providers}), alembic/, tests/, tools/
frontend/    React + Vite + TS (src/{api,components,pages}), tests/, nginx config, Dockerfile
k8s/         base/ + overlays/{dev,prod} (Kustomize), argocd/ (optional GitOps)
load/        k6 script
observability/  Prometheus + Grafana provisioning (compose profile)
scripts/     k8s-up, isolation/persistence proofs, HPA capture + chart, rollout-under-load, checks
docs/        ENGINEERING-NOTES, RUNBOOK, TRIAGE, AI-USAGE, TEAM-WORKFLOW, adr/, evidence/
```

## Team

TODO(team): names, roll numbers, who owned what. See `docs/TEAM-WORKFLOW.md` and
`docs/AI-USAGE.md`.

## License

MIT — see `LICENSE`.
