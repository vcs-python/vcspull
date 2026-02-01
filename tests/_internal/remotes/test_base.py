"""Tests for vcspull._internal.remotes.base module."""

from __future__ import annotations

import typing as t

import pytest

from vcspull._internal.remotes.base import (
    ImportMode,
    ImportOptions,
    RemoteRepo,
    filter_repo,
)


class FilterRepoFixture(t.NamedTuple):
    """Fixture for filter_repo test cases."""

    test_id: str
    repo_kwargs: dict[str, t.Any]
    options_kwargs: dict[str, t.Any]
    expected: bool


FILTER_REPO_FIXTURES: list[FilterRepoFixture] = [
    FilterRepoFixture(
        test_id="passes-all-defaults",
        repo_kwargs={
            "name": "test",
            "clone_url": "https://github.com/user/test.git",
            "html_url": "https://github.com/user/test",
            "description": None,
            "language": "Python",
            "topics": (),
            "stars": 50,
            "is_fork": False,
            "is_archived": False,
            "default_branch": "main",
            "owner": "user",
        },
        options_kwargs={},
        expected=True,
    ),
    FilterRepoFixture(
        test_id="excludes-fork-by-default",
        repo_kwargs={
            "name": "fork",
            "clone_url": "https://github.com/user/fork.git",
            "html_url": "https://github.com/user/fork",
            "description": None,
            "language": "Python",
            "topics": (),
            "stars": 10,
            "is_fork": True,
            "is_archived": False,
            "default_branch": "main",
            "owner": "user",
        },
        options_kwargs={"include_forks": False},
        expected=False,
    ),
    FilterRepoFixture(
        test_id="includes-fork-when-enabled",
        repo_kwargs={
            "name": "fork",
            "clone_url": "https://github.com/user/fork.git",
            "html_url": "https://github.com/user/fork",
            "description": None,
            "language": "Python",
            "topics": (),
            "stars": 10,
            "is_fork": True,
            "is_archived": False,
            "default_branch": "main",
            "owner": "user",
        },
        options_kwargs={"include_forks": True},
        expected=True,
    ),
    FilterRepoFixture(
        test_id="excludes-archived-by-default",
        repo_kwargs={
            "name": "archived",
            "clone_url": "https://github.com/user/archived.git",
            "html_url": "https://github.com/user/archived",
            "description": None,
            "language": "Python",
            "topics": (),
            "stars": 5,
            "is_fork": False,
            "is_archived": True,
            "default_branch": "main",
            "owner": "user",
        },
        options_kwargs={"include_archived": False},
        expected=False,
    ),
    FilterRepoFixture(
        test_id="includes-archived-when-enabled",
        repo_kwargs={
            "name": "archived",
            "clone_url": "https://github.com/user/archived.git",
            "html_url": "https://github.com/user/archived",
            "description": None,
            "language": "Python",
            "topics": (),
            "stars": 5,
            "is_fork": False,
            "is_archived": True,
            "default_branch": "main",
            "owner": "user",
        },
        options_kwargs={"include_archived": True},
        expected=True,
    ),
    FilterRepoFixture(
        test_id="filters-by-language-match",
        repo_kwargs={
            "name": "python-repo",
            "clone_url": "https://github.com/user/python-repo.git",
            "html_url": "https://github.com/user/python-repo",
            "description": None,
            "language": "Python",
            "topics": (),
            "stars": 50,
            "is_fork": False,
            "is_archived": False,
            "default_branch": "main",
            "owner": "user",
        },
        options_kwargs={"language": "Python"},
        expected=True,
    ),
    FilterRepoFixture(
        test_id="filters-by-language-mismatch",
        repo_kwargs={
            "name": "python-repo",
            "clone_url": "https://github.com/user/python-repo.git",
            "html_url": "https://github.com/user/python-repo",
            "description": None,
            "language": "Python",
            "topics": (),
            "stars": 50,
            "is_fork": False,
            "is_archived": False,
            "default_branch": "main",
            "owner": "user",
        },
        options_kwargs={"language": "JavaScript"},
        expected=False,
    ),
    FilterRepoFixture(
        test_id="filters-by-language-case-insensitive",
        repo_kwargs={
            "name": "python-repo",
            "clone_url": "https://github.com/user/python-repo.git",
            "html_url": "https://github.com/user/python-repo",
            "description": None,
            "language": "Python",
            "topics": (),
            "stars": 50,
            "is_fork": False,
            "is_archived": False,
            "default_branch": "main",
            "owner": "user",
        },
        options_kwargs={"language": "python"},
        expected=True,
    ),
    FilterRepoFixture(
        test_id="filters-by-min-stars-pass",
        repo_kwargs={
            "name": "popular",
            "clone_url": "https://github.com/user/popular.git",
            "html_url": "https://github.com/user/popular",
            "description": None,
            "language": "Python",
            "topics": (),
            "stars": 100,
            "is_fork": False,
            "is_archived": False,
            "default_branch": "main",
            "owner": "user",
        },
        options_kwargs={"min_stars": 50},
        expected=True,
    ),
    FilterRepoFixture(
        test_id="filters-by-min-stars-fail",
        repo_kwargs={
            "name": "unpopular",
            "clone_url": "https://github.com/user/unpopular.git",
            "html_url": "https://github.com/user/unpopular",
            "description": None,
            "language": "Python",
            "topics": (),
            "stars": 10,
            "is_fork": False,
            "is_archived": False,
            "default_branch": "main",
            "owner": "user",
        },
        options_kwargs={"min_stars": 50},
        expected=False,
    ),
    FilterRepoFixture(
        test_id="filters-by-topics-match",
        repo_kwargs={
            "name": "cli-tool",
            "clone_url": "https://github.com/user/cli-tool.git",
            "html_url": "https://github.com/user/cli-tool",
            "description": None,
            "language": "Python",
            "topics": ("cli", "tool", "python"),
            "stars": 50,
            "is_fork": False,
            "is_archived": False,
            "default_branch": "main",
            "owner": "user",
        },
        options_kwargs={"topics": ["cli", "python"]},
        expected=True,
    ),
    FilterRepoFixture(
        test_id="filters-by-topics-mismatch",
        repo_kwargs={
            "name": "web-app",
            "clone_url": "https://github.com/user/web-app.git",
            "html_url": "https://github.com/user/web-app",
            "description": None,
            "language": "Python",
            "topics": ("web", "django"),
            "stars": 50,
            "is_fork": False,
            "is_archived": False,
            "default_branch": "main",
            "owner": "user",
        },
        options_kwargs={"topics": ["cli"]},
        expected=False,
    ),
]


