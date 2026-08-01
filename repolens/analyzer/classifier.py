"""File category classification based on path evidence."""

from __future__ import annotations

import re
from fnmatch import fnmatch
from pathlib import PurePosixPath

from repolens.analyzer.binary_detect import (
    extension_of,
    is_asset_extension,
    is_binary_extension,
)
from repolens.analyzer.models import FileCategory

DEPENDENCY_FILENAMES: frozenset[str] = frozenset(
    {
        "requirements.txt",
        "requirements-dev.txt",
        "requirements_dev.txt",
        "pyproject.toml",
        "pipfile",
        "pipfile.lock",
        "package.json",
        "package-lock.json",
        "yarn.lock",
        "pnpm-lock.yaml",
        "go.mod",
        "go.sum",
        "cargo.toml",
        "cargo.lock",
        "pom.xml",
        "build.gradle",
        "build.gradle.kts",
        "composer.json",
        "composer.lock",
        "gemfile",
        "gemfile.lock",
        "poetry.lock",
    }
)

CONFIG_FILENAMES: frozenset[str] = frozenset(
    {
        "setup.cfg",
        "setup.py",
        "tox.ini",
        "pytest.ini",
        "mypy.ini",
        "ruff.toml",
        ".editorconfig",
        "tsconfig.json",
        "jsconfig.json",
        "webpack.config.js",
        "vite.config.js",
        "vite.config.ts",
        "next.config.js",
        "next.config.mjs",
        "next.config.ts",
        "angular.json",
        "nuxt.config.js",
        "nuxt.config.ts",
        "tailwind.config.js",
        "tailwind.config.ts",
        "babel.config.js",
        "rollup.config.js",
        "eslint.config.js",
        "settings.py",
        "config.py",
        "appsettings.json",
        "application.properties",
        "application.yml",
        "application.yaml",
    }
)

DOCKER_FILENAMES: frozenset[str] = frozenset(
    {
        "dockerfile",
        "docker-compose.yml",
        "docker-compose.yaml",
        "compose.yml",
        "compose.yaml",
    }
)

LICENSE_FILENAMES: frozenset[str] = frozenset(
    {
        "license",
        "license.md",
        "license.txt",
        "copying",
        "copying.md",
        "copying.txt",
        "notice",
        "notice.md",
        "notice.txt",
    }
)

GENERATED_DIR_COMPONENTS: frozenset[str] = frozenset(
    {
        "generated",
        "__generated__",
        "gen",
        "autogen",
        "auto-generated",
    }
)

GENERATED_EXTENSIONS: frozenset[str] = frozenset({".g.dart", ".pb.go", ".generated.cs"})

INFRASTRUCTURE_DIR_COMPONENTS: frozenset[str] = frozenset(
    {
        "terraform",
        "pulumi",
        "cloudformation",
        "helm",
        "charts",
        "k8s",
        "kubernetes",
        "infra",
        "infrastructure",
        "deploy",
    }
)

TEST_DIR_COMPONENTS: frozenset[str] = frozenset({"test", "tests", "testing", "__tests__"})
TEST_FILE_PATTERNS: tuple[str, ...] = (
    "test_*.py",
    "*_test.py",
    "*_test.go",
    "*.test.js",
    "*.test.ts",
    "*.test.tsx",
    "*.spec.js",
    "*.spec.ts",
    "*.spec.tsx",
    "*_spec.rb",
    "*_test.rb",
)

README_RE = re.compile(r"^readme(|\..+)$", re.IGNORECASE)
SOURCE_EXTENSIONS: dict[str, str] = {
    ".py": "Python",
    ".pyi": "Python",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".go": "Go",
    ".rs": "Rust",
    ".java": "Java",
    ".kt": "Kotlin",
    ".kts": "Kotlin",
    ".scala": "Scala",
    ".rb": "Ruby",
    ".php": "PHP",
    ".cs": "C#",
    ".cpp": "C++",
    ".cc": "C++",
    ".cxx": "C++",
    ".c": "C",
    ".h": "C",
    ".hpp": "C++",
    ".swift": "Swift",
    ".m": "Objective-C",
    ".mm": "Objective-C++",
    ".lua": "Lua",
    ".r": "R",
    ".R": "R",
    ".sql": "SQL",
    ".sh": "Shell",
    ".bash": "Shell",
    ".zsh": "Shell",
    ".ps1": "PowerShell",
    ".vue": "Vue",
    ".svelte": "Svelte",
    ".dart": "Dart",
    ".ex": "Elixir",
    ".exs": "Elixir",
    ".erl": "Erlang",
    ".hs": "Haskell",
    ".clj": "Clojure",
    ".cljs": "Clojure",
    ".html": "HTML",
    ".css": "CSS",
    ".scss": "SCSS",
    ".sass": "SASS",
    ".less": "Less",
    ".md": "Markdown",
}


