"""Unit tests for approximate token budgeting."""

from __future__ import annotations

from repolens.ai.token_budget import estimate_tokens, truncate_to_token_budget


def test_estimate_tokens_uses_character_heuristic() -> None:
    assert estimate_tokens("abcd") == 1
    assert estimate_tokens("abcde") == 2


def test_truncate_to_token_budget_caps_estimate() -> None:
    text = "x" * 100

    truncated = truncate_to_token_budget(text, 10)

    assert estimate_tokens(truncated) <= 10
    assert "truncated" in truncated