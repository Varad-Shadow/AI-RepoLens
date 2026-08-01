"""Parse and validate GitHub repository URLs into (owner, repo, ref)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import unquote, urlparse

from repolens.exceptions import InvalidURLError

_GITHUB_HOSTS = frozenset({"github.com", "www.github.com"})
_OWNER_REPO_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?$")
_NON_REPO_SEGMENTS = frozenset(
    {
        "issues",
        "pulls",
        "pull",
        "wiki",
        "settings",
        "actions",
        "projects",
        "security",
        "releases",
        "packages",
        "discussions",
        "graphs",
        "commits",
        "compare",
        "archive",
    }
)


@dataclass(frozen=True)
class ParsedRepo:
    """Normalized GitHub repository reference."""

    owner: str
    repo: str
    ref: str | None = None


def _validate_segment(name: str, label: str) -> None:
    if not name or not _OWNER_REPO_RE.match(name):
        raise InvalidURLError(
            f"Invalid GitHub {label} {name!r}. "
            "Expected a URL like https://github.com/owner/repo"
        )


def parse_github_url(url: str) -> ParsedRepo:
    """Validate and normalize a public GitHub repository URL.

    Supported forms:
    - https://github.com/owner/repo
    - https://github.com/owner/repo/tree/branch
    - https://github.com/owner/repo/blob/branch/path/to/file
    - github.com/owner/repo (scheme optional)
    """
    raw = url.strip()
    if not raw:
        raise InvalidURLError(
            "Repository URL cannot be empty. "
            "Example: https://github.com/owner/repo"
        )

    normalized = raw if "://" in raw else f"https://{raw}"
    parsed = urlparse(normalized)

    host = parsed.netloc.lower().split("@")[-1].split(":")[0]
    if host not in _GITHUB_HOSTS:
        raise InvalidURLError(
            f"Unsupported host {host!r}. Only github.com URLs are supported."
        )

    segments = [unquote(part) for part in parsed.path.strip("/").split("/") if part]
    if len(segments) < 2:
        raise InvalidURLError(
            "Invalid GitHub repository URL. "
            "Expected https://github.com/owner/repo"
        )

    owner, repo = segments[0], segments[1]
    if repo.endswith(".git"):
        repo = repo[:-4]

    _validate_segment(owner, "owner")
    _validate_segment(repo, "repository name")

    if len(segments) > 2 and segments[2] in _NON_REPO_SEGMENTS:
        raise InvalidURLError(
            f"URL points to a GitHub {segments[2]} page, not a repository root. "
            "Use https://github.com/owner/repo"
        )

    ref: str | None = None
    if len(segments) >= 4 and segments[2] in ("tree", "blob"):
        ref = segments[3]
        if not ref:
            raise InvalidURLError(
                "Missing branch or tag in GitHub URL. "
                "Example: https://github.com/owner/repo/tree/main"
            )

    return ParsedRepo(owner=owner, repo=repo, ref=ref)
