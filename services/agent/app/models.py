"""Pydantic models for the agent service."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)


class ToolCallRecord(BaseModel):
    tool: str
    input: dict[str, Any]
    output_summary: str
    error: str | None = None


class TokenUsage(BaseModel):
    input: int = 0
    output: int = 0


class AskResponse(BaseModel):
    answer: str
    tool_calls: list[ToolCallRecord]
    iterations: int
    model: str
    provider: str
    tokens_used: TokenUsage
