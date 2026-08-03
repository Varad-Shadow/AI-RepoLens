"""Unit tests for LLM schema validation."""

from __future__ import annotations

import json

import pytest

from repolens.ai.schema import cross_validate_paths, validate_analysis_json, validate_with_recovery
from repolens.exceptions import SchemaValidationError


def _payload() -> dict:
    return {
        "summary": "A Flask app.",
        "project_purpose": "Demo purpose.",
        "technology_stack": [
            {"name": "Flask", "confidence": "confirmed", "evidence": ["requirements.txt"]}
        ],
        "architecture": "Small web app.",
        "directory_analysis": {"src": "Application code"},
        "important_files": [{"path": "src/app.py", "why_important": "Entry point"}],
        "reading_order": ["README.md", "src/app.py"],
        "entry_points": ["src/app.py"],
        "code_flows": ["Request to route to response"],
        "dependencies_summary": "Uses Flask.",
        "testing_summary": "Tests present.",
        "configuration_summary": "Config is minimal.",
        "improvements": ["Add deployment docs"],
        "interview_questions": [],
        "limitations": [],
    }


def test_validate_analysis_json_accepts_valid_payload() -> None:
    analysis = validate_analysis_json(json.dumps(_payload()))

    assert analysis.summary == "A Flask app."
    assert analysis.technology_stack[0].evidence == ["requirements.txt"]


def test_validate_analysis_json_rejects_missing_fields() -> None:
    with pytest.raises(SchemaValidationError):
        validate_analysis_json('{"summary":"missing everything"}')


def test_validate_with_recovery_uses_one_recovery_callback() -> None:
    recovered = json.dumps(_payload())

    analysis, used_recovery = validate_with_recovery(
        "not json",
        recovery_fn=lambda error: recovered,
    )

    assert used_recovery is True
    assert analysis.summary == "A Flask app."


def test_cross_validate_paths_drops_hallucinated_paths() -> None:
    payload = _payload()
    payload["important_files"].append(
        {"path": "missing.py", "why_important": "Nope"}
    )
    payload["reading_order"].append("missing.py")
    payload["entry_points"].append("missing.py")
    analysis = validate_analysis_json(json.dumps(payload))

    sanitized = cross_validate_paths(analysis, {"README.md", "src/app.py"})

    assert [item.path for item in sanitized.important_files] == ["src/app.py"]
    assert sanitized.reading_order == ["README.md", "src/app.py"]
    assert sanitized.entry_points == ["src/app.py"]