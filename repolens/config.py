"""Environment-based configuration, validated at startup."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal

from dotenv import load_dotenv

from repolens.exceptions import ConfigurationError, MissingAPIKeyError

load_dotenv()

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
LLMProvider = Literal["anthropic"]


def _get_env(key: str, default: str | None = None) -> str | None:
    value = os.getenv(key, default)
    if value is not None and value.strip() == "":
        return default
    return value


def _require_int(key: str, default: int, *, min_value: int = 1) -> int:
    raw = _get_env(key, str(default))
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ConfigurationError(
            f"{key} must be an integer, got {raw!r}"
        ) from exc
    if value < min_value:
        raise ConfigurationError(
            f"{key} must be >= {min_value}, got {value}"
        )
    return value


def _require_log_level(key: str, default: LogLevel) -> LogLevel:
    raw = (_get_env(key, default) or default).upper()
    valid: tuple[LogLevel, ...] = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")
    if raw not in valid:
        raise ConfigurationError(
            f"{key} must be one of {', '.join(valid)}, got {raw!r}"
        )
    return raw  # type: ignore[return-value]


@dataclass(frozen=True)
class Config:
    """Validated application configuration."""

    github_token: str | None
    llm_provider: LLMProvider
    llm_api_key: str | None
    llm_model: str
    max_files_analyzed: int
    max_file_size_bytes: int
    max_context_size: int
    request_timeout: int
    max_retries: int
    log_level: LogLevel

    @classmethod
    def from_env(cls, *, no_ai: bool = False) -> Config:
        """Load and validate configuration from environment variables."""
        provider = (_get_env("LLM_PROVIDER", "anthropic") or "anthropic").lower()
        if provider != "anthropic":
            raise ConfigurationError(
                f"LLM_PROVIDER must be 'anthropic' for MVP, got {provider!r}"
            )

        llm_api_key = _get_env("LLM_API_KEY")
        if not no_ai and not llm_api_key:
            # Validation deferred to pipeline when analyze is invoked without --no-ai
            pass

        return cls(
            github_token=_get_env("GITHUB_TOKEN"),
            llm_provider="anthropic",
            llm_api_key=llm_api_key,
            llm_model=_get_env("LLM_MODEL", "claude-sonnet-4-6") or "claude-sonnet-4-6",
            max_files_analyzed=_require_int("MAX_FILES_ANALYZED", 12, min_value=1),
            max_file_size_bytes=_require_int("MAX_FILE_SIZE_BYTES", 15000, min_value=1),
            max_context_size=_require_int("MAX_CONTEXT_SIZE", 12000, min_value=1),
            request_timeout=_require_int("REQUEST_TIMEOUT", 10, min_value=1),
            max_retries=_require_int("MAX_RETRIES", 3, min_value=0),
            log_level=_require_log_level("LOG_LEVEL", "INFO"),
        )

    def require_llm_api_key(self) -> str:
        """Return LLM API key or raise if missing."""
        if not self.llm_api_key:
            raise MissingAPIKeyError(
                "LLM_API_KEY is required for AI analysis. "
                "Set it in .env or use --no-ai to skip LLM analysis."
            )
        return self.llm_api_key
