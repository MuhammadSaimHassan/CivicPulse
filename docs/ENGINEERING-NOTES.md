# Engineering notes

Answers to the eight questions in §5.2, with references to our own files. Line numbers
are for the commit this file was last updated in; `scripts/check_refs.py` verifies them.

Items marked **TODO(team)** can only be answered from *your* runs (your cluster, your
laptop, your hour lost). Fill them in; `scripts/check_submission.py` warns while any remain.

---

## Also required: the two indexes, and the cache volume

**Indexes** (`backend/alembic/versions/0001_create_complaints.py:65` and `:67`):

- `ix_complaints_status_priority (status, priority)` serves the operations dashboard's
  filter, `WHERE status = ? [AND priority = ?]`, built in
  `backend/app/repositories/complaint_repository.py:39`. Status is the leading column
  because operators almost always filter by status ("everything still open"), and a
  composite index serves the status-only filter as well as status+priority.
- `ix_complaints_created_at (created_at)` serves the default sort,
  `ORDER BY created_at DESC LIMIT n OFFSET m` (`complaint_repository.py:53`). Without it,
  every dashboard page load sorts the whole table to return 10 rows.

Check with `EXPLAIN ANALYZE` on a table big enough for the planner to prefer an index
(on 34 seed rows it will — correctly — choose a sequential scan).

**Why does the cache get a volume** (`compose.yaml:63`, `compose.yaml:67`)? A cache can be
rebuilt, so losing it is not *data loss*. We keep AOF on a named volume anyway because this
Redis holds more than a disposable cache: (1) the **rate-limit counters** — lose them on a
restart and every client gets a fresh budget, which is exactly when a burst of retries
arrives; (2) the **24 h triage cache**, whose entries each cost an LLM call against a small
daily free quota — a Redis restart should not re-spend it; (3) the last-20 outcomes list.
The defensible opposite answer: `/api/stats` (30 s TTL) needs no persistence at all, and a
pure cache on a volume can resurrect stale entries after a long outage. We accept that
because every value we store either has a TTL or is re-validated on read.

---

## Q1. Three things that differ between a laptop and a CI runner, and the line that freezes each

1. **The Python interpreter.** A laptop has whatever Python is installed (3.11, 3.13…); the
   runner has another. Frozen by `backend/Dockerfile:9` —
   `ARG PYTHON_IMAGE=python:3.12.14-slim-bookworm` (exact patch release and Debian base);
   the test job pins the same minor version at `.github/workflows/ci.yml:25`.
2. **Dependency versions.** `pip install fastapi` on two days gives two versions. Frozen by
   exact pins in `backend/requirements.txt` (e.g. `backend/requirements.txt:7`,
   `psycopg[binary]==3.3.6`), installed at `backend/Dockerfile:19`; and for the frontend by
   the lockfile, copied at `frontend/Dockerfile:16` and installed with `npm ci` (which fails
   if `package.json` and the lock disagree, instead of silently re-resolving).
3. **The services the code talks to.** On a laptop, "Postgres" is whatever is installed (or
   nothing). In CI it is `postgres:16.15-alpine3.24` (`.github/workflows/ci.yml:70`) — the
   same tag as `compose.yaml` and `k8s/base/postgres.yaml`. And the triage provider: a laptop
   may have a live Groq key, the runner must not — frozen to the deterministic fake by
   `TRIAGE_PROVIDER: simulated` at `.github/workflows/ci.yml:85`.

(A fourth, the Node toolchain, is frozen at `frontend/Dockerfile:10`.)

## Q2. Where the pipeline sits on the CI/CD maturity ladder

TODO(team): use the rung names from *your* Lecture 03 slide 32. Our assessment in general terms:

We are at **continuous delivery with automated deployment to an ephemeral environment**:
every PR runs lint, types, unit + integration tests, an image build, a vulnerability scan,
manifest validation and a full Compose integration test (`ci.yml`); every merge to `main`
re-tests the merged result, publishes signed, SBOM'd images by SHA and deploys the digest
to a real (ephemeral) Kubernetes cluster with a smoke test (`cd.yml`). Rollback is
scripted and demonstrated.

