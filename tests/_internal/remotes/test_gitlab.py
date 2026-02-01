"""Tests for vcspull._internal.remotes.gitlab module."""

from __future__ import annotations

import json
import typing as t

import pytest

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


def test_gitlab_search_requires_auth() -> None:
    """Test GitLab search raises error without authentication."""
    from vcspull._internal.remotes.base import AuthenticationError

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


def test_gitlab_importer_is_authenticated_without_token() -> None:
    """Test is_authenticated returns False without token."""
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
