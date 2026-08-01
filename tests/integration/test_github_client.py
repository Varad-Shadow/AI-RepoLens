import base64
import json
from pathlib import Path

import httpx
import pytest

from repolens.config import Config
from repolens.exceptions import RateLimitError, RepositoryNotFoundError
from repolens.github.client import GitHubClient

FIXTURES = Path(__file__).resolve().parent.parent / "mocks" / "github_responses"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _config() -> Config:
    return Config(
        github_token="test-token",
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


def test_get_repo_metadata() -> None:
    metadata_payload = _load("repo_metadata.json")

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/repos/pallets/flask":
            return httpx.Response(200, json=metadata_payload)
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    with GitHubClient(_config(), client=httpx.Client(transport=transport, base_url="https://api.github.com")) as gh:
        meta = gh.get_repo_metadata("pallets", "flask")

    assert meta.owner == "pallets"
    assert meta.name == "flask"
    assert meta.default_branch == "main"
    assert meta.stars == 70000
    assert meta.primary_language == "Python"
    assert meta.license == "BSD-3-Clause"


def test_get_tree_full() -> None:
    tree_payload = _load("tree_full.json")

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/repos/pallets/flask/git/trees/main":
            return httpx.Response(200, json=tree_payload)
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    with GitHubClient(_config(), client=httpx.Client(transport=transport, base_url="https://api.github.com")) as gh:
        result = gh.get_tree("pallets", "flask", "main")

    assert result.truncated is False
    assert result.partial is False
    assert len(result.entries) == 4
    assert result.entries[0].path == "README.md"


def test_get_tree_truncated_falls_back_to_partial() -> None:
    root_contents = [
        {"name": "README.md", "path": "README.md", "type": "file", "size": 100},
        {"name": "src", "path": "src", "type": "dir"},
    ]
    src_contents = [
        {"name": "app.py", "path": "src/app.py", "type": "file", "size": 200},
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/repos/huge/huge/git/trees/main":
            return httpx.Response(200, json=_load("tree_truncated.json"))
        if path == "/repos/huge/huge/contents":
            return httpx.Response(200, json=root_contents)
        if path == "/repos/huge/huge/contents/src":
            return httpx.Response(200, json=src_contents)
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    with GitHubClient(_config(), client=httpx.Client(transport=transport, base_url="https://api.github.com")) as gh:
        result = gh.get_tree("huge", "huge", "main")

    assert result.truncated is True
    assert result.partial is True
    assert result.partial_reason is not None
    paths = {entry.path for entry in result.entries}
    assert "README.md" in paths
    assert "src/app.py" in paths


def test_get_file_content_decodes_base64() -> None:
    content = "hello flask"
    encoded = base64.b64encode(content.encode()).decode()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/repos/pallets/flask/contents/README.md":
            return httpx.Response(
                200,
                json={"encoding": "base64", "content": encoded, "path": "README.md"},
            )
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    with GitHubClient(_config(), client=httpx.Client(transport=transport, base_url="https://api.github.com")) as gh:
        raw = gh.get_file_content("pallets", "flask", "README.md", "main")
        text = gh.decode_text_content(raw)

    assert text == content


def test_repo_not_found_maps_to_exception() -> None:
    transport = httpx.MockTransport(lambda request: httpx.Response(404))
    with GitHubClient(_config(), client=httpx.Client(transport=transport, base_url="https://api.github.com")) as gh:
        with pytest.raises(RepositoryNotFoundError):
            gh.get_repo_metadata("missing", "repo")


def test_rate_limit_exhausted_maps_to_exception() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            403,
            headers={"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "1700000000"},
        )

    transport = httpx.MockTransport(handler)
    with GitHubClient(_config(), client=httpx.Client(transport=transport, base_url="https://api.github.com")) as gh:
        with pytest.raises(RateLimitError, match="rate limit exhausted"):
            gh.get_repo_metadata("pallets", "flask")


def test_get_rate_limit() -> None:
    payload = _load("rate_limit.json")

    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, json=payload)
    )
    with GitHubClient(_config(), client=httpx.Client(transport=transport, base_url="https://api.github.com")) as gh:
        status = gh.get_rate_limit()

    assert status.limit == 60
    assert status.remaining == 59
    assert status.reset_epoch == 1700000000


def test_authorization_header_sent_when_token_configured() -> None:
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["authorization"] = request.headers.get("Authorization", "")
        return httpx.Response(200, json=_load("rate_limit.json"))

    transport = httpx.MockTransport(handler)
    with GitHubClient(_config(), client=httpx.Client(transport=transport, base_url="https://api.github.com")) as gh:
        gh.get_rate_limit()

    assert seen["authorization"] == "Bearer test-token"
