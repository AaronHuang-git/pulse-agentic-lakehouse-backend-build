"""Pulse ingest service — CSV upload, sync DuckDB parse, job tracking."""
from __future__ import annotations

import asyncio
from typing import Annotated
from uuid import UUID

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from services.ingest.app.models import JobStatus, UploadResponse
from services.ingest.app.storage_keys import raw_key
from services.ingest.app.tasks import parse_upload
from services.ingest.app.upload import spool_and_hash
from shared.auth import require_tenant
from shared.db import get_session
from shared.health import health_response
from shared.logging import configure_logging
from shared.middleware import install_observability
from shared.storage import put_stream

configure_logging("ingest")

app = FastAPI(
    title="Pulse Ingest",
    description="CSV upload, validation, normalization to Parquet.",
    version="0.1.0",
)
install_observability(app, "ingest")


@app.get("/health")
def health() -> dict[str, str]:
    return health_response(service="ingest")


@app.post(
    "/v1/ingest/upload",
    response_model=UploadResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def upload(
    dataset: Annotated[str, Form()],
    file: Annotated[UploadFile, File()],
    tenant_id: Annotated[str, Depends(require_tenant)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> UploadResponse:
    # ----- Phase 1: stream the body to a temp file while computing SHA256.
    tmp_path, sha256, total_bytes = await spool_and_hash(file)
    try:
        # ----- Phase 2: idempotency check.
        existing = (
            await db.execute(
                text(
                    "SELECT id, status, dataset_name, file_sha256, "
                    "       raw_object_key, parquet_object_key, rows_ingested "
                    "FROM jobs WHERE tenant_id = :t AND file_sha256 = :s"
                ),
                {"t": tenant_id, "s": sha256},
            )
        ).first()
        if existing is not None:
            return UploadResponse(
                job_id=existing.id,
                status=existing.status,
                dataset=existing.dataset_name,
                file_sha256=existing.file_sha256,
                rows_ingested=existing.rows_ingested,
                raw_object_key=existing.raw_object_key,
                parquet_object_key=existing.parquet_object_key,
                deduplicated=True,
            )

        # ----- Phase 3: upload raw to MinIO.
        raw_object = raw_key(tenant_id, sha256)
        with tmp_path.open("rb") as fh:
            await asyncio.to_thread(
                put_stream, raw_object, fh, total_bytes, "text/csv"
            )

        # ----- Phase 4: insert job row (status=queued) + enqueue task.
        job_row = (
            await db.execute(
                text(
                    "INSERT INTO jobs ("
                    "  tenant_id, dataset_name, file_sha256, file_size_bytes, "
                    "  status, raw_object_key"
                    ") VALUES ("
                    "  :tenant_id, :dataset, :sha, :size, 'queued', :raw"
                    ") RETURNING id"
                ),
                {
                    "tenant_id": tenant_id,
                    "dataset": dataset,
                    "sha": sha256,
                    "size": total_bytes,
                    "raw": raw_object,
                },
            )
        ).first()
        assert job_row is not None
        job_id: UUID = job_row.id
        await db.commit()

        # Enqueue the parse task. Returns immediately — worker takes over.
        parse_upload.delay(str(job_id))

        return UploadResponse(
            job_id=job_id,
            status="queued",
            dataset=dataset,
            file_sha256=sha256,
            rows_ingested=None,
            raw_object_key=raw_object,
            parquet_object_key=None,
            deduplicated=False,
        )
    finally:
        tmp_path.unlink(missing_ok=True)


@app.get("/v1/jobs/{job_id}", response_model=JobStatus)
async def get_job(
    job_id: UUID,
    tenant_id: Annotated[str, Depends(require_tenant)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> JobStatus:
    row = (
        await db.execute(
            text(
                "SELECT id, tenant_id, dataset_name, status, file_sha256, "
                "       file_size_bytes, raw_object_key, parquet_object_key, "
                "       rows_ingested, error_message, created_at, updated_at "
                "FROM jobs WHERE id = :id AND tenant_id = :t"
            ),
            {"id": job_id, "t": tenant_id},
        )
    ).first()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Job not found."
        )
    return JobStatus(
        job_id=row.id,
        tenant_id=row.tenant_id,
        dataset=row.dataset_name,
        status=row.status,
        file_sha256=row.file_sha256,
        file_size_bytes=row.file_size_bytes,
        raw_object_key=row.raw_object_key,
        parquet_object_key=row.parquet_object_key,
        rows_ingested=row.rows_ingested,
        error_message=row.error_message,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )
