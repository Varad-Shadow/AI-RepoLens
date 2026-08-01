"""Deterministic repository analysis without LLM involvement."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from repolens.analyzer.binary_detect import (
    DEFAULT_SAMPLE_SIZE,
    inspect_content,
    is_binary_path,
)
from repolens.analyzer.classifier import (
    detect_language,
    is_ci_file,
    is_dependency_file,
    is_docker_file,
    is_license,
    is_readme,
    is_test_file,
    classify_path,
    is_config_file,
)
from repolens.analyzer.filters import filter_paths
from repolens.analyzer.models import (
    DeterministicAnalysisResult,
    DeterministicStats,
    FileEntry,
)


@dataclass(frozen=True)
class PathInfo:
    """Minimal tree entry for deterministic analysis."""

    path: str
    entry_type: str
    size_bytes: int = 0


def _language_distribution(source_files: list[FileEntry]) -> dict[str, float]:
    counts: Counter[str] = Counter()
    for entry in source_files:
        if entry.language:
            counts[entry.language] += 1

    total = sum(counts.values())
    if total == 0:
        return {}

    return {
        language: round((count / total) * 100.0, 2)
        for language, count in sorted(counts.items())
    }


def _build_file_entry(
    path: str,
    size_bytes: int,
    content_samples: dict[str, bytes] | None,
) -> FileEntry:
    sample: bytes | None = None
    if content_samples and path in content_samples:
        sample = content_samples[path][:DEFAULT_SAMPLE_SIZE]

    is_binary = is_binary_path(path, sample)
    if sample is not None and not is_binary:
        inspection = inspect_content(sample)
        is_binary = inspection.is_binary

    category = classify_path(path, is_binary=is_binary)
    language = None if is_binary else detect_language(path)

    return FileEntry(
        path=path,
        size_bytes=size_bytes,
        category=category,
        is_binary=is_binary,
        is_excluded=False,
        language=language,
    )


def analyze_tree(
    entries: list[PathInfo],
    *,
    content_samples: dict[str, bytes] | None = None,
) -> DeterministicAnalysisResult:
    """Analyze repository tree entries using deterministic evidence only."""
    file_entries = [entry for entry in entries if entry.entry_type == "blob"]
    dir_entries = [entry for entry in entries if entry.entry_type == "tree"]

    all_file_paths = [entry.path for entry in file_entries]
    filtered_paths, ignored_paths = filter_paths(all_file_paths)

    size_by_path = {entry.path: entry.size_bytes for entry in file_entries}

    analyzed_files: list[FileEntry] = []
    for path in filtered_paths:
        analyzed_files.append(
            _build_file_entry(path, size_by_path.get(path, 0), content_samples)
        )

    ignored_file_entries = [
        FileEntry(
            path=path,
            size_bytes=size_by_path.get(path, 0),
            category="unknown",
            is_binary=is_binary_path(path),
            is_excluded=True,
            exclusion_reason="ignored_directory",
        )
        for path in ignored_paths
    ]

    dependency_files = sorted(
        entry.path for entry in analyzed_files if entry.category == "dependency"
    )
    config_files = sorted(
        entry.path
        for entry in analyzed_files
        if entry.category == "config" or is_config_file(entry.path)
    )
    ci_files = sorted(
        entry.path for entry in analyzed_files if entry.category == "ci_cd"
    )
    docker_files = sorted(
        entry.path for entry in analyzed_files if is_docker_file(entry.path)
    )
    test_files = sorted(
        entry.path
        for entry in analyzed_files
        if entry.category == "test" or is_test_file(entry.path)
    )

    source_files = [entry for entry in analyzed_files if entry.category == "source"]

    stats = DeterministicStats(
        total_files=len(file_entries),
        total_dirs=len(dir_entries),
        files_analyzed=len(filtered_paths),
        files_ignored=len(ignored_paths),
        language_distribution=_language_distribution(source_files),
        dependency_files=dependency_files,
        config_files=config_files,
        ci_files=ci_files,
        docker_files=docker_files,
        test_files=test_files,
        has_readme=any(is_readme(path) for path in filtered_paths),
        has_license=any(is_license(path) for path in filtered_paths),
        has_ci=any(is_ci_file(path) for path in filtered_paths),
        has_docker=any(is_docker_file(path) for path in filtered_paths),
        has_tests=any(is_test_file(path) for path in filtered_paths),
    )

    return DeterministicAnalysisResult(
        stats=stats,
        files=analyzed_files + ignored_file_entries,
        filtered_paths=filtered_paths,
        ignored_paths=ignored_paths,
    )


def analyze_paths(paths: list[str]) -> DeterministicAnalysisResult:
    """Convenience wrapper when only file paths (no dirs) are available."""
    entries = [PathInfo(path=path, entry_type="blob", size_bytes=0) for path in paths]
    return analyze_tree(entries)
