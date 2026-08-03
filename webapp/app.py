"""Thin Flask wrapper over the RepoLens analysis pipeline."""

from __future__ import annotations

import html
from collections.abc import Callable
from urllib.parse import urlparse

from flask import Flask, Response, render_template, request

from repolens.config import Config
from repolens.exceptions import InvalidURLError, RepoLensError
from repolens.github.url_parser import parse_github_url
from repolens.pipeline import PipelineResult, run_analysis

_ALLOWED_WEB_HOSTS = frozenset({"github.com", "www.github.com"})


def validate_web_repo_url(repo_url: str) -> None:
    """Validate the stricter web URL contract and the GitHub repo shape."""
    raw = repo_url.strip()
    parsed = urlparse(raw)
    host = parsed.netloc.lower().split("@")[-1].split(":")[0]
    if parsed.scheme != "https" or host not in _ALLOWED_WEB_HOSTS:
        raise InvalidURLError("Web analysis only accepts https://github.com/owner/repo URLs.")
    parse_github_url(raw)


def _flush_list(lines: list[str], html_lines: list[str], in_list: bool) -> bool:
    if in_list:
        html_lines.append("</ul>")
    return False


def safe_markdown_to_html(markdown: str) -> str:
    """Render a small safe Markdown subset while escaping all raw HTML."""
    html_lines: list[str] = []
    in_list = False

    for raw_line in markdown.splitlines():
        line = raw_line.rstrip()
        escaped = html.escape(line)
        if not line:
            in_list = _flush_list([], html_lines, in_list)
            continue
        if line.startswith("# "):
            in_list = _flush_list([], html_lines, in_list)
            html_lines.append(f"<h1>{html.escape(line[2:].strip())}</h1>")
        elif line.startswith("## "):
            in_list = _flush_list([], html_lines, in_list)
            html_lines.append(f"<h2>{html.escape(line[3:].strip())}</h2>")
        elif line.startswith("- "):
            if not in_list:
                html_lines.append("<ul>")
                in_list = True
            html_lines.append(f"<li>{html.escape(line[2:].strip())}</li>")
        else:
            in_list = _flush_list([], html_lines, in_list)
            html_lines.append(f"<p>{escaped}</p>")

    _flush_list([], html_lines, in_list)
    return "\n".join(html_lines)


def _bool_from_request(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").lower() in {"1", "true", "yes", "on"}


def create_app(
    *,
    config_factory: Callable[..., Config] = Config.from_env,
    analysis_runner: Callable[..., PipelineResult] = run_analysis,
) -> Flask:
    """Create the optional web UI application."""
    app = Flask(__name__)

    @app.get("/")
    def index() -> str:
        return render_template("index.html")

    @app.post("/analyze")
    def analyze() -> tuple[str, int] | Response:
        payload = request.get_json(silent=True) or request.form
        repo_url = str(payload.get("repo_url", "")).strip()
        interview = _bool_from_request(payload.get("interview"))

        if not repo_url:
            return render_template("index.html", error="Repository URL is required."), 400

        try:
            validate_web_repo_url(repo_url)
            config = config_factory(no_ai=False)
            no_ai = not bool(config.llm_api_key)
            result = analysis_runner(
                repo_url,
                config=config,
                include_interview=interview,
                no_ai=no_ai,
            )
        except RepoLensError as exc:
            return render_template("index.html", error=exc.message), exc.exit_code if exc.exit_code >= 400 else 400

        report_html = safe_markdown_to_html(result.content)
        return render_template("report.html", report_html=report_html, repo_url=repo_url)

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=False)