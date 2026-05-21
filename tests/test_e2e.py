"""End-to-end test: upload CSV -> wait -> query -> agent.

Requires the live stack (``.\\pulse.ps1 up -d``) and runs against
localhost. Marked ``e2e`` so it can be skipped in CI with
``pytest -m "not e2e"``.

For deterministic agent behavior, run with PULSE_AGENT_PROVIDER=mock in
the .env file (the answer text contains a literal "[MOCK provider]"
prefix that this test relies on indirectly via "tool calls > 0" only).
"""
from __future__ import annotations

import tempfile
import time
from pathlib import Path

import httpx
import pytest

from tests.conftest import AGENT_URL, DEMO_HEADERS, INGEST_URL, QUERY_URL

pytestmark = pytest.mark.e2e


def _make_csv(rows: int, salt: str) -> Path:
    """Write a small synthetic CSV with content unique to this run.

    The salt is embedded in every row so the file SHA differs from previous
    runs, defeating Pulse's (tenant, sha) idempotency dedup.
    """
    lines = ["id,group,value,salt"]
    for i in range(rows):
        lines.append(f"row_{i:04d},grp_{i % 3},{i * 10},{salt}")
    tmp = tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="w")
    tmp.write("\n".join(lines))
    tmp.close()
    return Path(tmp.name)


def test_full_pipeline_upload_query_agent(http_client: httpx.Client) -> None:
    salt = f"run_{time.time_ns()}"
    csv_path = _make_csv(rows=50, salt=salt)
    dataset_name = f"e2e_{salt}"

    try:
        # ---- 1. Upload ----
        with csv_path.open("rb") as fh:
            r = http_client.post(
                f"{INGEST_URL}/v1/ingest/upload",
                headers=DEMO_HEADERS,
                files={"file": (csv_path.name, fh, "text/csv")},
                data={"dataset": dataset_name},
            )
        assert r.status_code in (200, 202), r.text
        job_id = r.json()["job_id"]

        # ---- 2. Poll until done ----
        deadline = time.time() + 30
        status = None
        while time.time() < deadline:
            r = http_client.get(f"{INGEST_URL}/v1/jobs/{job_id}", headers=DEMO_HEADERS)
            status = r.json()["status"]
            if status in ("done", "failed"):
                break
            time.sleep(0.5)
        assert status == "done", f"Job did not complete: status={status}"
        assert r.json()["rows_ingested"] == 50

        # ---- 3. Structured query ----
        r = http_client.post(
            f"{QUERY_URL}/v1/query/structured",
            headers=DEMO_HEADERS,
            json={
                "dataset": dataset_name,
                "aggregate": [{"fn": "count", "as": "n"}],
            },
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["row_count"] == 1
        assert body["rows"][0]["n"] == 50

        # ---- 4. Agent ----
        r = http_client.post(
            f"{AGENT_URL}/v1/agent/ask",
            headers=DEMO_HEADERS,
            json={"question": f"How many rows are in {dataset_name}?"},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["answer"], "Agent returned empty answer"
        assert len(body["tool_calls"]) >= 1, "Agent made no tool calls"
        assert body["iterations"] >= 1
        assert body["provider"] in ("mock", "anthropic")
    finally:
        csv_path.unlink(missing_ok=True)
