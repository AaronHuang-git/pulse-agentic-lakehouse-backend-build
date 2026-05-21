"""DuckDB session configured for our MinIO endpoint."""
from __future__ import annotations

import duckdb

from shared.config import get_settings


def get_connection() -> duckdb.DuckDBPyConnection:
    """Return an in-memory DuckDB connection wired to read/write MinIO."""
    settings = get_settings()
    con = duckdb.connect(":memory:")
    con.execute("INSTALL httpfs")
    con.execute("LOAD httpfs")
    # The httpfs extension uses the S3 protocol. We point it at MinIO.
    con.execute(f"SET s3_endpoint='{settings.minio_endpoint}'")
    con.execute("SET s3_url_style='path'")
    con.execute("SET s3_use_ssl=false")
    con.execute(f"SET s3_access_key_id='{settings.minio_root_user}'")
    con.execute(f"SET s3_secret_access_key='{settings.minio_root_password}'")
    return con
