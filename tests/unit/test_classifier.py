"""Unit tests for file classification."""

import pytest

from repolens.analyzer.classifier import (
    classify_path,
    detect_language,
    is_dependency_file,
    is_readme,
    is_test_file,
)


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("README.md", "documentation"),
        ("readme.MD", "documentation"),
        ("LICENSE", "documentation"),
        ("requirements.txt", "dependency"),
        ("package.json", "dependency"),
        ("pyproject.toml", "dependency"),
        ("Dockerfile", "infrastructure"),
        ("docker-compose.yml", "infrastructure"),
        (".github/workflows/ci.yml", "ci_cd"),
        ("src/app.py", "source"),
        ("tests/test_app.py", "test"),
        ("test/unit/test_api.py", "test"),
        ("contest/scoring.py", "source"),
        ("config/settings.py", "config"),
        ("assets/logo.png", "asset"),
        ("dist/app.min.js", "generated"),
        ("generated/models.py", "generated"),
        ("node_modules/pkg/index.js", "source"),  # classifier alone; filter excludes
        ("terraform/main.tf", "infrastructure"),
        ("unknown/file.xyz", "unknown"),
    ],
)
def test_classify_path(path: str, expected: str) -> None:
    assert classify_path(path) == expected


def test_contest_not_classified_as_test() -> None:
    assert is_test_file("contest/run.py") is False
    assert classify_path("contest/run.py") == "source"


def test_tests_directory_classified_as_test() -> None:
    assert is_test_file("tests/integration/test_api.py") is True
    assert classify_path("tests/integration/test_api.py") == "test"


def test_detect_language_multi_language() -> None:
    assert detect_language("main.py") == "Python"
    assert detect_language("app.ts") == "TypeScript"
    assert detect_language("main.go") == "Go"
    assert detect_language("file.xyz") is None


def test_dependency_detection_evidence_based() -> None:
    assert is_dependency_file("requirements.txt") is True
    assert is_dependency_file("src/app.py") is False


def test_readme_variants() -> None:
    assert is_readme("README.rst") is True
    assert is_readme("README") is True
    assert is_readme("NOTREADME.md") is False
