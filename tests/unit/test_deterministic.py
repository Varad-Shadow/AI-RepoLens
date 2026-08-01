"""Unit tests for deterministic repository analysis."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from repolens.analyzer.deterministic import PathInfo, analyze_tree
from repolens.analyzer.models import DeterministicAnalysisResult

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "sample_trees"


def _load_fixture(name: str) -> list[PathInfo]:
    data = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
    return [
        PathInfo(
            path=item["path"],
            entry_type=item["type"],
            size_bytes=item.get("size", 0),
        )
        for item in data["entries"]
    ]


def test_empty_repository() -> None:
    result = analyze_tree(_load_fixture("empty_repo.json"))
    assert result.stats.total_files == 0
    assert result.stats.total_dirs == 0
    assert result.stats.files_analyzed == 0
    assert result.stats.language_distribution == {}
    assert result.stats.has_readme is False


def test_multi_language_repository() -> None:
    result = analyze_tree(_load_fixture("multi_language_repo.json"))
    assert result.stats.has_readme is True
    assert result.stats.has_license is True
    assert result.stats.has_ci is True
    assert result.stats.has_docker is True
    assert result.stats.has_tests is True
    assert "requirements.txt" in result.stats.dependency_files
    assert "package.json" in result.stats.dependency_files
    assert result.stats.language_distribution["Python"] > 0
    assert result.stats.language_distribution["TypeScript"] > 0
    assert abs(sum(result.stats.language_distribution.values()) - 100.0) < 0.01


def test_contest_latest_testing_utils_not_excluded() -> None:
    result = analyze_tree(_load_fixture("edge_cases_repo.json"))
    kept = set(result.filtered_paths)
    assert "contest/scoring.py" in kept
    assert "latest/release.py" in kept
    assert "testing-utils/helper.py" in kept


def test_vendor_and_node_modules_excluded() -> None:
    result = analyze_tree(_load_fixture("edge_cases_repo.json"))
    assert "vendor/lib.rb" in result.ignored_paths
    assert "node_modules/lodash/index.js" in result.ignored_paths
    assert result.stats.files_ignored >= 2


def test_binary_file_classified_without_utf8_decode() -> None:
    result = analyze_tree(_load_fixture("edge_cases_repo.json"))
    png = next(entry for entry in result.files if entry.path == "assets/logo.png")
    assert png.is_binary is True
    assert png.category == "asset"


def test_deeply_nested_file_analyzed() -> None:
    result = analyze_tree(_load_fixture("edge_cases_repo.json"))
    assert "deep/n1/n2/n3/n4/module.py" in result.filtered_paths


def test_content_sample_refines_binary_detection() -> None:
    entries = [PathInfo(path="data/custom", entry_type="blob", size_bytes=100)]
    result = analyze_tree(
        entries,
        content_samples={"data/custom": b"\x00binary"},
    )
    file_entry = result.files[0]
    assert file_entry.is_binary is True


def test_large_file_metadata_without_loading_content() -> None:
    entries = [
        PathInfo(path="src/huge.py", entry_type="blob", size_bytes=10_000_000),
    ]
    result = analyze_tree(entries)
    assert result.files[0].size_bytes == 10_000_000
    assert result.files[0].category == "source"


def test_encoding_failure_handled_via_latin1_fallback() -> None:
    entries = [PathInfo(path="legacy/data.txt", entry_type="blob", size_bytes=3)]
    latin1_bytes = b"\xe9\xe8\xe0"
    result = analyze_tree(entries, content_samples={"legacy/data.txt": latin1_bytes})
    entry = result.files[0]
    assert entry.is_binary is False


def test_unknown_extension_classified_as_unknown() -> None:
    entries = [PathInfo(path="misc/file.xyz", entry_type="blob", size_bytes=10)]
    result = analyze_tree(entries)
    assert result.files[0].category == "unknown"


def test_files_analyzed_count_excludes_ignored() -> None:
    result = analyze_tree(_load_fixture("edge_cases_repo.json"))
    assert (
        result.stats.files_analyzed + result.stats.files_ignored
        == result.stats.total_files
    )
