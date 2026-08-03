"""Pydantic schema and validation helpers for LLM output."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from repolens.exceptions import SchemaValidationError

Confidence = Literal["confirmed", "likely", "possible"]
Difficulty = Literal["easy", "medium", "hard"]


class TechStackItem(BaseModel):
    """Technology item claimed by the LLM."""

    model_config = ConfigDict(extra="ignore")

    name: str
    confidence: Confidence
    evidence: list[str]


class ImportantFile(BaseModel):
    """Important file explanation from the LLM."""

    model_config = ConfigDict(extra="ignore")

    path: str
    why_important: str


class InterviewQuestion(BaseModel):
    """Repository-specific interview question."""

    model_config = ConfigDict(extra="ignore")

    question: str
    topic: str
    difficulty: Difficulty
    why_it_matters: str
    expected_concepts: list[str]


class RepoAnalysis(BaseModel):
    """Validated structured repository analysis."""

    model_config = ConfigDict(extra="ignore")

    summary: str
    project_purpose: str
    technology_stack: list[TechStackItem]
    architecture: str
    directory_analysis: dict[str, str]
    important_files: list[ImportantFile] = Field(max_length=5)
    reading_order: list[str]
    entry_points: list[str]
    code_flows: list[str]
    dependencies_summary: str
    testing_summary: str
    configuration_summary: str
    improvements: list[str] = Field(min_length=1, max_length=3)
    interview_questions: list[InterviewQuestion] = Field(default_factory=list)
    limitations: list[str]


def extract_json_object(raw_text: str) -> str:
    """Extract the outer JSON object from a provider response."""
    stripped = raw_text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        stripped = "\n".join(lines).strip()

    start = stripped.find("{")
    end = stripped.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise SchemaValidationError("LLM response did not contain a JSON object.")
    return stripped[start : end + 1]


def validate_analysis_json(raw_text: str) -> RepoAnalysis:
    """Parse and validate one LLM JSON response."""
    try:
        payload = json.loads(extract_json_object(raw_text))
        return RepoAnalysis.model_validate(payload)
    except (json.JSONDecodeError, ValidationError, SchemaValidationError) as exc:
        raise SchemaValidationError(f"LLM output failed schema validation: {exc}") from exc


def validate_with_recovery(
    raw_text: str,
    *,
    recovery_fn: Callable[[str], str] | None = None,
) -> tuple[RepoAnalysis, bool]:
    """Validate raw output, optionally trying one bounded recovery call."""
    try:
        return validate_analysis_json(raw_text), False
    except SchemaValidationError as first_error:
        if recovery_fn is None:
            raise
        recovered = recovery_fn(first_error.message)
        try:
            return validate_analysis_json(recovered), True
        except SchemaValidationError as second_error:
            raise SchemaValidationError(
                f"LLM output failed recovery validation: {second_error.message}"
            ) from second_error


def cross_validate_paths(analysis: RepoAnalysis, valid_paths: set[str]) -> RepoAnalysis:
    """Drop LLM path claims that are not present in the filtered tree."""
    important_files = [
        item for item in analysis.important_files if item.path in valid_paths
    ][:5]
    reading_order = [path for path in analysis.reading_order if path in valid_paths]
    entry_points = [path for path in analysis.entry_points if path in valid_paths]
    directory_analysis = {
        path: explanation
        for path, explanation in analysis.directory_analysis.items()
        if path == "." or path in valid_paths or any(item.startswith(f"{path.rstrip('/')}/") for item in valid_paths)
    }
    technology_stack = [
        item for item in analysis.technology_stack if item.evidence
    ]

    return analysis.model_copy(
        update={
            "important_files": important_files,
            "reading_order": reading_order,
            "entry_points": entry_points,
            "directory_analysis": directory_analysis,
            "technology_stack": technology_stack,
        }
    )