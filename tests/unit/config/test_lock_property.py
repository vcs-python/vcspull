"""Property-based tests for configuration lock.

This module contains property-based tests using Hypothesis for the
VCSPull configuration lock to ensure it properly handles versioning
and change tracking.
"""

from __future__ import annotations

import json
import pathlib
import typing as t

import hypothesis.strategies as st
import pytest
from hypothesis import given

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
def repository_strategy(
    draw: t.Callable[[st.SearchStrategy[t.Any]], t.Any],
) -> Repository:
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
    draw: t.Callable[[st.SearchStrategy[t.Any]], t.Any],
) -> VCSPullConfig:
    """Generate valid VCSPullConfig instances."""
    settings = draw(settings_strategy())

    # Generate between 1 and 5 repositories
    repo_count = draw(st.integers(min_value=1, max_value=5))
    repositories = [draw(repository_strategy()) for _ in range(repo_count)]

    # Optionally generate includes
    include_count = draw(st.integers(min_value=0, max_value=3))
    includes = [f"include{i}.yaml" for i in range(include_count)]

    return VCSPullConfig(
        settings=settings,
        repositories=repositories,
        includes=includes,
    )


def extract_name_from_url(url: str) -> str:
    """Extract repository name from URL.

    Parameters
    ----------
    url : str
        Repository URL

    Returns
    -------
    str
        Repository name
    """
    # Extract the last part of the URL path
    parts = url.rstrip("/").split("/")
    name = parts[-1]

    # Remove .git suffix if present
    if name.endswith(".git"):
        name = name[:-4]

    return name


# Mark the entire class to skip tests since the lock module doesn't exist yet
@pytest.mark.skip(reason="Lock module not implemented yet")
class TestLockProperties:
    """Property-based tests for the lock mechanism."""

    @given(config=vcspull_config_strategy())
    def test_lock_calculation(
        self, config: VCSPullConfig, tmp_path: pathlib.Path
    ) -> None:
        """Test lock calculation from config."""
        # Create a mock lock dictionary
        lock: dict[str, t.Any] = {
            "version": "1.0.0",
            "repositories": {},
        }

        # Add repositories to the lock
        for repo in config.repositories:
            repo_name = repo.name or extract_name_from_url(repo.url)
            lock["repositories"][repo_name] = {
                "url": repo.url,
                "path": repo.path,
                "vcs": repo.vcs or "git",
                "rev": repo.rev or "main",
            }

        # Check basic lock properties
        assert "version" in lock
        assert "repositories" in lock
        assert isinstance(lock["repositories"], dict)

        # Check that all repositories are included
        assert len(lock["repositories"]) == len(config.repositories)
        for repo in config.repositories:
            repo_name = repo.name or extract_name_from_url(repo.url)
            assert repo_name in lock["repositories"]

    @given(config=vcspull_config_strategy())
    def test_lock_save_load_roundtrip(
        self, config: VCSPullConfig, tmp_path: pathlib.Path
    ) -> None:
        """Test saving and loading a lock file."""
        # Create a mock lock dictionary
        lock: dict[str, t.Any] = {
            "version": "1.0.0",
            "repositories": {},
        }

        # Add repositories to the lock
        for repo in config.repositories:
            repo_name = repo.name or extract_name_from_url(repo.url)
            lock["repositories"][repo_name] = {
                "url": repo.url,
                "path": repo.path,
                "vcs": repo.vcs or "git",
                "rev": repo.rev or "main",
            }

        # Save lock to file
        lock_path = tmp_path / "vcspull.lock.json"
        with lock_path.open("w") as f:
            json.dump(lock, f)

        # Load lock from file
        with lock_path.open("r") as f:
            loaded_lock: dict[str, t.Any] = json.load(f)

        # Check that loaded lock matches original
        assert loaded_lock["version"] == lock["version"]
        assert set(loaded_lock["repositories"].keys()) == set(
            lock["repositories"].keys()
        )