We are **not** at continuous *deployment to a persistent production environment*: the
cluster CI deploys to is created and destroyed per run, and nothing promotes the release
to a long-lived environment. **Next rung:** a persistent staging cluster reconciled by
GitOps (Argo CD, `k8s/argocd/application.yaml`) with automated promotion to production
behind health-based progressive delivery (canary + automatic rollback on error-rate). It
buys: deploys that are just commits, drift detection, and rollback = `git revert`.

## Q3. The line that guarantees build-once-deploy-many

`.github/workflows/cd.yml:186`:

```bash
kustomize edit set image "civicpulse-backend=${BACKEND_REF}" "civicpulse-frontend=${FRONTEND_REF}"
```

with `BACKEND_REF` defined at `.github/workflows/cd.yml:136` as
`ghcr.io/<owner>/civicpulse-backend@<digest>`, where the digest is the output of the
*one* build (`cd.yml:43`). The deploy job never builds; it deploys the exact bytes that
were tested, scanned and signed. On the frontend side the enabling line is
`frontend/default.conf.template:27` (`proxy_pass ${BACKEND_UPSTREAM};`, rendered at
container start): the bundle contains no environment-specific URL, so the same image can
be deployed anywhere (ADR 0002).

**What breaks without it:** if the deploy step rebuilt the image, or deployed a mutable tag
like `:latest`, then (a) what runs is not what was tested — a base-image update or a
dependency release between the two builds changes the bytes; (b) "which version is in
production?" has no reliable answer; (c) rollback to "the previous `latest`" is impossible;
(d) with `:latest` and `imagePullPolicy: IfNotPresent`, different nodes can run different
code under the same name.

## Q4. What "correct" means for a probabilistic component, and how CI stays deterministic

With `TRIAGE_PROVIDER=llm`, the same complaint can get different summaries — or, rarely,
a different category — on two runs. So "correct" for the **component** cannot mean "returns
this exact output". We define it as properties that must hold on every call:

1. **Contract:** the result is always a valid `TriageResult` (enum category/priority,
   summary ≤ 140, confidence in [0,1]) or the call falls back —
   `backend/app/providers/triage/prompt.py:79`.
2. **Availability:** the request always completes (201) within a bounded time (10 s
   timeout ×2 + jitter), whatever the provider does — `backend/app/services/triage_service.py:112`.
3. **Safety floor:** hazard wording is never ranked below high —
   `triage_service.py:146`.
4. **Quality** is a *statistical* property, measured, not asserted: accuracy on a labelled
   set (`backend/tools/eval_triage.py`, results in `docs/TRIAGE.md`).

CI tests properties 1–3 deterministically, by design rather than luck:
`TRIAGE_PROVIDER: simulated` (`ci.yml:85`) is a seeded fake; failure paths are tested by
**injecting** providers that always raise, return malformed JSON or obey an injection
(`backend/tests/test_api.py:36`, `:48`); retry timing is injected (`sleep`, `jitter`
parameters, `backend/tests/conftest.py:113`), so there is no `time.sleep()` in any test and
the suite runs in ~3 s. Property 4 is deliberately *not* in CI: a live-model accuracy check
would be flaky by definition and would spend quota.

## Q5. HPA lag

TODO(team): run the load test and measure.

```bash
make k8s-up
./scripts/hpa-capture.sh &                      # samples kubectl get hpa every 5 s
k6 run --out csv=load/results/k6.csv -e BASE_URL=http://civicpulse.localhost:8081 load/k6-script.js
kill %1
python scripts/plot_hpa.py                      # writes docs/evidence/hpa-scaling.png and prints the lag
```

Record: *load reached 50% of peak at t = __ s; replicas first rose at t = __ s; lag = __ s.*

Where the time goes (fill in with your observed values; the defaults are the mechanism):

1. **metrics-server scrape** — kubelet resource metrics are collected every ~15 s
   (k3s default); utilisation cannot rise before a scrape sees it.
2. **HPA sync period** — the controller evaluates every 15 s.
3. **Our `scaleUp.stabilizationWindowSeconds: 0`** (`k8s/base/hpa.yaml:25`) adds nothing;
   the scale-up policies allow +100% or +4 pods per 15 s.
4. **Pod start** — scheduling, image already cached (IfNotPresent), init container running
   migrations (~1–2 s, nothing to do), Python import + startup, then the **readiness probe**
   must pass (period 5 s) before the pod receives traffic.

