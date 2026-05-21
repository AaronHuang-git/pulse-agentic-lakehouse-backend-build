"""FastAPI middleware: request IDs, access logging, metrics."""
from __future__ import annotations

import time
import uuid

import structlog
from fastapi import FastAPI, Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from shared.logging import get_logger
from shared.metrics import REQUEST_COUNTER, REQUEST_DURATION, mount_metrics

REQUEST_ID_HEADER = "X-Request-ID"
log = get_logger(__name__)


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Generate/propagate request IDs, bind to structlog, time + record metrics."""

    def __init__(self, app: ASGIApp, service_name: str) -> None:
        super().__init__(app)
        self.service_name = service_name

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get(REQUEST_ID_HEADER) or uuid.uuid4().hex
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            service=self.service_name,
            request_id=request_id,
            method=request.method,
            path=request.url.path,
        )
        start = time.perf_counter()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            response.headers[REQUEST_ID_HEADER] = request_id
            return response
        finally:
            duration = time.perf_counter() - start
            REQUEST_COUNTER.labels(
                service=self.service_name,
                method=request.method,
                path=request.url.path,
                status=str(status_code),
            ).inc()
            REQUEST_DURATION.labels(
                service=self.service_name,
                method=request.method,
                path=request.url.path,
            ).observe(duration)
            log.info(
                "request_handled",
                status=status_code,
                duration_ms=round(duration * 1000, 2),
            )


def install_observability(app: FastAPI, service_name: str) -> None:
    """One call per service: middleware + /metrics mount."""
    app.add_middleware(RequestContextMiddleware, service_name=service_name)
    mount_metrics(app)
