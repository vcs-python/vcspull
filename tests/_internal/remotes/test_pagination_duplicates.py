"""Regression tests for pagination duplicate bug.

The pagination duplicate bug occurs when client-side filtering (excluding forks/archived
repos) causes the per_page/limit parameter to vary between API pages. This causes offset
misalignment because:

1. Page 1: per_page=10, returns items 0-9
2. Client-side filtering removes some items, count becomes less than per_page
3. Page 2: per_page=5 (recalculated), API interprets as items 5-9 instead of 10-14
4. Result: Items 5-9 appear twice (duplicates)

The fix is to always use a consistent per_page value across all pagination requests.
"""

from __future__ import annotations

import json
import typing as t
import urllib.parse
import urllib.request

import pytest

from vcspull._internal.remotes.base import ImportMode, ImportOptions
from vcspull._internal.remotes.gitea import (
    DEFAULT_PER_PAGE as GITEA_DEFAULT_PER_PAGE,
    GiteaImporter,
)
from vcspull._internal.remotes.github import (
    DEFAULT_PER_PAGE as GITHUB_DEFAULT_PER_PAGE,
    GitHubImporter,
)


def _make_github_repo(
    name: str,
    *,
    fork: bool = False,
    archived: bool = False,
) -> dict[str, t.Any]:
    """Create a GitHub API repo response object."""
    return {
        "name": name,
        "clone_url": f"https://github.com/testuser/{name}.git",
        "html_url": f"https://github.com/testuser/{name}",
        "description": f"Repo {name}",
        "language": "Python",
        "topics": [],
        "stargazers_count": 10,
        "fork": fork,
        "archived": archived,
        "default_branch": "main",
        "owner": {"login": "testuser"},
    }


def _make_gitea_repo(
    name: str,
    *,
    fork: bool = False,
    archived: bool = False,
) -> dict[str, t.Any]:
    """Create a Gitea API repo response object."""
    return {
        "name": name,
        "clone_url": f"https://codeberg.org/testuser/{name}.git",
        "html_url": f"https://codeberg.org/testuser/{name}",
        "description": f"Repo {name}",
        "language": "Python",
        "topics": [],
        "stars_count": 10,
        "fork": fork,
        "archived": archived,
        "default_branch": "main",
        "owner": {"login": "testuser"},
    }


class MockHTTPResponse:
    """Mock HTTP response for testing."""

    def __init__(
        self,
        body: bytes,
        headers: dict[str, str] | None = None,
        status: int = 200,
    ) -> None:
        """Initialize mock response."""
        self._body = body
        self._headers = headers or {}
        self.status = status
        self.code = status

    def read(self) -> bytes:
        """Return response body."""
        return self._body

    def getheaders(self) -> list[tuple[str, str]]:
        """Return response headers as list of tuples."""
        return list(self._headers.items())

    def __enter__(self) -> MockHTTPResponse:
        """Context manager entry."""
        return self

    def __exit__(self, *args: t.Any) -> None:
        """Context manager exit."""
        pass


