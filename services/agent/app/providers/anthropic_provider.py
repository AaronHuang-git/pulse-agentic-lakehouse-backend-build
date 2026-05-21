"""Anthropic provider: thin wrapper around the official SDK."""
from __future__ import annotations

from typing import Any, cast

from anthropic import AsyncAnthropic
from anthropic.types import MessageParam, ToolParam

from services.agent.app.config import get_agent_settings
from services.agent.app.providers.base import (
    ContentBlock,
    ProviderResponse,
    StopReason,
    TextBlock,
    ToolUseBlock,
)


class AnthropicProvider:
    def __init__(self) -> None:
        s = get_agent_settings()
        self._client = AsyncAnthropic(api_key=s.anthropic_api_key)
        self._model = s.model

    async def complete(
        self,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        max_tokens: int,
    ) -> ProviderResponse:
        resp = await self._client.messages.create(
            model=self._model,
            system=system,
            messages=cast(list[MessageParam], messages),
            tools=cast(list[ToolParam], tools),
            max_tokens=max_tokens,
        )

        blocks: list[ContentBlock] = []
        for block in resp.content:
            if block.type == "text":
                blocks.append(TextBlock(text=block.text))
            elif block.type == "tool_use":
                blocks.append(
                    ToolUseBlock(id=block.id, name=block.name, input=dict(block.input))
                )
            # Ignore other block types for now.

        stop_reason: StopReason = (
            resp.stop_reason  # type: ignore[assignment]
            if resp.stop_reason in {"end_turn", "tool_use", "max_tokens", "refusal"}
            else "other"
        )

        return ProviderResponse(
            content_blocks=blocks,
            stop_reason=stop_reason,
            input_tokens=resp.usage.input_tokens,
            output_tokens=resp.usage.output_tokens,
        )