def _filename(path: str) -> str:
    return PurePosixPath(path).name


def _lower_filename(path: str) -> str:
    return _filename(path).lower()


def _path_parts(path: str) -> tuple[str, ...]:
    return PurePosixPath(path).parts


def is_readme(path: str) -> bool:
    return bool(README_RE.match(_filename(path)))


def is_license(path: str) -> bool:
    return _lower_filename(path) in LICENSE_FILENAMES


def is_docker_file(path: str) -> bool:
    name = _lower_filename(path)
    if name in DOCKER_FILENAMES:
        return True
    return name.startswith("dockerfile") or name.endswith(".dockerfile")


def is_ci_file(path: str) -> bool:
    parts = _path_parts(path)
    lower_parts = [part.lower() for part in parts]
    name = _lower_filename(path)

    if ".github" in lower_parts and "workflows" in lower_parts:
        return True
    if name in {
        ".gitlab-ci.yml",
        "jenkinsfile",
        "azure-pipelines.yml",
        "azure-pipelines.yaml",
        "cloudbuild.yaml",
        "cloudbuild.yml",
        "bitbucket-pipelines.yml",
        ".travis.yml",
        "appveyor.yml",
        "circle.yml",
    }:
        return True
    if ".circleci" in lower_parts:
        return True
    return False


def is_dependency_file(path: str) -> bool:
    name = _lower_filename(path)
    if name in DEPENDENCY_FILENAMES:
        return True
    if fnmatch(name, "*.csproj"):
        return True
    return False


def is_config_file(path: str) -> bool:
    name = _lower_filename(path)
    if name in CONFIG_FILENAMES:
        return True
    if fnmatch(name, "*.config.js") or fnmatch(name, "*.config.ts"):
        return True
    return False


def is_test_file(path: str) -> bool:
    parts = _path_parts(path)
    if any(part.lower() in TEST_DIR_COMPONENTS for part in parts):
        return True
    name = _filename(path)
    return any(fnmatch(name, pattern) for pattern in TEST_FILE_PATTERNS)


def is_generated(path: str) -> bool:
    parts = {part.lower() for part in _path_parts(path)}
    if parts & GENERATED_DIR_COMPONENTS:
        return True
    ext = extension_of(path)
    return ext in GENERATED_EXTENSIONS or name_has_generated_marker(path)


def name_has_generated_marker(path: str) -> bool:
    name = _lower_filename(path)
    return (
        name.endswith(".generated.ts")
        or name.endswith(".generated.js")
        or ".min." in name
        or name.endswith(".min.js")
        or name.endswith(".min.css")
    )


def is_infrastructure(path: str) -> bool:
    parts = {part.lower() for part in _path_parts(path)}
    if parts & INFRASTRUCTURE_DIR_COMPONENTS:
        return True
    ext = extension_of(path)
    return ext in {".tf", ".tfvars", ".hcl", ".nomad"}


def detect_language(path: str) -> str | None:
    """Return language label from extension evidence, or None if unknown."""
    ext = extension_of(path)
    if ext in SOURCE_EXTENSIONS:
        return SOURCE_EXTENSIONS[ext]
    if ext == ".json" and _lower_filename(path) == "package.json":
        return "JSON"
    return None


def classify_path(
    path: str,
    *,
    is_binary: bool | None = None,
) -> FileCategory:
    """Assign a category using filename and path-component evidence only."""
    if is_binary is None:
        is_binary = is_binary_extension(path)

    if is_binary:
        if is_asset_extension(path):
            return "asset"
        return "binary"

    if is_readme(path):
        return "documentation"
    if is_license(path):
        return "documentation"
    if is_dependency_file(path):
        return "dependency"
    if is_docker_file(path):
        return "infrastructure"
    if is_ci_file(path):
        return "ci_cd"
    if is_infrastructure(path):
        return "infrastructure"
    if is_config_file(path):
        return "config"
    if is_generated(path):
        return "generated"
    if is_test_file(path):
        return "test"

    ext = extension_of(path)
    if ext in {".md", ".rst", ".txt", ".adoc"} and not is_readme(path):
        return "documentation"
    if ext in SOURCE_EXTENSIONS:
        return "source"

    return "unknown"
