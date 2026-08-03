"""Unit tests for the Anthropic LLM wrapper."""

from __future__ import annotations

import httpx
import pytest

from repolens.ai.llm_client import AnthropicLLMClient
from repolens.config import Config
from repolens.exceptions import LLMError, MissingAPIKeyError


def _config(api_key: str | None = "test-key") -> Config:
    return Config(
        github_token=None,
        llm_provider="anthropic",
        llm_api_key=api_key,
        llm_model="claude-sonnet-4-6",
        max_files_analyzed=12,
        max_file_size_bytes=15000,
        max_context_size=12000,
        request_timeout=10,
        max_retries=3,
        log_level="INFO",
    )


def test_anthropic_client_returns_text_from_mock_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["x-api-key"] == "test-key"
        return httpx.Response(200, json={"content": [{"type": "text", "text": "{}"}]})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    llm = AnthropicLLMClient(_config(), client=client)

    assert llm.generate("system", "user") == "{}"


def test_anthropic_client_requires_api_key() -> None:
    llm = AnthropicLLMClient(_config(api_key=None), client=httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200))))

    with pytest.raises(MissingAPIKeyError):
        llm.generate("system", "user")


def test_anthropic_client_maps_4xx_to_llm_error() -> None:
    client = httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(401)))
    llm = AnthropicLLMClient(_config(), client=client)

    with pytest.raises(LLMError):
        llm.generate("system", "user")