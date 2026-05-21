"""DuckDB session helper for the query service.

Each request opens a fresh in-memory DuckDB connection, points it at MinIO,
registers the requested dataset as a tenant-scoped temporary view, and runs
the user's query against that view.
"""
from __future__ import annotations

import duckdb

from shared.config import get_settings

# Per-query safety knobs. DuckDB has no native statement timeout; we enforce
# a row cap at the endpoint layer. A Python watchdog using
# DuckDBPyConnection.interrupt() is a follow-up if long-running queries
# become a problem.
MAX_ROWS_RETURNED = 10_000


def get_connection() -> duckdb.DuckDBPyConnection:
    """Return an in-memory DuckDB connection wired to MinIO."""
    settings = get_settings()
    con = duckdb.connect(":memory:")
    con.execute("INSTALL httpfs")
    con.execute("LOAD httpfs")
    con.execute(f"SET s3_endpoint='{settings.minio_endpoint}'")
    con.execute("SET s3_url_style='path'")
    con.execute("SET s3_use_ssl=false")
    con.execute(f"SET s3_access_key_id='{settings.minio_root_user}'")
    con.execute(f"SET s3_secret_access_key='{settings.minio_root_password}'")
    return con


def register_dataset_view(
    con: duckdb.DuckDBPyConnection,
    tenant_id: str,
    dataset: str,
) -> None:
    """Create a temp view named ``dataset`` that scans the tenant's Parquet glob.

    The view applies ``WHERE tenant_id = ?`` so any downstream query is
    automatically scoped to the caller's data. The view name == dataset name,
    so user SQL referring to ``olist_geolocation`` Just Works.

    Caller is responsible for validating ``dataset`` against the catalog
    before invoking this function (see ``catalog.dataset_exists``).
    """
    settings = get_settings()
    glob = f"s3://{settings.minio_bucket}/silver/{tenant_id}/{dataset}/*.parquet"
    con.execute(
        f'CREATE OR REPLACE TEMP VIEW "{dataset}" AS '
        f"SELECT * FROM read_parquet('{glob}') WHERE tenant_id = '{tenant_id}'"
    )
