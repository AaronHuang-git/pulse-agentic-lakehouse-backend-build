"""Unit tests for the structured-DSL compiler."""
from __future__ import annotations

import pytest
from fastapi import HTTPException

from services.query.app.dsl import compile_structured
from services.query.app.models import (
    Aggregate,
    Filter,
    OrderBy,
    StructuredQuery,
)

SCHEMA = ["order_id", "customer_id", "order_status", "price", "order_date"]


def test_simple_count_no_filter() -> None:
    q = StructuredQuery(
        dataset="orders",
        aggregate=[Aggregate(fn="count", **{"as": "n"})],
    )
    sql, params = compile_structured(q, SCHEMA, offset=0)
    assert "COUNT(*)" in sql
    assert 'FROM "orders"' in sql
    assert "LIMIT 100" in sql
    assert "OFFSET 0" in sql
    assert params == []


def test_filter_compiles_to_parameterized_sql() -> None:
    q = StructuredQuery(
        dataset="orders",
        filters=[Filter(column="order_status", op="eq", value="delivered")],
    )
    sql, params = compile_structured(q, SCHEMA, offset=0)
    assert '"order_status" = ?' in sql
    assert params == ["delivered"]


def test_group_by_aggregate_sort() -> None:
    q = StructuredQuery(
        dataset="orders",
        group_by=["order_status"],
        aggregate=[Aggregate(fn="count", **{"as": "n"})],
        order_by=[OrderBy(column="n", dir="desc")],
        limit=10,
    )
    sql, params = compile_structured(q, SCHEMA, offset=0)
    assert 'GROUP BY "order_status"' in sql
    assert 'ORDER BY "n" DESC' in sql
    assert "LIMIT 10" in sql


def test_in_operator_expands_placeholders() -> None:
    q = StructuredQuery(
        dataset="orders",
        filters=[Filter(column="order_status", op="in", value=["delivered", "shipped"])],
    )
    sql, params = compile_structured(q, SCHEMA, offset=0)
    assert '"order_status" IN (?, ?)' in sql
    assert params == ["delivered", "shipped"]


def test_between_requires_two_values() -> None:
    q = StructuredQuery(
        dataset="orders",
        filters=[Filter(column="price", op="between", value=[10, 100])],
    )
    sql, params = compile_structured(q, SCHEMA, offset=0)
    assert '"price" BETWEEN ? AND ?' in sql
    assert params == [10, 100]


def test_contains_uses_like_with_wildcards() -> None:
    q = StructuredQuery(
        dataset="orders",
        filters=[Filter(column="customer_id", op="contains", value="abc")],
    )
    sql, params = compile_structured(q, SCHEMA, offset=0)
    assert '"customer_id" LIKE ?' in sql
    assert params == ["%abc%"]


def test_is_null_takes_no_parameter() -> None:
    q = StructuredQuery(
        dataset="orders",
        filters=[Filter(column="price", op="is_null")],
    )
    sql, params = compile_structured(q, SCHEMA, offset=0)
    assert '"price" IS NULL' in sql
    assert params == []


def test_unknown_column_rejected() -> None:
    q = StructuredQuery(
        dataset="orders",
        filters=[Filter(column="nope", op="eq", value=1)],
    )
    with pytest.raises(HTTPException) as exc:
        compile_structured(q, SCHEMA, offset=0)
    assert exc.value.status_code == 400


def test_double_quote_in_identifier_rejected() -> None:
    q = StructuredQuery(
        dataset='ord"ers',
        aggregate=[Aggregate(fn="count", **{"as": "n"})],
    )
    with pytest.raises(HTTPException) as exc:
        compile_structured(q, list(SCHEMA), offset=0)
    assert exc.value.status_code == 400


def test_offset_threaded_through() -> None:
    q = StructuredQuery(dataset="orders", limit=50)
    sql, _ = compile_structured(q, SCHEMA, offset=150)
    assert "LIMIT 50" in sql
    assert "OFFSET 150" in sql
