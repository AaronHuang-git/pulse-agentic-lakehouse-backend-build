"""Provider factory."""
from __future__ import annotations

from services.agent.app.config import get_agent_settings
from services.agent.app.providers.anthropic_provider import AnthropicProvider
from services.agent.app.providers.base import Provider
from services.agent.app.providers.mock_provider import MockProvider


def _looks_like_placeholder(key: str) -> bool:
    return not key or "REPLACE" in key.upper() or key.endswith("ME")


def get_provider() -> Provider:
    s = get_agent_settings()
    if s.provider == "anthropic":
        if _looks_like_placeholder(s.anthropic_api_key):
            # Defensive fallback: misconfigured Anthropic = use mock rather
            # than crash. The selected provider is reported in the response
            # so the caller can spot the silent fallback.
            return MockProvider()
        return AnthropicProvider()
    return MockProvider()
