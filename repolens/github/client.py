"""GitHub REST API client."""

from __future__ import annotations

import base64
import logging
from dataclasses import dataclass
from typing import Any

import httpx

from repolens.config import Config
from repolens.exceptions import NetworkError
from repolens.github.rate_limit import execute_with_retry, raise_for_response

logger = logging.getLogger(__name__)

API_BASE = "https://api.github.com"


@dataclass(frozen=True)
class RepoMetadata:
    """Repository metadata from GitHub."""

    owner: str
    name: str
    description: str | None
    default_branch: str
    stars: int
    primary_language: str | None
    license: str | None
    size_kb: int


@dataclass(frozen=True)
class TreeEntry:
    """Single entry in a GitHub tree."""

    path: str
    type: str
    size: int | None = None


@dataclass(frozen=True)
class TreeResult:
    """Result of a recursive tree fetch, possibly partial."""

    entries: list[TreeEntry]
    truncated: bool
    partial: bool = False
    partial_reason: str | None = None


@dataclass(frozen=True)
class RateLimitStatus:
    """GitHub rate limit snapshot."""

    limit: int
    remaining: int
    reset_epoch: int


class GitHubClient:
    """Wrapper around GitHub REST API with retry and rate-limit handling."""

    def __init__(
        self,
        config: Config,
        *,
        client: httpx.Client | None = None,
    ) -> None:
        self._config = config
        self._headers = self._default_headers()
        self._owns_client = client is None
        self._client = client or httpx.Client(
            base_url=API_BASE,
            timeout=config.request_timeout,
            headers=self._headers,
        )

    def _default_headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self._config.github_token:
            headers["Authorization"] = f"Bearer {self._config.github_token}"
        return headers

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> GitHubClient:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def _request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        request_headers = {**self._headers, **kwargs.pop("headers", {})}

        def do_request() -> httpx.Response:
            return self._client.request(method, url, headers=request_headers, **kwargs)

        response = execute_with_retry(
            do_request,
            max_retries=self._config.max_retries,
        )
        raise_for_response(response)
        return response

    def get_rate_limit(self) -> RateLimitStatus:
        """Fetch current GitHub API rate limit status."""
        response = self._request("GET", "/rate_limit")
        core = response.json()["resources"]["core"]
        return RateLimitStatus(
            limit=core["limit"],
            remaining=core["remaining"],
            reset_epoch=core["reset"],
        )

    def get_repo_metadata(self, owner: str, repo: str) -> RepoMetadata:
        """Fetch repository metadata."""
        response = self._request("GET", f"/repos/{owner}/{repo}")
        data = response.json()
        license_info = data.get("license")
        return RepoMetadata(
            owner=data["owner"]["login"],
            name=data["name"],
            description=data.get("description"),
            default_branch=data["default_branch"],
            stars=data["stargazers_count"],
            primary_language=data.get("language"),
            license=license_info["spdx_id"] if license_info else None,
            size_kb=data["size"],
        )

    def get_tree(self, owner: str, repo: str, ref: str) -> TreeResult:
        """Fetch recursive repository tree for a ref.

        If GitHub returns truncated=true, falls back to enumerating the top
        two directory levels via the contents API.
        """
        response = self._request(
            "GET",
            f"/repos/{owner}/{repo}/git/trees/{ref}",
            params={"recursive": "1"},
        )
        data = response.json()
        if data.get("truncated"):
            logger.warning(
                "Tree for %s/%s@%s truncated; using partial top-level enumeration",
                owner,
                repo,
                ref,
            )
            return self._partial_tree(owner, repo, ref)

        entries = [
            TreeEntry(
                path=item["path"],
                type=item["type"],
                size=item.get("size"),
            )
            for item in data.get("tree", [])
            if item["type"] in ("blob", "tree")
        ]
        return TreeResult(entries=entries, truncated=False)

    def _partial_tree(self, owner: str, repo: str, ref: str) -> TreeResult:
        """Enumerate repository contents up to two levels deep."""
        entries: list[TreeEntry] = []
        self._collect_contents(owner, repo, "", ref, depth=0, entries=entries)
        return TreeResult(
            entries=entries,
            truncated=True,
            partial=True,
            partial_reason=(
                "Repository tree exceeded GitHub's recursive limit. "
                "Only the top two directory levels were enumerated."
            ),
        )

    def _collect_contents(
        self,
        owner: str,
        repo: str,
        path: str,
        ref: str,
        *,
        depth: int,
        entries: list[TreeEntry],
    ) -> None:
        if depth > 2:
            return

        url = f"/repos/{owner}/{repo}/contents/{path}" if path else f"/repos/{owner}/{repo}/contents"
        response = self._request("GET", url, params={"ref": ref})
        items = response.json()
        if isinstance(items, dict):
            items = [items]

        for item in items:
            item_path = item["path"]
            item_type = "tree" if item["type"] == "dir" else "blob"
            entries.append(
                TreeEntry(
                    path=item_path,
                    type=item_type,
                    size=item.get("size"),
                )
            )
            if item["type"] == "dir" and depth < 2:
                self._collect_contents(
                    owner,
                    repo,
                    item_path,
                    ref,
                    depth=depth + 1,
                    entries=entries,
                )

    def get_file_content(self, owner: str, repo: str, path: str, ref: str) -> bytes:
        """Fetch raw file bytes from the repository."""
        response = self._request(
            "GET",
            f"/repos/{owner}/{repo}/contents/{path}",
            params={"ref": ref},
        )
        data = response.json()
        if isinstance(data, list):
            raise NetworkError(f"Expected file at {path!r}, found a directory.")

        encoding = data.get("encoding")
        content = data.get("content")
        if encoding != "base64" or not content:
            raise NetworkError(f"Unable to decode content for {path!r}.")

        try:
            return base64.b64decode(content, validate=True)
        except (ValueError, TypeError) as exc:
            raise NetworkError(f"Unable to decode content for {path!r}.") from exc

    def decode_text_content(self, raw: bytes) -> str:
        """Decode bytes as UTF-8 text, falling back to latin-1."""
        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError:
            return raw.decode("latin-1", errors="replace")
