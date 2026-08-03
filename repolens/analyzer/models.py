"""Data models for repository analysis."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

FileCategory = Literal[
    "source",
    "test",
    "config",
    "documentation",
    "dependency",
    "ci_cd",
    "infrastructure",
    "generated",
    "binary",
    "asset",
    "unknown",
]


@dataclass
class FileEntry:
    """A repository file with classification metadata."""

    path: str
    size_bytes: int
    category: FileCategory
    is_binary: bool
    is_excluded: bool
    exclusion_reason: str | None = None
    importance_score: float = 0.0
    language: str | None = None


@dataclass(frozen=True)
class DeterministicStats:
    """Countable repository facts computed without an LLM."""

    total_files: int
    total_dirs: int
    files_analyzed: int
    files_ignored: int
    language_distribution: dict[str, float]
    dependency_files: list[str]
    config_files: list[str]
    ci_files: list[str]
    docker_files: list[str]
    test_files: list[str]
    has_readme: bool
    has_license: bool
    has_ci: bool
    has_docker: bool
    has_tests: bool


@dataclass
class DeterministicAnalysisResult:
    """Output of deterministic repository analysis."""

    stats: DeterministicStats
    files: list[FileEntry] = field(default_factory=list)
    filtered_paths: list[str] = field(default_factory=list)
    ignored_paths: list[str] = field(default_factory=list)


Confidence = Literal["confirmed", "likely", "possible"]


@dataclass(frozen=True)
class TechDetection:
    """Evidence-backed technology or framework detection."""

    name: str
    confidence: Confidence
    evidence: list[str]


@dataclass(frozen=True)
class ScoredFile:
    """A file ranked for human/LLM review."""

    path: str
    score: float
    reasons: list[str]
    category: FileCategory
    size_bytes: int