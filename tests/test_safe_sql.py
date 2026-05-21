"""Unit tests for the safe-SQL validator."""
from __future__ import annotations

import pytest
from fastapi import HTTPException

from services.query.app.safe_sql import validate_and_referenced_tables


def test_simple_select_accepted() -> None:
    sql, tables = validate_and_referenced_tables(
        "SELECT order_id FROM orders WHERE price > 10"
    )
    assert "SELECT" in sql.upper()
    assert tables == ["orders"]


def test_aggregate_select_accepted() -> None:
    sql, tables = validate_and_referenced_tables(
        "SELECT order_status, COUNT(*) FROM orders GROUP BY 1"
    )
    assert tables == ["orders"]


def test_join_returns_both_tables() -> None:
    sql, tables = validate_and_referenced_tables(
        "SELECT o.order_id FROM orders o "
        "JOIN customers c ON o.customer_id = c.id"
    )
    assert set(tables) == {"orders", "customers"}


def test_drop_table_rejected() -> None:
    with pytest.raises(HTTPException) as exc:
        validate_and_referenced_tables("DROP TABLE orders")
    assert exc.value.status_code == 400


def test_delete_rejected() -> None:
    with pytest.raises(HTTPException) as exc:
        validate_and_referenced_tables("DELETE FROM orders")
    assert exc.value.status_code == 400


def test_insert_rejected() -> None:
    with pytest.raises(HTTPException) as exc:
        validate_and_referenced_tables(
            "INSERT INTO orders (id) VALUES (1)"
        )
    assert exc.value.status_code == 400


def test_update_rejected() -> None:
    with pytest.raises(HTTPException) as exc:
        validate_and_referenced_tables(
            "UPDATE orders SET price = 0"
        )
    assert exc.value.status_code == 400


def test_multiple_statements_rejected() -> None:
    with pytest.raises(HTTPException) as exc:
        validate_and_referenced_tables(
            "SELECT 1; SELECT 2"
        )
    assert exc.value.status_code == 400


def test_unparseable_rejected() -> None:
    with pytest.raises(HTTPException) as exc:
        validate_and_referenced_tables("this is not sql at all !!!!")
    assert exc.value.status_code == 400


def test_select_with_no_tables_rejected() -> None:
    # `SELECT 1` parses fine but doesn't reference a dataset; we require at
    # least one named table so tenant-scoped views can be registered.
    with pytest.raises(HTTPException) as exc:
        validate_and_referenced_tables("SELECT 1")
    assert exc.value.status_code == 400
