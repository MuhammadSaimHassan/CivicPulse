# Team workflow — the parts of the rubric only you can do

Rubric section A (15 marks), the evidence screenshots, the demo video and the viva are
about *your* collaboration. Nothing here can be generated for you. This is the checklist.

## 1. Set up the repository (once)

1. Create `github.com/<you>/civicpulse` (public, or private with both instructors added).
2. Replace `OWNER` in `README.md`, `k8s/overlays/prod/kustomization.yaml`,
   `k8s/argocd/application.yaml` with your lowercase GitHub user/org.
3. Push the initial import to `main`, then create `dev` from it. From now on **nobody
   pushes to `main`**.
4. **Settings → Branches → Add rule for `main`:** require a pull request, require **1
   approval**, require status checks to pass, and select the checks by job name:
   `lint-and-type`, `test-backend`, `test-frontend`, `build (backend)`, `build (frontend)`,
   `scan (backend)`, `scan (frontend)`, `manifests`, `integration`. Tick *Do not allow
   bypassing*. Screenshot → `docs/evidence/branch-protection.png`.
5. **Settings → Secrets and variables → Actions:** add `LLM_API_KEY` (your Groq key).
   That is the only secret you need: the registry login uses the built-in `GITHUB_TOKEN`
   with `packages: write`, scoped to the job and revoked when it ends.
6. **Settings → Actions → General → Workflow permissions:** leave the default *read*;
   the workflows request exactly what each job needs.

## 2. Work in issues → feature branches → PRs into `dev` → release PRs into `main`

- One Issue per unit of work; branch `feat/<issue>-<slug>` from `dev`; PR into `dev`
  that says `Closes #<issue>`; **the other partner reviews** with a substantive comment
  (a question, a suggested change, a risk — not "LGTM").
- Periodically open a PR `dev → main`; CI must be green and your partner approves.
- Conventional commit prefixes: `feat:`, `fix:`, `test:`, `docs:`, `ci:`, `refactor:`, `chore:`.
- Target: ≥ 35 commits total, **each partner ≥ 35%** (`git shortlog -sn`), ≥ 5 merged PRs
  each linked to an Issue.

A reasonable split into issues (each of you should own some of the backend *and* some of
the infrastructure, because the viva asks about your partner's code too):

| # | issue | suggested owner |
|---|---|---|
| 1 | Backend skeleton: layers, schemas, repository, Alembic, seed | A |
| 2 | Triage providers + orchestration + tests (fallback, injection) | B |
| 3 | Redis: stats cache + rate limiter + tests | A |
| 4 | Frontend views, typed client, component tests | B |
| 5 | Dockerfiles, Compose networks/volumes, isolation + persistence proofs | A |
| 6 | Kubernetes base + overlays, probes, HPA/VPA/PDB | B |
| 7 | CI workflow incl. integration job | A |
| 8 | CD + release workflows, GHCR, signing | B |
| 9 | Load test, HPA capture + chart, VPA loop, ENGINEERING-NOTES Q5/Q6 | A + B |
| 10 | Docs: README screenshots, ADR review, RUNBOOK, AI-USAGE "what we changed" | A + B |

Read every file you commit. If you commit it, you must be able to defend it.

## 3. The deliberate merge conflict (3 marks)

On real code, e.g. `backend/app/providers/triage/rules.py`:

1. Both branch from the same `dev` commit.
2. Partner A adds Roman-Urdu hazard words (`"zakhmi"`, `"aag"`) to `HIGH_PRIORITY_KEYWORDS`;
   partner B, on another branch, reorders/edits the same tuple (e.g. adds `"injured child"`,
   removes `"danger"`).
3. Merge A's PR. B's PR now conflicts. Resolve it locally: `git merge dev`, screenshot the
   conflict markers, edit, commit, screenshot the resolution and the merge commit.
4. Write 2–4 sentences in the PR on why the final version won (e.g. "kept both additions;
   dropped `danger` because it fired on 'not dangerous', see test X").
Save screenshots as `docs/evidence/conflict-*.png`.

## 4. Red → green evidence (1 mark)

Open a PR that breaks a test on purpose (e.g. change the transition table so
`open → resolved` is allowed). Screenshot the red check and the **blocked merge button**
(`docs/evidence/blocked-merge.png`). Fix it in the same PR, screenshot green
(`docs/evidence/green-merge.png`).

## 5. Demo video (≤ 5 minutes, both speaking)

Suggested order: clean clone → `make up` → submit a complaint (show provider + summary) →
set `LLM_API_KEY` wrong or cut the network → submit again → `rules:fallback` and the WARNING
log → `make isolation` failing → `kubectl get hpa -w` while `make load` runs → a bad deploy
→ `kubectl rollout undo`. Upload unlisted, put the link in the submission.

## 6. Submission bundle (§5.8)

1. Repo URL. 2. Link to a green `cd.yml` run. 3. GHCR package links showing SHA tags
(make the packages visible to the instructors: *Package settings → Manage access*, or
public). 4. Video link. 5. `git shortlog -sn` output. 6. `kubectl get hpa -w` capture +
`docs/evidence/hpa-scaling.png`.
Run `python scripts/check_submission.py` and `python scripts/check_refs.py` first.