@pytest.mark.xfail(
    reason="Pagination uses inconsistent per_page when client-side filtering is active"
)
def test_github_pagination_consistent_per_page(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that GitHub pagination uses consistent per_page across all requests.

    When client-side filtering removes items, the per_page parameter should NOT
    be recalculated based on remaining count - it should stay constant to maintain
    proper pagination offsets.
    """
    captured_requests: list[urllib.request.Request] = []

    # Create repos: mix of regular and forked
    page1_repos = [
        _make_github_repo("repo1"),
        _make_github_repo("repo2"),
        _make_github_repo("fork1", fork=True),
        _make_github_repo("fork2", fork=True),
        _make_github_repo("fork3", fork=True),
    ]

    page2_repos = [
        _make_github_repo("repo3"),
        _make_github_repo("repo4"),
        _make_github_repo("repo5"),
    ]

    responses = [
        (
            json.dumps(page1_repos).encode(),
            {"x-ratelimit-remaining": "100", "x-ratelimit-limit": "60"},
            200,
        ),
        (
            json.dumps(page2_repos).encode(),
            {"x-ratelimit-remaining": "99", "x-ratelimit-limit": "60"},
            200,
        ),
    ]
    call_count = 0

    def urlopen_capture(
        request: urllib.request.Request,
        timeout: int | None = None,
    ) -> MockHTTPResponse:
        nonlocal call_count
        captured_requests.append(request)
        body, headers, status = responses[call_count % len(responses)]
        call_count += 1
        return MockHTTPResponse(body, headers, status)

    monkeypatch.setattr("urllib.request.urlopen", urlopen_capture)

    importer = GitHubImporter()
    options = ImportOptions(
        mode=ImportMode.USER,
        target="testuser",
        limit=5,
        include_forks=False,  # Filter out forks client-side
    )
    list(importer.fetch_repos(options))

    # Extract per_page values from all requests
    per_page_values = []
    for req in captured_requests:
        parsed = urllib.parse.urlparse(req.full_url)
        params = urllib.parse.parse_qs(parsed.query)
        if "per_page" in params:
            per_page_values.append(int(params["per_page"][0]))

    # All per_page values should be identical (consistent pagination)
    assert len(per_page_values) >= 2, "Expected at least 2 API requests"
    assert all(v == GITHUB_DEFAULT_PER_PAGE for v in per_page_values), (
        f"Expected all per_page values to be {GITHUB_DEFAULT_PER_PAGE}, "
        f"got: {per_page_values}"
    )


@pytest.mark.xfail(
    reason="Pagination uses inconsistent limit when client-side filtering is active"
)
def test_gitea_pagination_consistent_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that Gitea pagination uses consistent limit across all requests.

    When client-side filtering removes items, the limit parameter should NOT
    be recalculated based on remaining count - it should stay constant to maintain
    proper pagination offsets.
    """
    captured_requests: list[urllib.request.Request] = []

    # Create repos: mix of regular and forked
    page1_repos = [
        _make_gitea_repo("repo1"),
        _make_gitea_repo("repo2"),
        _make_gitea_repo("fork1", fork=True),
        _make_gitea_repo("fork2", fork=True),
        _make_gitea_repo("fork3", fork=True),
    ]

    page2_repos = [
        _make_gitea_repo("repo3"),
        _make_gitea_repo("repo4"),
        _make_gitea_repo("repo5"),
    ]

    responses: list[tuple[bytes, dict[str, str], int]] = [
        (json.dumps(page1_repos).encode(), {}, 200),
        (json.dumps(page2_repos).encode(), {}, 200),
    ]
    call_count = 0

    def urlopen_capture(
        request: urllib.request.Request,
        timeout: int | None = None,
    ) -> MockHTTPResponse:
        nonlocal call_count
        captured_requests.append(request)
        body, headers, status = responses[call_count % len(responses)]
        call_count += 1
        return MockHTTPResponse(body, headers, status)

    monkeypatch.setattr("urllib.request.urlopen", urlopen_capture)

    importer = GiteaImporter(base_url="https://codeberg.org")
    options = ImportOptions(
        mode=ImportMode.USER,
        target="testuser",
        limit=5,
        include_forks=False,  # Filter out forks client-side
    )
    list(importer.fetch_repos(options))

    # Extract limit values from all requests
    limit_values = []
    for req in captured_requests:
        parsed = urllib.parse.urlparse(req.full_url)
        params = urllib.parse.parse_qs(parsed.query)
        if "limit" in params:
            limit_values.append(int(params["limit"][0]))

    # All limit values should be identical (consistent pagination)
    assert len(limit_values) >= 2, "Expected at least 2 API requests"
    assert all(v == GITEA_DEFAULT_PER_PAGE for v in limit_values), (
        f"Expected all limit values to be {GITEA_DEFAULT_PER_PAGE}, got: {limit_values}"
    )
