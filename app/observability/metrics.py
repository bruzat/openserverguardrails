"""Prometheus metrics instrumentation."""
from __future__ import annotations

from prometheus_client import Counter, Histogram

REQUEST_COUNT = Counter(
    "guardrails_requests_total",
    "Total number of guardrail requests",
    ["endpoint", "status"],
)

LATENCY = Histogram(
    "guardrails_request_latency_seconds", "Latency of guardrail requests", ["endpoint"]
)

SEVERITY_HISTOGRAM = Histogram(
    "guardrails_moderation_severity",
    "Observed worst-case severity scores",
    buckets=[0, 1, 2, 3, 4],
)


def record(endpoint: str, status: str, duration: float) -> None:
    REQUEST_COUNT.labels(endpoint=endpoint, status=status).inc()
    LATENCY.labels(endpoint=endpoint).observe(duration)


def record_severity(score: int) -> None:
    """Track the worst severity score observed across moderation flows."""

    SEVERITY_HISTOGRAM.observe(score)
