# ADR 0002 — Frontend runtime configuration: same-origin `/api` proxy + `/config.js`

- **Status:** Accepted
- **Date:** 2026-09-27

## Context

Vite replaces `import.meta.env.*` with literal strings **at build time**. If the backend
URL is one of them, the built JavaScript — and therefore the image — only works in the
environment it was built for. That breaks build-once-deploy-many: CI would have to build
a different frontend image per environment, and the image we scanned would not be the
image we run.

## Decision

1. **No backend URL exists in the frontend at all.** The API client
   (`frontend/src/api/client.ts`) only calls relative paths (`/api/complaints`, …).
   - In Compose, nginx in the frontend container proxies `/api/` to `${BACKEND_UPSTREAM}`.
     nginx's image renders `/etc/nginx/templates/default.conf.template` with `envsubst`
     **at container start** (`frontend/default.conf.template`), so the upstream is runtime
     configuration: `http://backend:8000` in Compose and in Kubernetes, anything else elsewhere.
   - In Kubernetes, the Ingress routes `/api` to the backend Service directly and `/` to the
     frontend, on one host. The nginx proxy is still there and still correct, it is simply
     not on the hot path.
   - In development, Vite's dev server proxies `/api` the same way (`vite.config.ts`).
   Same origin everywhere, so there is no CORS configuration to get wrong.
2. **Non-URL runtime values go in `/config.js`**, written by
   `docker-entrypoint.d/40-runtime-config.sh` at container start from environment variables
   and loaded by `index.html` before the bundle. Today it carries only a display label
   (`APP_ENVIRONMENT`). The script whitelists characters so a value cannot break out of the
   JavaScript string.
3. **Nothing secret is ever in the frontend** — not in the bundle, not in `/config.js`.
   Anything served to a browser is public; minification is not protection.

## Consequences

- One frontend image, identified by digest, runs in Compose, in the dev cluster and in CI's
  prod-overlay deploy. Proven in CI: `ci.yml` builds once; `cd.yml` deploys the pushed
  digest with different configuration.
- nginx resolves `backend` when it starts. In Kubernetes that is a stable ClusterIP; in
  Compose, if the backend container is recreated with a new IP, restart the frontend too
  (`docker compose restart frontend`). A `resolver` + variable upstream would remove this,
  at the cost of hard-coding a DNS server address per platform; not worth it here.
- A request passes through one extra hop (nginx) in Compose. Measured overhead is well
  under a millisecond — irrelevant next to a triage call.

## Alternatives considered

- **Build per environment** with `VITE_API_URL`. Breaks build-once-deploy-many. Rejected.
- **`/config.js` carrying the API URL** (the other approach the brief allows). Works, but
  needs CORS on the backend and an absolute URL per environment; the proxy makes both
  unnecessary.