What would reduce it: a shorter metrics resolution (`--metric-resolution`), a lower
`averageUtilization` target so scaling starts earlier, a higher `minReplicas` for known
peaks, scaling on a leading signal (request rate / queue depth via custom metrics or KEDA)
instead of CPU, and a faster-starting image. None of these removes the lag — which is why
autoscaling complements capacity planning rather than replacing it.

## Q6. Why VPA is in `Off` mode

`k8s/base/vpa.yaml:19` — `updateMode: "Off"`.

The HPA scales on CPU **utilisation = usage ÷ request** (`k8s/base/hpa.yaml:18`). VPA in
`Auto` mode changes the **request**. Together they act on the same signal and fight:

1. Load rises → per-pod CPU usage rises.
2. VPA raises the CPU request (and evicts pods to apply it).
3. Utilisation = usage ÷ (bigger request) falls below 60%.
4. HPA scales **in** — fewer pods.
5. Each remaining pod now takes more load → usage rises → VPA raises the request again…

Meanwhile each VPA change *evicts* pods, so the loop also churns capacity during the very
load spike it is reacting to. In recommender mode VPA only publishes Target/Lower/Upper
bounds; a human copies a sensible request into `k8s/base/backend.yaml:87` in a reviewed
commit, and HPA keeps sole control of replica count. (The supported combination, if you
want both automatically, is HPA on a *different* metric — e.g. requests per second — than
the resource VPA manages.)

**The loop we ran** — TODO(team):

| | CPU request | memory request | HPA behaviour under `load/k6-script.js` |
|---|---|---|---|
| initial guess (`backend.yaml:87`) | 100m | 128Mi | peak replicas __, time to scale __ s |
| VPA recommendation (`kubectl describe vpa backend-vpa`) | Target __ / Lower __ / Upper __ | Target __ / Lower __ / Upper __ | — |
| after updating requests | __ | __ | peak replicas __, time to scale __ s |

Commit the `describe` output as `docs/evidence/vpa-recommendation.txt`. Expect: if VPA's
target is *higher* than 100m, the same load produces lower utilisation, so the HPA scales
out later and to fewer pods (each pod is "bigger"); if lower, it scales out sooner.

## Q7. `internal: true` blocks outbound traffic — where does that leave the LLM call?

`compose.yaml:229` makes the `internal` network have no route to the outside world. Only
Postgres, Redis (and Ollama) live there. The backend — the only service that calls Groq —
is attached to **both** `edge` and `internal` (`compose.yaml:111`). `edge` is an ordinary
bridge network with a default gateway, so the backend's outbound HTTPS to
`api.groq.com` leaves through its `edge` interface, while its database traffic stays on
`internal`. The frontend is on `edge` only (`compose.yaml:135`) and cannot even resolve
the name `postgres` — demonstrated by `scripts/prove-isolation.sh` and asserted in CI
(`ci.yml`, integration job).

Trade-off we accepted: the backend has general internet egress, not just egress to Groq.
Alternatives: (a) a dedicated egress proxy container on a third network that only allows
the LLM host (tighter, one more moving part); (b) run Ollama on `internal` and drop hosted
LLMs entirely (no egress at all — that is exactly how the `ollama` profile works, with a
separate `ollama_egress` network used only by Ollama to download weights once). In
Kubernetes the same intent is expressed by `k8s/base/networkpolicy.yaml`: only backend pods
may connect to Postgres and Redis; an egress policy restricting the backend to DNS + the
LLM host would be the next step.

## Q8. The failure

TODO(team) — this one must be yours. Something that cost you more than an hour while
building, deploying or demoing *this* repository. Keep the shape:

- **Symptoms:** what you saw (exact error text, which command, which pod/container).
- **What we wrongly believed first:** and what we tried because of it.
- **What told us the truth:** the exact command or log line (paste it).
- **Fix:** file and line.
- **What we would check first next time.**

Common candidates in this stack, if you hit one: HPA stuck at `<unknown>/60%`; the frontend
returning 502 after the backend container was recreated (ADR 0002); Postgres rejecting a
changed password because the volume was already initialised; an nginx `add_header` inside a
`location` silently dropping the server-level security headers (see the comment in
`frontend/default.conf.template`).
