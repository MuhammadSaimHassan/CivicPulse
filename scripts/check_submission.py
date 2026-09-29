#!/usr/bin/env python3
"""Pre-submission lint: `python scripts/check_submission.py` from the repo root.

A lint, not a grader. It looks for the mechanical failures behind most of the
automatic deductions (assignment §5.3) and for missing required files. A clean
run does not mean a good mark; a dirty run nearly guarantees a bad one.

If your instructor ships their own check_submission.py, theirs wins — run both.
Standard library only; no install needed. Exit code 1 if anything FAILs.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FAIL: list[str] = []
WARN: list[str] = []
OK: list[str] = []


def fail(msg: str) -> None:
    FAIL.append(msg)


def warn(msg: str) -> None:
    WARN.append(msg)


def ok(msg: str) -> None:
    OK.append(msg)


def read(rel: str) -> str:
    p = ROOT / rel
    return p.read_text(encoding="utf-8", errors="replace") if p.exists() else ""


def git(*args: str) -> str:
    try:
        return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=False).stdout
    except FileNotFoundError:
        return ""


# ---------------------------------------------------------------- required files
REQUIRED = [
    "README.md", "LICENSE", ".env.example", ".gitignore", "compose.yaml", "compose.prod.yaml",
    "backend/Dockerfile", "backend/.dockerignore", "backend/pyproject.toml", "backend/alembic.ini",
    "backend/app/providers/triage/base.py", "backend/app/providers/triage/llm.py",
    "backend/app/providers/triage/ollama.py", "backend/app/providers/triage/rules.py",
    "backend/app/providers/triage/simulated.py", "backend/app/providers/triage/factory.py",
    "frontend/Dockerfile", "frontend/.dockerignore", "frontend/nginx.conf", "frontend/package.json",
    "k8s/base/kustomization.yaml", "k8s/base/namespace.yaml", "k8s/base/backend.yaml", "k8s/base/frontend.yaml",
    "k8s/base/postgres.yaml", "k8s/base/redis.yaml", "k8s/base/ingress.yaml", "k8s/base/configmap.yaml",
    "k8s/base/secret.yaml", "k8s/base/hpa.yaml", "k8s/base/vpa.yaml", "k8s/base/pdb.yaml",
    "k8s/overlays/dev/kustomization.yaml", "k8s/overlays/prod/kustomization.yaml",
    "load/k6-script.js", ".github/workflows/ci.yml", ".github/workflows/cd.yml", ".github/workflows/release.yml",
    "docs/ENGINEERING-NOTES.md", "docs/RUNBOOK.md", "docs/AI-USAGE.md", "docs/TRIAGE.md",
    "docs/adr/0001-provider-interface.md", "docs/adr/0002-frontend-runtime-config.md",
    "docs/adr/0003-deploy-by-sha.md", "docs/adr/0004-pii-and-data-governance.md",
]
missing = [f for f in REQUIRED if not (ROOT / f).exists()]
if missing:
    fail("missing required files: " + ", ".join(missing))
else:
    ok(f"all {len(REQUIRED)} required files present")

migrations = list((ROOT / "backend/alembic/versions").glob("*.py"))
(ok if migrations else fail)(f"alembic migrations: {len(migrations)} found")

# ---------------------------------------------------------------- secrets (-20 / -15)
tracked = git("ls-files").splitlines()
if not tracked:
    warn("not a git repository (or git missing): history-based checks skipped")
env_files = [f for f in tracked if re.search(r"(^|/)\.env($|\.)", f) and not f.endswith(".env.example")]
secrets_env = [f for f in tracked if f.endswith("secrets.env")]
if env_files or secrets_env:
    fail(f"secret env file(s) tracked by git: {env_files + secrets_env}")
elif tracked:
    ok("no .env / secrets.env tracked")

history_env = [
    line for line in git("log", "--all", "--diff-filter=A", "--name-only", "--pretty=format:").splitlines()
    if re.search(r"(^|/)(\.env|secrets\.env)$", line)
]
if history_env:
    fail(f".env ever committed in history: {sorted(set(history_env))} — rotate credentials and write an incident note")

KEY_PATTERNS = {
    "Groq key": r"gsk_[A-Za-z0-9]{20,}",
    "Google API key": r"AIza[0-9A-Za-z_\-]{30,}",
    "OpenAI/OpenRouter key": r"sk-(or-v1-)?[A-Za-z0-9]{32,}",
    "GitHub token": r"gh[pousr]_[A-Za-z0-9]{30,}",
    "private key": r"-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----",
}
history_blob = git("log", "--all", "-p", "--no-color") if tracked else ""
scan_text = history_blob or "\n".join(read(f) for f in tracked)
for name, pattern in KEY_PATTERNS.items():
    if re.search(pattern, scan_text):
        fail(f"{name} pattern found in git history or tracked files")
if tracked:
    ok("no API-key patterns in git history")

secret_yaml = read("k8s/base/secret.yaml")
if re.search(r"^\s*(data|stringData):[\s\S]*?(gsk_|AIza|sk-)", secret_yaml, re.M):
    fail("k8s/base/secret.yaml appears to contain a real key")

# ---------------------------------------------------------------- image pinning (-8)
image_refs: list[tuple[str, str]] = []
for rel in ["backend/Dockerfile", "frontend/Dockerfile"]:
    for m in re.finditer(r"^\s*(?:FROM|ARG \w+_IMAGE=)\s*(\S+)", read(rel), re.M):
        image_refs.append((rel, m.group(1)))
for rel in ["compose.yaml", "compose.prod.yaml", *[str(p.relative_to(ROOT)) for p in (ROOT / "k8s").rglob("*.yaml")]]:
    for m in re.finditer(r"^\s*-?\s*image:\s*[\"']?([^\s\"'#]+)", read(rel), re.M):
        image_refs.append((rel, m.group(1)))
bad_pins = []
for rel, ref in image_refs:
    if ref.startswith("${") or ref.startswith("civicpulse-") or "${" in ref.split(":")[0] or ref in {"builder", "build"}:
        continue
    if ref.startswith("$"):
        continue
    name_tag = ref.split("@")[0]
    tag = name_tag.rsplit(":", 1)[1] if ":" in name_tag.split("/")[-1] else None
    if "@sha256:" in ref:
        continue
    if tag is None or tag in {"latest", "alpine", "slim", "stable", "mainline"} or not re.search(r"\d", tag):
        bad_pins.append(f"{rel}: {ref}")
(fail if bad_pins else ok)("unpinned images: " + ", ".join(bad_pins) if bad_pins else "all base/service images pinned to a version")

# ---------------------------------------------------------------- :latest deployed (-8)
deploy_latest = []
for rel in ["compose.prod.yaml", *[str(p.relative_to(ROOT)) for p in (ROOT / "k8s").rglob("*.yaml")]]:
    for n, line in enumerate(read(rel).splitlines(), 1):
        if re.search(r"(image:|newTag:).*:?latest\b", line) and not line.strip().startswith("#"):
            deploy_latest.append(f"{rel}:{n}")
(fail if deploy_latest else ok)(f"deploys :latest at {deploy_latest}" if deploy_latest else "nothing deploys :latest")

# ---------------------------------------------------------------- localhost service-to-service (-8)
localhost_hits = []
for rel in ["compose.yaml", "compose.prod.yaml", "frontend/default.conf.template", "backend/app/core/config.py",
            *[str(p.relative_to(ROOT)) for p in (ROOT / "k8s").rglob("*.yaml")]]:
    for n, line in enumerate(read(rel).splitlines(), 1):
        if line.strip().startswith("#"):
            continue
        # 127.0.0.1 inside a container's OWN healthcheck is correct; flag URLs to other services.
        # (civicpulse.localhost as an Ingress host name is fine; "http://localhost:5432" is not.)
        hit = re.search(r"(?<![.\w])(localhost|127\.0\.0\.1)(:\d+|/|\b)", line)
        if hit and "healthcheck" not in line and "urlopen" not in line and "wget" not in line \
                and not re.search(r"\"127\.0\.0\.1:\d+:\d+\"", line):
            localhost_hits.append(f"{rel}:{n}")
(fail if localhost_hits else ok)(
    f"localhost used for service-to-service: {localhost_hits}" if localhost_hits else "no localhost service-to-service URLs"
)

# ---------------------------------------------------------------- network segmentation (-8)
compose = read("compose.yaml")
seg_ok = re.search(r"internal:\s*\n\s*driver:\s*bridge\s*\n\s*internal:\s*true", compose) is not None
fe_block = re.search(r"\n  frontend:\n(.*?)(?=\n  \w[\w-]*:\n)", compose, re.S)
fe_nets = fe_block and re.search(r"networks:\s*\[([^\]]*)\]", fe_block.group(1))
if seg_ok and fe_nets and "internal" not in fe_nets.group(1):
    ok("frontend is not on the internal network; internal: true is set")
else:
    fail("network segmentation: need an `internal: true` network and the frontend must not join it")

# ---------------------------------------------------------------- published DB/cache port in prod (-8)
prod = read("compose.prod.yaml")
for svc in ("postgres", "redis"):
    block = re.search(rf"\n  {svc}:\n(.*?)(?=\n  \w[\w-]*:\n|\Z)", prod, re.S)
    if block and re.search(r"^\s+ports:", block.group(1), re.M):
        fail(f"compose.prod.yaml publishes a port on {svc}")
if re.search(r"^\s*build:", prod, re.M):
    fail("compose.prod.yaml contains a build: key")
if "${IMAGE_TAG" not in prod:
    fail("compose.prod.yaml does not use ${IMAGE_TAG}")
k8s_all = "\n".join(p.read_text() for p in (ROOT / "k8s").rglob("*.yaml"))
if re.search(r"name:\s*postgres[\s\S]{0,200}type:\s*(NodePort|LoadBalancer)", k8s_all):
    fail("postgres Service is NodePort/LoadBalancer")
if not any("compose.prod" in f or "postgres Service" in f for f in FAIL):
    ok("prod compose: no build key, no DB/cache ports, uses ${IMAGE_TAG}; DB Service is ClusterIP")

# ---------------------------------------------------------------- postgres as StatefulSet (-8)
pg = read("k8s/base/postgres.yaml")
if "kind: StatefulSet" in pg and "volumeClaimTemplates" in pg:
    ok("postgres is a StatefulSet with volumeClaimTemplates")
else:
    fail("postgres must be a StatefulSet with volumeClaimTemplates")

# ---------------------------------------------------------------- needs: gating (-8)
for wf in ("cd.yml", "release.yml"):
    text = read(f".github/workflows/{wf}")
    jobs = re.findall(r"^  ([\w-]+):\n((?:    .*\n|\n)*)", text, re.M)
    for name, body in jobs:
        publishes = re.search(r"push:\s*true|kubectl apply|gh release create|cosign sign", body)
        if publishes and "needs:" not in body:
            fail(f"{wf}: job '{name}' publishes/deploys without needs:")
if not any("needs:" in f for f in FAIL):
    ok("publishing/deploying jobs are gated by needs:")
for wf in ("ci.yml", "cd.yml", "release.yml"):
    if not re.search(r"^permissions:", read(f".github/workflows/{wf}"), re.M):
        fail(f"{wf}: no top-level permissions: block")

# ---------------------------------------------------------------- misc
if re.search(r"CREATE TABLE", "\n".join(p.read_text() for p in (ROOT / "backend/app").rglob("*.py")), re.I):
    fail("CREATE TABLE found in application code (schema must come from Alembic)")
else:
    ok("no schema DDL in application code")

hpa = read("k8s/base/backend.yaml")
(ok if re.search(r"requests:\s*\{?\s*cpu", hpa) else fail)("backend has resources.requests.cpu (HPA needs it)")

notes = read("docs/ENGINEERING-NOTES.md")
if "TODO(team)" in notes or "TODO(team)" in read("README.md"):
    warn("docs still contain TODO(team) placeholders — fill in your own measurements before submitting")

shortlog = git("shortlog", "-sn", "--all", "--no-merges")
if shortlog:
    counts = [int(line.split()[0]) for line in shortlog.strip().splitlines()]
    total = sum(counts)
    if total < 35:
        warn(f"only {total} commits (rubric asks for >= 35)")
    if len(counts) >= 2 and min(counts[:2]) / total < 0.35:
        warn("a partner is below 35% of commits (git shortlog -sn)")

# ---------------------------------------------------------------- report
for m in OK:
    print(f"  ok    {m}")
for m in WARN:
    print(f"  WARN  {m}")
for m in FAIL:
    print(f"  FAIL  {m}")
print(f"\n{len(OK)} ok, {len(WARN)} warnings, {len(FAIL)} failures")
sys.exit(1 if FAIL else 0)
