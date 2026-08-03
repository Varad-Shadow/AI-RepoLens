"""Unit tests for interview formatting."""

from __future__ import annotations

from repolens.analyzer.models import ScoredFile, TechDetection
from repolens.report.interview import build_deterministic_interview_questions, format_interview_questions


def test_deterministic_interview_questions_are_repo_specific() -> None:
    questions = build_deterministic_interview_questions(
        scored_files=[ScoredFile("src/app.py", 10, ["entry-point filename"], "source", 100)],
        tech_detections=[TechDetection("Flask", "confirmed", ["requirements.txt"])],
        dependencies={"python": ["flask"]},
    )

    assert 5 <= len(questions) <= 10
    assert any("src/app.py" in question.question for question in questions)
    assert any("Flask" in question.question for question in questions)


def test_format_interview_questions_renders_markdown() -> None:
    questions = build_deterministic_interview_questions(
        scored_files=[ScoredFile("README.md", 10, ["README"], "documentation", 100)],
        tech_detections=[],
        dependencies={},
    )

    rendered = format_interview_questions(questions[:1])

    assert "1. **" in rendered
    assert "Expected concepts" in rendered