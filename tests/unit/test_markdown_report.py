"""Unit tests for markdown report rendering."""

from __future__ import annotations

from repolens.analyzer.models import DeterministicStats, ScoredFile, TechDetection
from repolens.github.client import RepoMetadata
from repolens.report.markdown_report import render_markdown_report


def test_no_ai_report_contains_required_sections() -> None:
    report = render_markdown_report(
        metadata=RepoMetadata("pallets", "flask", "demo", "main", 1, "Python", "BSD", 10),
        stats=DeterministicStats(
            total_files=2,
            total_dirs=1,
            files_analyzed=2,
            files_ignored=0,
            language_distribution={"Python": 100.0},
            dependency_files=["requirements.txt"],
            config_files=[],
            ci_files=[],
            docker_files=[],
            test_files=[],
            has_readme=True,
            has_license=False,
            has_ci=False,
            has_docker=False,
            has_tests=False,
        ),
        filtered_paths=["README.md", "src/app.py"],
        scored_files=[ScoredFile("README.md", 13, ["README"], "documentation", 100)],
        tech_detections=[TechDetection("Flask", "confirmed", ["requirements.txt"])],
        dependencies={"python": ["flask"]},
    )

    for heading in (
        "## Summary",
        "## Technology Stack",
        "## Folder-by-Folder Breakdown",
        "## Top Files to Read First",
        "## Reading Order",
        "## Suggested Improvements",
        "## Analysis Limitations",
    ):
        assert heading in report