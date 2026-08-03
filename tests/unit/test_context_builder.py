"""Unit tests for AI context construction."""

from __future__ import annotations

from repolens.ai.context_builder import build_analysis_context
from repolens.ai.token_budget import estimate_tokens
from repolens.analyzer.models import DeterministicStats, TechDetection
from repolens.github.client import RepoMetadata


def _metadata() -> RepoMetadata:
    return RepoMetadata(
        owner="pallets",
        name="flask",
        description="demo",
        default_branch="main",
        stars=1,
        primary_language="Python",
        license="BSD-3-Clause",
        size_kb=10,
    )


def _stats() -> DeterministicStats:
    return DeterministicStats(
        total_files=3,
        total_dirs=1,
        files_analyzed=2,
        files_ignored=1,
        language_distribution={"Python": 100.0},
        dependency_files=["requirements.txt"],
        config_files=[],
        ci_files=[],
        docker_files=[],
        test_files=["tests/test_app.py"],
        has_readme=True,
        has_license=False,
        has_ci=False,
        has_docker=False,
        has_tests=True,
    )


def test_context_excludes_secret_paths_and_redacts_content() -> None:
    result = build_analysis_context(
        metadata=_metadata(),
        stats=_stats(),
        filtered_tree=["README.md", ".env", "src/app.py"],
        selected_file_contents={
            "src/app.py": "api_key = 'secret'\nprint('ok')",
            ".env": "TOKEN=secret",
        },
        tech_detections=[TechDetection("Flask", "confirmed", ["requirements.txt"])],
        dependencies={"python": ["flask"]},
        max_context_size=1200,
    )

    assert ".env" not in result.rendered
    assert "secret" not in result.rendered
    assert "[REDACTED]" in result.rendered
    assert "<<<FILE:src/app.py>>>" in result.rendered


def test_context_respects_token_budget() -> None:
    result = build_analysis_context(
        metadata=_metadata(),
        stats=_stats(),
        filtered_tree=[f"src/file_{index}.py" for index in range(200)],
        selected_file_contents={"src/app.py": "x" * 10_000},
        tech_detections=[],
        dependencies={},
        max_context_size=120,
    )

    assert estimate_tokens(result.rendered) <= 120