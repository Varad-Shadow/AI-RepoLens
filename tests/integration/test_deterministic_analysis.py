"""Integration tests for deterministic analysis on fixture trees."""

from __future__ import annotations

import json
from pathlib import Path

from repolens.analyzer.deterministic import PathInfo, analyze_tree
from repolens.github.client import TreeEntry

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "sample_trees"


def _entries_from_fixture(name: str) -> list[PathInfo]:
    data = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
    return [
        PathInfo(
            path=item["path"],
            entry_type=item["type"],
            size_bytes=item.get("size", 0),
        )
        for item in data["entries"]
    ]


def test_github_tree_entry_adapter_pattern() -> None:
    """Ensure GitHub TreeEntry objects map cleanly to deterministic analysis."""
    github_entries = [
        TreeEntry(path="README.md", type="blob", size=100),
        TreeEntry(path="src", type="tree"),
        TreeEntry(path="src/app.py", type="blob", size=200),
        TreeEntry(path="vendor", type="tree"),
        TreeEntry(path="vendor/lib.js", type="blob", size=300),
    ]
    path_infos = [
        PathInfo(path=e.path, entry_type=e.type, size_bytes=e.size or 0)
        for e in github_entries
    ]
    result = analyze_tree(path_infos)

    assert result.stats.total_files == 3
    assert result.stats.total_dirs == 2
    assert "src/app.py" in result.filtered_paths
    assert "vendor/lib.js" in result.ignored_paths


def test_end_to_end_fixture_pipeline() -> None:
    result = analyze_tree(_entries_from_fixture("multi_language_repo.json"))

    assert result.stats.total_files == 11
    assert len(result.stats.dependency_files) == 2
    assert result.stats.has_ci is True
    assert "frontend/app.ts" in result.filtered_paths
    assert "tests/test_main.py" in result.stats.test_files

    # No technology claims beyond evidence lists
    assert all(path in result.filtered_paths for path in result.stats.dependency_files)
