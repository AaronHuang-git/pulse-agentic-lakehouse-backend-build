"""Internal provider types + Provider protocol."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Protocol


@dataclass
class TextBlock:
    text: str
    type: Literal["text"] = "text"


@dataclass
class ToolUseBlock:
    id: str
    name: str
    input: dict[str, Any]
    type: Literal["tool_use"] = "tool_use"


ContentBlock = TextBlock | ToolUseBlock
StopReason = Literal["end_turn", "tool_use", "max_tokens", "refusal", "other"]


@dataclass
class ProviderResponse:
    content_blocks: list[ContentBlock]
    stop_reason: StopReason
    input_tokens: int = 0
    output_tokens: int = 0


class Provider(Protocol):
    async def complete(
        self,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        max_tokens: int,
    ) -> ProviderResponse: ...


def serialize_block(b: ContentBlock) -> dict[str, Any]:
    """Convert an internal block back to the dict shape the SDK expects."""
    if isinstance(b, TextBlock):
        return {"type": "text", "text": b.text}
    return {"type": "tool_use", "id": b.id, "name": b.name, "input": b.input}