@pytest.mark.parametrize(
    list(FilterRepoFixture._fields),
    FILTER_REPO_FIXTURES,
    ids=[f.test_id for f in FILTER_REPO_FIXTURES],
)
def test_filter_repo(
    test_id: str,
    repo_kwargs: dict[str, t.Any],
    options_kwargs: dict[str, t.Any],
    expected: bool,
) -> None:
    """Test filter_repo with various filter combinations."""
    repo = RemoteRepo(**repo_kwargs)
    options = ImportOptions(**options_kwargs)
    assert filter_repo(repo, options) == expected


def test_remote_repo_to_vcspull_url() -> None:
    """Test RemoteRepo.to_vcspull_url adds git+ prefix."""
    repo = RemoteRepo(
        name="test",
        clone_url="https://github.com/user/test.git",
        html_url="https://github.com/user/test",
        description=None,
        language=None,
        topics=(),
        stars=0,
        is_fork=False,
        is_archived=False,
        default_branch="main",
        owner="user",
    )
    assert repo.to_vcspull_url() == "git+https://github.com/user/test.git"


def test_remote_repo_to_vcspull_url_already_prefixed() -> None:
    """Test RemoteRepo.to_vcspull_url doesn't double-prefix."""
    repo = RemoteRepo(
        name="test",
        clone_url="git+https://github.com/user/test.git",
        html_url="https://github.com/user/test",
        description=None,
        language=None,
        topics=(),
        stars=0,
        is_fork=False,
        is_archived=False,
        default_branch="main",
        owner="user",
    )
    assert repo.to_vcspull_url() == "git+https://github.com/user/test.git"


def test_remote_repo_to_dict() -> None:
    """Test RemoteRepo.to_dict serialization."""
    repo = RemoteRepo(
        name="test",
        clone_url="https://github.com/user/test.git",
        html_url="https://github.com/user/test",
        description="A test repo",
        language="Python",
        topics=("cli", "tool"),
        stars=100,
        is_fork=False,
        is_archived=False,
        default_branch="main",
        owner="user",
    )
    d = repo.to_dict()
    assert d["name"] == "test"
    assert d["clone_url"] == "https://github.com/user/test.git"
    assert d["language"] == "Python"
    assert d["topics"] == ["cli", "tool"]
    assert d["stars"] == 100
    assert d["is_fork"] is False


def test_import_options_defaults() -> None:
    """Test ImportOptions default values."""
    options = ImportOptions()
    assert options.mode == ImportMode.USER
    assert options.target == ""
    assert options.base_url is None
    assert options.token is None
    assert options.include_forks is False
    assert options.include_archived is False
    assert options.language is None
    assert options.topics == []
    assert options.min_stars == 0
    assert options.limit == 100


def test_import_mode_values() -> None:
    """Test ImportMode enum values."""
    assert ImportMode.USER.value == "user"
    assert ImportMode.ORG.value == "org"
    assert ImportMode.SEARCH.value == "search"
