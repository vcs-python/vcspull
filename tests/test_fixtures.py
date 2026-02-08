"""Tests for vcspull test fixture infrastructure.

Validates that the autouse ``setup`` fixture in conftest.py correctly
propagates git identity, HOME, and gitconfig to subprocesses — the exact
conditions that fail in clean build environments (e.g. Arch Linux nspawn
containers without a global git identity).

Uses pytester to spawn isolated pytest runs, following the pattern in
``libvcs/tests/test_pytest_plugin.py:test_git_fixtures``.
"""

from __future__ import annotations

import os
import pathlib
import shutil
import subprocess
import textwrap
import typing as t

import pytest


def test_git_commit_envvars_in_environment(
    git_commit_envvars: dict[str, str],
) -> None:
    """Git commit env vars should be present in os.environ after autouse setup."""
    for key in (
        "GIT_AUTHOR_NAME",
        "GIT_AUTHOR_EMAIL",
        "GIT_COMMITTER_NAME",
        "GIT_COMMITTER_EMAIL",
    ):
        assert key in os.environ, f"{key} should be set in os.environ"
        assert os.environ[key] == git_commit_envvars[key]


def test_home_contains_gitconfig(
    set_home: pathlib.Path,
    gitconfig: pathlib.Path,
) -> None:
    """HOME should point to a directory containing .gitconfig."""
    home = os.environ.get("HOME", "")
    assert home, "HOME should be set"
    gitconfig_path = pathlib.Path(home) / ".gitconfig"
    assert gitconfig_path.exists(), (
        f"Expected .gitconfig at {gitconfig_path}, HOME={home}"
    )


@pytest.mark.skipif(not shutil.which("git"), reason="git is not available")
def test_git_commit_works_in_subprocess(
    tmp_path: pathlib.Path,
) -> None:
    """Git commit should succeed in a subprocess without global git identity.

    Simulates the Arch Linux clean build scenario where no ~/.gitconfig
    exists outside the test environment. The autouse setup fixture should
    have set the GIT_AUTHOR_* / GIT_COMMITTER_* env vars so that
    subprocesses inherit them.
    """
    repo_dir = tmp_path / "test_repo"
    repo_dir.mkdir()
    subprocess.run(["git", "init"], cwd=repo_dir, check=True, capture_output=True)
    (repo_dir / "file.txt").write_text("hello", encoding="utf-8")
    subprocess.run(
        ["git", "add", "file.txt"], cwd=repo_dir, check=True, capture_output=True
    )
    result = subprocess.run(
        ["git", "commit", "-m", "test commit"],
        cwd=repo_dir,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"git commit failed: {result.stderr}\n"
        "This simulates a clean build environment without global git identity."
    )


@pytest.mark.skipif(not shutil.which("git"), reason="git is not available")
def test_create_git_remote_repo_with_post_init(
    create_git_remote_repo: t.Any,
    git_commit_envvars: dict[str, str],
) -> None:
    """create_git_remote_repo with post_init commit should work.

    This is the factory call pattern used by tests that need a remote
    with an initial commit for clone/sync operations.
    """
    from libvcs.pytest_plugin import git_remote_repo_single_commit_post_init

    remote_path = create_git_remote_repo()
    # This call fails in clean builds if git identity isn't propagated
    git_remote_repo_single_commit_post_init(
        remote_repo_path=remote_path,
        env=git_commit_envvars,
    )
    assert remote_path.exists()


@pytest.mark.skipif(not shutil.which("git"), reason="git is not available")
def test_pytester_git_commit_in_isolated_run(
    pytester: pytest.Pytester,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: pathlib.Path,
) -> None:
    """Pytester-isolated test should be able to run git commit.

    Spawns an isolated pytest run that attempts a git commit, validating
    that the fixture infrastructure propagates correctly to subprocesses
    in a clean environment — the exact scenario that fails on Arch Linux.
    """
    monkeypatch.setenv("HOME", str(tmp_path))

    pytester.plugins = ["pytest_plugin"]
    pytester.makefile(
        ".ini",
        pytest=textwrap.dedent(
            """
[pytest]
addopts=-vv
        """.strip(),
        ),
    )
    pytester.makeconftest(
        textwrap.dedent(
            r"""
import pathlib
import pytest


@pytest.fixture(autouse=True)
def setup(
    request: pytest.FixtureRequest,
    monkeypatch: pytest.MonkeyPatch,
    gitconfig: pathlib.Path,
    set_home: pathlib.Path,
    git_commit_envvars: dict[str, str],
) -> None:
    for key, value in git_commit_envvars.items():
        monkeypatch.setenv(key, str(value))
    """,
        ),
    )
    tests_path = pytester.path / "tests"
    tests_path.mkdir()
    (tests_path / "test_git.py").write_text(
        textwrap.dedent(
            """\
import pathlib
import subprocess


def test_git_commit(tmp_path: pathlib.Path) -> None:
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    subprocess.run(["git", "init"], cwd=repo_dir, check=True, capture_output=True)
    (repo_dir / "f.txt").write_text("x", encoding="utf-8")
    subprocess.run(
        ["git", "add", "f.txt"], cwd=repo_dir, check=True, capture_output=True
    )
    result = subprocess.run(
        ["git", "commit", "-m", "test"],
        cwd=repo_dir,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"git commit failed: {result.stderr}"
""",
        ),
        encoding="utf-8",
    )

    result = pytester.runpytest(str(tests_path / "test_git.py"))
    result.assert_outcomes(passed=1)


@pytest.mark.skipif(not shutil.which("hg"), reason="hg is not available")
def test_hg_skip_marker_propagates(
    create_hg_remote_repo: t.Any,
) -> None:
    """Verify HG fixtures work when hg is available (skip otherwise).

    On systems without hg, this test is skipped. On systems with hg,
    it validates that the create_hg_remote_repo fixture works correctly.
    """
    remote_path = create_hg_remote_repo()
    assert remote_path.exists()
