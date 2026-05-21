"""Pulse query service — catalog + structured/SQL queries over the lakehouse."""
from __future__ import annotations

from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from services.query.app.catalog import (
    dataset_exists,
    describe_dataset_schema,
    list_datasets,
)
from services.query.app.dsl import compile_structured
from services.query.app.duck import MAX_ROWS_RETURNED, get_connection, register_dataset_view
from services.query.app.models import (
    DatasetDescribeResponse,
    DatasetSchemaColumn,
    DatasetSummary,
    DistinctValuesResponse,
    QueryResult,
    SqlRequest,
    StructuredQuery,
)
from services.query.app.pagination import decode_cursor, encode_cursor
from services.query.app.safe_sql import register_views, validate_and_referenced_tables
from shared.auth import require_tenant
from shared.db import get_session
from shared.health import health_response
from shared.logging import configure_logging
from shared.middleware import install_observability

configure_logging("query")

app = FastAPI(
    title="Pulse Query",
    description="Structured DSL and safe-SQL queries over the lakehouse.",
    version="0.1.0",
)
install_observability(app, "query")


@app.get("/health")
def health() -> dict[str, str]:
    return health_response(service="query")


# ============================================================
# Catalog
# ============================================================


@app.get("/v1/datasets", response_model=list[DatasetSummary])
async def datasets(
    tenant_id: Annotated[str, Depends(require_tenant)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> list[DatasetSummary]:
    rows = await list_datasets(db, tenant_id)
    return [DatasetSummary(**r) for r in rows]


@app.get("/v1/datasets/{name}", response_model=DatasetDescribeResponse)
async def describe(
    name: str,
    tenant_id: Annotated[str, Depends(require_tenant)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> DatasetDescribeResponse:
    if not await dataset_exists(db, tenant_id, name):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataset '{name}' not found for this tenant.",
        )
    summary_rows = await list_datasets(db, tenant_id)
    summary = next((s for s in summary_rows if s["name"] == name), None)
    if summary is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataset '{name}' not found for this tenant.",
        )
    cols = describe_dataset_schema(tenant_id, name)
    return DatasetDescribeResponse(
        name=name,
        total_rows=summary["total_rows"],
        last_ingested_at=summary["last_ingested_at"],
        columns=[DatasetSchemaColumn(**c) for c in cols],
    )


# ============================================================
# Structured DSL query
# ============================================================


@app.post("/v1/query/structured", response_model=QueryResult)
async def query_structured(
    body: StructuredQuery,
    tenant_id: Annotated[str, Depends(require_tenant)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> QueryResult:
    if not await dataset_exists(db, tenant_id, body.dataset):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataset '{body.dataset}' not found.",
        )

    schema_cols = [c["name"] for c in describe_dataset_schema(tenant_id, body.dataset)]
    offset = decode_cursor(body.cursor)
    sql, params = compile_structured(body, schema_cols, offset)

    con = get_connection()
    try:
        register_dataset_view(con, tenant_id, body.dataset)
        result = con.execute(sql, params)
        col_names = [d[0] for d in result.description]
        raw_rows = result.fetchall()
    finally:
        con.close()

    rows = [dict(zip(col_names, r, strict=True)) for r in raw_rows]
    next_cursor = encode_cursor(offset + body.limit) if len(rows) == body.limit else None

    return QueryResult(
        rows=rows,
        row_count=len(rows),
        next_cursor=next_cursor,
        executed_sql=sql,
    )


# ============================================================
# Safe SQL query
# ============================================================


@app.post("/v1/query/sql", response_model=QueryResult)
async def query_sql(
    body: SqlRequest,
    tenant_id: Annotated[str, Depends(require_tenant)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> QueryResult:
    normalized_sql, referenced_tables = validate_and_referenced_tables(body.sql)

    for t in referenced_tables:
        if not await dataset_exists(db, tenant_id, t):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Dataset '{t}' not found.",
            )

    wrapped = f"SELECT * FROM ({normalized_sql}) LIMIT {MAX_ROWS_RETURNED}"

    con = get_connection()
    try:
        register_views(con, tenant_id, referenced_tables)
        result = con.execute(wrapped)
        col_names = [d[0] for d in result.description]
        raw_rows = result.fetchall()
    finally:
        con.close()

    rows = [dict(zip(col_names, r, strict=True)) for r in raw_rows]
    return QueryResult(
        rows=rows,
        row_count=len(rows),
        next_cursor=None,
        executed_sql=wrapped,
    )


# ============================================================
# Distinct values
# ============================================================


@app.get("/v1/query/distinct_values", response_model=DistinctValuesResponse)
async def distinct_values(
    tenant_id: Annotated[str, Depends(require_tenant)],
    db: Annotated[AsyncSession, Depends(get_session)],
    dataset: Annotated[str, Query()],
    column: Annotated[str, Query()],
    limit: Annotated[int, Query(ge=1, le=10_000)] = 100,
) -> DistinctValuesResponse:
    if not await dataset_exists(db, tenant_id, dataset):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataset '{dataset}' not found.",
        )
    schema_cols = {c["name"] for c in describe_dataset_schema(tenant_id, dataset)}
    if column not in schema_cols:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown column: {column!r}",
        )

    con = get_connection()
    try:
        register_dataset_view(con, tenant_id, dataset)
        result = con.execute(
            f'SELECT DISTINCT "{column}" FROM "{dataset}" ORDER BY 1 LIMIT {int(limit)}'
        )
        values = [r[0] for r in result.fetchall()]
    finally:
        con.close()

    return DistinctValuesResponse(dataset=dataset, column=column, values=values)
