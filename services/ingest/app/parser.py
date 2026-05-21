"""DuckDB-driven CSV to Parquet parser."""
from __future__ import annotations

from services.ingest.app.duck import get_connection
from services.ingest.app.storage_keys import parquet_key
from shared.config import get_settings


def parse_csv_to_parquet(
    tenant_id: str,
    dataset: str,
    sha256: str,
    raw_key: str,
) -> tuple[str, int]:
    """Run DuckDB COPY: raw CSV in MinIO to Parquet in MinIO.

    Returns ``(parquet_object_key, row_count)``.
    """
    bucket = get_settings().minio_bucket
    out_key = parquet_key(tenant_id, dataset, sha256)
    raw_url = f"s3://{bucket}/{raw_key}"
    out_url = f"s3://{bucket}/{out_key}"

    con = get_connection()
    try:
        con.execute(
            f"""
            COPY (
                SELECT
                    *,
                    '{tenant_id}'::VARCHAR AS tenant_id,
                    NOW() AS ingested_at
                FROM read_csv_auto('{raw_url}', sample_size=-1)
            )
            TO '{out_url}' (FORMAT PARQUET, COMPRESSION ZSTD);
            """
        )
        rows = con.execute(
            f"SELECT COUNT(*) FROM read_parquet('{out_url}')"
        ).fetchone()
        row_count = int(rows[0]) if rows else 0
    finally:
        con.close()

    return out_key, row_count
