"""Markdown report assembly."""

from __future__ import annotations

from collections import defaultdict

from repolens.ai.schema import InterviewQuestion, RepoAnalysis
from repolens.analyzer.models import DeterministicStats, ScoredFile, TechDetection
from repolens.github.client import RepoMetadata
from repolens.report.interview import format_interview_questions


def _yes_no(value: bool) -> str:
    return "yes" if value else "no"


def _language_lines(stats: DeterministicStats) -> list[str]:
    if not stats.language_distribution:
        return ["- No source-language distribution could be determined."]
    return [
        f"- {language}: {percent:.2f}%"
        for language, percent in sorted(stats.language_distribution.items())
    ]


def _dependency_lines(dependencies: dict[str, list[str]]) -> list[str]:
    if not dependencies:
        return ["- No parsed dependency manifests were available."]
    lines: list[str] = []
    for ecosystem, packages in sorted(dependencies.items()):
        package_text = ", ".join(packages[:20]) if packages else "none parsed"
        if len(packages) > 20:
            package_text += f", and {len(packages) - 20} more"
        lines.append(f"- {ecosystem}: {package_text}")
    return lines


def _tech_lines(tech_detections: list[TechDetection], ai_analysis: RepoAnalysis | None) -> list[str]:
    if ai_analysis and ai_analysis.technology_stack:
        return [
            f"- {item.name} ({item.confidence}) - evidence: {', '.join(item.evidence)}"
            for item in ai_analysis.technology_stack
        ]
    if tech_detections:
        return [
            f"- {item.name} ({item.confidence}) - evidence: {', '.join(item.evidence)}"
            for item in tech_detections
        ]
    return ["- No specific frameworks were detected from available evidence."]


def _folder_breakdown(paths: list[str]) -> dict[str, str]:
    grouped: dict[str, list[str]] = defaultdict(list)
    for path in paths:
        parts = path.split("/")
        root = parts[0] if len(parts) > 1 else "."
        grouped[root].append(path)

    return {
        folder: f"{len(items)} analyzed file(s), including {', '.join(items[:5])}"
        for folder, items in sorted(grouped.items())
    }


def _directory_lines(paths: list[str], ai_analysis: RepoAnalysis | None) -> list[str]:
    directory_analysis = ai_analysis.directory_analysis if ai_analysis else _folder_breakdown(paths)
    if not directory_analysis:
        return ["- No folder breakdown is available."]
    return [
        f"- `{folder}`: {description}"
        for folder, description in sorted(directory_analysis.items())
    ]


def _scored_file_lines(scored_files: list[ScoredFile], ai_analysis: RepoAnalysis | None) -> list[str]:
    if ai_analysis and ai_analysis.important_files:
        return [
            f"- `{item.path}` - {item.why_important}"
            for item in ai_analysis.important_files
        ]
    if scored_files:
        return [
            f"- `{item.path}` - score {item.score:g}; {', '.join(item.reasons) or 'ranked by deterministic scoring'}"
            for item in scored_files[:10]
        ]
    return ["- No readable files were selected."]


def _reading_order(scored_files: list[ScoredFile], ai_analysis: RepoAnalysis | None) -> list[str]:
    if ai_analysis and ai_analysis.reading_order:
        return [f"- `{path}`" for path in ai_analysis.reading_order]
    return [f"- `{item.path}`" for item in scored_files[:5]] or ["- No reading order is available."]


