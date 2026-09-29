# syntax=docker/dockerfile:1.7
# ---------------------------------------------------------------------------
# CivicPulse backend. Two stages:
#   builder  — creates a virtualenv and installs pinned dependencies
#   runtime  — copies only the venv and the source; runs as a non-root user
# The base image is pinned to an exact patch version. For the digest bonus,
# replace the tag with tag@sha256:... (see docs/RUNBOOK.md, "Pinning by digest").
# ---------------------------------------------------------------------------
ARG PYTHON_IMAGE=python:3.12.14-slim-bookworm

FROM ${PYTHON_IMAGE} AS builder
ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:${PATH}"
WORKDIR /build
# Dependencies BEFORE source: this layer is rebuilt only when requirements.txt
# changes, not on every code edit.
COPY requirements.txt .
RUN pip install -r requirements.txt

FROM ${PYTHON_IMAGE} AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:${PATH}"
RUN groupadd --system --gid 10001 app \
 && useradd --system --uid 10001 --gid app --no-create-home --shell /usr/sbin/nologin app
WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
COPY alembic.ini ./
COPY alembic ./alembic
COPY app ./app
# Numeric UID so Kubernetes runAsNonRoot can verify it without /etc/passwd.
USER 10001:10001
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --start-period=15s --retries=3 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2)"]
# Exec form: python is PID 1 and receives SIGTERM directly (a shell would swallow it).
CMD ["python", "-m", "app.server"]
