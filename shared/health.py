"""Shared health-check response helper."""
from __future__ import annotations

from datetime import UTC, datetime


def health_response(service: str) -> dict[str, str]:
    """Return a standard health-check payload for a Pulse service."""
    return {
        "status": "ok",
        "service": service,
        "timestamp": datetime.now(UTC).isoformat(),
    }
