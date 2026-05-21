"""Bounded tool-use loop. Provider-agnostic."""
from __future__ import annotations

import json
from typing import Any

import httpx
from fastapi import HTTPException, status

from services.agent.app.config import get_agent_settings
from services.agent.app.dispatcher import ToolError, call_tool, summarize_result
from services.agent.app.models import AskResponse, TokenUsage, ToolCallRecord
from services.agent.app.providers import get_provider
from services.agent.app.providers.base import (
    ProviderResponse,
    TextBlock,
    ToolUseBlock,
    serialize_block,
)
from services.agent.app.system_prompt import SYSTEM_PROMPT
from services.agent.app.tool_specs import TOOL_SPECS
from shared.metrics import AGENT_ITERATIONS, AGENT_TOKENS, AGENT_TOOL_CALLS

MAX_TOOL_RESULT_BYTES = 30_000  # cap result size fed back to model


async def run_agent(
    question: str,
    bearer_token: str,
) -> AskResponse:
    settings = get_agent_settings()
    provider = get_provider()

    messages: list[dict[str, Any]] = [{"role": "user", "content": question}]
    tool_call_trace: list[ToolCallRecord] = []
    final_text_parts: list[str] = []
    iterations = 0
    total_input = 0
    total_output = 0

    async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
        while iterations < settings.max_iterations:
            iterations += 1

            try:
                resp: ProviderResponse = await provider.complete(
                    system=SYSTEM_PROMPT,
                    messages=messages,
                    tools=TOOL_SPECS,
                    max_tokens=settings.max_output_tokens,
                )
            except Exception as exc:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"Provider call failed: {exc!r}",
                ) from exc

            total_input += resp.input_tokens
            total_output += resp.output_tokens
            if total_input > settings.max_input_tokens:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Input token budget exceeded.",
                )

            messages.append({
                "role": "assistant",
                "content": [serialize_block(b) for b in resp.content_blocks],
            })

            text_blocks = [b for b in resp.content_blocks if isinstance(b, TextBlock)]
            tool_use_blocks = [b for b in resp.content_blocks if isinstance(b, ToolUseBlock)]

            if resp.stop_reason == "end_turn":
                final_text_parts.extend(b.text for b in text_blocks)
                break

            if resp.stop_reason == "tool_use":
                if not tool_use_blocks:
                    raise HTTPException(
                        status_code=500,
                        detail="Provider returned stop_reason=tool_use with no tool_use blocks.",
                    )
                tool_results: list[dict[str, Any]] = []
                for block in tool_use_blocks:
                    try:
                        result = await call_tool(
                            block.name, block.input, bearer_token, client
                        )
                        summary = summarize_result(block.name, result)
                        tool_call_trace.append(
                            ToolCallRecord(
                                tool=block.name,
                                input=block.input,
                                output_summary=summary,
                            )
                        )
                        AGENT_TOOL_CALLS.labels(tool=block.name, error="false").inc()
                        content_str = json.dumps(result, default=str)
                        if len(content_str) > MAX_TOOL_RESULT_BYTES:
                            content_str = content_str[:MAX_TOOL_RESULT_BYTES] + " ...[truncated]"
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": content_str,
                        })
                    except ToolError as exc:
                        tool_call_trace.append(
                            ToolCallRecord(
                                tool=block.name,
                                input=block.input,
                                output_summary="",
                                error=str(exc),
                            )
                        )
                        AGENT_TOOL_CALLS.labels(tool=block.name, error="true").inc()
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": f"Error: {exc}",
                            "is_error": True,
                        })
                messages.append({"role": "user", "content": tool_results})
                continue

            # Any other stop_reason ends the loop with whatever text we have.
            final_text_parts.extend(b.text for b in text_blocks)
            break
        else:
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail=f"Agent exceeded max iterations ({settings.max_iterations}).",
            )

    AGENT_ITERATIONS.labels(provider=settings.provider).observe(iterations)
    AGENT_TOKENS.labels(provider=settings.provider, direction="input").inc(total_input)
    AGENT_TOKENS.labels(provider=settings.provider, direction="output").inc(total_output)

    return AskResponse(
        answer=" ".join(p.strip() for p in final_text_parts if p.strip()),
        tool_calls=tool_call_trace,
        iterations=iterations,
        model=settings.model,
        provider=settings.provider,
        tokens_used=TokenUsage(input=total_input, output=total_output),
    )
