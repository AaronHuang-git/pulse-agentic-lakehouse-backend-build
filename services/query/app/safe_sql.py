"""SQL safety: validate a SELECT-only statement and register required views."""
from __future__ import annotations

import sqlglot
from fastapi import HTTPException, status
from sqlglot import exp

from services.query.app.duck import register_dataset_view

# Top-level expression types that count as read-only SELECT-shape statements.
_ALLOWED_TOP_TYPES = (exp.Select, exp.Union, exp.With, exp.Subquery)

# Mutating / DDL expression types we reject at any depth.
# Build the tuple defensively because sqlglot occasionally renames these
# across major versions.
_MUTATING_NAMES = (
    "Insert", "Update", "Delete",
    "Drop", "Create", "Alter",
    "TruncateTable", "Truncate",
    "Command",  # sqlglot wraps unknown/unsupported statements as Command
)
_MUTATING_TYPES = tuple(
    t for t in (getattr(exp, n, None) for n in _MUTATING_NAMES) if t is not None
)


def validate_and_referenced_tables(sql: str) -> tuple[str, list[str]]:
    """Parse user SQL; ensure single SELECT; return normalized SQL + tables.

    Raises 400 on anything we don't allow.
    """
    try:
        statements = sqlglot.parse(sql, read="duckdb")
    except sqlglot.errors.ParseError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"SQL parse error: {exc}",
        ) from exc

    statements = [s for s in statements if s is not None]
    if len(statements) != 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Exactly one SQL statement is allowed.",
        )
    stmt = statements[0]

    if isinstance(stmt, _MUTATING_TYPES):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only read-only SELECT statements are allowed.",
        )
    if not isinstance(stmt, _ALLOWED_TOP_TYPES):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only SELECT / CTE / UNION statements are allowed.",
        )

    # Walk the tree to catch a mutating construct nested inside (e.g. CTE).
    for node in stmt.walk():
        if isinstance(node, _MUTATING_TYPES):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Forbidden SQL construct detected.",
            )

    tables = [t.name for t in stmt.find_all(exp.Table)]
    if not tables:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="SQL must reference at least one dataset.",
        )

    normalized = stmt.sql(dialect="duckdb")
    return normalized, list(dict.fromkeys(tables))  # preserve order, dedupe


def register_views(con, tenant_id: str, datasets: list[str]) -> None:
    for d in datasets:
        register_dataset_view(con, tenant_id, d)
