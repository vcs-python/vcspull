"""Tests for vcspull._internal.remotes.gitlab module."""

from __future__ import annotations

import json
import typing as t
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

    monkeypatch.setattr("urllib.request.urlopen", urlopen_capture)

    importer = GitLabImporter()
    options = ImportOptions(mode=ImportMode.USER, target="user", include_archived=False)
    list(importer.fetch_repos(options))

    assert len(captured_urls) == 1
    assert "archived=false" in captured_urls[0], (
        f"Expected 'archived=false' in URL, got: {captured_urls[0]}"
    )
