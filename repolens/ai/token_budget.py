"""Approximate token estimation and truncation helpers."""

from __future__ import annotations

CHARS_PER_TOKEN = 4
TRUNCATION_MARKER = "\n[truncated]\n"


def estimate_tokens(text: str) -> int:
    """Estimate tokens with a conservative character heuristic."""
    if not text:
        return 0
    return max(1, (len(text) + CHARS_PER_TOKEN - 1) // CHARS_PER_TOKEN)


def truncate_to_token_budget(
    text: str,
    max_tokens: int,
    *,
    marker: str = TRUNCATION_MARKER,
) -> str:
    """Truncate text so the estimate fits within max_tokens."""
    if max_tokens <= 0:
        return marker.strip()
    if estimate_tokens(text) <= max_tokens:
        return text

    max_chars = max_tokens * CHARS_PER_TOKEN
    marker_chars = len(marker)
    if max_chars <= marker_chars:
        return marker[:max_chars]
    return text[: max_chars - marker_chars] + marker