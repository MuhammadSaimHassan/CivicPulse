"""Prometheus metrics exposed on GET /metrics."""

from __future__ import annotations

from prometheus_client import Counter, Histogram

REQUEST_COUNT = Counter(
    "civicpulse_http_requests_total",
    "HTTP requests handled",
    ["method", "route", "status"],
)
REQUEST_LATENCY = Histogram(
    "civicpulse_http_request_duration_seconds",
    "HTTP request latency",
    ["method", "route"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 20),
)
TRIAGE_LATENCY = Histogram(
    "civicpulse_triage_latency_seconds",
    "Time spent producing a triage result, by the provider that produced it",
    ["provider"],
    buckets=(0.001, 0.01, 0.05, 0.1, 0.25, 0.5, 1, 2, 4, 8, 12, 25),
)
TRIAGE_FALLBACK = Counter(
    "civicpulse_triage_fallback_total",
    "Triage calls that fell back to RuleBasedTriage",
    ["provider", "error"],
)
TRIAGE_CACHE = Counter(
    "civicpulse_triage_cache_total",
    "Content-hash triage cache lookups",
    ["result"],  # hit | miss
)
RATE_LIMITED = Counter(
    "civicpulse_rate_limited_total",
    "Complaint submissions rejected with 429",
)
