"""Retry and backoff logic for GitHub API requests."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from datetime import UTC, datetime
from typing import TypeVar

import httpx

from repolens.exceptions import NetworkError, RateLimitError, RepositoryNotFoundError

logger = logging.getLogger(__name__)

T = TypeVar("T")

_RETRYABLE_SERVER_ERRORS = frozenset({500, 502, 503, 504})
_ABUSE_MAX_RETRIES = 2
_DEFAULT_MAX_RETRIES = 3


def is_rate_limit_exhausted(response: httpx.Response) -> bool:
    """Return True when GitHub reports primary or secondary rate limiting."""
    remaining = response.headers.get("X-RateLimit-Remaining", "1")
    body = response.text.lower() if response.content else ""
    return (
        response.status_code == 429
        or (response.status_code == 403 and remaining == "0")
        or (response.status_code == 403 and "rate limit" in body)
    )


def is_abuse_detection(response: httpx.Response) -> bool:
    """Return True for GitHub abuse-detection 403 responses."""
    return response.status_code == 403 and not is_rate_limit_exhausted(response)


def format_reset_time(reset_header: str | None) -> str | None:
    """Convert X-RateLimit-Reset epoch header to a human-readable UTC timestamp."""
    if not reset_header:
        return None
    try:
        reset_epoch = int(reset_header)
    except ValueError:
        return None
    return datetime.fromtimestamp(reset_epoch, tz=UTC).strftime("%Y-%m-%d %H:%M:%S UTC")


def raise_for_response(response: httpx.Response) -> None:
    """Map GitHub HTTP failures to RepoLens exceptions."""
    if response.status_code == 404:
        raise RepositoryNotFoundError("Repository not found or is private.")

    if is_rate_limit_exhausted(response):
        reset_time = format_reset_time(response.headers.get("X-RateLimit-Reset"))
        message = "GitHub API rate limit exhausted."
        if reset_time:
            message = f"{message} Resets at {reset_time}."
        message = f"{message} Set GITHUB_TOKEN for a higher limit."
        raise RateLimitError(message, reset_time=reset_time)

    if response.status_code >= 400:
        response.raise_for_status()


def execute_with_retry(
    request_fn: Callable[[], httpx.Response],
    *,
    max_retries: int = _DEFAULT_MAX_RETRIES,
    base_delay: float = 1.0,
    backoff_factor: float = 2.0,
) -> httpx.Response:
    """Execute an HTTP request with bounded exponential backoff."""
    server_attempts = 0
    abuse_attempts = 0
    timeout_attempts = 0

    while True:
        try:
            response = request_fn()
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            timeout_attempts += 1
            if timeout_attempts > max_retries:
                raise NetworkError(
                    "GitHub is unreachable right now, try again later."
                ) from exc
            delay = base_delay * (backoff_factor ** (timeout_attempts - 1))
            logger.warning(
                "GitHub request timed out (attempt %s/%s); retrying in %.1fs",
                timeout_attempts,
                max_retries,
                delay,
            )
            time.sleep(delay)
            continue

        if response.status_code in _RETRYABLE_SERVER_ERRORS:
            server_attempts += 1
            if server_attempts > max_retries:
                raise NetworkError(
                    "GitHub is unreachable right now, try again later."
                )
            delay = base_delay * (backoff_factor ** (server_attempts - 1))
            logger.warning(
                "GitHub returned %s (attempt %s/%s); retrying in %.1fs",
                response.status_code,
                server_attempts,
                max_retries,
                delay,
            )
            time.sleep(delay)
            continue

        if is_abuse_detection(response):
            abuse_attempts += 1
            if abuse_attempts > _ABUSE_MAX_RETRIES:
                raise NetworkError(
                    "GitHub is unreachable right now, try again later."
                )
            delay = base_delay * (backoff_factor ** (abuse_attempts - 1))
            logger.warning(
                "GitHub abuse detection triggered (attempt %s/%s); retrying in %.1fs",
                abuse_attempts,
                _ABUSE_MAX_RETRIES,
                delay,
            )
            time.sleep(delay)
            continue

        return response
