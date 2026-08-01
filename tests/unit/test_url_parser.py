"""Unit tests for GitHub URL parsing."""

import pytest

from repolens.exceptions import InvalidURLError
from repolens.github.url_parser import ParsedRepo, parse_github_url


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        (
            "https://github.com/pallets/flask",
            ParsedRepo(owner="pallets", repo="flask", ref=None),
        ),
        (
            "github.com/pallets/flask",
            ParsedRepo(owner="pallets", repo="flask", ref=None),
        ),
        (
            "https://github.com/pallets/flask/",
            ParsedRepo(owner="pallets", repo="flask", ref=None),
        ),
        (
            "https://github.com/pallets/flask.git",
            ParsedRepo(owner="pallets", repo="flask", ref=None),
        ),
        (
            "https://github.com/pallets/flask/tree/main",
            ParsedRepo(owner="pallets", repo="flask", ref="main"),
        ),
        (
            "https://github.com/pallets/flask/tree/main/src",
            ParsedRepo(owner="pallets", repo="flask", ref="main"),
        ),
        (
            "https://github.com/pallets/flask/blob/main/README.md",
            ParsedRepo(owner="pallets", repo="flask", ref="main"),
        ),
        (
            "https://www.github.com/axios/axios",
            ParsedRepo(owner="axios", repo="axios", ref=None),
        ),
    ],
)
def test_parse_valid_urls(url: str, expected: ParsedRepo) -> None:
    assert parse_github_url(url) == expected


@pytest.mark.parametrize(
    "url",
    [
        "",
        "   ",
        "https://gitlab.com/owner/repo",
        "https://github.com/owner",
        "https://github.com/owner/repo/issues",
        "https://github.com/owner/repo/pulls",
        "https://example.com/owner/repo",
        "not-a-url",
    ],
)
def test_parse_invalid_urls(url: str) -> None:
    with pytest.raises(InvalidURLError):
        parse_github_url(url)


def test_invalid_owner_raises_clear_message() -> None:
    with pytest.raises(InvalidURLError, match="Invalid GitHub owner"):
        parse_github_url("https://github.com/-bad/repo")
