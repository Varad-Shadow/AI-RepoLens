"""Unit tests for CLI integration and expected exit codes."""

from __future__ import annotations

from repolens import cli
from repolens.github.client import RepoMetadata
from repolens.exceptions import RateLimitError
from repolens.pipeline import PipelineResult


def _result(content: str = "report") -> PipelineResult:
    return PipelineResult(
        content=content,
        output_format="md",
        metadata=RepoMetadata("owner", "repo", None, "main", 0, None, None, 1),
        partial=False,
        limitations=[],
        ai_used=False,
    )


def test_invalid_url_returns_exit_code_2_before_missing_key(monkeypatch, capsys) -> None:
    monkeypatch.delenv("LLM_API_KEY", raising=False)

    exit_code = cli.main(["analyze", "https://example.com/owner/repo"])

    captured = capsys.readouterr()
    assert exit_code == 2
    assert "Only github.com URLs are supported" in captured.err
    assert "LLM_API_KEY" not in captured.err


def test_missing_llm_key_returns_exit_code_6_before_pipeline(monkeypatch, capsys) -> None:
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    called = False

    def fake_run_analysis(*args, **kwargs):  # type: ignore[no-untyped-def]
        nonlocal called
        called = True
        return _result()

    monkeypatch.setattr(cli, "run_analysis", fake_run_analysis)

    exit_code = cli.main(["analyze", "https://github.com/owner/repo"])

    captured = capsys.readouterr()
    assert exit_code == 6
    assert called is False
    assert "LLM_API_KEY is required" in captured.err
    assert "Traceback" not in captured.err


def test_no_ai_calls_pipeline_without_llm_key(monkeypatch, capsys) -> None:
    monkeypatch.delenv("LLM_API_KEY", raising=False)

    def fake_run_analysis(*args, **kwargs):  # type: ignore[no-untyped-def]
        assert kwargs["no_ai"] is True
        return _result("hello report")

    monkeypatch.setattr(cli, "run_analysis", fake_run_analysis)

    exit_code = cli.main(["analyze", "https://github.com/owner/repo", "--no-ai", "--output", "-"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "hello report" in captured.out


def test_rate_limit_error_returns_exit_code_4_without_traceback(monkeypatch, capsys) -> None:
    monkeypatch.setenv("LLM_API_KEY", "test-key")

    def fake_run_analysis(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise RateLimitError("GitHub API rate limit exhausted. Set GITHUB_TOKEN for a higher limit.")

    monkeypatch.setattr(cli, "run_analysis", fake_run_analysis)

    exit_code = cli.main(["analyze", "https://github.com/owner/repo"])

    captured = capsys.readouterr()
    assert exit_code == 4
    assert "rate limit exhausted" in captured.err
    assert "Traceback" not in captured.err