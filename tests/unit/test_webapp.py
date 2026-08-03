"""Tests for the optional Flask web UI."""

from __future__ import annotations

from repolens.config import Config
from repolens.github.client import RepoMetadata
from repolens.pipeline import PipelineResult
from webapp.app import create_app, safe_markdown_to_html, validate_web_repo_url
from repolens.exceptions import InvalidURLError


def _config(*, no_ai: bool = False) -> Config:
    return Config(
        github_token=None,
        llm_provider="anthropic",
        llm_api_key=None,
        llm_model="claude-sonnet-4-6",
        max_files_analyzed=12,
        max_file_size_bytes=15000,
        max_context_size=12000,
        request_timeout=10,
        max_retries=3,
        log_level="INFO",
    )


def _result(content: str = "# Report\n- safe item") -> PipelineResult:
    return PipelineResult(
        content=content,
        output_format="md",
        metadata=RepoMetadata("owner", "repo", None, "main", 0, None, None, 1),
        partial=False,
        limitations=[],
        ai_used=False,
    )


def test_validate_web_repo_url_accepts_https_github() -> None:
    validate_web_repo_url("https://github.com/pallets/flask")


def test_validate_web_repo_url_rejects_invalid_and_ssrf_like_urls() -> None:
    bad_urls = [
        "http://github.com/pallets/flask",
        "https://localhost/pallets/flask",
        "https://github.com@localhost/pallets/flask",
        "file:///etc/passwd",
        "javascript:alert(1)",
        "https://example.com/pallets/flask",
    ]

    for url in bad_urls:
        try:
            validate_web_repo_url(url)
        except InvalidURLError:
            continue
        raise AssertionError(f"Accepted unsafe URL: {url}")


def test_post_analyze_calls_pipeline_for_valid_github_url() -> None:
    calls: list[dict[str, object]] = []

    def fake_runner(repo_url: str, **kwargs):  # type: ignore[no-untyped-def]
        calls.append({"repo_url": repo_url, **kwargs})
        return _result()

    app = create_app(config_factory=_config, analysis_runner=fake_runner)
    client = app.test_client()

    response = client.post(
        "/analyze",
        data={"repo_url": "https://github.com/pallets/flask", "interview": "on"},
    )

    assert response.status_code == 200
    assert calls[0]["repo_url"] == "https://github.com/pallets/flask"
    assert calls[0]["include_interview"] is True
    assert calls[0]["no_ai"] is True
    assert b"RepoLens report" in response.data


def test_post_analyze_rejects_malformed_input() -> None:
    app = create_app(config_factory=_config, analysis_runner=lambda *args, **kwargs: _result())
    client = app.test_client()

    response = client.post("/analyze", data={})

    assert response.status_code == 400
    assert b"Repository URL is required" in response.data


def test_post_analyze_rejects_non_github_url() -> None:
    app = create_app(config_factory=_config, analysis_runner=lambda *args, **kwargs: _result())
    client = app.test_client()

    response = client.post("/analyze", data={"repo_url": "https://localhost/repo"})

    assert response.status_code == 400
    assert b"only accepts https://github.com" in response.data


def test_safe_markdown_renderer_escapes_xss() -> None:
    rendered = safe_markdown_to_html("# Title\n<script>alert(1)</script>\n- <b>item</b>")

    assert "<script>" not in rendered
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in rendered
    assert "&lt;b&gt;item&lt;/b&gt;" in rendered