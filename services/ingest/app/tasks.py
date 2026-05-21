"""Celery tasks for the ingest service."""
from __future__ import annotations

import time
from uuid import UUID

from sqlalchemy import text

from services.ingest.app.celery_app import celery_app
from services.ingest.app.parser import parse_csv_to_parquet
from shared.db import SyncSessionLocal
from shared.metrics import INGEST_DURATION, INGEST_ROWS_TOTAL


@celery_app.task(name="ingest.parse_upload", bind=True, max_retries=0)
def parse_upload(self, job_id: str) -> dict[str, object]:
    """Run DuckDB COPY for the given job row.

    Reads job metadata, transitions queued -> processing -> done|failed,
    writes Parquet to MinIO, updates row_count and parquet_object_key.

    Tasks are idempotent: re-running on the same job_id will overwrite the
    same Parquet object in MinIO and set the same final state. Safe to retry.
    """
    with SyncSessionLocal() as s:
        row = s.execute(
            text(
                "SELECT id, tenant_id, dataset_name, file_sha256, raw_object_key "
                "FROM jobs WHERE id = :id"
            ),
            {"id": UUID(job_id)},
        ).first()
        if row is None:
            return {"job_id": job_id, "status": "not_found"}

        # transition queued -> processing
        s.execute(
            text(
                "UPDATE jobs SET status='processing', updated_at=NOW() "
                "WHERE id=:id"
            ),
            {"id": row.id},
        )
        s.commit()

        try:
            start = time.perf_counter()
            parquet_object, row_count = parse_csv_to_parquet(
                tenant_id=row.tenant_id,
                dataset=row.dataset_name,
                sha256=row.file_sha256,
                raw_key=row.raw_object_key,
            )
            duration = time.perf_counter() - start
            INGEST_DURATION.labels(
                tenant=row.tenant_id, dataset=row.dataset_name
            ).observe(duration)
            INGEST_ROWS_TOTAL.labels(
                tenant=row.tenant_id, dataset=row.dataset_name
            ).inc(row_count)
        except Exception as exc:
            s.execute(
                text(
                    "UPDATE jobs SET status='failed', error_message=:e, "
                    "updated_at=NOW() WHERE id=:id"
                ),
                {"e": repr(exc), "id": row.id},
            )
            s.commit()
            raise  # let Celery record the failure

        s.execute(
            text(
                "UPDATE jobs SET status='done', parquet_object_key=:p, "
                "rows_ingested=:n, updated_at=NOW() WHERE id=:id"
            ),
            {"p": parquet_object, "n": row_count, "id": row.id},
        )
        s.commit()

        return {
            "job_id": job_id,
            "status": "done",
            "rows_ingested": row_count,
            "parquet_object_key": parquet_object,
        }
