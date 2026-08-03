"""Build bounded, labeled LLM context from deterministic analysis."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any

from repolens.ai.token_budget import estimate_tokens, truncate_to_token_budget
from repolens.analyzer.models import DeterministicStats, TechDetection
from repolens.github.client import RepoMetadata
from repolens.security.secret_filter import filter_secret_paths, is_secret_path, redact_secrets


@dataclass(frozen=True)
class AnalysisContext:
    """Structured context assembled before prompt rendering."""

    metadata: RepoMetadata
    stats: DeterministicStats
    filtered_tree: list[str]
    selected_files: dict[str, str]
    tech_detections: list[TechDetection]
    dependencies: dict[str, list[str]]
    limitations: list[str]


@dataclass(frozen=True)
class ContextBuildResult:
    """Rendered context and budget accounting."""

    context: AnalysisContext
    rendered: str
    estimated_tokens: int
    omitted_files: list[str]
    excluded_secret_paths: list[str]


def _to_plain(value: Any) -> Any:
    if hasattr(value, "__dataclass_fields__"):
        return asdict(value)
    return value


def _json_block(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=True, default=_to_plain)


def _render_without_files(context: AnalysisContext) -> str:
    metadata = _json_block(context.metadata)
    stats = _json_block(context.stats)
    tech = _json_block(context.tech_detections)
    dependencies = _json_block(context.dependencies)
    limitations = _json_block(context.limitations)
    tree = "\n".join(f"- {path}" for path in context.filtered_tree)
    if not tree:
        tree = "(no files after filtering)"

    return (
        "REPOSITORY METADATA:\n"
        f"{metadata}\n\n"
        "DETERMINISTIC ANALYSIS:\n"
        f"Stats:\n{stats}\n\n"
        f"Technology detections:\n{tech}\n\n"
        f"Dependencies:\n{dependencies}\n\n"
        f"Limitations:\n{limitations}\n\n"
        "REPOSITORY STRUCTURE:\n"
        f"{tree}\n\n"
        "SELECTED FILE CONTENTS:\n"
    )


def _file_block(path: str, content: str) -> str:
    return f"<<<FILE:{path}>>>\n{content}\n<<<END_FILE>>>\n\n"


def build_analysis_context(
    *,
    metadata: RepoMetadata,
    stats: DeterministicStats,
    filtered_tree: list[str],
    selected_file_contents: dict[str, str],
    tech_detections: list[TechDetection],
    dependencies: dict[str, list[str]],
    max_context_size: int,
    limitations: list[str] | None = None,
) -> ContextBuildResult:
    """Build sanitized context that does not exceed the configured budget."""
    safe_tree, excluded_from_tree = filter_secret_paths(filtered_tree)
    selected_files: dict[str, str] = {}
    omitted_files: list[str] = []
    excluded_selected: list[str] = []

    for path, content in sorted(selected_file_contents.items()):
        if is_secret_path(path):
            excluded_selected.append(path)
            continue
        selected_files[path] = redact_secrets(content)

    context = AnalysisContext(
        metadata=metadata,
        stats=stats,
        filtered_tree=safe_tree,
        selected_files={},
        tech_detections=tech_detections,
        dependencies=dependencies,
        limitations=list(limitations or []),
    )
    base = _render_without_files(context)
    if estimate_tokens(base) > max_context_size:
        base = truncate_to_token_budget(base, max_context_size)
        rendered = base
        return ContextBuildResult(
            context=context,
            rendered=rendered,
            estimated_tokens=estimate_tokens(rendered),
            omitted_files=list(selected_files),
            excluded_secret_paths=excluded_from_tree + excluded_selected,
        )

    rendered = base
    kept_files: dict[str, str] = {}
    for path, content in selected_files.items():
        block = _file_block(path, content)
        if estimate_tokens(rendered + block) <= max_context_size:
            rendered += block
            kept_files[path] = content
            continue

        remaining_tokens = max_context_size - estimate_tokens(rendered) - estimate_tokens(
            _file_block(path, "")
        )
        if remaining_tokens > 5:
            truncated = truncate_to_token_budget(content, remaining_tokens)
            rendered += _file_block(path, truncated)
            kept_files[path] = truncated
        else:
            omitted_files.append(path)

    final_context = AnalysisContext(
        metadata=metadata,
        stats=stats,
        filtered_tree=safe_tree,
        selected_files=kept_files,
        tech_detections=tech_detections,
        dependencies=dependencies,
        limitations=list(limitations or []),
    )
    if estimate_tokens(rendered) > max_context_size:
        rendered = truncate_to_token_budget(rendered, max_context_size)

    return ContextBuildResult(
        context=final_context,
        rendered=rendered,
        estimated_tokens=estimate_tokens(rendered),
        omitted_files=omitted_files,
        excluded_secret_paths=excluded_from_tree + excluded_selected,
    )