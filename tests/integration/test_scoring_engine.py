"""Integration tests for deterministic file scoring."""

from __future__ import annotations

import json
from pathlib import Path

from repolens.analyzer.deterministic import PathInfo, analyze_tree
from repolens.analyzer.models import FileEntry
from repolens.analyzer.scoring import normalize_path, rank_files, score_file

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "sample_trees"
MAX_FILE_SIZE_BYTES = 15_000


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


def _file(path: str, category: str = "source", size: int = 100) -> FileEntry:
    return FileEntry(
        path=path,
        size_bytes=size,
        category=category,  # type: ignore[arg-type]
        is_binary=False,
        is_excluded=False,
    )


def _rank(paths: list[str]) -> list[str]:
    return [
        normalize_path(item.path)
        for item in rank_files([_file(path) for path in paths])
    ]


def test_equal_score_shallower_depth_wins() -> None:
    ranked = _rank(["src/deep/core.py", "lib/core.py", "alpha/core.py"])

    assert ranked.index("lib/core.py") < ranked.index("src/deep/core.py")
    assert ranked.index("alpha/core.py") < ranked.index("src/deep/core.py")


def test_equal_score_and_depth_uses_alphabetical_normalized_path() -> None:
    ranked = _rank(["src/zeta.py", "src/alpha.py", "src/middle.py"])

    assert ranked == ["src/alpha.py", "src/middle.py", "src/zeta.py"]


def test_ordering_is_deterministic_across_path_separators() -> None:
    ranked = _rank(["src\\zeta.py", "src/alpha.py", "src\\middle.py"])

    assert ranked == ["src/alpha.py", "src/middle.py", "src/zeta.py"]


def test_large_file_penalty_is_applied() -> None:
    small = score_file(_file("app.py", size=100), max_file_size_bytes=MAX_FILE_SIZE_BYTES)
    large = score_file(_file("app.py", size=50_000), max_file_size_bytes=MAX_FILE_SIZE_BYTES)

    assert small.score - large.score == 4
    assert "large file penalty" in large.reasons


def test_complex_fixture_large_file_is_demoted_from_top_five() -> None:
    analysis = analyze_tree(_entries_from_fixture("scoring_complex_repo.json"))

    ranked = rank_files(
        analysis.files,
        max_file_size_bytes=MAX_FILE_SIZE_BYTES,
    )
    top_five = [item.path for item in ranked[:5]]

    assert "app.py" not in top_five
    assert ranked.index(next(item for item in ranked if item.path == "app.py")) >= 5


def test_duplicate_filenames_remain_distinguishable() -> None:
    analysis = analyze_tree(_entries_from_fixture("scoring_complex_repo.json"))

    ranked_paths = [item.path for item in rank_files(analysis.files)]

    assert "src/app.py" in ranked_paths
    assert "backend/app.py" in ranked_paths
    assert "services/app.py" in ranked_paths
    assert "tests/app.py" in ranked_paths


def test_repeated_execution_produces_identical_ranking() -> None:
    analysis = analyze_tree(_entries_from_fixture("scoring_complex_repo.json"))

    first = [item.path for item in rank_files(analysis.files)]
    second = [item.path for item in rank_files(list(reversed(analysis.files)))]
    third = [item.path for item in rank_files(analysis.files)]

    assert first == second == third


def test_no_randomness_is_used_for_equivalent_inputs() -> None:
    files = [_file("src/c.py"), _file("src/a.py"), _file("src/b.py")]

    rankings = {
        tuple(item.path for item in rank_files(files)),
        tuple(item.path for item in rank_files(list(reversed(files)))),
        tuple(item.path for item in rank_files([files[1], files[2], files[0]])),
    }

    assert rankings == {("src/a.py", "src/b.py", "src/c.py")}