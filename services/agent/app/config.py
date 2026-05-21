"""Agent service settings (thin wrapper around shared/config.py)."""
from __future__ import annotations

from functools import lru_cache
from typing import Literal

from shared.config import get_settings as get_shared_settings


class AgentSettings:
    """Read-only view of agent-relevant settings."""

    def __init__(self) -> None:
        s = get_shared_settings()
        self.provider: Literal["anthropic", "mock"] = (
            "anthropic" if s.pulse_agent_provider == "anthropic" else "mock"
        )
        self.model: str = s.pulse_agent_model
        self.anthropic_api_key: str = s.anthropic_api_key
        self.query_service_url: str = s.query_service_url.rstrip("/")
        # Loop safety
        self.max_iterations: int = 8
        self.max_input_tokens: int = 50_000
        self.max_output_tokens: int = 4_000
        self.timeout_seconds: int = 60


@lru_cache
def get_agent_settings() -> AgentSettings:
    return AgentSettings()
