"""Unit tests for dependency manifest parsing."""

from __future__ import annotations

from repolens.analyzer.dependency_parse import parse_dependency_files, parse_manifest


def test_parse_requirements_txt() -> None:
    parsed = parse_manifest("requirements.txt", "Flask==3.0\nhttpx>=0.27\n# comment\n-r dev.txt")

    assert parsed.ecosystem == "python"
    assert parsed.packages == ["flask", "httpx"]
    assert parsed.errors == []


def test_parse_pyproject_dependencies() -> None:
    content = """
[project]
dependencies = ["pydantic>=2", "httpx"]

[project.optional-dependencies]
dev = ["pytest>=8"]
"""

    parsed = parse_manifest("pyproject.toml", content)

    assert parsed.packages == ["httpx", "pydantic", "pytest"]


def test_parse_package_json_sections() -> None:
    parsed = parse_manifest(
        "package.json",
        '{"dependencies":{"react":"latest"},"devDependencies":{"vite":"latest"}}',
    )

    assert parsed.ecosystem == "javascript"
    assert parsed.packages == ["react", "vite"]


def test_parse_go_mod_require_block() -> None:
    parsed = parse_manifest(
        "go.mod",
        "module demo\nrequire (\n github.com/gin-gonic/gin v1.9.0\n)\n",
    )

    assert parsed.packages == ["github.com/gin-gonic/gin"]


def test_parse_csproj_package_reference() -> None:
    parsed = parse_manifest(
        "App.csproj",
        '<Project><ItemGroup><PackageReference Include="Newtonsoft.Json" Version="13" /></ItemGroup></Project>',
    )

    assert parsed.ecosystem == "dotnet"
    assert parsed.packages == ["Newtonsoft.Json"]


def test_parse_many_groups_by_ecosystem() -> None:
    result = parse_dependency_files(
        {
            "requirements.txt": "flask\npytest",
            "package.json": '{"dependencies":{"axios":"1"}}',
        }
    )

    assert result == {"javascript": ["axios"], "python": ["flask", "pytest"]}


def test_malformed_manifest_returns_error_not_exception() -> None:
    parsed = parse_manifest("package.json", "{bad json")

    assert parsed.ecosystem == "javascript"
    assert parsed.packages == []
    assert parsed.errors