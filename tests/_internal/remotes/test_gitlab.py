"""Tests for vcspull._internal.remotes.gitlab module."""

from __future__ import annotations

import json
import typing as t
import urllib.parse
import urllib.request

import pytest

from tests._internal.remotes.conftest import MockHTTPResponse
from vcspull._internal.remotes.base import ImportMode, ImportOptions
from vcspull._internal.remotes.gitlab import GitLabImporter


def test_gitlab_fetch_user(
    mock_urlopen: t.Callable[..., None],
    gitlab_user_projects_response: bytes,
) -> None:
    """Test GitLab user project fetching."""
    mock_urlopen([(gitlab_user_projects_response, {}, 200)])
    importer = GitLabImporter()
    options = ImportOptions(mode=ImportMode.USER, target="testuser")
    repos = list(importer.fetch_repos(options))
    assert len(repos) == 1
    assert repos[0].name == "project1"
    assert repos[0].owner == "testuser"


def test_gitlab_fetch_group(
    mock_urlopen: t.Callable[..., None],
) -> None:
    """Test GitLab group (org) project fetching."""
    response_json = [
        {
            "path": "group-project",
            "name": "Group Project",
            "http_url_to_repo": "https://gitlab.com/testgroup/group-project.git",
            "ssh_url_to_repo": "git@gitlab.com:testgroup/group-project.git",
            "web_url": "https://gitlab.com/testgroup/group-project",
            "description": "Group project",
            "topics": [],
            "star_count": 50,
            "archived": False,
            "default_branch": "main",
            "namespace": {"path": "testgroup"},
        }
    ]
    mock_urlopen([(json.dumps(response_json).encode(), {}, 200)])
    importer = GitLabImporter()
    options = ImportOptions(mode=ImportMode.ORG, target="testgroup")
    repos = list(importer.fetch_repos(options))
    assert len(repos) == 1
    assert repos[0].name == "group-project"


def test_gitlab_owner_uses_namespace_full_path(
    mock_urlopen: t.Callable[..., None],
) -> None:
    """Test GitLab owner preserves full namespace path when available."""
    response_json = [
        {
            "path": "group-project",
            "name": "Group Project",
            "path_with_namespace": (
                "vcs-python-group-test/vcs-python-subgroup-test/group-project"
            ),
            "http_url_to_repo": (
                "https://gitlab.com/vcs-python-group-test/"
                "vcs-python-subgroup-test/group-project.git"
            ),
            "ssh_url_to_repo": (
                "git@gitlab.com:vcs-python-group-test/"
                "vcs-python-subgroup-test/group-project.git"
            ),
            "web_url": (
                "https://gitlab.com/vcs-python-group-test/"
                "vcs-python-subgroup-test/group-project"
            ),
            "description": "Group project",
            "topics": [],
            "star_count": 50,
            "archived": False,
            "default_branch": "main",
            "namespace": {
                "path": "vcs-python-subgroup-test",
                "full_path": "vcs-python-group-test/vcs-python-subgroup-test",
            },
        }
    ]
    mock_urlopen([(json.dumps(response_json).encode(), {}, 200)])
    importer = GitLabImporter()
    options = ImportOptions(mode=ImportMode.ORG, target="vcs-python-group-test")
    repos = list(importer.fetch_repos(options))
    assert len(repos) == 1
    assert repos[0].owner == "vcs-python-group-test/vcs-python-subgroup-test"


def test_gitlab_owner_falls_back_to_path_with_namespace(
    mock_urlopen: t.Callable[..., None],
) -> None:
    """Test owner derivation uses path_with_namespace when full_path is missing."""
    response_json = [
        {
            "path": "group-project",
            "name": "Group Project",
            "path_with_namespace": (
                "vcs-python-group-test/vcs-python-subgroup-test/group-project"
            ),
            "http_url_to_repo": (
                "https://gitlab.com/vcs-python-group-test/"
                "vcs-python-subgroup-test/group-project.git"
            ),
            "ssh_url_to_repo": (
                "git@gitlab.com:vcs-python-group-test/"
                "vcs-python-subgroup-test/group-project.git"
            ),
            "web_url": (
                "https://gitlab.com/vcs-python-group-test/"
                "vcs-python-subgroup-test/group-project"
            ),
            "description": "Group project",
            "topics": [],
            "star_count": 50,
            "archived": False,
            "default_branch": "main",
            "namespace": {
                "path": "vcs-python-subgroup-test",
            },
        }
    ]
    mock_urlopen([(json.dumps(response_json).encode(), {}, 200)])
    importer = GitLabImporter()
    options = ImportOptions(mode=ImportMode.ORG, target="vcs-python-group-test")
    repos = list(importer.fetch_repos(options))
    assert len(repos) == 1
    assert repos[0].owner == "vcs-python-group-test/vcs-python-subgroup-test"


