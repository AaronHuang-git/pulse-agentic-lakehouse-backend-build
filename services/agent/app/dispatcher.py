"""Dispatch tool calls to the query service.

Each tool maps to one HTTP call. Auth is forwarded from the original
caller — the agent service never elevates privileges, the tenant scope
of every tool call equals the tenant scope of the asker.
"""
from __future__ import annotations

import json
from typing import Any

import httpx

from services.agent.app.config import get_agent_settings


class ToolError(Exception):
    """Raised when a tool call fails. The error message is fed back to the model."""


async def call_tool(
    name: str,
    args: dict[str, Any],
    bearer_token: str,
    client: httpx.AsyncClient,
) -> dict[str, Any] | list[Any]:
    """Execute the named tool with the given args. Returns the parsed JSON.

    Raises ``ToolError`` with a human-readable message on failure; the loop
    feeds that back to the model as a tool_result with ``is_error=True``.
    """
    base = get_agent_settings().query_service_url
    headers = {"Authorization": bearer_token}

    try:
        if name == "list_datasets":
            r = await client.get(f"{base}/v1/datasets", headers=headers)
        elif name == "describe_dataset":
            dataset = args["name"]
            r = await client.get(
                f"{base}/v1/datasets/{dataset}", headers=headers
            )
        elif name == "run_query":
            r = await client.post(
                f"{base}/v1/query/structured", headers=headers, json=args
            )
        elif name == "get_distinct_values":
            r = await client.get(
                f"{base}/v1/query/distinct_values",
                headers=headers,
                params={
                    "dataset": args["dataset"],
                    "column": args["column"],
                    "limit": args.get("limit", 100),
                },
            )
        else:
            raise ToolError(f"Unknown tool: {name}")

        if r.status_code >= 400:
            try:
                detail = r.json().get("detail", r.text)
            except Exception:
                detail = r.text or r.reason_phrase
            raise ToolError(f"HTTP {r.status_code}: {detail}")

        return r.json()
    except httpx.HTTPError as exc:
        raise ToolError(f"HTTP request failed: {exc!r}") from exc
    except KeyError as exc:
        raise ToolError(f"Missing required argument: {exc!s}") from exc


def summarize_result(name: str, result: dict[str, Any] | list[Any]) -> str:
    """Short human-readable summary of a tool result for the trace."""
    if isinstance(result, list):
        return f"{len(result)} items"
    if name == "describe_dataset":
        return (
            f"{result.get('name')}: {len(result.get('columns', []))} columns, "
            f"{result.get('total_rows', 0):,} rows"
        )
    if name == "run_query":
        rows = result.get("rows", [])
        first_keys = list(rows[0].keys()) if rows else []
        return f"Returned {result.get('row_count', 0)} rows; columns: {first_keys}"
    if name == "get_distinct_values":
        return f"{len(result.get('values', []))} distinct values"
    return json.dumps(result)[:200]
