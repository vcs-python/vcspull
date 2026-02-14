"""Shared fixtures for remotes tests."""

from __future__ import annotations

import json
import typing as t
import urllib.error

import pytest


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


@pytest.fixture
def mock_urlopen(monkeypatch: pytest.MonkeyPatch) -> t.Callable[..., None]:
    """Create factory fixture to mock urllib.request.urlopen responses.

    Parameters
    ----------
    monkeypatch : pytest.MonkeyPatch
        Pytest monkeypatch fixture

    Returns
    -------
    Callable
        Function to set up mock responses
    """

    def _mock(
        responses: list[tuple[bytes, dict[str, str], int]] | None = None,
        error: urllib.error.HTTPError | None = None,
    ) -> None:
        """Set up mock responses.

        Parameters
        ----------
        responses : list[tuple[bytes, dict[str, str], int]] | None
            List of (body, headers, status) tuples for sequential responses
        error : urllib.error.HTTPError | None
            Error to raise instead of returning response
        """
        call_count = 0
        responses = responses or []

        def urlopen_side_effect(
            request: t.Any,
            timeout: int | None = None,
        ) -> MockHTTPResponse:
            nonlocal call_count
            if error:
                raise error
            if not responses:
                return MockHTTPResponse(b"[]", {}, 200)
            body, headers, status = responses[call_count % len(responses)]
            call_count += 1
            return MockHTTPResponse(body, headers, status)

        monkeypatch.setattr("urllib.request.urlopen", urlopen_side_effect)

    return _mock


@pytest.fixture
def github_user_repos_response() -> bytes:
    """Return standard GitHub user repos API response."""
    return json.dumps(
        [
            {
                "name": "repo1",
                "clone_url": "https://github.com/testuser/repo1.git",
                "ssh_url": "git@github.com:testuser/repo1.git",
                "html_url": "https://github.com/testuser/repo1",
                "description": "Test repo 1",
                "language": "Python",
                "topics": ["cli", "tool"],
                "stargazers_count": 100,
                "fork": False,
                "archived": False,
                "default_branch": "main",
                "owner": {"login": "testuser"},
            },
            {
                "name": "repo2",
                "clone_url": "https://github.com/testuser/repo2.git",
                "ssh_url": "git@github.com:testuser/repo2.git",
                "html_url": "https://github.com/testuser/repo2",
                "description": "Test repo 2",
                "language": "JavaScript",
                "topics": [],
                "stargazers_count": 50,
                "fork": False,
                "archived": False,
                "default_branch": "main",
                "owner": {"login": "testuser"},
            },
        ]
    ).encode()


@pytest.fixture
def github_forked_repo_response() -> bytes:
    """GitHub repo that is a fork."""
    return json.dumps(
        [
            {
                "name": "forked-repo",
                "clone_url": "https://github.com/testuser/forked-repo.git",
                "ssh_url": "git@github.com:testuser/forked-repo.git",
                "html_url": "https://github.com/testuser/forked-repo",
                "description": "A forked repo",
                "language": "Python",
                "topics": [],
                "stargazers_count": 10,
                "fork": True,
                "archived": False,
                "default_branch": "main",
                "owner": {"login": "testuser"},
            }
        ]
    ).encode()


@pytest.fixture
def github_archived_repo_response() -> bytes:
    """GitHub repo that is archived."""
    return json.dumps(
        [
            {
                "name": "archived-repo",
                "clone_url": "https://github.com/testuser/archived-repo.git",
                "ssh_url": "git@github.com:testuser/archived-repo.git",
                "html_url": "https://github.com/testuser/archived-repo",
                "description": "An archived repo",
                "language": "Python",
                "topics": [],
                "stargazers_count": 5,
                "fork": False,
                "archived": True,
                "default_branch": "main",
                "owner": {"login": "testuser"},
            }
        ]
    ).encode()


@pytest.fixture
def gitlab_user_projects_response() -> bytes:
    """Return standard GitLab user projects API response."""
    return json.dumps(
        [
            {
                "path": "project1",
                "name": "Project 1",
                "http_url_to_repo": "https://gitlab.com/testuser/project1.git",
                "ssh_url_to_repo": "git@gitlab.com:testuser/project1.git",
                "web_url": "https://gitlab.com/testuser/project1",
                "description": "Test project 1",
                "topics": ["python"],
                "star_count": 20,
                "archived": False,
                "default_branch": "main",
                "namespace": {"path": "testuser", "full_path": "testuser"},
            },
        ]
    ).encode()


@pytest.fixture
def gitea_user_repos_response() -> bytes:
    """Return standard Gitea user repos API response."""
    return json.dumps(
        [
            {
                "name": "repo1",
                "clone_url": "https://codeberg.org/testuser/repo1.git",
                "ssh_url": "git@codeberg.org:testuser/repo1.git",
                "html_url": "https://codeberg.org/testuser/repo1",
                "description": "Test repo 1",
                "language": "Python",
                "topics": [],
                "stars_count": 15,
                "fork": False,
                "archived": False,
                "default_branch": "main",
                "owner": {"login": "testuser"},
            },
        ]
    ).encode()


@pytest.fixture
def gitea_search_response() -> bytes:
    """Gitea search API response with wrapped data."""
    return json.dumps(
        {
            "ok": True,
            "data": [
                {
                    "name": "search-result",
                    "clone_url": "https://codeberg.org/user/search-result.git",
                    "ssh_url": "git@codeberg.org:user/search-result.git",
                    "html_url": "https://codeberg.org/user/search-result",
                    "description": "Found by search",
                    "language": "Go",
                    "topics": ["search"],
                    "stars_count": 30,
                    "fork": False,
                    "archived": False,
                    "default_branch": "main",
                    "owner": {"login": "user"},
                },
            ],
        }
    ).encode()
