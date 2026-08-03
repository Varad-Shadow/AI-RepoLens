"""Unit tests for file importance scoring."""

from __future__ import annotations

from repolens.analyzer.models import FileEntry
from repolens.analyzer.scoring import rank_files, score_file


def _file(path: str, category: str = "source", size: int = 100) -> FileEntry:
    return FileEntry(
        path=path,
        size_bytes=size,
        category=category,  # type: ignore[arg-type]
        is_binary=False,
        is_excluded=False,
    )


def test_readme_scores_above_deep_source_file() -> None:
    readme = _file("README.md", "documentation")
    deep = _file("src/features/deep/service.py")

    ranked = rank_files([deep, readme])

    assert ranked[0].path == "README.md"
    assert "README" in ranked[0].reasons


def test_dependency_manifest_gets_high_score() -> None:
    scored = score_file(_file("pyproject.toml", "dependency"))

    assert scored.score >= 12
    assert "dependency manifest" in scored.reasons


def test_routing_directory_and_entrypoint_are_scored() -> None:
    scored = score_file(_file("src/api/server.py"))

    assert "routing/controller/API path" in scored.reasons
    assert "entry-point filename" in scored.reasons


def test_large_file_penalty_applies() -> None:
    scored = score_file(_file("src/app.py", size=20_000), max_file_size_bytes=1_000)

    assert "large file penalty" in scored.reasons


def test_rank_excludes_binary_generated_and_excluded_files() -> None:
    files = [
        _file("src/app.py"),
        FileEntry("logo.png", 10, "asset", True, False),
        FileEntry("src/generated/client.py", 10, "generated", False, False),
        FileEntry("node_modules/x/index.js", 10, "source", False, True),
    ]

    ranked = rank_files(files)

    assert [item.path for item in ranked] == ["src/app.py"]


def test_tie_breaker_is_deterministic_by_depth_then_path() -> None:
    files = [_file("b.py"), _file("src/a.py"), _file("a.py")]

    ranked = rank_files(files)

    assert [item.path for item in ranked] == ["a.py", "b.py", "src/a.py"]