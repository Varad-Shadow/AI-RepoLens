"""Mocked full-pipeline integration tests."""

from __future__ import annotations

import json

from repolens.config import Config
from repolens.github.client import RepoMetadata, TreeEntry, TreeResult
from repolens.pipeline import run_analysis


class FakeGitHubClient:
    def __init__(self) -> None:
        self.content_requests: list[str] = []

    def get_repo_metadata(self, owner: str, repo: str) -> RepoMetadata:
        return RepoMetadata(
            owner=owner,
            name=repo,
            description="A small Flask demo",
            default_branch="main",
            stars=42,
            primary_language="Python",
            license="MIT",
            size_kb=100,
        )

    def get_tree(self, owner: str, repo: str, ref: str) -> TreeResult:
        return TreeResult(
            entries=[
                TreeEntry("README.md", "blob", 100),
                TreeEntry("requirements.txt", "blob", 50),
                TreeEntry("src", "tree"),
                TreeEntry("src/app.py", "blob", 100),
                TreeEntry("tests", "tree"),
                TreeEntry("tests/test_app.py", "blob", 100),
                TreeEntry(".env", "blob", 20),
            ],
            truncated=False,
        )

    def get_file_content(self, owner: str, repo: str, path: str, ref: str) -> bytes:
        self.content_requests.append(path)
        contents = {
            "README.md": b"# Demo\n",
            "requirements.txt": b"flask\npytest\n",
            "src/app.py": b"from flask import Flask\napp = Flask(__name__)\n",
            "tests/test_app.py": b"def test_ok():\n    assert True\n",
        }
        return contents[path]

    def close(self) -> None:
        pass


class FakeLLMClient:
    def __init__(self, response: str) -> None:
        self.response = response
        self.calls = 0

    def generate(self, system: str, user: str) -> str:
        self.calls += 1
        assert "SELECTED FILE CONTENTS" in user
        return self.response


def _config() -> Config:
    return Config(
        github_token=None,
        llm_provider="anthropic",
        llm_api_key="test-key",
        llm_model="claude-sonnet-4-6",
        max_files_analyzed=4,
        max_file_size_bytes=15000,
        max_context_size=12000,
        request_timeout=10,
        max_retries=3,
        log_level="INFO",
    )


def _ai_payload() -> str:
    return json.dumps(
        {
            "summary": "AI summary",
            "project_purpose": "Explain a Flask demo.",
            "technology_stack": [
                {"name": "Flask", "confidence": "confirmed", "evidence": ["requirements.txt"]}
            ],
            "architecture": "A small app module with tests.",
            "directory_analysis": {"src": "Application code", "tests": "Tests"},
            "important_files": [
                {"path": "src/app.py", "why_important": "Application entry point"},
                {"path": "missing.py", "why_important": "Hallucinated"},
            ],
            "reading_order": ["README.md", "src/app.py", "missing.py"],
            "entry_points": ["src/app.py", "missing.py"],
            "code_flows": ["Request enters Flask app"],
            "dependencies_summary": "Uses Flask and pytest.",
            "testing_summary": "Contains a pytest file.",
            "configuration_summary": "No major config detected.",
            "improvements": ["Add usage examples"],
            "interview_questions": [],
            "limitations": [],
        }
    )


def test_no_ai_pipeline_generates_report_without_llm_or_secret_fetch() -> None:
    github = FakeGitHubClient()

    result = run_analysis(
        "https://github.com/pallets/flask",
        config=_config(),
        no_ai=True,
        include_interview=True,
        github_client=github,  # type: ignore[arg-type]
    )

    assert result.ai_used is False
    assert "# RepoLens Report: pallets/flask" in result.content
    assert "## Interview Questions" in result.content
    assert ".env" not in github.content_requests
    assert ".env" not in result.content


def test_ai_pipeline_validates_and_drops_hallucinated_paths() -> None:
    github = FakeGitHubClient()
    llm = FakeLLMClient(_ai_payload())

    result = run_analysis(
        "https://github.com/pallets/flask",
        config=_config(),
        no_ai=False,
        github_client=github,  # type: ignore[arg-type]
        llm_client=llm,
    )

    assert result.ai_used is True
    assert llm.calls == 1
    assert "AI summary" in result.content
    assert "missing.py" not in result.content
    assert "`src/app.py`" in result.content


def test_json_output_contains_deterministic_sections() -> None:
    result = run_analysis(
        "https://github.com/pallets/flask",
        config=_config(),
        no_ai=True,
        output_format="json",
        github_client=FakeGitHubClient(),  # type: ignore[arg-type]
    )

    payload = json.loads(result.content)
    assert payload["metadata"]["name"] == "flask"
    assert payload["dependencies"]["python"] == ["flask", "pytest"]
    assert payload["ai_analysis"] is None

class ManyManifestGitHubClient(FakeGitHubClient):
    def get_tree(self, owner: str, repo: str, ref: str) -> TreeResult:
        entries = [TreeEntry("README.md", "blob", 100)]
        entries.extend(TreeEntry(f"crate_{index}/Cargo.toml", "blob", 50) for index in range(10))
        return TreeResult(entries=entries, truncated=False)

    def get_file_content(self, owner: str, repo: str, path: str, ref: str) -> bytes:
        self.content_requests.append(path)
        if path == "README.md":
            return b"# Demo\n"
        return b"[dependencies]\nserde = \"1\"\n"


def test_pipeline_bounds_dependency_manifest_fetches() -> None:
    config = _config()
    object.__setattr__(config, "max_files_analyzed", 3)
    github = ManyManifestGitHubClient()

    result = run_analysis(
        "https://github.com/pallets/flask",
        config=config,
        no_ai=True,
        output_format="json",
        github_client=github,  # type: ignore[arg-type]
    )

    manifest_requests = [path for path in github.content_requests if path.endswith("Cargo.toml")]
    assert len(manifest_requests) == 3
    assert "Parsed top 3 of 10 supported dependency manifest" in result.content