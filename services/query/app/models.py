"""Pydantic models for the query service."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

# ----- Catalog responses -----


class DatasetSummary(BaseModel):
    name: str
    total_rows: int
    upload_count: int
    last_ingested_at: datetime | None


class DatasetSchemaColumn(BaseModel):
    name: str
    type: str


class DatasetDescribeResponse(BaseModel):
    name: str
    total_rows: int
    columns: list[DatasetSchemaColumn]
    last_ingested_at: datetime | None


# ----- Structured DSL -----

FilterOp = Literal[
    "eq", "neq", "gt", "gte", "lt", "lte",
    "in", "contains", "between", "is_null", "not_null",
]
AggFn = Literal["count", "count_distinct", "sum", "avg", "min", "max"]
SortDir = Literal["asc", "desc"]


class Filter(BaseModel):
    column: str
    op: FilterOp
    value: Any = None  # required for most ops; ignored for is_null/not_null


class Aggregate(BaseModel):
    fn: AggFn
    column: str | None = None  # None means count(*)
    as_: str = Field(alias="as")


class OrderBy(BaseModel):
    column: str
    dir: SortDir = "asc"


class StructuredQuery(BaseModel):
    dataset: str
    select: list[str] | None = None
    filters: list[Filter] = []
    group_by: list[str] = []
    aggregate: list[Aggregate] = []
    order_by: list[OrderBy] = []
    limit: int = Field(default=100, ge=1, le=10_000)
    cursor: str | None = None


class QueryResult(BaseModel):
    rows: list[dict[str, Any]]
    row_count: int
    next_cursor: str | None
    executed_sql: str


# ----- Safe SQL -----


class SqlRequest(BaseModel):
    sql: str = Field(min_length=1, max_length=10_000)


# ----- Distinct values -----


class DistinctValuesResponse(BaseModel):
    dataset: str
    column: str
    values: list[Any]
