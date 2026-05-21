"""Pydantic response models for the ingest service."""
from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel

JobStatusLiteral = Literal["queued", "processing", "done", "failed"]


class UploadResponse(BaseModel):
    job_id: UUID
    status: JobStatusLiteral
    dataset: str
    file_sha256: str
    rows_ingested: int | None = None
    raw_object_key: str
    parquet_object_key: str | None = None
    deduplicated: bool = False


class JobStatus(BaseModel):
    job_id: UUID
    tenant_id: str
    dataset: str
    status: JobStatusLiteral
    file_sha256: str
    file_size_bytes: int
    raw_object_key: str
    parquet_object_key: str | None
    rows_ingested: int | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime
