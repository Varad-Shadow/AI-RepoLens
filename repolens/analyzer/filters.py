"""Path-component ignore-list filtering for repository trees."""

from __future__ import annotations

from pathlib import PurePosixPath

EXCLUDED_DIRS: frozenset[str] = frozenset(
    {
        ".git",
        "node_modules",
        "__pycache__",
        ".venv",
        "venv",
        "dist",
        "build",
        "coverage",
        "target",
        "vendor",
        ".next",
        ".cache",
        ".idea",
        ".vscode",
    }
)

# Explicitly not excluded by default (documented for reviewers):
# test, tests, src, app, server, client, lib, config


def path_components(path: str) -> tuple[str, ...]:
    """Return normalized path components using forward slashes."""
    normalized = path.replace("\\", "/").strip("/")
    if not normalized:
        return ()
    return PurePosixPath(normalized).parts


def is_ignored(
    path: str,
    excluded_dirs: frozenset[str] | None = None,
) -> bool:
    """Return True when any whole path component matches the ignore list."""
    excluded = excluded_dirs if excluded_dirs is not None else EXCLUDED_DIRS
    return any(part in excluded for part in path_components(path))


def filter_paths(
    paths: list[str],
    excluded_dirs: frozenset[str] | None = None,
) -> tuple[list[str], list[str]]:
    """Split paths into kept and ignored lists preserving input order."""
    kept: list[str] = []
    ignored: list[str] = []
    for path in paths:
        if is_ignored(path, excluded_dirs):
            ignored.append(path)
        else:
            kept.append(path)
    return kept, ignored
