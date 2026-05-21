"""Structured JSON logging via structlog.

Called once at service startup. Subsequent logger calls produce JSON lines
with consistent fields: timestamp, level, service, request_id (if bound),
tenant_id (if bound), event, plus any kwargs the caller adds.
"""
from __future__ import annotations

import logging
import sys

import structlog
from structlog.stdlib import BoundLogger


def configure_logging(service_name: str) -> None:
    """Configure structlog + stdlib logging for the calling service."""
    log_level = logging.INFO

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
    )

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.dict_tracebacks,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    structlog.contextvars.bind_contextvars(service=service_name)


def get_logger(name: str | None = None) -> BoundLogger:
    return structlog.get_logger(name)
