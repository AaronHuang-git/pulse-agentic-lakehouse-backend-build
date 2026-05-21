"""Prometheus metrics primitives + /metrics mount."""
from __future__ import annotations

from fastapi import FastAPI
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Histogram,
    generate_latest,
)
from starlette.responses import Response

# HTTP-level metrics
REQUEST_COUNTER = Counter(
    "pulse_requests_total",
    "Total HTTP requests handled.",
    labelnames=("service", "method", "path", "status"),
)

REQUEST_DURATION = Histogram(
    "pulse_request_duration_seconds",
    "HTTP request duration.",
    labelnames=("service", "method", "path"),
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

# Ingest-specific
INGEST_ROWS_TOTAL = Counter(
    "pulse_ingest_rows_total",
    "Total rows ingested.",
    labelnames=("tenant", "dataset"),
)
INGEST_DURATION = Histogram(
    "pulse_ingest_duration_seconds",
    "DuckDB COPY duration (worker side).",
    labelnames=("tenant", "dataset"),
    buckets=(0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0, 300.0),
)

# Agent-specific
AGENT_ITERATIONS = Histogram(
    "pulse_agent_iterations",
    "Tool-use loop iterations per request.",
    labelnames=("provider",),
    buckets=(1, 2, 3, 4, 5, 6, 7, 8),
)
AGENT_TOOL_CALLS = Counter(
    "pulse_agent_tool_calls_total",
    "Tool calls made by the agent.",
    labelnames=("tool", "error"),
)
AGENT_TOKENS = Counter(
    "pulse_agent_tokens_total",
    "Tokens consumed by the agent.",
    labelnames=("provider", "direction"),
)


def mount_metrics(app: FastAPI) -> None:
    """Add ``GET /metrics`` returning the Prometheus text exposition."""

    @app.get("/metrics", include_in_schema=False)
    def metrics() -> Response:
        return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
