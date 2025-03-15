"""Property-based tests for configuration models.

This module contains property-based tests using Hypothesis
for the VCSPull configuration models to ensure they handle
various inputs correctly and maintain their invariants.
"""

from __future__ import annotations

import os
import pathlib
import typing as t

import hypothesis.strategies as st
import pytest
from hypothesis import given, settings

from vcspull.config.models import Repository, Settings, VCSPullConfig


@st.composite
def valid_url_strategy(draw: t.Callable[[st.SearchStrategy[t.Any]], t.Any]) -> str:
    """Generate valid URLs for repositories."""
    protocols = ["https://", "http://", "git://", "ssh://git@"]
    domains = ["github.com", "gitlab.com", "bitbucket.org", "example.com"]
    usernames = ["user", "organization", "team", draw(st.text(min_size=3, max_size=10))]
    repo_names = [
        "repo",
        "project",
        "library",
        f"repo-{
            draw(
                st.text(
                    alphabet='abcdefghijklmnopqrstuvwxyz0123456789-_',
                    min_size=1,
                    max_size=8,
                )
            )
        }",
    ]

    protocol = draw(st.sampled_from(protocols))
    domain = draw(st.sampled_from(domains))
    username = draw(st.sampled_from(usernames))
    repo_name = draw(st.sampled_from(repo_names))

    suffix = ".git" if protocol != "ssh://git@" else ""

    return f"{protocol}{domain}/{username}/{repo_name}{suffix}"


@st.composite
def valid_path_strategy(draw: t.Callable[[st.SearchStrategy[t.Any]], t.Any]) -> str:
    """Generate valid paths for repositories."""
    base_dirs = ["~/code", "~/projects", "/tmp", "./projects"]
    sub_dirs = [
        "repo",
        "lib",
        "src",
        f"dir-{
            draw(
                st.text(
                    alphabet='abcdefghijklmnopqrstuvwxyz0123456789-_',
                    min_size=1,
                    max_size=8,
                )
            )
        }",
    ]

    base_dir = draw(st.sampled_from(base_dirs))
    sub_dir = draw(st.sampled_from(sub_dirs))

    return f"{base_dir}/{sub_dir}"


@st.composite
def repository_strategy(draw: t.Callable[[st.SearchStrategy[t.Any]], t.Any]) -> Repository:
    """Generate valid Repository instances."""
    name = draw(st.one_of(st.none(), st.text(min_size=1, max_size=20)))
    url = draw(valid_url_strategy())
    path = draw(valid_path_strategy())
    vcs = draw(st.one_of(st.none(), st.sampled_from(["git", "hg", "svn"])))

    # Optionally generate remotes
    remotes = {}
    if draw(st.booleans()):
        remote_names = ["upstream", "origin", "fork"]
        remote_count = draw(st.integers(min_value=1, max_value=3))
        for _ in range(remote_count):
            remote_name = draw(st.sampled_from(remote_names))
            if remote_name not in remotes:  # Avoid duplicates
                remotes[remote_name] = draw(valid_url_strategy())

    rev = draw(
        st.one_of(
            st.none(),
            st.text(min_size=1, max_size=40),  # Can be branch name, tag, or commit hash
        ),
    )

    web_url = draw(
        st.one_of(
            st.none(),
            st.sampled_from(
                [
                    f"https://github.com/user/{name}"
                    if name
                    else "https://github.com/user/repo",
                    f"https://gitlab.com/user/{name}"
                    if name
                    else "https://gitlab.com/user/repo",
                ],
            ),
        ),
    )

    return Repository(
        name=name,
        url=url,
        path=path,
        vcs=vcs,
        remotes=remotes,
        rev=rev,
        web_url=web_url,
    )


