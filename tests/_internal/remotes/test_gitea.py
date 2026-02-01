"""Tests for vcspull._internal.remotes.gitea module."""

from __future__ import annotations

import json
import typing as t

import pytest

from vcspull._internal.remotes.base import ImportMode, ImportOptions
from vcspull._internal.remotes.gitea import GiteaImporter


def test_gitea_fetch_user(
    mock_urlopen: t.Callable[..., None],
    gitea_user_repos_response: bytes,
) -> None:
    """Test Gitea user repository fetching."""
    mock_urlopen([(gitea_user_repos_response, {}, 200)])
    importer = GiteaImporter(base_url="https://codeberg.org")
    options = ImportOptions(mode=ImportMode.USER, target="testuser")
    repos = list(importer.fetch_repos(options))
    assert len(repos) == 1
    assert repos[0].name == "repo1"
    assert repos[0].owner == "testuser"
    assert repos[0].stars == 15


def test_gitea_fetch_org(
    mock_urlopen: t.Callable[..., None],
) -> None:
    """Test Gitea org repository fetching."""
    response_json = [
        {
            "name": "org-repo",
            "clone_url": "https://codeberg.org/testorg/org-repo.git",
            "html_url": "https://codeberg.org/testorg/org-repo",
            "description": "Org repo",
            "language": "Go",
            "topics": [],
            "stars_count": 100,
            "fork": False,
            "archived": False,
            "default_branch": "main",
            "owner": {"login": "testorg"},
        }
    ]
    mock_urlopen([(json.dumps(response_json).encode(), {}, 200)])
    importer = GiteaImporter(base_url="https://codeberg.org")
    options = ImportOptions(mode=ImportMode.ORG, target="testorg")
    repos = list(importer.fetch_repos(options))
    assert len(repos) == 1
    assert repos[0].name == "org-repo"


def test_gitea_search_with_wrapped_response(
    mock_urlopen: t.Callable[..., None],
    gitea_search_response: bytes,
) -> None:
    """Test Gitea search handles wrapped response format."""
    mock_urlopen([(gitea_search_response, {}, 200)])
    importer = GiteaImporter(base_url="https://codeberg.org")
    options = ImportOptions(mode=ImportMode.SEARCH, target="test")
    repos = list(importer.fetch_repos(options))
    assert len(repos) == 1
    assert repos[0].name == "search-result"


def test_gitea_search_with_array_response(
    mock_urlopen: t.Callable[..., None],
) -> None:
    """Test Gitea search handles plain array response format."""
    # Some Gitea instances return plain array instead of {"ok": true, "data": [...]}
    response_json = [
        {
            "name": "plain-result",
            "clone_url": "https://gitea.example.com/user/plain-result.git",
            "html_url": "https://gitea.example.com/user/plain-result",
            "description": "Plain array result",
            "language": "Python",
            "topics": [],
            "stars_count": 20,
            "fork": False,
            "archived": False,
            "default_branch": "main",
            "owner": {"login": "user"},
        }
    ]
    mock_urlopen([(json.dumps(response_json).encode(), {}, 200)])
    importer = GiteaImporter(base_url="https://gitea.example.com")
    options = ImportOptions(mode=ImportMode.SEARCH, target="test")
    repos = list(importer.fetch_repos(options))
    assert len(repos) == 1
    assert repos[0].name == "plain-result"


def test_gitea_importer_defaults_to_codeberg() -> None:
    """Test GiteaImporter defaults to Codeberg URL."""
    importer = GiteaImporter()
    assert importer._base_url == "https://codeberg.org"


def test_gitea_importer_service_name() -> None:
    """Test service_name property."""
    importer = GiteaImporter()
    assert importer.service_name == "Gitea"


def test_gitea_importer_is_authenticated_without_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test is_authenticated returns False without token."""
    # Clear environment variables that could provide a token
    monkeypatch.delenv("CODEBERG_TOKEN", raising=False)
    monkeypatch.delenv("GITEA_TOKEN", raising=False)
    monkeypatch.delenv("FORGEJO_TOKEN", raising=False)
    importer = GiteaImporter(token=None)
    assert importer.is_authenticated is False


def test_gitea_importer_is_authenticated_with_token() -> None:
    """Test is_authenticated returns True with token."""
    importer = GiteaImporter(token="test-token")
    assert importer.is_authenticated is True


def test_gitea_uses_stars_count_field(
    mock_urlopen: t.Callable[..., None],
) -> None:
    """Test Gitea correctly reads stars_count (not stargazers_count)."""
    response_json = [
        {
            "name": "starred-repo",
            "clone_url": "https://codeberg.org/user/starred-repo.git",
            "html_url": "https://codeberg.org/user/starred-repo",
            "description": "Popular repo",
            "language": "Rust",
            "topics": [],
            "stars_count": 500,  # Gitea uses stars_count
            "fork": False,
            "archived": False,
            "default_branch": "main",
            "owner": {"login": "user"},
        }
    ]
    mock_urlopen([(json.dumps(response_json).encode(), {}, 200)])
    importer = GiteaImporter(base_url="https://codeberg.org")
    options = ImportOptions(mode=ImportMode.USER, target="user")
    repos = list(importer.fetch_repos(options))
    assert len(repos) == 1
    assert repos[0].stars == 500


def test_gitea_filters_by_language(
    mock_urlopen: t.Callable[..., None],
) -> None:
    """Test Gitea language filter works."""
    response_json = [
        {
            "name": "go-repo",
            "clone_url": "https://codeberg.org/user/go-repo.git",
            "html_url": "https://codeberg.org/user/go-repo",
            "description": "Go repo",
            "language": "Go",
            "topics": [],
            "stars_count": 50,
            "fork": False,
            "archived": False,
            "default_branch": "main",
            "owner": {"login": "user"},
        },
        {
            "name": "rust-repo",
            "clone_url": "https://codeberg.org/user/rust-repo.git",
            "html_url": "https://codeberg.org/user/rust-repo",
            "description": "Rust repo",
            "language": "Rust",
            "topics": [],
            "stars_count": 30,
            "fork": False,
            "archived": False,
            "default_branch": "main",
            "owner": {"login": "user"},
        },
    ]
    mock_urlopen([(json.dumps(response_json).encode(), {}, 200)])
    importer = GiteaImporter(base_url="https://codeberg.org")
    options = ImportOptions(mode=ImportMode.USER, target="user", language="Rust")
    repos = list(importer.fetch_repos(options))
    assert len(repos) == 1
    assert repos[0].name == "rust-repo"
