"""Unit tests for configuration loading and validation."""

from __future__ import annotations

import os

import pytest

from repolens.config import Config
from repolens.exceptions import ConfigurationError


@pytest.fixture(autouse=True)
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Clear config-related env vars before each test."""
    keys = [
        "GITHUB_TOKEN",
        "LLM_PROVIDER",
        "LLM_API_KEY",
        "LLM_MODEL",
        "MAX_FILES_ANALYZED",
        "MAX_FILE_SIZE_BYTES",
        "MAX_CONTEXT_SIZE",
        "REQUEST_TIMEOUT",
        "MAX_RETRIES",
        "LOG_LEVEL",
    ]
    for key in keys:
        monkeypatch.delenv(key, raising=False)


def test_default_config_values() -> None:
    config = Config.from_env()
    assert config.llm_provider == "anthropic"
    assert config.llm_model == "claude-sonnet-4-6"
    assert config.max_files_analyzed == 12
    assert config.max_file_size_bytes == 15000
    assert config.max_context_size == 12000
    assert config.request_timeout == 10
    assert config.max_retries == 3
    assert config.log_level == "INFO"
    assert config.github_token is None
    assert config.llm_api_key is None


def test_custom_config_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MAX_FILES_ANALYZED", "20")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_test")

    config = Config.from_env()
    assert config.max_files_analyzed == 20
    assert config.log_level == "DEBUG"
    assert config.github_token == "ghp_test"


def test_invalid_max_files_raises_clear_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MAX_FILES_ANALYZED", "not-a-number")
    with pytest.raises(ConfigurationError, match="MAX_FILES_ANALYZED must be an integer"):
        Config.from_env()


def test_max_files_below_minimum_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MAX_FILES_ANALYZED", "0")
    with pytest.raises(ConfigurationError, match="MAX_FILES_ANALYZED must be >= 1"):
        Config.from_env()


def test_invalid_log_level_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOG_LEVEL", "VERBOSE")
    with pytest.raises(ConfigurationError, match="LOG_LEVEL must be one of"):
        Config.from_env()


def test_invalid_llm_provider_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    with pytest.raises(ConfigurationError, match="LLM_PROVIDER must be 'anthropic'"):
        Config.from_env()


def test_require_llm_api_key_raises_when_missing() -> None:
    config = Config.from_env()
    with pytest.raises(ConfigurationError, match="LLM_API_KEY is required"):
        config.require_llm_api_key()


def test_require_llm_api_key_returns_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_API_KEY", "sk-test")
    config = Config.from_env()
    assert config.require_llm_api_key() == "sk-test"


def test_empty_string_env_uses_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MAX_FILES_ANALYZED", "")
    config = Config.from_env()
    assert config.max_files_analyzed == 12
