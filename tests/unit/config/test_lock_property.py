"""Property-based tests for lock file models.

This module contains property-based tests using Hypothesis for the
VCSPull lock file models to ensure they meet invariants and
handle edge cases properly.
"""

from __future__ import annotations

import datetime
from pathlib import Path
from typing import Any, Callable

import hypothesis.strategies as st
from hypothesis import given

from vcspull.config.models import LockedRepository, LockFile


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
def valid_revision_strategy(draw: Callable[[st.SearchStrategy[Any]], Any]) -> str:
    """Generate valid revision strings for repositories."""
    # Git commit hash (40 chars hex)
    git_hash = draw(st.text(alphabet="0123456789abcdef", min_size=7, max_size=40))

    # Git branch/tag (simpler text)
    git_ref = draw(
        st.text(
            alphabet="abcdefghijklmnopqrstuvwxyz0123456789-_/.",
            min_size=1,
            max_size=20,
        ),
    )

    # SVN revision number
    svn_rev = str(draw(st.integers(min_value=1, max_value=10000)))

    # HG changeset ID
    hg_id = draw(st.text(alphabet="0123456789abcdef", min_size=12, max_size=40))

    result: str = draw(st.sampled_from([git_hash, git_ref, svn_rev, hg_id]))
    return result


@st.composite
def datetime_strategy(
    draw: Callable[[st.SearchStrategy[Any]], Any],
) -> datetime.datetime:
    """Generate valid datetime objects within a reasonable range."""
    # Using fixed datetimes to avoid flaky behavior
    datetimes = [
        datetime.datetime(2020, 1, 1),
        datetime.datetime(2021, 6, 15),
        datetime.datetime(2022, 12, 31),
        datetime.datetime(2023, 3, 10),
        datetime.datetime(2024, 1, 1),
    ]

    result: datetime.datetime = draw(st.sampled_from(datetimes))
    return result


@st.composite
def locked_repository_strategy(
    draw: Callable[[st.SearchStrategy[Any]], Any],
) -> LockedRepository:
    """Generate valid LockedRepository instances."""
    name = draw(st.one_of(st.none(), st.text(min_size=1, max_size=20)))
    url = draw(valid_url_strategy())
    path = draw(valid_path_strategy())
    vcs = draw(st.sampled_from(["git", "hg", "svn"]))
    rev = draw(valid_revision_strategy())
    locked_at = draw(datetime_strategy())

    return LockedRepository(
        name=name,
        url=url,
        path=path,
        vcs=vcs,
        rev=rev,
        locked_at=locked_at,
    )


@st.composite
def lock_file_strategy(draw: Callable[[st.SearchStrategy[Any]], Any]) -> LockFile:
    """Generate valid LockFile instances."""
    version = draw(st.sampled_from(["1.0.0", "1.0.1", "1.1.0"]))
    created_at = draw(datetime_strategy())

    # Generate between 0 and 5 locked repositories
    repo_count = draw(st.integers(min_value=0, max_value=5))
    repositories = [draw(locked_repository_strategy()) for _ in range(repo_count)]

    return LockFile(
        version=version,
        created_at=created_at,
        repositories=repositories,
    )


class TestLockedRepositoryProperties:
    """Property-based tests for the LockedRepository model."""

    @given(
        url=valid_url_strategy(),
        path=valid_path_strategy(),
        vcs=st.sampled_from(["git", "hg", "svn"]),
        rev=valid_revision_strategy(),
    )
    def test_minimal_locked_repository_properties(
        self, url: str, path: str, vcs: str, rev: str
    ) -> None:
        """Test properties of locked repositories."""
        repo = LockedRepository(url=url, path=path, vcs=vcs, rev=rev)

        # Check invariants
        assert repo.url == url
        assert Path(repo.path).is_absolute()
        assert repo.path.startswith("/")  # Path should be absolute after normalization
        assert repo.vcs in {"git", "hg", "svn"}
        assert repo.rev == rev
        assert isinstance(repo.locked_at, datetime.datetime)

    @given(repo=locked_repository_strategy())
    def test_locked_repository_roundtrip(self, repo: LockedRepository) -> None:
        """Test locked repository serialization and deserialization."""
        # Roundtrip test: convert to dict and back to model
        repo_dict = repo.model_dump()
        repo2 = LockedRepository.model_validate(repo_dict)

        # The resulting object should match the original
        assert repo2.url == repo.url
        assert repo2.path == repo.path
        assert repo2.name == repo.name
        assert repo2.vcs == repo.vcs
        assert repo2.rev == repo.rev
        assert repo2.locked_at == repo.locked_at


class TestLockFileProperties:
    """Property-based tests for the LockFile model."""

    @given(lock_file=lock_file_strategy())
    def test_lock_file_roundtrip(self, lock_file: LockFile) -> None:
        """Test lock file serialization and deserialization."""
        # Roundtrip test: convert to dict and back to model
        lock_dict = lock_file.model_dump()
        lock_file2 = LockFile.model_validate(lock_dict)

        # The resulting object should match the original
        assert lock_file2.version == lock_file.version
        assert lock_file2.created_at == lock_file.created_at
        assert len(lock_file2.repositories) == len(lock_file.repositories)

    @given(lock_file=lock_file_strategy())
    def test_lock_file_repository_paths(self, lock_file: LockFile) -> None:
        """Test that locked repositories have valid paths."""
        for repo in lock_file.repositories:
            # All paths should be absolute after normalization
            assert Path(repo.path).is_absolute()

    @given(lock_file=lock_file_strategy())
    def test_semver_version_format(self, lock_file: LockFile) -> None:
        """Test that the version follows semver format."""
        # Version should be in the format x.y.z
        assert lock_file.version.count(".") == 2
        major, minor, patch = lock_file.version.split(".")
        assert major.isdigit()
        assert minor.isdigit()
        assert patch.isdigit()
