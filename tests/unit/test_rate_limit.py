"""Unit tests for GitHub retry and rate-limit helpers."""

from __future__ import annotations

from unittest.mock import patch

import httpx
import pytest

from repolens.exceptions import NetworkError, RateLimitError, RepositoryNotFoundError
from repolens.github.rate_limit import (
    execute_with_retry,
    format_reset_time,
    is_abuse_detection,
    is_rate_limit_exhausted,
    raise_for_response,
)


def test_is_rate_limit_exhausted() -> None:
    response = httpx.Response(403, headers={"X-RateLimit-Remaining": "0"})
    assert is_rate_limit_exhausted(response) is True


def test_is_abuse_detection() -> None:
    response = httpx.Response(403, headers={"X-RateLimit-Remaining": "10"})
    assert is_abuse_detection(response) is True
    assert is_rate_limit_exhausted(response) is False


def test_format_reset_time() -> None:
    assert format_reset_time("1700000000") == "2023-11-14 22:13:20 UTC"
    assert format_reset_time("invalid") is None


def test_raise_for_response_not_found() -> None:
    response = httpx.Response(404)
    with pytest.raises(RepositoryNotFoundError, match="not found or is private"):
        raise_for_response(response)


def test_raise_for_response_rate_limit() -> None:
    response = httpx.Response(
        403,
        headers={"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "1700000000"},
    )
    with pytest.raises(RateLimitError, match="rate limit exhausted") as exc_info:
        raise_for_response(response)
    assert exc_info.value.reset_time == "2023-11-14 22:13:20 UTC"


@patch("repolens.github.rate_limit.time.sleep")
def test_execute_with_retry_on_server_error(mock_sleep: object) -> None:
    calls = {"count": 0}

    def request_fn() -> httpx.Response:
        calls["count"] += 1
        if calls["count"] < 3:
            return httpx.Response(503)
        return httpx.Response(200, json={"ok": True})

    response = execute_with_retry(request_fn, max_retries=3)
    assert response.status_code == 200
    assert calls["count"] == 3


@patch("repolens.github.rate_limit.time.sleep")
def test_execute_with_retry_exhausted_server_errors(mock_sleep: object) -> None:
    def request_fn() -> httpx.Response:
        return httpx.Response(503)

    with pytest.raises(NetworkError, match="unreachable"):
        execute_with_retry(request_fn, max_retries=2)


@patch("repolens.github.rate_limit.time.sleep")
def test_execute_with_retry_does_not_retry_rate_limit(mock_sleep: object) -> None:
    def request_fn() -> httpx.Response:
        return httpx.Response(403, headers={"X-RateLimit-Remaining": "0"})

    response = execute_with_retry(request_fn, max_retries=3)
    assert response.status_code == 403
    assert mock_sleep.call_count == 0


@patch("repolens.github.rate_limit.time.sleep")
def test_execute_with_retry_abuse_detection(mock_sleep: object) -> None:
    calls = {"count": 0}

    def request_fn() -> httpx.Response:
        calls["count"] += 1
        if calls["count"] <= 2:
            return httpx.Response(403, headers={"X-RateLimit-Remaining": "10"})
        return httpx.Response(200)

    response = execute_with_retry(request_fn, max_retries=3)
    assert response.status_code == 200
    assert calls["count"] == 3
