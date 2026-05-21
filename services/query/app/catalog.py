"""Catalog operations: list datasets, describe a dataset's schema."""
from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from services.query.app.duck import get_connection, register_dataset_view


async def list_datasets(db: AsyncSession, tenant_id: str) -> list[dict[str, Any]]:
    """Return one row per dataset that has at least one completed job."""
    rows = (
        await db.execute(
            text(
                "SELECT dataset_name, "
                "       SUM(rows_ingested) AS total_rows, "
                "       MAX(updated_at) AS last_ingested_at, "
                "       COUNT(*) AS upload_count "
                "FROM jobs "
                "WHERE tenant_id = :t AND status = 'done' "
                "GROUP BY dataset_name "
                "ORDER BY dataset_name"
            ),
            {"t": tenant_id},
        )
    ).all()
    return [
        {
            "name": r.dataset_name,
            "total_rows": int(r.total_rows or 0),
            "last_ingested_at": r.last_ingested_at,
            "upload_count": r.upload_count,
        }
        for r in rows
    ]


async def dataset_exists(db: AsyncSession, tenant_id: str, dataset: str) -> bool:
    """Cheap check: does this tenant have any completed job for this dataset?"""
    row = (
        await db.execute(
            text(
                "SELECT 1 FROM jobs "
                "WHERE tenant_id = :t AND dataset_name = :d AND status = 'done' "
                "LIMIT 1"
            ),
            {"t": tenant_id, "d": dataset},
        )
    ).first()
    return row is not None


def describe_dataset_schema(tenant_id: str, dataset: str) -> list[dict[str, str]]:
    """Use DuckDB DESCRIBE on the Parquet to return ``[{name, type}, ...]``."""
    con = get_connection()
    try:
        register_dataset_view(con, tenant_id, dataset)
        rows = con.execute(f'DESCRIBE SELECT * FROM "{dataset}"').fetchall()
    finally:
        con.close()
    # DESCRIBE returns: column_name, column_type, null, key, default, extra
    return [{"name": r[0], "type": r[1]} for r in rows]
