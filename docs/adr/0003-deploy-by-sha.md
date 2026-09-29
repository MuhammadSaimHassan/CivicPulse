# ADR 0003 — Deploy by immutable reference (commit SHA tag, digest in CD)

- **Status:** Accepted
- **Date:** 2026-09-27

## Context

"What is production running?" must have a one-word answer you can paste into `git show`.
A mutable tag such as `:latest` cannot give that answer: it points at whatever was pushed
last, it can change between a rollout's first and last pod, and it makes rollback
ambiguous ("roll back to which `latest`?").

## Decision

- `cd.yml` pushes each image twice: `:<full commit SHA>` and `:latest`. `:latest` is a
  convenience for humans pulling by hand; **it is never deployed**.
- The deploy job deploys by **digest** (`image@sha256:…`), taken from the build job's
  output, via `kustomize edit set image` (`.github/workflows/cd.yml`). A digest is the hash
  of the image content: it cannot be re-pointed, and it is what Cosign signs and verifies.
  The SHA tag maps a digest back to a commit.
- Images are signed keyless with Cosign in `build-push` and **verified in `deploy-k8s`
  before anything is applied**, with the certificate identity pinned to this repository's
  `cd.yml` on `refs/heads/main`.
- `compose.prod.yaml` requires `IMAGE_TAG` (no default) so a Compose deployment is also
  pinned to a SHA.
- The committed `k8s/overlays/prod/kustomization.yaml` holds a placeholder tag, never
  `latest`; CI replaces it. `scripts/check_submission.py` fails if `latest` appears in any
  deployable manifest.

## Consequences

- Answering "what is running": `kubectl -n civicpulse get deploy backend -o jsonpath='{..image}'`
  gives the digest; the GHCR package page (or `crane ls`) maps it to the SHA tag; `git show <sha>`.
- Rollback is well-defined, two ways (see `docs/RUNBOOK.md`):
  `kubectl rollout undo` (fast, imperative) or re-applying the previous digest (declarative).
- Every deployable change is a new commit → new SHA → new digest. There is no "redeploy
  the same tag to pick up a fix".

## Alternatives considered

- **Deploy `:<sha>` tags.** Acceptable per the brief and nearly as good; a registry *can* in
  principle re-point a tag, a digest cannot. We use digests because Cosign verification
  already needs them.
- **Semver tags only.** Needs a human to cut a release for every deploy; used for
  `release.yml`, not for continuous deployment.
