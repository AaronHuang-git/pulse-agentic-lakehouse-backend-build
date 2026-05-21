"""Shared pytest fixtures and config."""
from __future__ import annotations

import httpx
import pytest

INGEST_URL = "http://localhost:8001"
QUERY_URL = "http://localhost:8002"
AGENT_URL = "http://localhost:8003"
DEMO_HEADERS = {"Authorization": "Bearer demo-key-1234"}


@pytest.fixture
def http_client() -> httpx.Client:
    """Sync httpx client with a 60s timeout (E2E ingest can take a few seconds)."""
    with httpx.Client(timeout=60.0) as c:
        yield c
