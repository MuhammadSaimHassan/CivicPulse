# CivicPulse Runbook

For whoever is holding the pager. Commands assume the repository root and, for
Kubernetes, `kubectl` pointing at the right cluster with namespace `civicpulse`.

## 1. Deploy

### Compose (single machine)

```bash
make up                                   # dev: builds images, migrates, seeds, waits for healthy
# production-style, from published images:
IMAGE_TAG=<full commit sha> docker compose -f compose.prod.yaml up -d --wait
```

### Kubernetes — local k3d

```bash
make k8s-up                               # cluster + VPA + images + secret + overlays/dev
open http://civicpulse.localhost:8081
```

### Kubernetes — CI (the real path)

Merge a PR into `main`. `cd.yml` runs the full test suite on the merged commit, builds
and pushes both images to GHCR tagged with the commit SHA, signs them, then deploys the
**digest** to an ephemeral k3d cluster, waits for every rollout and smoke-tests the Ingress.
Watch it under *Actions → cd*. The job summary lists the published digests.

**What is running?**

```bash
kubectl -n civicpulse get deploy backend frontend -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.spec.template.spec.containers[0].image}{"\n"}{end}'
# -> ghcr.io/<owner>/civicpulse-backend@sha256:...   match the digest to its <sha> tag on the GHCR
#    package page, then: git show <sha>
```

## 2. Roll back

Two mechanisms, for two moments.

**At 3 a.m., while it is on fire — imperative, ~30 seconds:**

```bash
kubectl -n civicpulse rollout undo deployment/backend
kubectl -n civicpulse rollout status deployment/backend
kubectl -n civicpulse rollout history deployment/backend      # revisionHistoryLimit: 5
```

Fast, needs nothing but cluster access, and the rolling-update settings
(`maxUnavailable: 0`) keep serving while it happens. But the cluster now differs from
what Git says, and the next deploy will re-apply the broken version.

**Once the fire is out — declarative, auditable:**

```bash
cd k8s/overlays/prod
kustomize edit set image civicpulse-backend=ghcr.io/<owner>/civicpulse-backend@sha256:<previous digest>
kubectl apply -k .
# and make it permanent in Git: revert the offending commit on main (PR as usual),
# so CI rebuilds and redeploys a version that the repository actually describes.
```

Use `rollout undo` to stop the bleeding; use the declarative path so the fix is reviewed,
recorded and survives the next deploy. Compose equivalent: re-run
`IMAGE_TAG=<previous sha> docker compose -f compose.prod.yaml up -d --wait`.

## 3. Read the logs

Every line is one JSON object on stdout with a `request_id`.

```bash
docker compose logs -f backend                                   # Compose
kubectl -n civicpulse logs -f deploy/backend --all-containers    # Kubernetes (one pod)
kubectl -n civicpulse logs -l app.kubernetes.io/name=backend --prefix --tail=200   # all pods

# follow one request across nginx and the backend
kubectl -n civicpulse logs -l app.kubernetes.io/part-of=civicpulse --tail=-1 --prefix | grep '<id>'

# only warnings and errors
docker compose logs --no-log-prefix backend | jq -c 'select(.level != "INFO")'
```

The browser shows the id in the `X-Request-ID` response header; a caller may also send
its own `X-Request-ID` and it is propagated.

Useful fields: `msg` (`request`, `triage fallback`, `triage retry`, `startup`, `shutdown…`),
`status`, `duration_ms`, `provider`, `error`, `complaint_id`.

## 4. Triage starts failing

**Symptoms:** complaints show *Keyword rules (LLM fallback)*; `triaged_by = rules:fallback`
in the dashboard; `civicpulse_triage_fallback_total` rising; WARNING lines
`"msg": "triage fallback"`. Citizens are **not** affected beyond classification quality:
every complaint is still accepted (201) and stored. This is a degradation, not an outage.

1. **Which error?**
   ```bash
   curl -s http://localhost:8080/api/meta/providers | jq '.recent[] | {provider, error, latency_ms}'
   docker compose logs backend | jq -c 'select(.msg=="triage fallback") | {error, provider}' | sort | uniq -c
   ```
