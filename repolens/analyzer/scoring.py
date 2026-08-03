"""Deterministic file importance scoring."""

from __future__ import annotations

from pathlib import PurePosixPath

from repolens.analyzer.classifier import (
    is_ci_file,
    is_config_file,
    is_dependency_file,
    is_license,
    is_readme,
    is_test_file,
)
from repolens.analyzer.models import FileEntry, ScoredFile

ENTRYPOINT_NAMES = frozenset(
    {
        "main",
        "app",
        "index",
        "server",
        "cli",
        "wsgi",
        "asgi",
    }
)

ROUTING_COMPONENTS = frozenset({"routes", "controllers", "api", "handlers"})


def normalize_path(path: str) -> str:
    """Normalize repository paths for deterministic scoring comparisons."""
    return path.replace("\\", "/").strip("/")


def _path_parts(path: str) -> tuple[str, ...]:
    return PurePosixPath(normalize_path(path)).parts


def _stem(path: str) -> str:
    return PurePosixPath(normalize_path(path)).stem.lower()


def _depth(path: str) -> int:
    parts = _path_parts(path)
    return max(len(parts) - 1, 0)


def score_file(
    file_entry: FileEntry,
    *,
    max_file_size_bytes: int = 15_000,
) -> ScoredFile:
    """Return the deterministic importance score and human-readable reasons."""
    score = 0.0
    reasons: list[str] = []
    path = file_entry.path
    parts = tuple(part.lower() for part in _path_parts(path))

    if len(parts) == 1:
        score += 5
        reasons.append("root-level file")

    if is_readme(path):
        score += 8
        reasons.append("README")

    if is_license(path):
        score += 1
        reasons.append("license")

    if is_dependency_file(path):
        score += 7
        reasons.append("dependency manifest")

    if _stem(path) in ENTRYPOINT_NAMES:
        score += 6
        reasons.append("entry-point filename")

    if any(part in ROUTING_COMPONENTS for part in parts):
        score += 5
        reasons.append("routing/controller/API path")

    if "config" in parts or is_config_file(path):
        score += 3
        reasons.append("configuration")

    if file_entry.category == "test" or is_test_file(path):
        score += 2
        reasons.append("test file")

    if file_entry.category == "documentation" and not is_readme(path):
        score += 2
        reasons.append("documentation")

    path_depth = _depth(path)
    if path_depth > 2:
        penalty = path_depth - 2
        score -= penalty
        reasons.append(f"depth penalty -{penalty}")

    if file_entry.size_bytes > max_file_size_bytes:
        score -= 4
        reasons.append("large file penalty")

    if is_ci_file(path):
        score += 2
        reasons.append("CI/CD file")

    return ScoredFile(
        path=path,
        score=score,
        reasons=reasons,
        category=file_entry.category,
        size_bytes=file_entry.size_bytes,
    )


def rank_files(
    files: list[FileEntry],
    *,
    max_files: int | None = None,
    max_file_size_bytes: int = 15_000,
) -> list[ScoredFile]:
    """Rank non-excluded, non-binary files by importance."""
    scored = [
        score_file(entry, max_file_size_bytes=max_file_size_bytes)
        for entry in files
        if not entry.is_excluded
        and not entry.is_binary
        and entry.category not in {"binary", "asset", "generated"}
    ]

    scored.sort(
        key=lambda item: (
            -item.score,
            _depth(item.path),
            normalize_path(item.path).lower(),
        )
    )
    if max_files is None:
        return scored
    return scored[:max_files]