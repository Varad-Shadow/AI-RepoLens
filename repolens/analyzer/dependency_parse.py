"""Read-only dependency manifest parsing."""

from __future__ import annotations

import json
import re
import tomllib
import xml.etree.ElementTree as ET
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import PurePosixPath
from typing import Any

from repolens.analyzer.classifier import is_dependency_file


@dataclass(frozen=True)
class ParsedDependencies:
    """Dependencies parsed from one manifest file."""

    ecosystem: str
    packages: list[str]
    source_path: str
    errors: list[str] = field(default_factory=list)


_REQ_NAME_RE = re.compile(r"^\s*([A-Za-z0-9_.-]+)")
_GRADLE_DEP_RE = re.compile(r"['\"]([A-Za-z0-9_.-]+):([A-Za-z0-9_.-]+):[^'\"]+['\"]")
_GO_REQUIRE_RE = re.compile(r"^\s*([A-Za-z0-9_.\-/]+)\s+v[0-9]")
_GEM_RE = re.compile(r"^\s*gem\s+['\"]([^'\"]+)['\"]")


def _name(path: str) -> str:
    return PurePosixPath(path).name.lower()


def _dedupe(packages: list[str]) -> list[str]:
    return sorted({package for package in packages if package})


def _parse_requirements(content: str) -> list[str]:
    packages: list[str] = []
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or line.startswith("-"):
            continue
        line = line.split("#", 1)[0].strip()
        match = _REQ_NAME_RE.match(line)
        if match:
            packages.append(match.group(1).lower())
    return _dedupe(packages)


def _parse_pyproject(content: str) -> list[str]:
    data = tomllib.loads(content)
    packages: list[str] = []
    project = data.get("project", {})
    for dependency in project.get("dependencies", []) or []:
        match = _REQ_NAME_RE.match(str(dependency))
        if match:
            packages.append(match.group(1).lower())
    optional = project.get("optional-dependencies", {})
    for values in optional.values():
        for dependency in values or []:
            match = _REQ_NAME_RE.match(str(dependency))
            if match:
                packages.append(match.group(1).lower())

    poetry = data.get("tool", {}).get("poetry", {})
    for section in ("dependencies", "dev-dependencies"):
        for package in poetry.get(section, {}) or {}:
            if package.lower() != "python":
                packages.append(package.lower())
    poetry_groups = poetry.get("group", {})
    for group in poetry_groups.values():
        for package in group.get("dependencies", {}) or {}:
            if package.lower() != "python":
                packages.append(package.lower())

    return _dedupe(packages)


def _parse_pipfile(content: str) -> list[str]:
    data = tomllib.loads(content)
    packages: list[str] = []
    for section in ("packages", "dev-packages"):
        packages.extend(package.lower() for package in data.get(section, {}) or {})
    return _dedupe(packages)


def _parse_package_json(content: str) -> list[str]:
    data = json.loads(content)
    packages: list[str] = []
    for section in (
        "dependencies",
        "devDependencies",
        "peerDependencies",
        "optionalDependencies",
    ):
        packages.extend((data.get(section) or {}).keys())
    return _dedupe(packages)