2. **By error class:**

   | `error` | meaning | action |
   |---|---|---|
   | `TriageRateLimited` | HTTP 429 from the provider, even after one retry | Free-tier quota exhausted. Check the provider console. Lower `RATE_LIMIT_PER_WINDOW`; wait for the window; or switch provider (below). |
   | `TriageTimeout` | no answer within 10 s | Provider slow/degraded. Check its status page. Consider a smaller model. |
   | `TriageServerError` | 5xx, DNS failure or connection refused | Provider down, or **egress blocked** (see Q7 in ENGINEERING-NOTES: the backend must be on a network with a route out). `docker compose exec backend python -c "import socket; socket.create_connection(('api.groq.com', 443), 3)"` |
   | `TriageBadRequest` | 400/401/403/404 | Our request is wrong: **invalid or revoked `LLM_API_KEY`** (401), unknown `LLM_MODEL` (404/400). Not retried. Fix the config. |
   | `MalformedTriageOutput` | provider answered, but not with valid JSON matching the schema | Model changed behaviour, or the prompt changed. Inspect with `python -m tools.eval_triage`; consider bumping `CACHE_KEY_VERSION` after a prompt fix. |

3. **Switch provider without a code change:**
   ```bash
   # Compose: edit .env, then
   docker compose up -d backend                 # TRIAGE_PROVIDER=rules | ollama | llm
   # Kubernetes:
   kubectl -n civicpulse patch configmap civicpulse-config --type merge -p '{"data":{"TRIAGE_PROVIDER":"rules"}}'
   kubectl -n civicpulse rollout restart deployment/backend
   ```
4. **Rotate a leaked/revoked key:** revoke it in the provider console; create a new one;
   update `.env` (Compose), `k8s/overlays/<env>/secrets.env` + `kubectl apply -k` (k8s),
   or the `LLM_API_KEY` GitHub Secret (CI). Restart the backend. Never commit it.

## 5. Other failures

| symptom | likely cause | check / fix |
|---|---|---|
| Backend pods `0/1 Ready`, not restarting | `/ready` failing: Postgres or Redis unreachable | `kubectl -n civicpulse exec deploy/backend -- python -c "import urllib.request;print(urllib.request.urlopen('http://127.0.0.1:8000/ready').read())"` — the body names the failed dependency. Liveness stays green by design, so pods are **not** restart-looping. |
| Backend `Init:CrashLoopBackOff` | migration failed | `kubectl -n civicpulse logs deploy/backend -c migrate` |
| Postgres auth failures after changing `POSTGRES_PASSWORD` | Postgres reads the password only when it first initialises the volume | Change it in the database (`ALTER USER`) or, in dev only, `make reset` / delete the PVC. |
| HPA shows `<unknown>/60%` | no CPU request, or metrics-server not ready | `kubectl -n civicpulse describe hpa backend`; `kubectl top pods -n civicpulse` |
| 429 on every submission | rate limiter (10/min per IP). Behind a proxy that does not set `X-Forwarded-For`, all users share one IP | check `X-RateLimit-Remaining`; raise `RATE_LIMIT_PER_WINDOW`. |
| Redis down | cache misses, rate limiter **fails open** (logged), stats computed from DB each time, `/ready` 503 | Restart Redis; AOF restores rate-limit counters and cached triage answers. |
| Frontend 502 on `/api` in Compose after backend recreate | nginx cached the old backend IP | `docker compose restart frontend` (ADR 0002). |

## 6. Pinning base images by digest (bonus)

```bash
docker buildx imagetools inspect python:3.12.14-slim-bookworm --format '{{json .Manifest.Digest}}'
# then in backend/Dockerfile:  ARG PYTHON_IMAGE=python:3.12.14-slim-bookworm@sha256:<digest>
```
Same for `node`, `nginx` (frontend/Dockerfile), `postgres`, `redis` (compose files, k8s).
Renovate or Dependabot can then open PRs when a new digest is published.
