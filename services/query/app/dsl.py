"""Compile the structured DSL into parameterized SQL."""
from __future__ import annotations

from fastapi import HTTPException, status

from services.query.app.models import Aggregate, Filter, OrderBy, StructuredQuery

# Map filter op -> SQL fragment with placeholder(s)
_FILTER_SQL: dict[str, str] = {
    "eq": "= ?",
    "neq": "!= ?",
    "gt": "> ?",
    "gte": ">= ?",
    "lt": "< ?",
    "lte": "<= ?",
    "is_null": "IS NULL",
    "not_null": "IS NOT NULL",
}


def _qident(name: str) -> str:
    """Double-quote an identifier after rejecting illegal characters."""
    if '"' in name or "\x00" in name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Illegal character in identifier: {name!r}",
        )
    return f'"{name}"'


def _ensure_column(col: str, schema: set[str]) -> None:
    if col not in schema:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown column: {col!r}",
        )


def _compile_filter(f: Filter, schema: set[str], params: list) -> str:
    _ensure_column(f.column, schema)
    col = _qident(f.column)

    if f.op in ("is_null", "not_null"):
        return f"{col} {_FILTER_SQL[f.op]}"
    if f.op in _FILTER_SQL:
        params.append(f.value)
        return f"{col} {_FILTER_SQL[f.op]}"
    if f.op == "in":
        if not isinstance(f.value, list) or not f.value:
            raise HTTPException(400, "`in` requires a non-empty list value.")
        placeholders = ", ".join(["?"] * len(f.value))
        params.extend(f.value)
        return f"{col} IN ({placeholders})"
    if f.op == "contains":
        if not isinstance(f.value, str):
            raise HTTPException(400, "`contains` requires a string value.")
        params.append(f"%{f.value}%")
        return f"{col} LIKE ?"
    if f.op == "between":
        if not isinstance(f.value, list) or len(f.value) != 2:
            raise HTTPException(400, "`between` requires a [low, high] list.")
        params.extend(f.value)
        return f"{col} BETWEEN ? AND ?"
    raise HTTPException(400, f"Unsupported op: {f.op}")


def _compile_aggregate(a: Aggregate, schema: set[str]) -> str:
    if a.fn == "count" and a.column is None:
        body = "COUNT(*)"
    else:
        if a.column is None:
            raise HTTPException(400, f"{a.fn} requires a column.")
        _ensure_column(a.column, schema)
        col = _qident(a.column)
        if a.fn == "count":
            body = f"COUNT({col})"
        elif a.fn == "count_distinct":
            body = f"COUNT(DISTINCT {col})"
        elif a.fn == "sum":
            body = f"SUM({col})"
        elif a.fn == "avg":
            body = f"AVG({col})"
        elif a.fn == "min":
            body = f"MIN({col})"
        elif a.fn == "max":
            body = f"MAX({col})"
        else:
            raise HTTPException(400, f"Unsupported aggregate fn: {a.fn}")
    return f"{body} AS {_qident(a.as_)}"


def _compile_order_by(o: OrderBy, schema: set[str], select_aliases: set[str]) -> str:
    if o.column not in schema and o.column not in select_aliases:
        raise HTTPException(
            status_code=400,
            detail=f"ORDER BY references unknown column or alias: {o.column!r}",
        )
    return f"{_qident(o.column)} {o.dir.upper()}"


def compile_structured(
    q: StructuredQuery,
    schema_columns: list[str],
    offset: int,
) -> tuple[str, list]:
    """Return ``(sql, params)`` ready for DuckDB ``execute()``."""
    schema = set(schema_columns)
    params: list = []

    # SELECT
    if q.aggregate:
        select_parts = [_qident(c) for c in q.group_by]
        select_parts += [_compile_aggregate(a, schema) for a in q.aggregate]
    else:
        cols = q.select or schema_columns
        for c in cols:
            _ensure_column(c, schema)
        select_parts = [_qident(c) for c in cols]
    select_sql = ", ".join(select_parts)

    # WHERE
    where_sql = ""
    if q.filters:
        clauses = [_compile_filter(f, schema, params) for f in q.filters]
        where_sql = " WHERE " + " AND ".join(clauses)

    # GROUP BY
    group_sql = ""
    if q.group_by:
        for c in q.group_by:
            _ensure_column(c, schema)
        group_sql = " GROUP BY " + ", ".join(_qident(c) for c in q.group_by)

    # ORDER BY
    order_sql = ""
    if q.order_by:
        select_aliases = {a.as_ for a in q.aggregate}
        order_sql = " ORDER BY " + ", ".join(
            _compile_order_by(o, schema, select_aliases) for o in q.order_by
        )

    sql = (
        f"SELECT {select_sql} FROM {_qident(q.dataset)}"
        f"{where_sql}{group_sql}{order_sql}"
        f" LIMIT {int(q.limit)} OFFSET {int(offset)}"
    )
    return sql, params