def _strip_xml_namespace(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _parse_pom(content: str) -> list[str]:
    root = ET.fromstring(content)
    packages: list[str] = []
    for dependency in root.iter():
        if _strip_xml_namespace(dependency.tag) != "dependency":
            continue
        artifact = None
        group = None
        for child in dependency:
            child_name = _strip_xml_namespace(child.tag)
            if child_name == "artifactId":
                artifact = child.text
            elif child_name == "groupId":
                group = child.text
        if artifact:
            packages.append(f"{group}:{artifact}" if group else artifact)
    return _dedupe(packages)


def _parse_gradle(content: str) -> list[str]:
    return _dedupe(
        [
            f"{match.group(1)}:{match.group(2)}"
            for match in _GRADLE_DEP_RE.finditer(content)
        ]
    )


def _parse_go_mod(content: str) -> list[str]:
    packages: list[str] = []
    for line in content.splitlines():
        stripped = line.split("//", 1)[0].strip()
        if not stripped or stripped in {"require (", ")"}:
            continue
        match = _GO_REQUIRE_RE.match(stripped)
        if match:
            packages.append(match.group(1))
    return _dedupe(packages)


def _parse_cargo(content: str) -> list[str]:
    data = tomllib.loads(content)
    packages: list[str] = []
    for section in ("dependencies", "dev-dependencies", "build-dependencies"):
        packages.extend((data.get(section) or {}).keys())
    return _dedupe(packages)


def _parse_csproj(content: str) -> list[str]:
    root = ET.fromstring(content)
    packages: list[str] = []
    for element in root.iter():
        if _strip_xml_namespace(element.tag) != "PackageReference":
            continue
        include = element.attrib.get("Include") or element.attrib.get("Update")
        if include:
            packages.append(include)
    return _dedupe(packages)


def _parse_composer(content: str) -> list[str]:
    data = json.loads(content)
    packages: list[str] = []
    for section in ("require", "require-dev"):
        for package in (data.get(section) or {}).keys():
            if package.lower() != "php":
                packages.append(package)
    return _dedupe(packages)


def _parse_gemfile(content: str) -> list[str]:
    return _dedupe([match.group(1) for match in _GEM_RE.finditer(content)])


def ecosystem_for_manifest(path: str) -> str | None:
    """Return the ecosystem handled by a dependency manifest path."""
    name = _name(path)
    if name.startswith("requirements") or name in {"pyproject.toml", "pipfile"}:
        return "python"
    if name == "package.json":
        return "javascript"
    if name in {"pom.xml", "build.gradle", "build.gradle.kts"}:
        return "java"
    if name == "go.mod":
        return "go"
    if name == "cargo.toml":
        return "rust"
    if name.endswith(".csproj"):
        return "dotnet"
    if name == "composer.json":
        return "php"
    if name == "gemfile":
        return "ruby"
    return None


def parse_manifest(path: str, content: str) -> ParsedDependencies:
    """Parse one dependency manifest without executing anything."""
    ecosystem = ecosystem_for_manifest(path)
    if ecosystem is None or not is_dependency_file(path):
        return ParsedDependencies(
            ecosystem="unknown",
            packages=[],
            source_path=path,
            errors=[f"Unsupported manifest: {path}"],
        )

    name = _name(path)
    try:
        if name.startswith("requirements"):
            packages = _parse_requirements(content)
        elif name == "pyproject.toml":
            packages = _parse_pyproject(content)
        elif name == "pipfile":
            packages = _parse_pipfile(content)
        elif name == "package.json":
            packages = _parse_package_json(content)
        elif name == "pom.xml":
            packages = _parse_pom(content)
        elif name in {"build.gradle", "build.gradle.kts"}:
            packages = _parse_gradle(content)
        elif name == "go.mod":
            packages = _parse_go_mod(content)
        elif name == "cargo.toml":
            packages = _parse_cargo(content)
        elif name.endswith(".csproj"):
            packages = _parse_csproj(content)
        elif name == "composer.json":
            packages = _parse_composer(content)
        elif name == "gemfile":
            packages = _parse_gemfile(content)
        else:
            packages = []
    except (json.JSONDecodeError, tomllib.TOMLDecodeError, ET.ParseError, TypeError, ValueError) as exc:
        return ParsedDependencies(
            ecosystem=ecosystem,
            packages=[],
            source_path=path,
            errors=[f"Could not parse {path}: {exc}"],
        )

    return ParsedDependencies(ecosystem=ecosystem, packages=packages, source_path=path)


def parse_dependency_files(contents_by_path: dict[str, str]) -> dict[str, list[str]]:
    """Parse many manifests into ecosystem -> package list."""
    grouped: dict[str, list[str]] = defaultdict(list)
    for path, content in sorted(contents_by_path.items()):
        parsed = parse_manifest(path, content)
        if parsed.ecosystem != "unknown":
            grouped[parsed.ecosystem].extend(parsed.packages)

    return {
        ecosystem: _dedupe(packages)
        for ecosystem, packages in sorted(grouped.items())
    }


def flatten_dependencies(dependencies: dict[str, list[str]]) -> set[str]:
    """Return a lowercase package-name set across ecosystems."""
    return {
        package.lower()
        for packages in dependencies.values()
        for package in packages
    }


def dependency_summary(dependencies: dict[str, list[str]]) -> dict[str, Any]:
    """Small serializable summary used by reports and tests."""
    return {
        ecosystem: {"count": len(packages), "packages": packages}
        for ecosystem, packages in dependencies.items()
    }