def render_markdown_report(
    *,
    metadata: RepoMetadata,
    stats: DeterministicStats,
    filtered_paths: list[str],
    scored_files: list[ScoredFile],
    tech_detections: list[TechDetection],
    dependencies: dict[str, list[str]],
    ai_analysis: RepoAnalysis | None = None,
    interview_questions: list[InterviewQuestion] | None = None,
    limitations: list[str] | None = None,
) -> str:
    """Render a complete markdown report from deterministic and AI data."""
    limitations = list(limitations or [])
    if ai_analysis:
        limitations.extend(ai_analysis.limitations)

    summary = ai_analysis.summary if ai_analysis else (
        f"Deterministic analysis of {metadata.owner}/{metadata.name} found "
        f"{stats.files_analyzed} analyzed files across {stats.total_dirs} directories."
    )
    purpose = ai_analysis.project_purpose if ai_analysis else (
        metadata.description or "Project purpose cannot be determined from deterministic metadata alone."
    )
    architecture = ai_analysis.architecture if ai_analysis else (
        "Architecture summary is based on folder structure, dependency manifests, and ranked files only."
    )
    dependencies_summary = ai_analysis.dependencies_summary if ai_analysis else (
        "Dependencies were parsed from supported manifests without installing or executing them."
    )
    testing_summary = ai_analysis.testing_summary if ai_analysis else (
        "Tests detected." if stats.has_tests else "No tests were detected in the analyzed tree."
    )
    configuration_summary = ai_analysis.configuration_summary if ai_analysis else (
        "Configuration files were detected." if stats.config_files else "No dedicated config files were detected."
    )
    improvements = ai_analysis.improvements if ai_analysis else [
        "Review documentation and tests around the highest-ranked files."
    ]
    code_flows = ai_analysis.code_flows if ai_analysis else [
        "Detailed code flows require AI analysis or manual review of selected files."
    ]
    entry_points = ai_analysis.entry_points if ai_analysis else [
        item.path for item in scored_files if "entry-point filename" in item.reasons
    ]

    questions = interview_questions if interview_questions is not None else (
        ai_analysis.interview_questions if ai_analysis else []
    )

    lines: list[str] = [
        f"# RepoLens Report: {metadata.owner}/{metadata.name}",
        "",
        "## Summary",
        summary,
        "",
        "## Project Purpose",
        purpose,
        "",
        "## Repository Metadata",
        f"- Default branch: `{metadata.default_branch}`",
        f"- Stars: {metadata.stars}",
        f"- Primary language: {metadata.primary_language or 'unknown'}",
        f"- License: {metadata.license or 'unknown'}",
        f"- Size: {metadata.size_kb} KB",
        "",
        "## Deterministic Overview",
        f"- Total files: {stats.total_files}",
        f"- Total directories: {stats.total_dirs}",
        f"- Files analyzed: {stats.files_analyzed}",
        f"- Files ignored: {stats.files_ignored}",
        f"- README present: {_yes_no(stats.has_readme)}",
        f"- License present: {_yes_no(stats.has_license)}",
        f"- CI present: {_yes_no(stats.has_ci)}",
        f"- Docker present: {_yes_no(stats.has_docker)}",
        f"- Tests present: {_yes_no(stats.has_tests)}",
        "",
        "## Language Distribution",
        *_language_lines(stats),
        "",
        "## Technology Stack",
        *_tech_lines(tech_detections, ai_analysis),
        "",
        "## Dependencies",
        dependencies_summary,
        *_dependency_lines(dependencies),
        "",
        "## Architecture",
        architecture,
        "",
        "## Folder-by-Folder Breakdown",
        *_directory_lines(filtered_paths, ai_analysis),
        "",
        "## Top Files to Read First",
        *_scored_file_lines(scored_files, ai_analysis),
        "",
        "## Reading Order",
        *_reading_order(scored_files, ai_analysis),
        "",
        "## Entry Points",
        *([f"- `{path}`" for path in entry_points] or ["- No entry points were identified."]),
        "",
        "## Code Flows",
        *[f"- {flow}" for flow in code_flows],
        "",
        "## Testing Summary",
        testing_summary,
        "",
        "## Configuration Summary",
        configuration_summary,
        "",
        "## Suggested Improvements",
        *[f"- {item}" for item in improvements],
    ]

    if questions:
        lines.extend(["", "## Interview Questions", format_interview_questions(questions)])

    lines.extend(
        [
            "",
            "## Analysis Limitations",
            *([f"- {item}" for item in sorted(set(limitations))] or ["- No specific limitations were recorded."]),
            "",
        ]
    )
    return "\n".join(lines)