def test_gitlab_search_requires_auth(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test GitLab search raises error without authentication."""
    from vcspull._internal.remotes.base import AuthenticationError

    # Clear environment variables that could provide a token
    monkeypatch.delenv("GITLAB_TOKEN", raising=False)
    monkeypatch.delenv("GL_TOKEN", raising=False)
    importer = GitLabImporter(token=None)
    options = ImportOptions(mode=ImportMode.SEARCH, target="test")
    with pytest.raises(AuthenticationError, match="requires authentication"):
        list(importer.fetch_repos(options))


def test_gitlab_search_with_auth(
    mock_urlopen: t.Callable[..., None],
) -> None:
    """Test GitLab search works with authentication."""
    search_response = [
        {
            "path": "search-result",
            "name": "Search Result",
            "http_url_to_repo": "https://gitlab.com/user/search-result.git",
            "ssh_url_to_repo": "git@gitlab.com:user/search-result.git",
            "web_url": "https://gitlab.com/user/search-result",
            "description": "Found",
            "topics": [],
            "star_count": 100,
            "archived": False,
            "default_branch": "main",
            "namespace": {"path": "user"},
        }
    ]
    mock_urlopen([(json.dumps(search_response).encode(), {}, 200)])
    importer = GitLabImporter(token="test-token")
    options = ImportOptions(mode=ImportMode.SEARCH, target="test")
    repos = list(importer.fetch_repos(options))
    assert len(repos) == 1
    assert repos[0].name == "search-result"


def test_gitlab_importer_is_authenticated_without_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test is_authenticated returns False without token."""
    # Clear environment variables that could provide a token
    monkeypatch.delenv("GITLAB_TOKEN", raising=False)
    monkeypatch.delenv("GL_TOKEN", raising=False)
    importer = GitLabImporter(token=None)
    assert importer.is_authenticated is False


def test_gitlab_importer_is_authenticated_with_token() -> None:
    """Test is_authenticated returns True with token."""
    importer = GitLabImporter(token="test-token")
    assert importer.is_authenticated is True


def test_gitlab_importer_service_name() -> None:
    """Test service_name property."""
    importer = GitLabImporter()
    assert importer.service_name == "GitLab"


def test_gitlab_handles_forked_project(
    mock_urlopen: t.Callable[..., None],
) -> None:
    """Test GitLab correctly identifies forked projects."""
    response_json = [
        {
            "path": "forked-project",
            "name": "Forked Project",
            "http_url_to_repo": "https://gitlab.com/user/forked-project.git",
            "ssh_url_to_repo": "git@gitlab.com:user/forked-project.git",
            "web_url": "https://gitlab.com/user/forked-project",
            "description": "A fork",
            "topics": [],
            "star_count": 5,
            "archived": False,
            "default_branch": "main",
            "namespace": {"path": "user"},
            "forked_from_project": {"id": 123},
        }
    ]
    mock_urlopen([(json.dumps(response_json).encode(), {}, 200)])
    importer = GitLabImporter()
    options = ImportOptions(mode=ImportMode.USER, target="user", include_forks=False)
    repos = list(importer.fetch_repos(options))
    # Fork should be filtered out
    assert len(repos) == 0


def test_gitlab_uses_path_not_name(
    mock_urlopen: t.Callable[..., None],
) -> None:
    """Test GitLab uses 'path' for filesystem-safe names, not 'name'."""
    response_json = [
        {
            "path": "my-project",
            "name": "My Project With Spaces",  # This should NOT be used
            "http_url_to_repo": "https://gitlab.com/user/my-project.git",
            "ssh_url_to_repo": "git@gitlab.com:user/my-project.git",
            "web_url": "https://gitlab.com/user/my-project",
            "description": "Project with spaces in name",
            "topics": [],
            "star_count": 10,
            "archived": False,
            "default_branch": "main",
            "namespace": {"path": "user"},
        }
    ]
    mock_urlopen([(json.dumps(response_json).encode(), {}, 200)])
    importer = GitLabImporter()
    options = ImportOptions(mode=ImportMode.USER, target="user")
    repos = list(importer.fetch_repos(options))
    assert len(repos) == 1
    assert repos[0].name == "my-project"  # Uses 'path', not 'name'


def test_gitlab_subgroup_url_encoding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that GitLab subgroups are URL-encoded correctly.

    Subgroups use slash notation (e.g., parent/child) which must be
    URL-encoded as %2F in API requests.
    """
    captured_urls: list[str] = []

    response_json = [
        {
            "path": "subgroup-project",
            "name": "Subgroup Project",
            "http_url_to_repo": "https://gitlab.com/parent/child/subgroup-project.git",
            "ssh_url_to_repo": "git@gitlab.com:parent/child/subgroup-project.git",
            "web_url": "https://gitlab.com/parent/child/subgroup-project",
            "description": "Project in subgroup",
            "topics": [],
            "star_count": 10,
            "archived": False,
            "default_branch": "main",
            "namespace": {"path": "child", "full_path": "parent/child"},
        }
    ]

    def urlopen_capture(
        request: urllib.request.Request,
        timeout: int | None = None,
    ) -> MockHTTPResponse:
        captured_urls.append(request.full_url)
        return MockHTTPResponse(json.dumps(response_json).encode())

    # Mock urlopen: capture request URLs to verify subgroup path encoding
    monkeypatch.setattr("urllib.request.urlopen", urlopen_capture)

    importer = GitLabImporter()
    options = ImportOptions(mode=ImportMode.ORG, target="parent/child")
    repos = list(importer.fetch_repos(options))

    # Verify the URL was encoded correctly
    assert len(captured_urls) == 1
    assert "parent%2Fchild" in captured_urls[0], (
        f"Expected URL-encoded subgroup path 'parent%2Fchild', got: {captured_urls[0]}"
    )
    assert "/groups/parent%2Fchild/projects" in captured_urls[0]

    # Verify repos were returned
    assert len(repos) == 1
    assert repos[0].name == "subgroup-project"
    assert repos[0].owner == "parent/child"


def test_gitlab_deeply_nested_subgroup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that deeply nested subgroups (multiple slashes) work correctly."""
    captured_urls: list[str] = []

    response_json = [
        {
            "path": "deep-project",
            "name": "Deep Project",
            "http_url_to_repo": "https://gitlab.com/a/b/c/d/deep-project.git",
            "ssh_url_to_repo": "git@gitlab.com:a/b/c/d/deep-project.git",
            "web_url": "https://gitlab.com/a/b/c/d/deep-project",
            "description": "Deeply nested project",
            "topics": [],
            "star_count": 5,
            "archived": False,
            "default_branch": "main",
            "namespace": {"path": "d", "full_path": "a/b/c/d"},
        }
    ]

    def urlopen_capture(
        request: urllib.request.Request,
        timeout: int | None = None,
    ) -> MockHTTPResponse:
        captured_urls.append(request.full_url)
        return MockHTTPResponse(json.dumps(response_json).encode())

    # Mock urlopen: capture request URLs to verify deep nesting path encoding
    monkeypatch.setattr("urllib.request.urlopen", urlopen_capture)

    importer = GitLabImporter()
    # Test with 4 levels of nesting: a/b/c/d
    options = ImportOptions(mode=ImportMode.ORG, target="a/b/c/d")
    repos = list(importer.fetch_repos(options))

    # Verify URL encoding - each slash should become %2F
    assert len(captured_urls) == 1
    assert "a%2Fb%2Fc%2Fd" in captured_urls[0], (
        f"Expected URL-encoded path 'a%2Fb%2Fc%2Fd', got: {captured_urls[0]}"
    )

    assert len(repos) == 1
    assert repos[0].name == "deep-project"
    assert repos[0].owner == "a/b/c/d"


def test_gitlab_handles_null_topics(
    mock_urlopen: t.Callable[..., None],
) -> None:
    """Test GitLab handles null topics in API response.

    GitLab API can return "topics": null instead of an empty array.
    dict.get("topics", []) returns None when the key exists with null value,
    causing tuple(None) to crash with TypeError.
    """
    response_json = [
        {
            "path": "null-topics-project",
            "name": "Null Topics Project",
            "http_url_to_repo": "https://gitlab.com/user/null-topics-project.git",
            "ssh_url_to_repo": "git@gitlab.com:user/null-topics-project.git",
            "web_url": "https://gitlab.com/user/null-topics-project",
            "description": "Project with null topics",
            "topics": None,
            "star_count": 10,
            "archived": False,
            "default_branch": "main",
            "namespace": {"path": "user"},
        }
    ]
    mock_urlopen([(json.dumps(response_json).encode(), {}, 200)])
    importer = GitLabImporter()
    options = ImportOptions(mode=ImportMode.USER, target="user")
    repos = list(importer.fetch_repos(options))
    assert len(repos) == 1
    assert repos[0].topics == ()


def test_gitlab_archived_param_omitted_when_including(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that archived param is omitted when include_archived=True.

    GitLab API: archived=true returns ONLY archived projects.
    Omitting the param returns all projects (archived + non-archived).
    """
    captured_urls: list[str] = []

    response_json = [
        {
            "path": "project1",
            "name": "Project 1",
            "http_url_to_repo": "https://gitlab.com/user/project1.git",
            "ssh_url_to_repo": "git@gitlab.com:user/project1.git",
            "web_url": "https://gitlab.com/user/project1",
            "description": "Active project",
            "topics": [],
            "star_count": 10,
            "archived": False,
            "default_branch": "main",
            "namespace": {"path": "user"},
        }
    ]

    def urlopen_capture(
        request: urllib.request.Request,
        timeout: int | None = None,
    ) -> MockHTTPResponse:
        captured_urls.append(request.full_url)
        return MockHTTPResponse(json.dumps(response_json).encode())

    # Mock urlopen: capture request URLs to verify archived param is omitted
    monkeypatch.setattr("urllib.request.urlopen", urlopen_capture)

    importer = GitLabImporter()
    options = ImportOptions(mode=ImportMode.USER, target="user", include_archived=True)
    list(importer.fetch_repos(options))

    assert len(captured_urls) == 1
    # archived param should NOT be in the URL when include_archived=True
    assert "archived=" not in captured_urls[0], (
        f"Expected no 'archived' param in URL, got: {captured_urls[0]}"
    )


def test_gitlab_archived_param_false_when_excluding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that archived=false is set when include_archived=False."""
    captured_urls: list[str] = []

    response_json = [
        {
            "path": "project1",
            "name": "Project 1",
            "http_url_to_repo": "https://gitlab.com/user/project1.git",
            "ssh_url_to_repo": "git@gitlab.com:user/project1.git",
            "web_url": "https://gitlab.com/user/project1",
            "description": "Active project",
            "topics": [],
            "star_count": 10,
            "archived": False,
            "default_branch": "main",
            "namespace": {"path": "user"},
        }
    ]

    def urlopen_capture(
        request: urllib.request.Request,
        timeout: int | None = None,
    ) -> MockHTTPResponse:
        captured_urls.append(request.full_url)
        return MockHTTPResponse(json.dumps(response_json).encode())

    # Mock urlopen: capture request URLs to verify archived=false is included
    monkeypatch.setattr("urllib.request.urlopen", urlopen_capture)

    importer = GitLabImporter()
    options = ImportOptions(mode=ImportMode.USER, target="user", include_archived=False)
    list(importer.fetch_repos(options))

    assert len(captured_urls) == 1
    assert "archived=false" in captured_urls[0], (
        f"Expected 'archived=false' in URL, got: {captured_urls[0]}"
    )


def test_gitlab_search_archived_param_false_when_excluding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that _fetch_search includes archived=false when excluding archived."""
    captured_urls: list[str] = []

    search_response = [
        {
            "path": "search-result",
            "name": "Search Result",
            "http_url_to_repo": "https://gitlab.com/user/search-result.git",
            "ssh_url_to_repo": "git@gitlab.com:user/search-result.git",
            "web_url": "https://gitlab.com/user/search-result",
            "description": "Found",
            "topics": [],
            "star_count": 100,
            "archived": False,
            "default_branch": "main",
            "namespace": {"path": "user"},
        }
    ]

    def urlopen_capture(
        request: urllib.request.Request,
        timeout: int | None = None,
    ) -> MockHTTPResponse:
        captured_urls.append(request.full_url)
        return MockHTTPResponse(json.dumps(search_response).encode())

    # Mock urlopen: capture request URLs to verify search archived=false param
    monkeypatch.setattr("urllib.request.urlopen", urlopen_capture)

    importer = GitLabImporter(token="test-token")
    options = ImportOptions(
        mode=ImportMode.SEARCH, target="test", include_archived=False
    )
    list(importer.fetch_repos(options))

    assert len(captured_urls) == 1
    assert "archived=false" in captured_urls[0], (
        f"Expected 'archived=false' in search URL, got: {captured_urls[0]}"
    )


def test_gitlab_search_archived_param_omitted_when_including(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that _fetch_search omits archived param when including archived."""
    captured_urls: list[str] = []

    search_response = [
        {
            "path": "search-result",
            "name": "Search Result",
            "http_url_to_repo": "https://gitlab.com/user/search-result.git",
            "ssh_url_to_repo": "git@gitlab.com:user/search-result.git",
            "web_url": "https://gitlab.com/user/search-result",
            "description": "Found",
            "topics": [],
            "star_count": 100,
            "archived": False,
            "default_branch": "main",
            "namespace": {"path": "user"},
        }
    ]

    def urlopen_capture(
        request: urllib.request.Request,
        timeout: int | None = None,
    ) -> MockHTTPResponse:
        captured_urls.append(request.full_url)
        return MockHTTPResponse(json.dumps(search_response).encode())

    # Mock urlopen: capture request URLs to verify archived param is omitted in search
    monkeypatch.setattr("urllib.request.urlopen", urlopen_capture)

    importer = GitLabImporter(token="test-token")
    options = ImportOptions(
        mode=ImportMode.SEARCH, target="test", include_archived=True
    )
    list(importer.fetch_repos(options))

    assert len(captured_urls) == 1
    assert "archived=" not in captured_urls[0], (
        f"Expected no 'archived' param in search URL, got: {captured_urls[0]}"
    )


def test_gitlab_parse_repo_null_namespace(
    mock_urlopen: t.Callable[..., None],
) -> None:
    """Test GitLab _parse_repo handles null namespace without crashing.

    Self-hosted GitLab instances may return ``"namespace": null`` for
    system-level projects. The importer must not raise AttributeError.
    """
    response_json = [
        {
            "path": "my-project",
            "name": "my-project",
            "http_url_to_repo": "https://gitlab.example.com/my-project.git",
            "ssh_url_to_repo": "git@gitlab.example.com:my-project.git",
            "web_url": "https://gitlab.example.com/my-project",
            "description": "Orphaned project",
            "star_count": 0,
            "namespace": None,
            "path_with_namespace": "my-project",
        }
    ]
    mock_urlopen([(json.dumps(response_json).encode(), {}, 200)])
    importer = GitLabImporter()
    options = ImportOptions(mode=ImportMode.USER, target="testuser")
    repos = list(importer.fetch_repos(options))
    assert len(repos) == 1
    assert repos[0].name == "my-project"
    assert repos[0].owner == ""


# ---------------------------------------------------------------------------
# Rate limit header logging
# ---------------------------------------------------------------------------


class GitLabLogRateLimitFixture(t.NamedTuple):
    """Fixture for GitLabImporter._log_rate_limit test cases."""

    test_id: str
    headers: dict[str, str]
    expected_log_level: str | None
    expected_message_fragment: str | None


GITLAB_LOG_RATE_LIMIT_FIXTURES: list[GitLabLogRateLimitFixture] = [
    GitLabLogRateLimitFixture(
        test_id="low-remaining",
        headers={"ratelimit-remaining": "5", "ratelimit-limit": "600"},
        expected_log_level="warning",
        expected_message_fragment="rate limit low",
    ),
    GitLabLogRateLimitFixture(
        test_id="sufficient-remaining",
        headers={"ratelimit-remaining": "500", "ratelimit-limit": "600"},
        expected_log_level="debug",
        expected_message_fragment="rate limit",
    ),
    GitLabLogRateLimitFixture(
        test_id="non-numeric-remaining",
        headers={"ratelimit-remaining": "unlimited", "ratelimit-limit": "600"},
        expected_log_level=None,
        expected_message_fragment=None,
    ),
    GitLabLogRateLimitFixture(
        test_id="missing-remaining-header",
        headers={"ratelimit-limit": "600"},
        expected_log_level=None,
        expected_message_fragment=None,
    ),
    GitLabLogRateLimitFixture(
        test_id="missing-both-headers",
        headers={},
        expected_log_level=None,
        expected_message_fragment=None,
    ),
]


@pytest.mark.parametrize(
    list(GitLabLogRateLimitFixture._fields),
    GITLAB_LOG_RATE_LIMIT_FIXTURES,
    ids=[f.test_id for f in GITLAB_LOG_RATE_LIMIT_FIXTURES],
)
def test_gitlab_log_rate_limit(
    test_id: str,
    headers: dict[str, str],
    expected_log_level: str | None,
    expected_message_fragment: str | None,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test _log_rate_limit handles various GitLab header scenarios."""
    import logging

    caplog.set_level(logging.DEBUG)
    importer = GitLabImporter()
    importer._log_rate_limit(headers)
    if expected_message_fragment is not None:
        assert expected_message_fragment in caplog.text.lower()
    else:
        assert "rate limit" not in caplog.text.lower()


# ---------------------------------------------------------------------------
# Truncation warnings
# ---------------------------------------------------------------------------


def _make_gitlab_project(idx: int) -> dict[str, t.Any]:
    """Create a minimal GitLab project API object for testing."""
    return {
        "path": f"project-{idx}",
        "name": f"Project {idx}",
        "http_url_to_repo": f"https://gitlab.com/user/project-{idx}.git",
        "ssh_url_to_repo": f"git@gitlab.com:user/project-{idx}.git",
        "web_url": f"https://gitlab.com/user/project-{idx}",
        "description": f"Project {idx}",
        "topics": [],
        "star_count": 10,
        "archived": False,
        "default_branch": "main",
        "namespace": {"path": "user", "full_path": "user"},
    }


class TruncationWarningFixture(t.NamedTuple):
    """Fixture for GitLab truncation warning test cases."""

    test_id: str
    limit: int
    num_repos_on_server: int  # total repos to simulate
    x_total_header: str | None  # x-total header value, None to omit
    x_next_page_header: str | None  # x-next-page header, None to omit
    expect_warning: bool
    expected_warning_fragment: str | None


TRUNCATION_WARNING_FIXTURES: list[TruncationWarningFixture] = [
    TruncationWarningFixture(
        test_id="truncated-with-x-total",
        limit=2,
        num_repos_on_server=5,
        x_total_header="5",
        x_next_page_header="2",
        expect_warning=True,
        expected_warning_fragment="showing 2 of 5",
    ),
    TruncationWarningFixture(
        test_id="truncated-without-x-total-with-next-page",
        limit=2,
        num_repos_on_server=5,
        x_total_header=None,
        x_next_page_header="2",
        expect_warning=True,
        expected_warning_fragment="more are available",
    ),
    TruncationWarningFixture(
        test_id="not-truncated-all-fetched",
        limit=100,
        num_repos_on_server=3,
        x_total_header="3",
        x_next_page_header=None,
        expect_warning=False,
        expected_warning_fragment=None,
    ),
    TruncationWarningFixture(
        test_id="truncated-no-headers-but-full-page",
        limit=2,
        num_repos_on_server=5,
        x_total_header=None,
        x_next_page_header=None,
        expect_warning=False,  # no headers = no way to warn
        expected_warning_fragment=None,
    ),
]


@pytest.mark.parametrize(
    list(TruncationWarningFixture._fields),
    TRUNCATION_WARNING_FIXTURES,
    ids=[f.test_id for f in TRUNCATION_WARNING_FIXTURES],
)
def test_gitlab_truncation_warning(
    test_id: str,
    limit: int,
    num_repos_on_server: int,
    x_total_header: str | None,
    x_next_page_header: str | None,
    expect_warning: bool,
    expected_warning_fragment: str | None,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test truncation warnings when results exceed --limit."""
    import logging

    caplog.set_level(logging.WARNING)

    repos = [_make_gitlab_project(i) for i in range(num_repos_on_server)]

    # Build response pages with appropriate headers
    page_headers: dict[str, str] = {}
    if x_total_header is not None:
        page_headers["x-total"] = x_total_header
    if x_next_page_header is not None:
        page_headers["x-next-page"] = x_next_page_header

    def urlopen_side_effect(
        request: urllib.request.Request,
        timeout: int | None = None,
    ) -> MockHTTPResponse:
        return MockHTTPResponse(
            json.dumps(repos).encode(),
            page_headers,
            200,
        )

    # Mock urlopen: return all repos in one page with configured headers
    monkeypatch.setattr("urllib.request.urlopen", urlopen_side_effect)

    importer = GitLabImporter()
    options = ImportOptions(mode=ImportMode.USER, target="user", limit=limit)
    list(importer.fetch_repos(options))

    if expect_warning:
        assert expected_warning_fragment is not None
        assert expected_warning_fragment in caplog.text.lower()
    else:
        assert "--limit" not in caplog.text.lower()


# ---------------------------------------------------------------------------
# with_shared URL parameter tests
# ---------------------------------------------------------------------------


def _make_group_project(name: str = "project1") -> dict[str, t.Any]:
    """Create a minimal GitLab group project API object."""
    return {
        "path": name,
        "name": name,
        "http_url_to_repo": f"https://gitlab.com/testgroup/{name}.git",
        "ssh_url_to_repo": f"git@gitlab.com:testgroup/{name}.git",
        "web_url": f"https://gitlab.com/testgroup/{name}",
        "description": None,
        "topics": [],
        "star_count": 0,
        "archived": False,
        "default_branch": "main",
        "namespace": {"path": "testgroup", "full_path": "testgroup"},
    }


def test_gitlab_with_shared_false_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that with_shared=false is sent to GitLab API in group mode by default."""
    captured_urls: list[str] = []

    response_json = [_make_group_project()]

    def urlopen_capture(
        request: urllib.request.Request,
        timeout: int | None = None,
    ) -> MockHTTPResponse:
        captured_urls.append(request.full_url)
        return MockHTTPResponse(json.dumps(response_json).encode())

    # Mock urlopen: verify with_shared=false is sent when not explicitly set
    monkeypatch.setattr("urllib.request.urlopen", urlopen_capture)

    importer = GitLabImporter()
    options = ImportOptions(mode=ImportMode.ORG, target="testgroup")
    list(importer.fetch_repos(options))

    assert len(captured_urls) == 1
    qs = urllib.parse.parse_qs(urllib.parse.urlsplit(captured_urls[0]).query)
    assert qs.get("with_shared") == ["false"], (
        f"Expected with_shared=false, got: {captured_urls[0]}"
    )


def test_gitlab_with_shared_true_when_flag_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that with_shared=true is sent to GitLab API when with_shared=True."""
    captured_urls: list[str] = []

    response_json = [_make_group_project()]

    def urlopen_capture(
        request: urllib.request.Request,
        timeout: int | None = None,
    ) -> MockHTTPResponse:
        captured_urls.append(request.full_url)
        return MockHTTPResponse(json.dumps(response_json).encode())

    # Mock urlopen: verify with_shared=true is sent when explicitly enabled
    monkeypatch.setattr("urllib.request.urlopen", urlopen_capture)

    importer = GitLabImporter()
    options = ImportOptions(mode=ImportMode.ORG, target="testgroup", with_shared=True)
    list(importer.fetch_repos(options))

    assert len(captured_urls) == 1
    qs = urllib.parse.parse_qs(urllib.parse.urlsplit(captured_urls[0]).query)
    assert qs.get("with_shared") == ["true"], (
        f"Expected with_shared=true, got: {captured_urls[0]}"
    )


def test_gitlab_with_shared_not_sent_in_user_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that with_shared is NOT sent to GitLab API in user mode."""
    captured_urls: list[str] = []

    response_json = [_make_group_project()]

    def urlopen_capture(
        request: urllib.request.Request,
        timeout: int | None = None,
    ) -> MockHTTPResponse:
        captured_urls.append(request.full_url)
        return MockHTTPResponse(json.dumps(response_json).encode())

    # Mock urlopen: verify with_shared is absent from user-mode API calls
    monkeypatch.setattr("urllib.request.urlopen", urlopen_capture)

    importer = GitLabImporter()
    options = ImportOptions(mode=ImportMode.USER, target="testuser", with_shared=True)
    list(importer.fetch_repos(options))

    assert len(captured_urls) == 1
    qs = urllib.parse.parse_qs(urllib.parse.urlsplit(captured_urls[0]).query)
    assert "with_shared" not in qs, (
        f"Expected no with_shared param in user-mode URL, got: {captured_urls[0]}"
    )


# ---------------------------------------------------------------------------
# skip_groups filtering tests
# ---------------------------------------------------------------------------


def test_gitlab_skip_groups_filters_repos(
    mock_urlopen: t.Callable[..., None],
) -> None:
    """Test skip_groups excludes repos whose owner path contains the group segment."""
    response_json: list[dict[str, t.Any]] = [
        {
            "path": "top-repo",
            "name": "top-repo",
            "http_url_to_repo": "https://gitlab.com/testgroup/top-repo.git",
            "ssh_url_to_repo": "git@gitlab.com:testgroup/top-repo.git",
            "web_url": "https://gitlab.com/testgroup/top-repo",
            "description": None,
            "topics": [],
            "star_count": 0,
            "archived": False,
            "default_branch": "main",
            "namespace": {"path": "testgroup", "full_path": "testgroup"},
        },
        {
            "path": "bots-repo",
            "name": "bots-repo",
            "http_url_to_repo": "https://gitlab.com/testgroup/bots/bots-repo.git",
            "ssh_url_to_repo": "git@gitlab.com:testgroup/bots/bots-repo.git",
            "web_url": "https://gitlab.com/testgroup/bots/bots-repo",
            "description": None,
            "topics": [],
            "star_count": 0,
            "archived": False,
            "default_branch": "main",
            "namespace": {"path": "bots", "full_path": "testgroup/bots"},
        },
        {
            "path": "sub-bots-repo",
            "name": "sub-bots-repo",
            "http_url_to_repo": (
                "https://gitlab.com/testgroup/bots/subteam/sub-bots-repo.git"
            ),
            "ssh_url_to_repo": (
                "git@gitlab.com:testgroup/bots/subteam/sub-bots-repo.git"
            ),
            "web_url": ("https://gitlab.com/testgroup/bots/subteam/sub-bots-repo"),
            "description": None,
            "topics": [],
            "star_count": 0,
            "archived": False,
            "default_branch": "main",
            "namespace": {
                "path": "subteam",
                "full_path": "testgroup/bots/subteam",
            },
        },
    ]
    mock_urlopen([(json.dumps(response_json).encode(), {}, 200)])
    importer = GitLabImporter()
    options = ImportOptions(
        mode=ImportMode.ORG, target="testgroup", skip_groups=["bots"]
    )
    repos = list(importer.fetch_repos(options))

    # Only top-level repo should survive; bots and bots/subteam are excluded
    assert len(repos) == 1
    assert repos[0].name == "top-repo"


def test_gitlab_skip_groups_case_insensitive(
    mock_urlopen: t.Callable[..., None],
) -> None:
    """Test skip_groups matching is case-insensitive."""
    response_json: list[dict[str, t.Any]] = [
        {
            "path": "bots-repo",
            "name": "bots-repo",
            "http_url_to_repo": "https://gitlab.com/ORG/Bots/bots-repo.git",
            "ssh_url_to_repo": "git@gitlab.com:ORG/Bots/bots-repo.git",
            "web_url": "https://gitlab.com/ORG/Bots/bots-repo",
            "description": None,
            "topics": [],
            "star_count": 0,
            "archived": False,
            "default_branch": "main",
            "namespace": {"path": "Bots", "full_path": "ORG/Bots"},
        },
    ]
    mock_urlopen([(json.dumps(response_json).encode(), {}, 200)])
    importer = GitLabImporter()
    # Lowercase skip group matches uppercase owner segment
    options = ImportOptions(mode=ImportMode.ORG, target="ORG", skip_groups=["bots"])
    repos = list(importer.fetch_repos(options))
    assert len(repos) == 0