@st.composite
def settings_strategy(draw: t.Callable[[st.SearchStrategy[t.Any]], t.Any]) -> Settings:
    """Generate valid Settings instances."""
    sync_remotes = draw(st.booleans())
    default_vcs = draw(st.one_of(st.none(), st.sampled_from(["git", "hg", "svn"])))
    depth = draw(st.one_of(st.none(), st.integers(min_value=1, max_value=10)))

    return Settings(
        sync_remotes=sync_remotes,
        default_vcs=default_vcs,
        depth=depth,
    )


@st.composite
def vcspull_config_strategy(
    draw: t.Callable[[st.SearchStrategy[t.Any]], t.Any]
) -> VCSPullConfig:
    """Generate valid VCSPullConfig instances."""
    settings = draw(settings_strategy())

    # Generate between 0 and 5 repositories
    repo_count = draw(st.integers(min_value=0, max_value=5))
    repositories = [draw(repository_strategy()) for _ in range(repo_count)]

    # Optionally generate includes (0 to 3)
    include_count = draw(st.integers(min_value=0, max_value=3))
    includes = [f"include{i}.yaml" for i in range(include_count)]

    return VCSPullConfig(
        settings=settings,
        repositories=repositories,
        includes=includes,
    )


class TestRepositoryModel:
    """Property-based tests for Repository model."""

    @given(repository=repository_strategy())
    def test_repository_construction(self, repository: Repository) -> None:
        """Test Repository model construction with varied inputs."""
        # Verify required fields are set
        assert repository.url is not None
        assert repository.path is not None

        # Check computed fields
        if repository.name is None:
            # Name should be derived from URL if not explicitly set
            assert repository.get_name() != ""

    @given(url=valid_url_strategy())
    def test_repository_name_extraction(self, url: str) -> None:
        """Test Repository can extract names from URLs."""
        repo = Repository(url=url, path="/tmp/repo")
        # Should be able to extract a name from any valid URL
        assert repo.get_name() != ""
        # The name shouldn't contain protocol or domain parts
        assert "://" not in repo.get_name()
        assert "github.com" not in repo.get_name()

    @given(repository=repository_strategy())
    def test_repository_path_expansion(self, repository: Repository) -> None:
        """Test path expansion in Repository model."""
        # Get the expanded path
        expanded_path = repository.get_path()

        # Check for tilde expansion
        assert "~" not in str(expanded_path)

        # If original path started with ~, expanded should be absolute
        if repository.path.startswith("~"):
            assert os.path.isabs(expanded_path)


class TestSettingsModel:
    """Property-based tests for Settings model."""

    @given(settings=settings_strategy())
    def test_settings_construction(self, settings: Settings) -> None:
        """Test Settings model construction with varied inputs."""
        # Check types
        assert isinstance(settings.sync_remotes, bool)
        if settings.default_vcs is not None:
            assert settings.default_vcs in ["git", "hg", "svn"]
        if settings.depth is not None:
            assert isinstance(settings.depth, int)
            assert settings.depth > 0


class TestVCSPullConfigModel:
    """Property-based tests for VCSPullConfig model."""

    @given(config=vcspull_config_strategy())
    def test_config_construction(self, config: VCSPullConfig) -> None:
        """Test VCSPullConfig model construction with varied inputs."""
        # Verify nested models are properly initialized
        assert isinstance(config.settings, Settings)
        assert all(isinstance(repo, Repository) for repo in config.repositories)
        assert all(isinstance(include, str) for include in config.includes)

    @given(
        repo1=repository_strategy(),
        repo2=repository_strategy(),
        repo3=repository_strategy(),
    )
    def test_config_with_multiple_repositories(
        self, repo1: Repository, repo2: Repository, repo3: Repository
    ) -> None:
        """Test VCSPullConfig with multiple repositories."""
        # Create a config with multiple repositories
        config = VCSPullConfig(repositories=[repo1, repo2, repo3])

        # Verify all repositories are present
        assert len(config.repositories) == 3
        assert repo1 in config.repositories
        assert repo2 in config.repositories
        assert repo3 in config.repositories
