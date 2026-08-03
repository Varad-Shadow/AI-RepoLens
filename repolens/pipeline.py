"""End-to-end repository analysis pipeline."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from typing import Any

from repolens.ai.context_builder import build_analysis_context
from repolens.ai.llm_client import AnthropicLLMClient, LLMClient
from repolens.ai.prompts import SYSTEM_PROMPT, build_recovery_prompt, build_user_prompt
from repolens.ai.schema import RepoAnalysis, cross_validate_paths, validate_with_recovery
from repolens.analyzer.dependency_parse import ecosystem_for_manifest, parse_dependency_files
from repolens.analyzer.deterministic import PathInfo, analyze_tree
from repolens.analyzer.scoring import rank_files
from repolens.analyzer.tech_detect import detect_technologies
from repolens.config import Config
from repolens.exceptions import LLMError, RepoLensError, SchemaValidationError
from repolens.github.client import GitHubClient, RepoMetadata, TreeEntry
from repolens.github.url_parser import parse_github_url
from repolens.report.interview import build_deterministic_interview_questions
from repolens.report.markdown_report import render_markdown_report
from repolens.security.secret_filter import filter_secret_paths, is_secret_path

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PipelineResult:
    """User-facing pipeline output and useful metadata."""

    content: str
    output_format: str
    metadata: RepoMetadata
    partial: bool
    limitations: list[str]
    ai_used: bool


def _to_plain(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if hasattr(value, "__dataclass_fields__"):
        return asdict(value)
    return value


def _decode_text(raw: bytes, *, max_bytes: int) -> str:
    truncated = len(raw) > max_bytes
    sample = raw[:max_bytes]
    try:
        text = sample.decode("utf-8")
    except UnicodeDecodeError:
        text = sample.decode("latin-1", errors="replace")
    if truncated:
        text += "\n[truncated]"
    return text


def _tree_to_path_info(entries: list[TreeEntry]) -> list[PathInfo]:
    return [
        PathInfo(
            path=entry.path,
            entry_type=entry.type,
            size_bytes=entry.size or 0,
        )
        for entry in entries
    ]


def _safe_fetch_text(
    github_client: GitHubClient,
    metadata: RepoMetadata,
    path: str,
    ref: str,
    config: Config,
    limitations: list[str],
) -> str | None:
    if is_secret_path(path):
        limitations.append(f"Secret-like path excluded before content fetch: {path}")
        return None
    try:
        raw = github_client.get_file_content(metadata.owner, metadata.name, path, ref)
    except RepoLensError as exc:
        limitations.append(f"Could not fetch {path}: {exc.message}")
        return None
    return _decode_text(raw, max_bytes=config.max_file_size_bytes)


def _json_output(
    *,
    metadata: RepoMetadata,
    stats: Any,
    filtered_paths: list[str],
    scored_files: Any,
    tech_detections: Any,
    dependencies: dict[str, list[str]],
    ai_analysis: RepoAnalysis | None,
    limitations: list[str],
) -> str:
    payload = {
        "metadata": metadata,
        "stats": stats,
        "filtered_paths": filtered_paths,
        "top_files": scored_files,
        "technology_stack": tech_detections,
        "dependencies": dependencies,
        "ai_analysis": ai_analysis,
        "limitations": limitations,
    }
    return json.dumps(payload, indent=2, sort_keys=True, default=_to_plain)


def run_analysis(
    repository_url: str,
    *,
    config: Config,
    output_format: str = "md",
    include_interview: bool = False,
    no_ai: bool = False,
    github_client: GitHubClient | None = None,
    llm_client: LLMClient | None = None,
) -> PipelineResult:
    """Run the RepoLens analysis pipeline."""
    parsed = parse_github_url(repository_url)
    owns_github_client = github_client is None
    github_client = github_client or GitHubClient(config)
    limitations: list[str] = []
    ai_analysis: RepoAnalysis | None = None
    ai_used = False

    try:
        metadata = github_client.get_repo_metadata(parsed.owner, parsed.repo)
        ref = parsed.ref or metadata.default_branch
        tree = github_client.get_tree(metadata.owner, metadata.name, ref)
        if tree.partial and tree.partial_reason:
            limitations.append(tree.partial_reason)

        blob_paths = [entry.path for entry in tree.entries if entry.type == "blob"]
        _, secret_paths = filter_secret_paths(blob_paths)
        if secret_paths:
            limitations.append(
                f"Excluded {len(secret_paths)} secret-like path(s) before content fetch."
            )
        safe_entries = [
            entry
            for entry in tree.entries
            if entry.type != "blob" or not is_secret_path(entry.path)
        ]

        deterministic = analyze_tree(_tree_to_path_info(safe_entries))
        ranked_all_files = rank_files(
            deterministic.files,
            max_files=None,
            max_file_size_bytes=config.max_file_size_bytes,
        )
        supported_manifest_paths = [
            scored.path
            for scored in ranked_all_files
            if scored.path in deterministic.stats.dependency_files
            and ecosystem_for_manifest(scored.path) is not None
        ]
        manifest_fetch_limit = config.max_files_analyzed
        manifest_contents: dict[str, str] = {}
        for path in supported_manifest_paths[:manifest_fetch_limit]:
            text = _safe_fetch_text(github_client, metadata, path, ref, config, limitations)
            if text is not None:
                manifest_contents[path] = text
        if len(supported_manifest_paths) > manifest_fetch_limit:
            limitations.append(
                f"Parsed top {manifest_fetch_limit} of {len(supported_manifest_paths)} supported dependency manifest(s) to avoid excessive API calls."
            )

        dependencies = parse_dependency_files(manifest_contents)
        scored_files = ranked_all_files[: config.max_files_analyzed]

        selected_contents: dict[str, str] = {}
        for scored in scored_files:
            if scored.path in manifest_contents:
                selected_contents[scored.path] = manifest_contents[scored.path]
                continue
            text = _safe_fetch_text(github_client, metadata, scored.path, ref, config, limitations)
            if text is not None:
                selected_contents[scored.path] = text

        tech_detections = detect_technologies(
            deterministic.filtered_paths,
            dependencies=dependencies,
            file_contents=selected_contents,
        )

        context_result = build_analysis_context(
            metadata=metadata,
            stats=deterministic.stats,
            filtered_tree=deterministic.filtered_paths,
            selected_file_contents=selected_contents,
            tech_detections=tech_detections,
            dependencies=dependencies,
            max_context_size=config.max_context_size,
            limitations=limitations,
        )
        if context_result.omitted_files:
            limitations.append(
                f"Omitted {len(context_result.omitted_files)} selected file(s) due to context budget."
            )
        if context_result.excluded_secret_paths:
            logger.info("Secret-like paths excluded from context: %s", context_result.excluded_secret_paths)

        if not no_ai:
            llm = llm_client or AnthropicLLMClient(config)
            user_prompt = build_user_prompt(
                context_result.rendered,
                include_interview=include_interview,
            )
            try:
                raw = llm.generate(SYSTEM_PROMPT, user_prompt)
                ai_analysis, used_recovery = validate_with_recovery(
                    raw,
                    recovery_fn=lambda error: llm.generate(
                        SYSTEM_PROMPT,
                        build_recovery_prompt(raw, error),
                    ),
                )
                if used_recovery:
                    limitations.append("LLM output required one schema-recovery pass.")
                ai_analysis = cross_validate_paths(
                    ai_analysis,
                    set(deterministic.filtered_paths),
                )
                ai_used = True
            except (LLMError, SchemaValidationError) as exc:
                limitations.append(
                    f"AI analysis failed; deterministic report generated instead: {exc.message}"
                )

        interview_questions = None
        if include_interview and (no_ai or ai_analysis is None):
            interview_questions = build_deterministic_interview_questions(
                scored_files=scored_files,
                tech_detections=tech_detections,
                dependencies=dependencies,
            )

        if output_format == "json":
            content = _json_output(
                metadata=metadata,
                stats=deterministic.stats,
                filtered_paths=deterministic.filtered_paths,
                scored_files=scored_files,
                tech_detections=tech_detections,
                dependencies=dependencies,
                ai_analysis=ai_analysis,
                limitations=limitations,
            )
        else:
            content = render_markdown_report(
                metadata=metadata,
                stats=deterministic.stats,
                filtered_paths=deterministic.filtered_paths,
                scored_files=scored_files,
                tech_detections=tech_detections,
                dependencies=dependencies,
                ai_analysis=ai_analysis,
                interview_questions=interview_questions,
                limitations=limitations,
            )

        return PipelineResult(
            content=content,
            output_format=output_format,
            metadata=metadata,
            partial=tree.partial or ai_analysis is None and not no_ai,
            limitations=limitations,
            ai_used=ai_used,
        )
    finally:
        if owns_github_client:
            github_client.close()