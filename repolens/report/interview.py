"""Interview question helpers."""

from __future__ import annotations

from repolens.ai.schema import InterviewQuestion
from repolens.analyzer.models import ScoredFile, TechDetection


def build_deterministic_interview_questions(
    *,
    scored_files: list[ScoredFile],
    tech_detections: list[TechDetection],
    dependencies: dict[str, list[str]],
) -> list[InterviewQuestion]:
    """Build repository-specific fallback questions without an LLM."""
    questions: list[InterviewQuestion] = []
    top_file = scored_files[0].path if scored_files else "the highest-ranked file"
    top_tech = tech_detections[0].name if tech_detections else "the detected stack"
    ecosystems = ", ".join(dependencies) if dependencies else "the dependency manifests"

    seeds = [
        (
            f"Walk me through why {top_file} is important in this repository.",
            "code reading",
            "easy",
            "It checks whether the candidate can orient themselves from concrete files.",
            ["entry points", "repository navigation"],
        ),
        (
            f"How does {top_tech} appear to fit into the project architecture?",
            "architecture",
            "medium",
            "It connects technology evidence to design reasoning.",
            ["technology evidence", "architecture tradeoffs"],
        ),
        (
            f"What risks would you review before changing {top_file}?",
            "maintenance",
            "medium",
            "It tests change safety and impact analysis.",
            ["tests", "dependencies", "call flow"],
        ),
        (
            f"What do the {ecosystems} dependencies suggest about runtime behavior?",
            "dependencies",
            "medium",
            "It checks whether manifest evidence is interpreted carefully.",
            ["dependency manifests", "runtime stack"],
        ),
        (
            "Which analyzed files would you read next after the top-ranked files, and why?",
            "onboarding",
            "easy",
            "It tests practical codebase exploration strategy.",
            ["reading order", "file prioritization"],
        ),
    ]

    for question, topic, difficulty, why, concepts in seeds:
        questions.append(
            InterviewQuestion(
                question=question,
                topic=topic,
                difficulty=difficulty,  # type: ignore[arg-type]
                why_it_matters=why,
                expected_concepts=concepts,
            )
        )
    return questions


def format_interview_questions(questions: list[InterviewQuestion]) -> str:
    """Render interview questions as markdown."""
    if not questions:
        return "No interview questions were generated."

    lines: list[str] = []
    for index, question in enumerate(questions, start=1):
        concepts = ", ".join(question.expected_concepts)
        lines.extend(
            [
                f"{index}. **{question.question}**",
                f"   - Topic: {question.topic}",
                f"   - Difficulty: {question.difficulty}",
                f"   - Why it matters: {question.why_it_matters}",
                f"   - Expected concepts: {concepts}",
            ]
        )
    return "\n".join(lines)