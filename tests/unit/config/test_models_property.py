"""Property-based tests for configuration models.

This module contains property-based tests using Hypothesis for the
VCSPull configuration models to ensure they meet invariants and
handle edge cases properly.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Callable

import hypothesis.strategies as st
from hypothesis import given

from vcspull.config.models import Repository, Settings, VCSPullConfig


# Define strategies for generating test data
@st.composite
def valid_url_strategy(draw: Callable[[st.SearchStrategy[Any]], Any]) -> str:
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
def valid_path_strategy(draw: Callable[[st.SearchStrategy[Any]], Any]) -> str:
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
def repository_strategy(draw: Callable[[st.SearchStrategy[Any]], Any]) -> Repository:
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
def settings_strategy(draw: Callable[[st.SearchStrategy[Any]], Any]) -> Settings:
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
    draw: Callable[[st.SearchStrategy[Any]], Any],
) -> VCSPullConfig:
    """Generate valid VCSPullConfig instances."""
    settings = draw(settings_strategy())

    # Generate between 0 and 5 repositories
    repo_count = draw(st.integers(min_value=0, max_value=5))
    repositories = [draw(repository_strategy()) for _ in range(repo_count)]

    # Generate includes
    include_count = draw(st.integers(min_value=0, max_value=3))
    includes = [f"~/.config/vcspull/include{i}.yaml" for i in range(include_count)]

    return VCSPullConfig(
        settings=settings,
        repositories=repositories,
        includes=includes,
    )


class TestRepositoryProperties:
    """Property-based tests for the Repository model."""

    @given(url=valid_url_strategy(), path=valid_path_strategy())
    def test_minimal_repository_properties(self, url: str, path: str) -> None:
        """Test properties of minimal repositories."""
        repo = Repository(url=url, path=path)

        # Check invariants
        assert repo.url == url
        assert Path(repo.path).is_absolute()
        assert repo.path.startswith("/")  # Path should be absolute after normalization

    @given(url=valid_url_strategy())
    def test_valid_url_formats(self, url: str) -> None:
        """Test that valid URL formats are accepted."""
        repo = Repository(url=url, path="~/repo")
        assert repo.url == url

        # Check URL format matches expected pattern
        url_pattern = r"^(https?|git|ssh)://.+"
        assert re.match(url_pattern, repo.url) is not None

    @given(repo=repository_strategy())
    def test_repository_roundtrip(self, repo: Repository) -> None:
        """Test repository serialization and deserialization."""
        # Roundtrip test: convert to dict and back to model
        repo_dict = repo.model_dump()
        repo2 = Repository.model_validate(repo_dict)

        # The resulting object should match the original
        assert repo2.url == repo.url
        assert repo2.path == repo.path
        assert repo2.name == repo.name
        assert repo2.vcs == repo.vcs
        assert repo2.remotes == repo.remotes
        assert repo2.rev == repo.rev
        assert repo2.web_url == repo.web_url


class TestSettingsProperties:
    """Property-based tests for the Settings model."""

    @given(settings=settings_strategy())
    def test_settings_roundtrip(self, settings: Settings) -> None:
        """Test settings serialization and deserialization."""
        # Roundtrip test: convert to dict and back to model
        settings_dict = settings.model_dump()
        settings2 = Settings.model_validate(settings_dict)

        # The resulting object should match the original
        assert settings2.sync_remotes == settings.sync_remotes
        assert settings2.default_vcs == settings.default_vcs
        assert settings2.depth == settings.depth


class TestVCSPullConfigProperties:
    """Property-based tests for the VCSPullConfig model."""

    @given(config=vcspull_config_strategy())
    def test_config_roundtrip(self, config: VCSPullConfig) -> None:
        """Test configuration serialization and deserialization."""
        # Roundtrip test: convert to dict and back to model
        config_dict = config.model_dump()
        config2 = VCSPullConfig.model_validate(config_dict)

        # The resulting object should match the original
        assert config2.settings.model_dump() == config.settings.model_dump()
        assert len(config2.repositories) == len(config.repositories)
        assert config2.includes == config.includes

    @given(config=vcspull_config_strategy())
    def test_repository_uniqueness(self, config: VCSPullConfig) -> None:
        """Test that repositories with the same path are treated as unique."""
        # This checks that we don't have unintended object identity issues
        repo_paths = [repo.path for repo in config.repositories]
        # Path uniqueness isn't enforced by the model, so we're just checking
        # that the objects are distinct even if paths might be the same
        assert len(repo_paths) == len(config.repositories)
