"""Secret path exclusion and lightweight content redaction."""

from __future__ import annotations

import re
from fnmatch import fnmatch
from pathlib import PurePosixPath

SECRET_FILENAME_PATTERNS: tuple[str, ...] = (
    ".env",
    ".env.*",
    "*.pem",
    "*.key",
    "*.pfx",
    "*id_rsa*",
    "*id_dsa*",
    "credentials.*",
    "secret*.*",
    "*.p12",
    "*.keystore",
    ".npmrc",
    ".netrc",
)

_SECRET_CONTENT_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(
        r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----",
        re.DOTALL,
    ),
    re.compile(
        r"(?i)(api[_-]?key\s*=\s*)['\"][^'\"\r\n]+['\"]",
    ),
    re.compile(
        r"(?i)(token\s*=\s*)['\"][^'\"\r\n]+['\"]",
    ),
)


def _path_parts(path: str) -> tuple[str, ...]:
    normalized = path.replace("\\", "/").strip("/")
    if not normalized:
        return ()
    return PurePosixPath(normalized).parts


def is_secret_path(path: str) -> bool:
    """Return True if a file path should never be read for AI context."""
    parts = tuple(part.lower() for part in _path_parts(path))
    if not parts:
        return False
    name = parts[-1]
    return any(fnmatch(name, pattern) for pattern in SECRET_FILENAME_PATTERNS)


def filter_secret_paths(paths: list[str]) -> tuple[list[str], list[str]]:
    """Split paths into safe and secret-like lists while preserving order."""
    safe: list[str] = []
    excluded: list[str] = []
    for path in paths:
        if is_secret_path(path):
            excluded.append(path)
        else:
            safe.append(path)
    return safe, excluded


def redact_secrets(content: str) -> str:
    """Redact common secret-looking substrings from already-selected text."""
    redacted = content
    for pattern in _SECRET_CONTENT_PATTERNS:
        redacted = pattern.sub(_redaction_replacement, redacted)
    return redacted


def _redaction_replacement(match: re.Match[str]) -> str:
    if match.lastindex:
        return f"{match.group(1)}[REDACTED]"
    return "[REDACTED]"