"""Evidence-based technology detection."""

from __future__ import annotations

import re
from collections import defaultdict
from pathlib import PurePosixPath

from repolens.analyzer.dependency_parse import flatten_dependencies
from repolens.analyzer.models import Confidence, TechDetection

_PACKAGE_TECH: dict[str, str] = {
    "flask": "Flask",
    "django": "Django",
    "fastapi": "FastAPI",
    "pydantic": "Pydantic",
    "pytest": "pytest",
    "requests": "Requests",
    "httpx": "HTTPX",
    "sqlalchemy": "SQLAlchemy",
    "react": "React",
    "next": "Next.js",
    "next.js": "Next.js",
    "vue": "Vue",
    "nuxt": "Nuxt",
    "angular": "Angular",
    "@angular/core": "Angular",
    "express": "Express",
    "vite": "Vite",
    "axios": "Axios",
    "tailwindcss": "Tailwind CSS",
    "gin-gonic/gin": "Gin",
    "github.com/gin-gonic/gin": "Gin",
    "actix-web": "Actix Web",
    "rocket": "Rocket",
    "rails": "Ruby on Rails",
    "laravel/framework": "Laravel",
    "spring-boot-starter-web": "Spring Boot",
    "microsoft.aspnetcore.app": "ASP.NET Core",
}

_CONFIG_MARKERS: tuple[tuple[str, str], ...] = (
    ("next.config.", "Next.js"),
    ("vite.config.", "Vite"),
    ("angular.json", "Angular"),
    ("nuxt.config.", "Nuxt"),
    ("tailwind.config.", "Tailwind CSS"),
    ("dockerfile", "Docker"),
    ("docker-compose.", "Docker Compose"),
    ("compose.yml", "Docker Compose"),
    ("compose.yaml", "Docker Compose"),
)

_IMPORT_MARKERS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"^\s*(from|import)\s+flask\b", re.MULTILINE), "Flask"),
    (re.compile(r"^\s*(from|import)\s+django\b", re.MULTILINE), "Django"),
    (re.compile(r"^\s*(from|import)\s+fastapi\b", re.MULTILINE), "FastAPI"),
    (re.compile(r"from\s+['\"]react['\"]|require\(['\"]react['\"]\)", re.MULTILINE), "React"),
    (re.compile(r"from\s+['\"]next/|require\(['\"]next", re.MULTILINE), "Next.js"),
    (re.compile(r"from\s+['\"]express['\"]|require\(['\"]express['\"]\)", re.MULTILINE), "Express"),
    (re.compile(r"from\s+['\"]axios['\"]|require\(['\"]axios['\"]\)", re.MULTILINE), "Axios"),
)

_CONFIDENCE_ORDER: dict[Confidence, int] = {
    "possible": 0,
    "likely": 1,
    "confirmed": 2,
}


def _name(path: str) -> str:
    return PurePosixPath(path).name.lower()


def _parts(path: str) -> tuple[str, ...]:
    return tuple(part.lower() for part in PurePosixPath(path).parts)


def _add(
    detections: dict[str, tuple[Confidence, list[str]]],
    name: str,
    confidence: Confidence,
    evidence: str,
) -> None:
    current = detections.get(name)
    if current is None:
        detections[name] = (confidence, [evidence])
        return

    current_confidence, current_evidence = current
    best = (
        confidence
        if _CONFIDENCE_ORDER[confidence] > _CONFIDENCE_ORDER[current_confidence]
        else current_confidence
    )
    if evidence not in current_evidence:
        current_evidence.append(evidence)
    detections[name] = (best, current_evidence)


def detect_technologies(
    paths: list[str],
    *,
    dependencies: dict[str, list[str]] | None = None,
    file_contents: dict[str, str] | None = None,
) -> list[TechDetection]:
    """Detect technologies using manifests, marker files, conventions, and imports."""
    detections: dict[str, tuple[Confidence, list[str]]] = {}
    dependencies = dependencies or {}

    packages = flatten_dependencies(dependencies)
    for package in sorted(packages):
        tech = _PACKAGE_TECH.get(package)
        if tech is not None:
            _add(detections, tech, "confirmed", f"dependency manifest includes {package}")

    for path in sorted(paths):
        name = _name(path)
        for marker, tech in _CONFIG_MARKERS:
            if name == marker or name.startswith(marker):
                _add(detections, tech, "confirmed", f"marker file {path}")

    parts_by_root: dict[str, set[str]] = defaultdict(set)
    for path in paths:
        parts = _parts(path)
        if len(parts) >= 2:
            parts_by_root[parts[0]].add(parts[1])

    for root, children in parts_by_root.items():
        if {"models", "controllers"}.issubset(children):
            _add(
                detections,
                "MVC-style application",
                "likely",
                f"{root}/ contains models/ and controllers/",
            )
        if {"pages", "components"}.issubset(children):
            _add(
                detections,
                "Component-based frontend",
                "likely",
                f"{root}/ contains pages/ and components/",
            )

    for path, content in sorted((file_contents or {}).items()):
        for pattern, tech in _IMPORT_MARKERS:
            if pattern.search(content):
                _add(detections, tech, "possible", f"{path} imports {tech}")

    return [
        TechDetection(name=name, confidence=confidence, evidence=evidence)
        for name, (confidence, evidence) in sorted(detections.items())
        if evidence
    ]