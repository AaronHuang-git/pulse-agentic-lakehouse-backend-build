"""Mock provider: deterministic tool-use sequence for offline / CI / no-API-key.

Strategy: ignore the user's question content; always emit the same three-turn
sequence (list_datasets -> run_query -> final answer constructed from the
actual query result so the response reflects real data).
"""
from __future__ import annotations

import json
import uuid
from typing import Any

from services.agent.app.providers.base import (
    ProviderResponse,
    TextBlock,
    ToolUseBlock,
)


class MockProvider:
    def __init__(self) -> None:
        self._model = "mock-fixed-sequence-v1"

    async def complete(
        self,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        max_tokens: int,
    ) -> ProviderResponse:
        prior_assistant_turns = sum(1 for m in messages if m["role"] == "assistant")

        if prior_assistant_turns == 0:
            return _wrap_tool_call("list_datasets", {})

        if prior_assistant_turns == 1:
            return _wrap_tool_call(
                "run_query",
                {
                    "dataset": "olist_geolocation",
                    "group_by": ["geolocation_state"],
                    "aggregate": [{"fn": "count", "as": "n"}],
                    "order_by": [{"column": "n", "dir": "desc"}],
                    "limit": 5,
                },
            )

        answer = _craft_answer_from_history(messages)
        return ProviderResponse(
            content_blocks=[TextBlock(text=answer)],
            stop_reason="end_turn",
            input_tokens=42,
            output_tokens=42,
        )


def _wrap_tool_call(name: str, args: dict[str, Any]) -> ProviderResponse:
    return ProviderResponse(
        content_blocks=[
            ToolUseBlock(id=f"toolu_{uuid.uuid4().hex[:12]}", name=name, input=args),
        ],
        stop_reason="tool_use",
        input_tokens=42,
        output_tokens=42,
    )


def _craft_answer_from_history(messages: list[dict[str, Any]]) -> str:
    """Find the last run_query result in the conversation and summarize."""
    last = messages[-1]
    if last["role"] != "user" or not isinstance(last["content"], list):
        return "[MOCK] No tool results available to summarize."
    for block in last["content"]:
        if block.get("type") != "tool_result":
            continue
        try:
            result = json.loads(block["content"])
        except Exception:
            continue
        rows = result.get("rows") if isinstance(result, dict) else None
        if rows and "geolocation_state" in rows[0]:
            parts = [
                f"{r['geolocation_state']} ({r['n']:,} rows)" for r in rows[:3]
            ]
            return (
                "[MOCK provider] Top Brazilian states by geolocation row count: "
                + ", ".join(parts) + "."
            )
    return "[MOCK] Could not find a run_query result in the conversation."
