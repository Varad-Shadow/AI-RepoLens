"""Provider-agnostic LLM client with an Anthropic MVP implementation."""

from __future__ import annotations

import time
from typing import Protocol

import httpx

from repolens.config import Config
from repolens.exceptions import LLMError

ANTHROPIC_MESSAGES_URL = "https://api.anthropic.com/v1/messages"


class LLMClient(Protocol):
    """Small interface used by the pipeline and tests."""

    def generate(self, system: str, user: str) -> str:
        """Generate one structured response."""


class AnthropicLLMClient:
    """Anthropic Messages API wrapper."""

    def __init__(self, config: Config, *, client: httpx.Client | None = None) -> None:
        self._config = config
        self._owns_client = client is None
        self._client = client or httpx.Client(timeout=config.request_timeout)

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> "AnthropicLLMClient":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def generate(self, system: str, user: str) -> str:
        """Call the configured Anthropic model and return text content."""
        api_key = self._config.require_llm_api_key()
        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        payload = {
            "model": self._config.llm_model,
            "max_tokens": 2048,
            "system": system,
            "messages": [{"role": "user", "content": user}],
        }

        last_error: Exception | None = None
        for attempt in range(3):
            try:
                response = self._client.post(
                    ANTHROPIC_MESSAGES_URL,
                    headers=headers,
                    json=payload,
                )
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                last_error = exc
                if attempt == 2:
                    break
                time.sleep(2**attempt)
                continue

            if response.status_code >= 500:
                last_error = LLMError("LLM provider is temporarily unavailable.")
                if attempt == 2:
                    break
                time.sleep(2**attempt)
                continue
            if response.status_code >= 400:
                raise LLMError("LLM provider rejected the request or credentials.")

            data = response.json()
            content = data.get("content", [])
            for item in content:
                if item.get("type") == "text" and item.get("text"):
                    return str(item["text"])
            raise LLMError("LLM provider returned no text content.")

        raise LLMError("LLM provider failed after retries.") from last_error