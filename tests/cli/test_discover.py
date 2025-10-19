"""Tests for vcspull discover command."""

from __future__ import annotations

import pathlib
import subprocess
import typing as t

import pytest

from vcspull.cli.discover import discover_repos

if t.TYPE_CHECKING:
    from _pytest.monkeypatch import MonkeyPatch


def init_git_repo(repo_path: pathlib.Path, remote_url: str) -> None:
    """Initialize a git repository with a remote."""
    repo_path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init"], cwd=repo_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "remote", "add", "origin", remote_url],
        cwd=repo_path,
        check=True,
        capture_output=True,
    )


class DiscoverFixture(t.NamedTuple):
    """Fixture for discover test cases."""

    test_id: str
    repos_to_create: list[tuple[str, str]]  # (name, remote_url)
    recursive: bool
    workspace_override: str | None
    dry_run: bool
    yes: bool
    expected_repo_count: int


DISCOVER_FIXTURES: list[DiscoverFixture] = [
    DiscoverFixture(
        test_id="discover-single-level",
        repos_to_create=[
            ("repo1", "git+https://github.com/user/repo1.git"),
            ("repo2", "git+https://github.com/user/repo2.git"),
        ],
        recursive=False,
        workspace_override=None,
        dry_run=False,
        yes=True,
        expected_repo_count=2,
    ),
    DiscoverFixture(
        test_id="discover-recursive",
        repos_to_create=[
            ("repo1", "git+https://github.com/user/repo1.git"),
            ("subdir/repo2", "git+https://github.com/user/repo2.git"),
            ("subdir/nested/repo3", "git+https://github.com/user/repo3.git"),
        ],
        recursive=True,
        workspace_override=None,
        dry_run=False,
        yes=True,
        expected_repo_count=3,
    ),
    DiscoverFixture(
        test_id="discover-dry-run",
        repos_to_create=[
            ("repo1", "git+https://github.com/user/repo1.git"),
        ],
        recursive=False,
        workspace_override=None,
        dry_run=True,
        yes=True,
        expected_repo_count=0,  # Nothing written in dry-run
    ),
]


@pytest.mark.parametrize(
    list(DiscoverFixture._fields),
    DISCOVER_FIXTURES,
    ids=[fixture.test_id for fixture in DISCOVER_FIXTURES],
)
def test_discover_repos(
    test_id: str,
    repos_to_create: list[tuple[str, str]],
    recursive: bool,
    workspace_override: str | None,
    dry_run: bool,
    yes: bool,
    expected_repo_count: int,
    tmp_path: pathlib.Path,
    monkeypatch: MonkeyPatch,
    caplog: t.Any,
) -> None:
    """Test discovering repositories from filesystem."""
    import logging

    caplog.set_level(logging.INFO)

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)

    scan_dir = tmp_path / "code"
    scan_dir.mkdir()

    # Create git repos
    for repo_name, remote_url in repos_to_create:
        repo_path = scan_dir / repo_name
        init_git_repo(repo_path, remote_url)

    config_file = tmp_path / ".vcspull.yaml"

    # Run discover
    discover_repos(
        scan_dir_str=str(scan_dir),
        config_file_path_str=str(config_file),
        recursive=recursive,
        workspace_root_override=workspace_override,
        yes=yes,
        dry_run=dry_run,
    )

    if dry_run:
        # In dry-run mode, config file should not be created/modified
        if expected_repo_count == 0:
            assert "Dry run complete" in caplog.text
        return

    # Check config file was created and has expected repos
    if expected_repo_count > 0:
        assert config_file.exists()

        import yaml

        with config_file.open() as f:
            config = yaml.safe_load(f)

        # Count repos in config
        total_repos = sum(
            len(repos) for repos in config.values() if isinstance(repos, dict)
        )
        assert total_repos == expected_repo_count, (
            f"Expected {expected_repo_count} repos, got {total_repos}"
        )


def test_discover_skips_repos_without_remote(
    tmp_path: pathlib.Path,
    monkeypatch: MonkeyPatch,
    caplog: t.Any,
) -> None:
    """Test that discover skips git repos without a remote."""
    import logging

    caplog.set_level(logging.INFO)

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)

    scan_dir = tmp_path / "code"
    scan_dir.mkdir()

    # Create a repo without remote
    repo_path = scan_dir / "no-remote"
    repo_path.mkdir()
    subprocess.run(["git", "init"], cwd=repo_path, check=True, capture_output=True)

    config_file = tmp_path / ".vcspull.yaml"

    discover_repos(
        scan_dir_str=str(scan_dir),
        config_file_path_str=str(config_file),
        recursive=False,
        workspace_root_override=None,
        yes=True,
        dry_run=False,
    )

    # Should log a warning
    assert "Could not determine remote URL" in caplog.text


def test_discover_shows_existing_repos(
    tmp_path: pathlib.Path,
    monkeypatch: MonkeyPatch,
    caplog: t.Any,
) -> None:
    """Test that discover shows which repos already exist in config."""
    import logging

    caplog.set_level(logging.INFO)

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)

    scan_dir = tmp_path / "code"
    scan_dir.mkdir()

    # Create a git repo
    repo_path = scan_dir / "existing-repo"
    init_git_repo(repo_path, "git+https://github.com/user/existing-repo.git")

    config_file = tmp_path / ".vcspull.yaml"

    # First discovery
    discover_repos(
        scan_dir_str=str(scan_dir),
        config_file_path_str=str(config_file),
        recursive=False,
        workspace_root_override=None,
        yes=True,
        dry_run=False,
    )

    # Clear logs
    caplog.clear()

    # Second discovery (should find existing repo)
    discover_repos(
        scan_dir_str=str(scan_dir),
        config_file_path_str=str(config_file),
        recursive=False,
        workspace_root_override=None,
        yes=True,
        dry_run=False,
    )

    # Should mention existing repos
    assert "existing" in caplog.text.lower() or "already" in caplog.text.lower()


def test_discover_with_workspace_override(
    tmp_path: pathlib.Path,
    monkeypatch: MonkeyPatch,
) -> None:
    """Test discover with workspace root override."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)

    scan_dir = tmp_path / "code"
    scan_dir.mkdir()

    # Create a git repo
    repo_path = scan_dir / "myrepo"
    init_git_repo(repo_path, "git+https://github.com/user/myrepo.git")

    config_file = tmp_path / ".vcspull.yaml"

    # Discover with workspace override
    discover_repos(
        scan_dir_str=str(scan_dir),
        config_file_path_str=str(config_file),
        recursive=False,
        workspace_root_override="~/projects/",
        yes=True,
        dry_run=False,
    )

    import yaml

    with config_file.open() as f:
        config = yaml.safe_load(f)

    # Should use the overridden workspace root
    assert "~/projects/" in config
    assert "myrepo" in config["~/projects/"]
