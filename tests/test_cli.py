"""Test CLI entry point for for vcspull."""

from __future__ import annotations

import contextlib
import importlib
import json
import pathlib
import shutil
import sys
import typing as t

import pytest
import yaml

from vcspull.__about__ import __version__
from vcspull._internal.private_path import PrivatePath
from vcspull.cli import cli
from vcspull.cli._output import PlanAction, PlanEntry, PlanResult, PlanSummary
from vcspull.cli.sync import EXIT_ON_ERROR_MSG, NO_REPOS_FOR_TERM_MSG

sync_module = importlib.import_module("vcspull.cli.sync")

if t.TYPE_CHECKING:
    from typing import TypeAlias

    from libvcs.sync.git import GitSync

    ExpectedOutput: TypeAlias = str | list[str] | None


class SyncCLINonExistentRepo(t.NamedTuple):
    """Pytest fixture for vcspull syncing when repo does not exist."""

    # pytest internal: used for naming test
    test_id: str

    # test parameters
    sync_args: list[str]
    expected_exit_code: int
    expected_in_out: ExpectedOutput = None
    expected_not_in_out: ExpectedOutput = None
    expected_in_err: ExpectedOutput = None
    expected_not_in_err: ExpectedOutput = None


SYNC_CLI_EXISTENT_REPO_FIXTURES: list[SyncCLINonExistentRepo] = [
    SyncCLINonExistentRepo(
        test_id="exists",
        sync_args=["my_git_project"],
        expected_exit_code=0,
        expected_in_out="Already on 'master'",
        expected_not_in_out=NO_REPOS_FOR_TERM_MSG.format(name="my_git_repo"),
    ),
    SyncCLINonExistentRepo(
        test_id="non-existent-only",
        sync_args=["this_isnt_in_the_config"],
        expected_exit_code=0,
        expected_in_out=NO_REPOS_FOR_TERM_MSG.format(name="this_isnt_in_the_config"),
    ),
    SyncCLINonExistentRepo(
        test_id="non-existent-mixed",
        sync_args=["this_isnt_in_the_config", "my_git_project", "another"],
        expected_exit_code=0,
        expected_in_out=[
            NO_REPOS_FOR_TERM_MSG.format(name="this_isnt_in_the_config"),
            NO_REPOS_FOR_TERM_MSG.format(name="another"),
        ],
        expected_not_in_out=NO_REPOS_FOR_TERM_MSG.format(name="my_git_repo"),
    ),
]


@pytest.mark.parametrize(
    list(SyncCLINonExistentRepo._fields),
    SYNC_CLI_EXISTENT_REPO_FIXTURES,
    ids=[test.test_id for test in SYNC_CLI_EXISTENT_REPO_FIXTURES],
)
def test_sync_cli_filter_non_existent(
    tmp_path: pathlib.Path,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
    user_path: pathlib.Path,
    config_path: pathlib.Path,
    git_repo: GitSync,
    test_id: str,
    sync_args: list[str],
    expected_exit_code: int,
    expected_in_out: ExpectedOutput,
    expected_not_in_out: ExpectedOutput,
    expected_in_err: ExpectedOutput,
    expected_not_in_err: ExpectedOutput,
) -> None:
    """Tests vcspull syncing when repo does not exist."""
    config = {
        "~/github_projects/": {
            "my_git_project": {
                "url": f"git+file://{git_repo.path}",
                "remotes": {"test_remote": f"git+file://{git_repo.path}"},
            },
        },
    }
    yaml_config = config_path / ".vcspull.yaml"
    yaml_config_data = yaml.dump(config, default_flow_style=False)
    yaml_config.write_text(yaml_config_data, encoding="utf-8")

    monkeypatch.chdir(tmp_path)

    with contextlib.suppress(SystemExit):
        cli(["sync", *sync_args])

    captured = capsys.readouterr()
    output = "".join([*caplog.messages, captured.out, captured.err])

    if expected_in_out is not None:
        if isinstance(expected_in_out, str):
            expected_in_out = [expected_in_out]
        for needle in expected_in_out:
            assert needle in output

    if expected_not_in_out is not None:
        if isinstance(expected_not_in_out, str):
            expected_not_in_out = [expected_not_in_out]
        for needle in expected_not_in_out:
            assert needle not in output


class SyncFixture(t.NamedTuple):
    """Pytest fixture for vcspull sync."""

    # pytest internal: used for naming test
    test_id: str

    # test params
    sync_args: list[str]
    expected_exit_code: int
    expected_in_out: ExpectedOutput = None
    expected_not_in_out: ExpectedOutput = None
    expected_in_err: ExpectedOutput = None
    expected_not_in_err: ExpectedOutput = None


SYNC_REPO_FIXTURES: list[SyncFixture] = [
    # Empty (root command)
    SyncFixture(
        test_id="empty",
        sync_args=[],
        expected_exit_code=0,
        expected_in_out=["{sync", "positional arguments:"],
    ),
    # Version
    SyncFixture(
        test_id="--version",
        sync_args=["--version"],
        expected_exit_code=0,
        expected_in_out=[__version__, ", libvcs"],
    ),
    SyncFixture(
        test_id="-V",
        sync_args=["-V"],
        expected_exit_code=0,
        expected_in_out=[__version__, ", libvcs"],
    ),
    # Help
    SyncFixture(
        test_id="--help",
        sync_args=["--help"],
        expected_exit_code=0,
        expected_in_out=["{sync", "positional arguments:"],
    ),
    SyncFixture(
        test_id="-h",
        sync_args=["-h"],
        expected_exit_code=0,
        expected_in_out=["{sync", "positional arguments:"],
    ),
    # Sync
    SyncFixture(
        test_id="sync--empty",
        sync_args=["sync"],
        expected_exit_code=0,
        expected_in_out=["No repositories matched the criteria."],
    ),
    # Sync: Help
    SyncFixture(
        test_id="sync---help",
        sync_args=["sync", "--help"],
        expected_exit_code=0,
        expected_in_out=["filter", "--exit-on-error"],
        expected_not_in_out="--version",
    ),
    SyncFixture(
        test_id="sync--h",
        sync_args=["sync", "-h"],
        expected_exit_code=0,
        expected_in_out=["filter", "--exit-on-error"],
        expected_not_in_out="--version",
    ),
    # Sync: Repo terms
    SyncFixture(
        test_id="sync--one-repo-term",
        sync_args=["sync", "my_git_repo"],
        expected_exit_code=0,
        expected_in_out="my_git_repo",
    ),
]


class CLINegativeFixture(t.NamedTuple):
    """Fixture for CLI negative flow validation."""

    test_id: str
    cli_args: list[str]
    scenario: t.Literal["discover-non-dict-config", "status-missing-git"]
    expected_log_fragment: str | None
    expected_stdout_fragment: str | None


CLI_NEGATIVE_FIXTURES: list[CLINegativeFixture] = [
    CLINegativeFixture(
        test_id="discover-invalid-config",
        cli_args=["discover"],
        scenario="discover-non-dict-config",
        expected_log_fragment="not a valid YAML dictionary",
        expected_stdout_fragment=None,
    ),
    CLINegativeFixture(
        test_id="status-missing-git",
        cli_args=["status", "--detailed"],
        scenario="status-missing-git",
        expected_log_fragment=None,
        expected_stdout_fragment="Summary:",
    ),
]


@pytest.mark.parametrize(
    list(SyncFixture._fields),
    SYNC_REPO_FIXTURES,
    ids=[test.test_id for test in SYNC_REPO_FIXTURES],
)
def test_sync(
    tmp_path: pathlib.Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    user_path: pathlib.Path,
    config_path: pathlib.Path,
    git_repo: GitSync,
    test_id: str,
    sync_args: list[str],
    expected_exit_code: int,
    expected_in_out: ExpectedOutput,
    expected_not_in_out: ExpectedOutput,
    expected_in_err: ExpectedOutput,
    expected_not_in_err: ExpectedOutput,
) -> None:
    """Tests for vcspull sync."""
    config = {
        "~/github_projects/": {
            "my_git_repo": {
                "url": f"git+file://{git_repo.path}",
                "remotes": {"test_remote": f"git+file://{git_repo.path}"},
            },
            "broken_repo": {
                "url": f"git+file://{git_repo.path}",
                "remotes": {"test_remote": "git+file://non-existent-remote"},
            },
        },
    }
    yaml_config = config_path / ".vcspull.yaml"
    yaml_config_data = yaml.dump(config, default_flow_style=False)
    yaml_config.write_text(yaml_config_data, encoding="utf-8")

    # CLI can sync
    with contextlib.suppress(SystemExit):
        cli(sync_args)

    result = capsys.readouterr()
    output = "".join(list(result.out if expected_exit_code == 0 else result.err))

    if expected_in_out is not None:
        if isinstance(expected_in_out, str):
            expected_in_out = [expected_in_out]
        for needle in expected_in_out:
            assert needle in output

    if expected_not_in_out is not None:
        if isinstance(expected_not_in_out, str):
            expected_not_in_out = [expected_not_in_out]
        for needle in expected_not_in_out:
            assert needle not in output


class SyncBrokenFixture(t.NamedTuple):
    """Tests for vcspull  sync when something breaks."""

    # pytest internal: used for naming test
    test_id: str

    # test params
    sync_args: list[str]
    expected_exit_code: int
    expected_in_out: ExpectedOutput = None
    expected_not_in_out: ExpectedOutput = None
    expected_in_err: ExpectedOutput = None
    expected_not_in_err: ExpectedOutput = None


SYNC_BROKEN_REPO_FIXTURES: list[SyncBrokenFixture] = [
    SyncBrokenFixture(
        test_id="normal-checkout",
        sync_args=["my_git_repo"],
        expected_exit_code=0,
        expected_in_out="Already on 'master'",
    ),
    SyncBrokenFixture(
        test_id="normal-checkout--exit-on-error",
        sync_args=["my_git_repo", "--exit-on-error"],
        expected_exit_code=0,
        expected_in_out="Already on 'master'",
    ),
    SyncBrokenFixture(
        test_id="normal-checkout--x",
        sync_args=["my_git_repo", "-x"],
        expected_exit_code=0,
        expected_in_out="Already on 'master'",
    ),
    SyncBrokenFixture(
        test_id="normal-first-broken",
        sync_args=["my_git_repo_not_found", "my_git_repo"],
        expected_exit_code=0,
        expected_not_in_out=EXIT_ON_ERROR_MSG,
    ),
    SyncBrokenFixture(
        test_id="normal-last-broken",
        sync_args=["my_git_repo", "my_git_repo_not_found"],
        expected_exit_code=0,
        expected_not_in_out=EXIT_ON_ERROR_MSG,
    ),
    SyncBrokenFixture(
        test_id="exit-on-error--exit-on-error-first-broken",
        sync_args=["my_git_repo_not_found", "my_git_repo", "--exit-on-error"],
        expected_exit_code=1,
        expected_in_err=EXIT_ON_ERROR_MSG,
    ),
    SyncBrokenFixture(
        test_id="exit-on-error--x-first-broken",
        sync_args=["my_git_repo_not_found", "my_git_repo", "-x"],
        expected_exit_code=1,
        expected_in_err=EXIT_ON_ERROR_MSG,
        expected_not_in_out="master",
    ),
    #
    # Verify ordering
    #
    SyncBrokenFixture(
        test_id="exit-on-error--exit-on-error-last-broken",
        sync_args=["my_git_repo", "my_git_repo_not_found", "-x"],
        expected_exit_code=1,
        expected_in_out="Already on 'master'",
        expected_in_err=EXIT_ON_ERROR_MSG,
    ),
    SyncBrokenFixture(
        test_id="exit-on-error--x-last-item",
        sync_args=["my_git_repo", "my_git_repo_not_found", "--exit-on-error"],
        expected_exit_code=1,
        expected_in_out="Already on 'master'",
        expected_in_err=EXIT_ON_ERROR_MSG,
    ),
]


@pytest.mark.parametrize(
    list(SyncBrokenFixture._fields),
    SYNC_BROKEN_REPO_FIXTURES,
    ids=[test.test_id for test in SYNC_BROKEN_REPO_FIXTURES],
)
def test_sync_broken(
    tmp_path: pathlib.Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    user_path: pathlib.Path,
    config_path: pathlib.Path,
    git_repo: GitSync,
    test_id: str,
    sync_args: list[str],
    expected_exit_code: int,
    expected_in_out: ExpectedOutput,
    expected_not_in_out: ExpectedOutput,
    expected_in_err: ExpectedOutput,
    expected_not_in_err: ExpectedOutput,
) -> None:
    """Tests for syncing in vcspull when unexpected error occurs."""
    github_projects = user_path / "github_projects"
    my_git_repo = github_projects / "my_git_repo"
    if my_git_repo.is_dir():
        shutil.rmtree(my_git_repo)

    config = {
        "~/github_projects/": {
            "my_git_repo": {
                "url": f"git+file://{git_repo.path}",
                "remotes": {"test_remote": f"git+file://{git_repo.path}"},
            },
            "my_git_repo_not_found": {
                "url": "git+file:///dev/null",
            },
        },
    }
    yaml_config = config_path / ".vcspull.yaml"
    yaml_config_data = yaml.dump(config, default_flow_style=False)
    yaml_config.write_text(yaml_config_data, encoding="utf-8")

    # CLI can sync
    assert isinstance(sync_args, list)

    with contextlib.suppress(SystemExit):
        cli(["sync", *sync_args])

    result = capsys.readouterr()
    out = "".join(list(result.out))
    err = "".join(list(result.err))

    if expected_in_out is not None:
        if isinstance(expected_in_out, str):
            expected_in_out = [expected_in_out]
        for needle in expected_in_out:
            assert needle in out

    if expected_not_in_out is not None:
        if isinstance(expected_not_in_out, str):
            expected_not_in_out = [expected_not_in_out]
        for needle in expected_not_in_out:
            assert needle not in out

    if expected_in_err is not None:
        if isinstance(expected_in_err, str):
            expected_in_err = [expected_in_err]
        for needle in expected_in_err:
            assert needle in err

    if expected_not_in_err is not None:
        if isinstance(expected_not_in_err, str):
            expected_not_in_err = [expected_not_in_err]
        for needle in expected_not_in_err:
            assert needle not in err


class SyncErroredRepoFixture(t.NamedTuple):
    """Tests for vcspull sync when a git operation fails silently in libvcs."""

    test_id: str
    sync_args: list[str]
    expected_in_out: ExpectedOutput = None
    expected_not_in_out: ExpectedOutput = None
    expected_in_err: ExpectedOutput = None
    expected_not_in_err: ExpectedOutput = None


SYNC_ERRORED_REPO_FIXTURES: list[SyncErroredRepoFixture] = [
    SyncErroredRepoFixture(
        test_id="fetch-failure-shows-failed",
        sync_args=["my_errored_repo"],
        expected_in_out="Failed syncing",
        expected_not_in_out="Synced my_errored_repo",
    ),
    SyncErroredRepoFixture(
        test_id="fetch-failure-exit-on-error",
        sync_args=["my_errored_repo", "--exit-on-error"],
        expected_in_err=EXIT_ON_ERROR_MSG,
    ),
    SyncErroredRepoFixture(
        test_id="mixed-good-and-fetch-failure",
        sync_args=["my_good_repo", "my_errored_repo"],
        expected_in_out=["Synced my_good_repo", "Failed syncing my_errored_repo"],
    ),
    SyncErroredRepoFixture(
        test_id="fetch-failure-summary-line",
        sync_args=["my_errored_repo"],
        expected_in_out=[
            "Failed syncing",
            "Summary:",
            "1 repos",
            "0 synced",
            "1 failed",
        ],
    ),
    SyncErroredRepoFixture(
        test_id="mixed-good-and-fetch-failure-summary-line",
        sync_args=["my_good_repo", "my_errored_repo"],
        expected_in_out=[
            "Synced my_good_repo",
            "Failed syncing my_errored_repo",
            "Summary:",
            "2 repos",
            "1 synced",
            "1 failed",
        ],
    ),
]


@pytest.mark.parametrize(
    list(SyncErroredRepoFixture._fields),
    SYNC_ERRORED_REPO_FIXTURES,
    ids=[test.test_id for test in SYNC_ERRORED_REPO_FIXTURES],
)
def test_sync_errored_repo(
    tmp_path: pathlib.Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    user_path: pathlib.Path,
    config_path: pathlib.Path,
    git_repo: GitSync,
    test_id: str,
    sync_args: list[str],
    expected_in_out: ExpectedOutput,
    expected_not_in_out: ExpectedOutput,
    expected_in_err: ExpectedOutput,
    expected_not_in_err: ExpectedOutput,
) -> None:
    """Tests for syncing in vcspull when git operations fail (e.g. fetch error).

    Unlike test_sync_broken which tests repos that can't be cloned at all,
    this tests repos that clone successfully but then fail on subsequent sync
    due to the remote becoming unreachable. Before SyncResult, these failures
    were silently swallowed and reported as successful syncs.
    """
    github_projects = user_path / "github_projects"

    from libvcs._internal.run import run as libvcs_run

    # git_repo comes from libvcs pytest plugin — already has a valid remote
    good_remote_url = f"git+file://{git_repo.path}"

    # Create a bare remote for the errored repo, with an initial commit
    # so that the clone + update_repo cycle succeeds on first sync.
    errored_remote_dir = tmp_path / "errored_remote"
    errored_remote_dir.mkdir()
    libvcs_run(["git", "init", "--bare"], cwd=errored_remote_dir)

    # Bootstrap the bare remote with a commit via a temporary clone
    bootstrap_dir = tmp_path / "bootstrap"
    libvcs_run(
        ["git", "clone", str(errored_remote_dir), str(bootstrap_dir)],
    )
    (bootstrap_dir / "initial.txt").write_text("init", encoding="utf-8")
    libvcs_run(["git", "add", "initial.txt"], cwd=bootstrap_dir)
    libvcs_run(["git", "commit", "-m", "initial commit"], cwd=bootstrap_dir)
    libvcs_run(["git", "push", "origin", "master"], cwd=bootstrap_dir)

    # Add a second commit and push so we can create a "behind" state
    (bootstrap_dir / "second.txt").write_text("second", encoding="utf-8")
    libvcs_run(["git", "add", "second.txt"], cwd=bootstrap_dir)
    libvcs_run(["git", "commit", "-m", "second commit"], cwd=bootstrap_dir)
    libvcs_run(["git", "push", "origin", "master"], cwd=bootstrap_dir)
    shutil.rmtree(bootstrap_dir)

    errored_remote_url = f"git+file://{errored_remote_dir}"

    config: dict[str, dict[str, dict[str, t.Any]]] = {
        "~/github_projects/": {
            "my_good_repo": {
                "url": good_remote_url,
                "remotes": {"origin": good_remote_url},
            },
            "my_errored_repo": {
                "url": errored_remote_url,
                "remotes": {"origin": errored_remote_url},
            },
        },
    }
    yaml_config = config_path / ".vcspull.yaml"
    yaml_config.write_text(
        yaml.dump(config, default_flow_style=False),
        encoding="utf-8",
    )

    monkeypatch.chdir(tmp_path)

    # First sync: clone both repos successfully
    for repo_name in ("my_good_repo", "my_errored_repo"):
        repo_dir = github_projects / repo_name
        if repo_dir.exists():
            shutil.rmtree(repo_dir)
    with contextlib.suppress(SystemExit):
        cli(["sync", "my_good_repo", "my_errored_repo"])
    capsys.readouterr()  # Discard initial sync output

    # Reset the errored repo's local clone back one commit to create
    # a "behind" state that will trigger a fetch on the next sync.
    errored_repo_dir = github_projects / "my_errored_repo"
    libvcs_run(["git", "reset", "--hard", "HEAD^"], cwd=errored_repo_dir)

    # Delete the errored remote to cause fetch failure on next sync
    shutil.rmtree(errored_remote_dir)

    # Second sync: should show failure for errored repo
    with contextlib.suppress(SystemExit):
        cli(["sync", *sync_args])

    result = capsys.readouterr()
    out = "".join(list(result.out))
    err = "".join(list(result.err))

    if expected_in_out is not None:
        if isinstance(expected_in_out, str):
            expected_in_out = [expected_in_out]
        for needle in expected_in_out:
            assert needle in out, f"Expected {needle!r} in stdout: {out!r}"

    if expected_not_in_out is not None:
        if isinstance(expected_not_in_out, str):
            expected_not_in_out = [expected_not_in_out]
        for needle in expected_not_in_out:
            assert needle not in out, f"Did not expect {needle!r} in stdout: {out!r}"

    if expected_in_err is not None:
        if isinstance(expected_in_err, str):
            expected_in_err = [expected_in_err]
        for needle in expected_in_err:
            assert needle in err, f"Expected {needle!r} in stderr: {err!r}"

    if expected_not_in_err is not None:
        if isinstance(expected_not_in_err, str):
            expected_not_in_err = [expected_not_in_err]
        for needle in expected_not_in_err:
            assert needle not in err, f"Did not expect {needle!r} in stderr: {err!r}"


class SyncRevBranchMismatchFixture(t.NamedTuple):
    """Tests for vcspull sync when git rev references a non-existent branch."""

    test_id: str
    sync_args: list[str]
    expected_in_out: ExpectedOutput = None
    expected_not_in_out: ExpectedOutput = None
    expected_in_err: ExpectedOutput = None
    expected_not_in_err: ExpectedOutput = None


SYNC_REV_BRANCH_MISMATCH_FIXTURES: list[SyncRevBranchMismatchFixture] = [
    SyncRevBranchMismatchFixture(
        test_id="rev-master-on-main-only-remote",
        sync_args=["my_repo"],
        expected_in_out="Failed syncing",
        expected_not_in_out="Synced my_repo",
    ),
    SyncRevBranchMismatchFixture(
        test_id="rev-master-on-main-only-remote--exit-on-error",
        sync_args=["my_repo", "--exit-on-error"],
        expected_in_err=EXIT_ON_ERROR_MSG,
    ),
]


@pytest.mark.parametrize(
    list(SyncRevBranchMismatchFixture._fields),
    SYNC_REV_BRANCH_MISMATCH_FIXTURES,
    ids=[test.test_id for test in SYNC_REV_BRANCH_MISMATCH_FIXTURES],
)
def test_sync_rev_branch_mismatch(
    tmp_path: pathlib.Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    user_path: pathlib.Path,
    config_path: pathlib.Path,
    test_id: str,
    sync_args: list[str],
    expected_in_out: ExpectedOutput,
    expected_not_in_out: ExpectedOutput,
    expected_in_err: ExpectedOutput,
    expected_not_in_err: ExpectedOutput,
) -> None:
    """Tests for syncing when git rev references a branch that doesn't exist.

    Creates a bare remote with only a 'main' branch, then configures vcspull
    with rev: master. The checkout of 'master' fails because the branch
    doesn't exist on the remote, exercising the checkout error path in
    GitSync.update_repo().
    """
    from libvcs._internal.run import run as libvcs_run

    # Create a bare remote with only a 'main' branch (no 'master')
    remote_dir = tmp_path / "main_only_remote"
    remote_dir.mkdir()
    libvcs_run(["git", "init", "--bare", "--initial-branch=main"], cwd=remote_dir)

    # Bootstrap the bare remote with a commit via a temporary clone
    bootstrap_dir = tmp_path / "bootstrap"
    libvcs_run(["git", "clone", str(remote_dir), str(bootstrap_dir)])
    (bootstrap_dir / "initial.txt").write_text("init", encoding="utf-8")
    libvcs_run(["git", "add", "initial.txt"], cwd=bootstrap_dir)
    libvcs_run(["git", "commit", "-m", "initial commit"], cwd=bootstrap_dir)
    libvcs_run(["git", "push", "origin", "main"], cwd=bootstrap_dir)
    shutil.rmtree(bootstrap_dir)

    github_projects = user_path / "github_projects"
    config: dict[str, dict[str, dict[str, t.Any]]] = {
        "~/github_projects/": {
            "my_repo": {
                "url": f"git+file://{remote_dir}",
                "remotes": {"origin": f"git+file://{remote_dir}"},
                "rev": "master",
            },
        },
    }
    yaml_config = config_path / ".vcspull.yaml"
    yaml_config.write_text(
        yaml.dump(config, default_flow_style=False),
        encoding="utf-8",
    )

    monkeypatch.chdir(tmp_path)

    # Clean up any prior clone
    repo_dir = github_projects / "my_repo"
    if repo_dir.exists():
        shutil.rmtree(repo_dir)

    # Single sync: clone gets 'main', then update_repo() tries
    # git checkout master → fails (no such branch)
    with contextlib.suppress(SystemExit):
        cli(["sync", *sync_args])

    result = capsys.readouterr()
    out = "".join(list(result.out))
    err = "".join(list(result.err))

    if expected_in_out is not None:
        if isinstance(expected_in_out, str):
            expected_in_out = [expected_in_out]
        for needle in expected_in_out:
            assert needle in out, f"Expected {needle!r} in stdout: {out!r}"

    if expected_not_in_out is not None:
        if isinstance(expected_not_in_out, str):
            expected_not_in_out = [expected_not_in_out]
        for needle in expected_not_in_out:
            assert needle not in out, f"Did not expect {needle!r} in stdout: {out!r}"

    if expected_in_err is not None:
        if isinstance(expected_in_err, str):
            expected_in_err = [expected_in_err]
        for needle in expected_in_err:
            assert needle in err, f"Expected {needle!r} in stderr: {err!r}"

    if expected_not_in_err is not None:
        if isinstance(expected_not_in_err, str):
            expected_not_in_err = [expected_not_in_err]
        for needle in expected_not_in_err:
            assert needle not in err, f"Did not expect {needle!r} in stderr: {err!r}"


class SyncErroredSvnRepoFixture(t.NamedTuple):
    """Tests for vcspull sync when an SVN operation fails."""

    test_id: str
    sync_args: list[str]
    expected_in_out: ExpectedOutput = None
    expected_not_in_out: ExpectedOutput = None
    expected_in_err: ExpectedOutput = None
    expected_not_in_err: ExpectedOutput = None


SYNC_ERRORED_SVN_REPO_FIXTURES: list[SyncErroredSvnRepoFixture] = [
    SyncErroredSvnRepoFixture(
        test_id="svn-deleted-remote-shows-failed",
        sync_args=["my_svn_repo"],
        expected_in_out="Failed syncing",
        expected_not_in_out="Synced my_svn_repo",
    ),
    SyncErroredSvnRepoFixture(
        test_id="svn-deleted-remote-exit-on-error",
        sync_args=["my_svn_repo", "--exit-on-error"],
        expected_in_err=EXIT_ON_ERROR_MSG,
    ),
]


@pytest.mark.skipif(not shutil.which("svn"), reason="svn not installed")
@pytest.mark.skipif(not shutil.which("svnadmin"), reason="svnadmin not installed")
@pytest.mark.parametrize(
    list(SyncErroredSvnRepoFixture._fields),
    SYNC_ERRORED_SVN_REPO_FIXTURES,
    ids=[test.test_id for test in SYNC_ERRORED_SVN_REPO_FIXTURES],
)
def test_sync_errored_svn_repo(
    tmp_path: pathlib.Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    user_path: pathlib.Path,
    config_path: pathlib.Path,
    test_id: str,
    sync_args: list[str],
    expected_in_out: ExpectedOutput,
    expected_not_in_out: ExpectedOutput,
    expected_in_err: ExpectedOutput,
    expected_not_in_err: ExpectedOutput,
) -> None:
    """Tests for syncing in vcspull when SVN remote becomes unavailable.

    Creates a local SVN repository, syncs (checkout) successfully,
    then deletes the SVN repository and verifies that the next sync
    reports the failure instead of silently succeeding.
    """
    import subprocess

    # Create an SVN repository
    svn_remote_dir = tmp_path / "svn_remote"
    subprocess.run(
        ["svnadmin", "create", str(svn_remote_dir)],
        check=True,
        capture_output=True,
    )

    # Import initial content into the SVN repo
    import_dir = tmp_path / "svn_import"
    import_dir.mkdir()
    (import_dir / "initial.txt").write_text("init", encoding="utf-8")
    subprocess.run(
        [
            "svn",
            "import",
            str(import_dir),
            f"file://{svn_remote_dir}/trunk",
            "-m",
            "initial import",
        ],
        check=True,
        capture_output=True,
    )
    shutil.rmtree(import_dir)

    svn_url = f"svn+file://{svn_remote_dir}/trunk"

    github_projects = user_path / "github_projects"
    config: dict[str, dict[str, dict[str, t.Any]]] = {
        "~/github_projects/": {
            "my_svn_repo": {
                "url": svn_url,
            },
        },
    }
    yaml_config = config_path / ".vcspull.yaml"
    yaml_config.write_text(
        yaml.dump(config, default_flow_style=False),
        encoding="utf-8",
    )

    monkeypatch.chdir(tmp_path)

    # Clean up any prior checkout
    repo_dir = github_projects / "my_svn_repo"
    if repo_dir.exists():
        shutil.rmtree(repo_dir)

    # First sync: svn checkout succeeds
    with contextlib.suppress(SystemExit):
        cli(["sync", "my_svn_repo"])
    capsys.readouterr()  # Discard initial sync output

    # Delete the SVN remote to cause failure on next sync
    shutil.rmtree(svn_remote_dir)

    # Second sync: should show failure
    with contextlib.suppress(SystemExit):
        cli(["sync", *sync_args])

    result = capsys.readouterr()
    out = "".join(list(result.out))
    err = "".join(list(result.err))

    if expected_in_out is not None:
        if isinstance(expected_in_out, str):
            expected_in_out = [expected_in_out]
        for needle in expected_in_out:
            assert needle in out, f"Expected {needle!r} in stdout: {out!r}"

    if expected_not_in_out is not None:
        if isinstance(expected_not_in_out, str):
            expected_not_in_out = [expected_not_in_out]
        for needle in expected_not_in_out:
            assert needle not in out, f"Did not expect {needle!r} in stdout: {out!r}"

    if expected_in_err is not None:
        if isinstance(expected_in_err, str):
            expected_in_err = [expected_in_err]
        for needle in expected_in_err:
            assert needle in err, f"Expected {needle!r} in stderr: {err!r}"

    if expected_not_in_err is not None:
        if isinstance(expected_not_in_err, str):
            expected_not_in_err = [expected_not_in_err]
        for needle in expected_not_in_err:
            assert needle not in err, f"Did not expect {needle!r} in stderr: {err!r}"


class SyncErroredHgRepoFixture(t.NamedTuple):
    """Tests for vcspull sync when an HG operation fails."""

    test_id: str
    sync_args: list[str]
    expected_in_out: ExpectedOutput = None
    expected_not_in_out: ExpectedOutput = None
    expected_in_err: ExpectedOutput = None
    expected_not_in_err: ExpectedOutput = None


SYNC_ERRORED_HG_REPO_FIXTURES: list[SyncErroredHgRepoFixture] = [
    SyncErroredHgRepoFixture(
        test_id="hg-deleted-remote-shows-failed",
        sync_args=["my_hg_repo"],
        expected_in_out="Failed syncing",
        expected_not_in_out="Synced my_hg_repo",
    ),
    SyncErroredHgRepoFixture(
        test_id="hg-deleted-remote-exit-on-error",
        sync_args=["my_hg_repo", "--exit-on-error"],
        expected_in_err=EXIT_ON_ERROR_MSG,
    ),
]


@pytest.mark.skipif(not shutil.which("hg"), reason="hg not installed")
@pytest.mark.parametrize(
    list(SyncErroredHgRepoFixture._fields),
    SYNC_ERRORED_HG_REPO_FIXTURES,
    ids=[test.test_id for test in SYNC_ERRORED_HG_REPO_FIXTURES],
)
def test_sync_errored_hg_repo(
    tmp_path: pathlib.Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    user_path: pathlib.Path,
    config_path: pathlib.Path,
    test_id: str,
    sync_args: list[str],
    expected_in_out: ExpectedOutput,
    expected_not_in_out: ExpectedOutput,
    expected_in_err: ExpectedOutput,
    expected_not_in_err: ExpectedOutput,
) -> None:
    """Tests for syncing in vcspull when HG remote becomes unavailable.

    Creates a local Mercurial repository, syncs (clone) successfully,
    then deletes the repository and verifies that the next sync
    reports the failure instead of silently succeeding.
    """
    import subprocess

    monkeypatch.setenv("HGUSER", "Test User <test@test.com>")

    # Create an HG repository
    hg_remote_dir = tmp_path / "hg_remote"
    hg_remote_dir.mkdir()
    subprocess.run(["hg", "init"], cwd=hg_remote_dir, check=True, capture_output=True)

    # Add initial content
    (hg_remote_dir / "initial.txt").write_text("init", encoding="utf-8")
    subprocess.run(
        ["hg", "add", "initial.txt"],
        cwd=hg_remote_dir,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["hg", "commit", "-m", "initial commit"],
        cwd=hg_remote_dir,
        check=True,
        capture_output=True,
    )

    hg_url = f"hg+file://{hg_remote_dir}"

    github_projects = user_path / "github_projects"
    config: dict[str, dict[str, dict[str, t.Any]]] = {
        "~/github_projects/": {
            "my_hg_repo": {
                "url": hg_url,
            },
        },
    }
    yaml_config = config_path / ".vcspull.yaml"
    yaml_config.write_text(
        yaml.dump(config, default_flow_style=False),
        encoding="utf-8",
    )

    monkeypatch.chdir(tmp_path)

    # Clean up any prior clone
    repo_dir = github_projects / "my_hg_repo"
    if repo_dir.exists():
        shutil.rmtree(repo_dir)

    # First sync: hg clone succeeds
    with contextlib.suppress(SystemExit):
        cli(["sync", "my_hg_repo"])
    capsys.readouterr()  # Discard initial sync output

    # Delete the HG remote to cause failure on next sync
    shutil.rmtree(hg_remote_dir)

    # Second sync: should show failure
    with contextlib.suppress(SystemExit):
        cli(["sync", *sync_args])

    result = capsys.readouterr()
    out = "".join(list(result.out))
    err = "".join(list(result.err))

    if expected_in_out is not None:
        if isinstance(expected_in_out, str):
            expected_in_out = [expected_in_out]
        for needle in expected_in_out:
            assert needle in out, f"Expected {needle!r} in stdout: {out!r}"

    if expected_not_in_out is not None:
        if isinstance(expected_not_in_out, str):
            expected_not_in_out = [expected_not_in_out]
        for needle in expected_not_in_out:
            assert needle not in out, f"Did not expect {needle!r} in stdout: {out!r}"

    if expected_in_err is not None:
        if isinstance(expected_in_err, str):
            expected_in_err = [expected_in_err]
        for needle in expected_in_err:
            assert needle in err, f"Expected {needle!r} in stderr: {err!r}"

    if expected_not_in_err is not None:
        if isinstance(expected_not_in_err, str):
            expected_not_in_err = [expected_not_in_err]
        for needle in expected_not_in_err:
            assert needle not in err, f"Did not expect {needle!r} in stderr: {err!r}"


SYNC_ALL_FAIL_FIXTURES: list[SyncErroredRepoFixture] = [
    SyncErroredRepoFixture(
        test_id="two-git-repos-all-fail",
        sync_args=["my_errored_repo_a", "my_errored_repo_b"],
        expected_in_out=[
            "Failed syncing my_errored_repo_a",
            "Failed syncing my_errored_repo_b",
            "0 synced",
            "2 failed",
        ],
        expected_not_in_out="Synced",
    ),
    SyncErroredRepoFixture(
        test_id="two-git-repos-all-fail-exit-on-error",
        sync_args=["my_errored_repo_a", "my_errored_repo_b", "--exit-on-error"],
        expected_in_out="Failed syncing my_errored_repo_a",
        expected_not_in_out="my_errored_repo_b",
        expected_in_err=EXIT_ON_ERROR_MSG,
    ),
]


@pytest.mark.parametrize(
    list(SyncErroredRepoFixture._fields),
    SYNC_ALL_FAIL_FIXTURES,
    ids=[test.test_id for test in SYNC_ALL_FAIL_FIXTURES],
)
def test_sync_all_repos_fail(
    tmp_path: pathlib.Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    user_path: pathlib.Path,
    config_path: pathlib.Path,
    test_id: str,
    sync_args: list[str],
    expected_in_out: ExpectedOutput,
    expected_not_in_out: ExpectedOutput,
    expected_in_err: ExpectedOutput,
    expected_not_in_err: ExpectedOutput,
) -> None:
    """Tests for syncing when every repo in a multi-repo sync fails.

    Creates two bare git remotes, clones both successfully, resets both
    local clones behind, then deletes both remotes so every fetch fails.
    """
    from libvcs._internal.run import run as libvcs_run

    github_projects = user_path / "github_projects"

    # Create two bare remotes, each with two commits
    remote_dirs: dict[str, pathlib.Path] = {}
    for suffix in ("a", "b"):
        remote_dir = tmp_path / f"errored_remote_{suffix}"
        remote_dir.mkdir()
        libvcs_run(["git", "init", "--bare"], cwd=remote_dir)

        bootstrap_dir = tmp_path / f"bootstrap_{suffix}"
        libvcs_run(["git", "clone", str(remote_dir), str(bootstrap_dir)])
        (bootstrap_dir / "initial.txt").write_text("init", encoding="utf-8")
        libvcs_run(["git", "add", "initial.txt"], cwd=bootstrap_dir)
        libvcs_run(["git", "commit", "-m", "initial commit"], cwd=bootstrap_dir)
        libvcs_run(["git", "push", "origin", "master"], cwd=bootstrap_dir)

        (bootstrap_dir / "second.txt").write_text("second", encoding="utf-8")
        libvcs_run(["git", "add", "second.txt"], cwd=bootstrap_dir)
        libvcs_run(["git", "commit", "-m", "second commit"], cwd=bootstrap_dir)
        libvcs_run(["git", "push", "origin", "master"], cwd=bootstrap_dir)
        shutil.rmtree(bootstrap_dir)

        remote_dirs[suffix] = remote_dir

    config: dict[str, dict[str, dict[str, t.Any]]] = {
        "~/github_projects/": {
            "my_errored_repo_a": {
                "url": f"git+file://{remote_dirs['a']}",
                "remotes": {"origin": f"git+file://{remote_dirs['a']}"},
            },
            "my_errored_repo_b": {
                "url": f"git+file://{remote_dirs['b']}",
                "remotes": {"origin": f"git+file://{remote_dirs['b']}"},
            },
        },
    }
    yaml_config = config_path / ".vcspull.yaml"
    yaml_config.write_text(
        yaml.dump(config, default_flow_style=False),
        encoding="utf-8",
    )

    monkeypatch.chdir(tmp_path)

    # Clean up any prior clones
    for repo_name in ("my_errored_repo_a", "my_errored_repo_b"):
        repo_dir = github_projects / repo_name
        if repo_dir.exists():
            shutil.rmtree(repo_dir)

    # First sync: clone both repos successfully
    with contextlib.suppress(SystemExit):
        cli(["sync", "my_errored_repo_a", "my_errored_repo_b"])
    capsys.readouterr()  # Discard initial sync output

    # Reset both local clones back one commit to create "behind" state
    for repo_name in ("my_errored_repo_a", "my_errored_repo_b"):
        repo_dir = github_projects / repo_name
        libvcs_run(["git", "reset", "--hard", "HEAD^"], cwd=repo_dir)

    # Delete both remotes to cause fetch failure on next sync
    for remote_dir in remote_dirs.values():
        shutil.rmtree(remote_dir)

    # Second sync: both should fail
    with contextlib.suppress(SystemExit):
        cli(["sync", *sync_args])

    result = capsys.readouterr()
    out = "".join(list(result.out))
    err = "".join(list(result.err))

    if expected_in_out is not None:
        if isinstance(expected_in_out, str):
            expected_in_out = [expected_in_out]
        for needle in expected_in_out:
            assert needle in out, f"Expected {needle!r} in stdout: {out!r}"

    if expected_not_in_out is not None:
        if isinstance(expected_not_in_out, str):
            expected_not_in_out = [expected_not_in_out]
        for needle in expected_not_in_out:
            assert needle not in out, f"Did not expect {needle!r} in stdout: {out!r}"

    if expected_in_err is not None:
        if isinstance(expected_in_err, str):
            expected_in_err = [expected_in_err]
        for needle in expected_in_err:
            assert needle in err, f"Expected {needle!r} in stderr: {err!r}"

    if expected_not_in_err is not None:
        if isinstance(expected_not_in_err, str):
            expected_not_in_err = [expected_not_in_err]
        for needle in expected_not_in_err:
            assert needle not in err, f"Did not expect {needle!r} in stderr: {err!r}"


SYNC_CROSS_VCS_MIXED_FIXTURES: list[SyncErroredRepoFixture] = [
    SyncErroredRepoFixture(
        test_id="git-ok-svn-fails",
        sync_args=["my_git_repo", "my_svn_repo"],
        expected_in_out=[
            "Synced my_git_repo",
            "Failed syncing my_svn_repo",
            "1 synced",
            "1 failed",
        ],
    ),
    SyncErroredRepoFixture(
        test_id="git-ok-svn-fails-exit-on-error",
        sync_args=["my_svn_repo", "my_git_repo", "--exit-on-error"],
        expected_in_out="Failed syncing my_svn_repo",
        expected_not_in_out="Synced my_git_repo",
        expected_in_err=EXIT_ON_ERROR_MSG,
    ),
]


@pytest.mark.skipif(not shutil.which("svn"), reason="svn not installed")
@pytest.mark.skipif(not shutil.which("svnadmin"), reason="svnadmin not installed")
@pytest.mark.parametrize(
    list(SyncErroredRepoFixture._fields),
    SYNC_CROSS_VCS_MIXED_FIXTURES,
    ids=[test.test_id for test in SYNC_CROSS_VCS_MIXED_FIXTURES],
)
def test_sync_cross_vcs_mixed_failure(
    tmp_path: pathlib.Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    user_path: pathlib.Path,
    config_path: pathlib.Path,
    git_repo: GitSync,
    test_id: str,
    sync_args: list[str],
    expected_in_out: ExpectedOutput,
    expected_not_in_out: ExpectedOutput,
    expected_in_err: ExpectedOutput,
    expected_not_in_err: ExpectedOutput,
) -> None:
    """Tests for syncing when git succeeds but SVN fails in the same run.

    Uses the libvcs git_repo fixture for the good repo, creates an SVN remote
    that gets deleted after initial sync to trigger failure.
    """
    import subprocess

    github_projects = user_path / "github_projects"
    good_git_url = f"git+file://{git_repo.path}"

    # Create an SVN repository
    svn_remote_dir = tmp_path / "svn_remote"
    subprocess.run(
        ["svnadmin", "create", str(svn_remote_dir)],
        check=True,
        capture_output=True,
    )

    import_dir = tmp_path / "svn_import"
    import_dir.mkdir()
    (import_dir / "initial.txt").write_text("init", encoding="utf-8")
    subprocess.run(
        [
            "svn",
            "import",
            str(import_dir),
            f"file://{svn_remote_dir}/trunk",
            "-m",
            "initial import",
        ],
        check=True,
        capture_output=True,
    )
    shutil.rmtree(import_dir)

    svn_url = f"svn+file://{svn_remote_dir}/trunk"

    config: dict[str, dict[str, dict[str, t.Any]]] = {
        "~/github_projects/": {
            "my_git_repo": {
                "url": good_git_url,
                "remotes": {"origin": good_git_url},
            },
            "my_svn_repo": {
                "url": svn_url,
            },
        },
    }
    yaml_config = config_path / ".vcspull.yaml"
    yaml_config.write_text(
        yaml.dump(config, default_flow_style=False),
        encoding="utf-8",
    )

    monkeypatch.chdir(tmp_path)

    # Clean up any prior checkouts
    for repo_name in ("my_git_repo", "my_svn_repo"):
        repo_dir = github_projects / repo_name
        if repo_dir.exists():
            shutil.rmtree(repo_dir)

    # First sync: clone both repos successfully
    with contextlib.suppress(SystemExit):
        cli(["sync", "my_git_repo", "my_svn_repo"])
    capsys.readouterr()  # Discard initial sync output

    # Delete the SVN remote to cause failure on next sync
    shutil.rmtree(svn_remote_dir)

    # Second sync: git succeeds, SVN fails
    with contextlib.suppress(SystemExit):
        cli(["sync", *sync_args])

    result = capsys.readouterr()
    out = "".join(list(result.out))
    err = "".join(list(result.err))

    if expected_in_out is not None:
        if isinstance(expected_in_out, str):
            expected_in_out = [expected_in_out]
        for needle in expected_in_out:
            assert needle in out, f"Expected {needle!r} in stdout: {out!r}"

    if expected_not_in_out is not None:
        if isinstance(expected_not_in_out, str):
            expected_not_in_out = [expected_not_in_out]
        for needle in expected_not_in_out:
            assert needle not in out, f"Did not expect {needle!r} in stdout: {out!r}"

    if expected_in_err is not None:
        if isinstance(expected_in_err, str):
            expected_in_err = [expected_in_err]
        for needle in expected_in_err:
            assert needle in err, f"Expected {needle!r} in stderr: {err!r}"

    if expected_not_in_err is not None:
        if isinstance(expected_not_in_err, str):
            expected_not_in_err = [expected_not_in_err]
        for needle in expected_not_in_err:
            assert needle not in err, f"Did not expect {needle!r} in stderr: {err!r}"


@pytest.mark.parametrize(
    list(CLINegativeFixture._fields),
    CLI_NEGATIVE_FIXTURES,
    ids=[fixture.test_id for fixture in CLI_NEGATIVE_FIXTURES],
)
def test_cli_negative_flows(
    test_id: str,
    cli_args: list[str],
    scenario: t.Literal["discover-non-dict-config", "status-missing-git"],
    expected_log_fragment: str | None,
    expected_stdout_fragment: str | None,
    tmp_path: pathlib.Path,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Exercise common CLI error flows without raising."""
    import logging
    import subprocess

    import yaml

    caplog.set_level(logging.INFO)

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)

    if scenario == "discover-non-dict-config":
        scan_dir = tmp_path / "scan"
        scan_dir.mkdir(parents=True, exist_ok=True)
        config_file = tmp_path / "config.yaml"
        config_file.write_text("[]\n", encoding="utf-8")

        with contextlib.suppress(SystemExit):
            cli([*cli_args, str(scan_dir), "--file", str(config_file)])
    else:
        workspace_dir = tmp_path / "workspace"
        repo_dir = workspace_dir / "project"
        repo_dir.mkdir(parents=True, exist_ok=True)
        (repo_dir / ".git").mkdir()

        config_file = tmp_path / "status.yaml"
        config_file.write_text(
            yaml.dump(
                {
                    "~/workspace/": {
                        "project": {
                            "url": "git+https://example.com/project.git",
                            "path": str(repo_dir),
                        },
                    },
                },
            ),
            encoding="utf-8",
        )

        def _missing_git(
            cmd: list[str],
            **kwargs: object,
        ) -> subprocess.CompletedProcess[str]:
            if cmd and cmd[0] == "git":
                error_message = "git not installed"
                raise FileNotFoundError(error_message)
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

        monkeypatch.setattr("vcspull.cli.status.subprocess.run", _missing_git)

        with contextlib.suppress(SystemExit):
            cli([*cli_args, "--file", str(config_file)])

    captured = capsys.readouterr()

    if expected_log_fragment is not None:
        assert expected_log_fragment in caplog.text

    if expected_stdout_fragment is not None:
        assert expected_stdout_fragment in captured.out


class DryRunPlanFixture(t.NamedTuple):
    """Fixture for Terraform-style dry-run plan output."""

    test_id: str
    cli_args: list[str]
    pre_sync: bool = False
    expected_contains: list[str] | None = None
    expected_not_contains: list[str] | None = None
    repository_names: tuple[str, ...] = ("my_git_repo",)
    force_tty: bool = False
    plan_entries: list[PlanEntry] | None = None
    plan_summary: PlanSummary | None = None
    set_no_color: bool = True


DRY_RUN_PLAN_FIXTURES: list[DryRunPlanFixture] = [
    DryRunPlanFixture(
        test_id="clone-default",
        cli_args=["sync", "--dry-run", "my_git_repo"],
        expected_contains=[
            "Plan: 1 to clone (+)",
            "+ my_git_repo",
            "missing",
        ],
    ),
    DryRunPlanFixture(
        test_id="summary-only",
        cli_args=["sync", "--dry-run", "--summary-only", "my_git_repo"],
        expected_contains=["Plan: 1 to clone (+)", "Tip: run without --dry-run"],
        expected_not_contains=["~/github_projects/"],
    ),
    DryRunPlanFixture(
        test_id="unchanged-show",
        cli_args=["sync", "--dry-run", "--show-unchanged", "my_git_repo"],
        pre_sync=True,
        expected_contains=["Plan: 0 to clone (+)", "✓ my_git_repo"],
    ),
    DryRunPlanFixture(
        test_id="long-format",
        cli_args=["sync", "--dry-run", "--long", "repo-long"],
        expected_contains=[
            "Plan: 1 to clone (+)",
            "+ repo-long",
            "url: git+https://example.com/repo-long.git",
        ],
        repository_names=("repo-long",),
        plan_entries=[
            PlanEntry(
                name="repo-long",
                path="~/github_projects/repo-long",
                workspace_root="~/github_projects/",
                action=PlanAction.CLONE,
                detail="missing",
                url="git+https://example.com/repo-long.git",
            ),
        ],
    ),
    DryRunPlanFixture(
        test_id="relative-paths",
        cli_args=["sync", "--dry-run", "--relative-paths", "repo-rel"],
        expected_contains=[
            "Plan: 0 to clone (+), 1 to update (~)",
            "~ repo-rel",
            "repo-rel  remote state unknown; use --fetch",
        ],
        expected_not_contains=["~/github_projects/repo-rel"],
        repository_names=("repo-rel",),
        plan_entries=[
            PlanEntry(
                name="repo-rel",
                path="~/github_projects/repo-rel",
                workspace_root="~/github_projects/",
                action=PlanAction.UPDATE,
                detail="remote state unknown; use --fetch",
            ),
        ],
    ),
    DryRunPlanFixture(
        test_id="offline-detail",
        cli_args=["sync", "--dry-run", "--offline", "repo-offline"],
        expected_contains=[
            "Plan: 0 to clone (+), 1 to update (~)",
            "~ repo-offline",
            "remote state unknown (offline)",
        ],
        repository_names=("repo-offline",),
        plan_entries=[
            PlanEntry(
                name="repo-offline",
                path="~/github_projects/repo-offline",
                workspace_root="~/github_projects/",
                action=PlanAction.UPDATE,
                detail="remote state unknown (offline)",
            ),
        ],
    ),
]


@pytest.mark.parametrize(
    list(DryRunPlanFixture._fields),
    DRY_RUN_PLAN_FIXTURES,
    ids=[fixture.test_id for fixture in DRY_RUN_PLAN_FIXTURES],
)
def test_sync_dry_run_plan_human(
    test_id: str,
    cli_args: list[str],
    pre_sync: bool,
    expected_contains: list[str] | None,
    expected_not_contains: list[str] | None,
    repository_names: tuple[str, ...],
    force_tty: bool,
    plan_entries: list[PlanEntry] | None,
    plan_summary: PlanSummary | None,
    set_no_color: bool,
    tmp_path: pathlib.Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    user_path: pathlib.Path,
    config_path: pathlib.Path,
    git_repo: GitSync,
) -> None:
    """Validate human-readable plan output variants."""
    if set_no_color:
        monkeypatch.setenv("NO_COLOR", "1")

    config: dict[str, dict[str, dict[str, t.Any]]] = {"~/github_projects/": {}}
    for name in repository_names:
        config["~/github_projects/"][name] = {
            "url": f"git+file://{git_repo.path}",
            "remotes": {"origin": f"git+file://{git_repo.path}"},
        }

    yaml_config = config_path / ".vcspull.yaml"
    yaml_config.write_text(
        yaml.dump(config, default_flow_style=False),
        encoding="utf-8",
    )

    monkeypatch.chdir(tmp_path)

    workspace_root = pathlib.Path(user_path) / "github_projects"
    for name in repository_names:
        candidate = workspace_root / name
        if candidate.exists():
            shutil.rmtree(candidate)

    if force_tty:
        monkeypatch.setattr(sys.stdout, "isatty", lambda: True)

    if pre_sync:
        with contextlib.suppress(SystemExit):
            cli(["sync", repository_names[0]])

    if plan_entries is not None:
        for entry in plan_entries:
            entry.path = str(workspace_root / entry.name)
        computed_summary = plan_summary
        if computed_summary is None:
            computed_summary = PlanSummary(
                clone=sum(entry.action is PlanAction.CLONE for entry in plan_entries),
                update=sum(entry.action is PlanAction.UPDATE for entry in plan_entries),
                unchanged=sum(
                    entry.action is PlanAction.UNCHANGED for entry in plan_entries
                ),
                blocked=sum(
                    entry.action is PlanAction.BLOCKED for entry in plan_entries
                ),
                errors=sum(entry.action is PlanAction.ERROR for entry in plan_entries),
            )

        async def _fake_plan(*args: t.Any, **kwargs: t.Any) -> PlanResult:
            return PlanResult(entries=plan_entries, summary=computed_summary)

        monkeypatch.setattr(sync_module, "_build_plan_result_async", _fake_plan)

    with contextlib.suppress(SystemExit):
        cli(cli_args)

    captured = capsys.readouterr()
    output = f"{captured.out}{captured.err}"

    if expected_contains:
        for needle in expected_contains:
            assert needle in output

    if expected_not_contains:
        for needle in expected_not_contains:
            assert needle not in output


class DryRunPlanMachineFixture(t.NamedTuple):
    """Fixture for JSON/NDJSON plan output."""

    test_id: str
    cli_args: list[str]
    mode: t.Literal["json", "ndjson"]
    expected_summary: dict[str, int]
    repository_names: tuple[str, ...] = ("my_git_repo",)
    pre_sync: bool = True
    plan_entries: list[PlanEntry] | None = None
    plan_summary: PlanSummary | None = None
    expected_operation_subset: dict[str, t.Any] | None = None


DRY_RUN_PLAN_MACHINE_FIXTURES: list[DryRunPlanMachineFixture] = [
    DryRunPlanMachineFixture(
        test_id="json-summary",
        cli_args=["sync", "--dry-run", "--json", "--show-unchanged", "my_git_repo"],
        mode="json",
        expected_summary={
            "clone": 0,
            "update": 0,
            "unchanged": 1,
            "blocked": 0,
            "errors": 0,
        },
    ),
    DryRunPlanMachineFixture(
        test_id="ndjson-summary",
        cli_args=["sync", "--dry-run", "--ndjson", "--show-unchanged", "my_git_repo"],
        mode="ndjson",
        expected_summary={
            "clone": 0,
            "update": 0,
            "unchanged": 1,
            "blocked": 0,
            "errors": 0,
        },
    ),
    DryRunPlanMachineFixture(
        test_id="json-operation-fields",
        cli_args=["sync", "--dry-run", "--json", "repo-json"],
        mode="json",
        expected_summary={
            "clone": 0,
            "update": 1,
            "unchanged": 0,
            "blocked": 0,
            "errors": 0,
        },
        repository_names=("repo-json",),
        pre_sync=False,
        plan_entries=[
            PlanEntry(
                name="repo-json",
                path="~/github_projects/repo-json",
                workspace_root="~/github_projects/",
                action=PlanAction.UPDATE,
                detail="behind 2",
                ahead=0,
                behind=2,
                branch="main",
                remote_branch="origin/main",
            ),
        ],
        expected_operation_subset={
            "name": "repo-json",
            "detail": "behind 2",
            "behind": 2,
            "branch": "main",
        },
    ),
    DryRunPlanMachineFixture(
        test_id="ndjson-operation-fields",
        cli_args=["sync", "--dry-run", "--ndjson", "repo-ndjson"],
        mode="ndjson",
        expected_summary={
            "clone": 1,
            "update": 0,
            "unchanged": 0,
            "blocked": 0,
            "errors": 0,
        },
        repository_names=("repo-ndjson",),
        pre_sync=False,
        plan_entries=[
            PlanEntry(
                name="repo-ndjson",
                path="~/github_projects/repo-ndjson",
                workspace_root="~/github_projects/",
                action=PlanAction.CLONE,
                detail="missing",
                url="git+https://example.com/repo-ndjson.git",
            ),
        ],
        expected_operation_subset={
            "name": "repo-ndjson",
            "action": "clone",
            "url": "git+https://example.com/repo-ndjson.git",
        },
    ),
]


@pytest.mark.parametrize(
    list(DryRunPlanMachineFixture._fields),
    DRY_RUN_PLAN_MACHINE_FIXTURES,
    ids=[fixture.test_id for fixture in DRY_RUN_PLAN_MACHINE_FIXTURES],
)
def test_sync_dry_run_plan_machine(
    test_id: str,
    cli_args: list[str],
    mode: t.Literal["json", "ndjson"],
    expected_summary: dict[str, int],
    repository_names: tuple[str, ...],
    pre_sync: bool,
    plan_entries: list[PlanEntry] | None,
    plan_summary: PlanSummary | None,
    expected_operation_subset: dict[str, t.Any] | None,
    tmp_path: pathlib.Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    user_path: pathlib.Path,
    config_path: pathlib.Path,
    git_repo: GitSync,
) -> None:
    """Validate machine-readable plan parity."""
    monkeypatch.setenv("NO_COLOR", "1")

    config: dict[str, dict[str, dict[str, t.Any]]] = {"~/github_projects/": {}}
    for name in repository_names:
        config["~/github_projects/"][name] = {
            "url": f"git+file://{git_repo.path}",
            "remotes": {"origin": f"git+file://{git_repo.path}"},
        }

    yaml_config = config_path / ".vcspull.yaml"
    yaml_config.write_text(
        yaml.dump(config, default_flow_style=False),
        encoding="utf-8",
    )

    monkeypatch.chdir(tmp_path)

    workspace_root = pathlib.Path(user_path) / "github_projects"
    for name in repository_names:
        candidate = workspace_root / name
        if candidate.exists():
            shutil.rmtree(candidate)

    if pre_sync:
        with contextlib.suppress(SystemExit):
            cli(["sync", repository_names[0]])
        capsys.readouterr()

    if plan_entries is not None:
        for entry in plan_entries:
            entry.path = str(workspace_root / entry.name)
        computed_summary = plan_summary
        if computed_summary is None:
            computed_summary = PlanSummary(
                clone=sum(entry.action is PlanAction.CLONE for entry in plan_entries),
                update=sum(entry.action is PlanAction.UPDATE for entry in plan_entries),
                unchanged=sum(
                    entry.action is PlanAction.UNCHANGED for entry in plan_entries
                ),
                blocked=sum(
                    entry.action is PlanAction.BLOCKED for entry in plan_entries
                ),
                errors=sum(entry.action is PlanAction.ERROR for entry in plan_entries),
            )

        async def _fake_plan(*args: t.Any, **kwargs: t.Any) -> PlanResult:
            return PlanResult(entries=plan_entries, summary=computed_summary)

        monkeypatch.setattr(sync_module, "_build_plan_result_async", _fake_plan)

    with contextlib.suppress(SystemExit):
        cli(cli_args)

    captured = capsys.readouterr()

    if mode == "json":
        payload = json.loads(captured.out)
        summary = payload["summary"]
    else:
        events = [
            json.loads(line) for line in captured.out.splitlines() if line.strip()
        ]
        assert events, "Expected NDJSON payload"
        summary = events[-1]
        if expected_operation_subset:
            operation_payload = next(
                (event for event in events if event.get("type") == "operation"),
                None,
            )
            assert operation_payload is not None
            for key, value in expected_operation_subset.items():
                assert operation_payload[key] == value

    assert summary["clone"] == expected_summary["clone"]
    assert summary["update"] == expected_summary["update"]
    assert summary["unchanged"] == expected_summary["unchanged"]
    assert summary["blocked"] == expected_summary["blocked"]
    assert summary["errors"] == expected_summary["errors"]

    if mode == "json" and expected_operation_subset:
        operations: list[dict[str, t.Any]] = []
        for workspace in payload["workspaces"]:
            operations.extend(workspace["operations"])
        assert operations, "Expected at least one operation payload"
        for key, value in expected_operation_subset.items():
            assert operations[0][key] == value


def test_sync_dry_run_plan_progress(
    tmp_path: pathlib.Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    user_path: pathlib.Path,
    config_path: pathlib.Path,
    git_repo: GitSync,
) -> None:
    """TTY dry-run should surface a live progress line."""
    config = {
        "~/github_projects/": {
            "repo_one": {
                "url": f"git+file://{git_repo.path}",
                "remotes": {"origin": f"git+file://{git_repo.path}"},
            },
            "repo_two": {
                "url": f"git+file://{git_repo.path}",
                "remotes": {"origin": f"git+file://{git_repo.path}"},
            },
        },
    }
    yaml_config = config_path / ".vcspull.yaml"
    yaml_config.write_text(
        yaml.dump(config, default_flow_style=False),
        encoding="utf-8",
    )

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True)

    workspace_root = pathlib.Path(user_path) / "github_projects"
    for name in ("repo_one", "repo_two"):
        candidate = workspace_root / name
        if candidate.exists():
            shutil.rmtree(candidate)

    with contextlib.suppress(SystemExit):
        cli(["sync", "--dry-run", "repo_*"])

    captured = capsys.readouterr()
    output = f"{captured.out}{captured.err}"
    assert "Progress:" in output
    assert "Plan:" in output


def test_sync_human_output_redacts_repo_paths(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    user_path: pathlib.Path,
) -> None:
    """Synced log lines should collapse repo paths via PrivatePath."""
    repo_path = user_path / "repos" / "private"
    repo_path.mkdir(parents=True, exist_ok=True)

    repo_config = {
        "name": "private",
        "url": "git+https://example.com/private.git",
        "path": str(repo_path),
        "workspace_root": "~/repos/",
    }

    monkeypatch.setattr(
        sync_module,
        "load_configs",
        lambda _paths: [repo_config],
    )
    monkeypatch.setattr(
        sync_module,
        "find_config_files",
        lambda include_home=True: [],
    )

    def _fake_filter_repos(
        _configs: list[dict[str, t.Any]],
        *,
        path: str | None = None,
        vcs_url: str | None = None,
        name: str | None = None,
    ) -> list[dict[str, t.Any]]:
        if name and name != repo_config["name"]:
            return []
        if path and path != repo_config["path"]:
            return []
        if vcs_url and vcs_url != repo_config["url"]:
            return []
        return [repo_config]

    monkeypatch.setattr(sync_module, "filter_repos", _fake_filter_repos)
    monkeypatch.setattr(
        sync_module,
        "update_repo",
        lambda _repo, progress_callback=None: None,
    )

    sync_module.sync(
        repo_patterns=[repo_config["name"]],
        config=None,
        workspace_root=None,
        dry_run=False,
        output_json=False,
        output_ndjson=False,
        color="never",
        exit_on_error=False,
        show_unchanged=False,
        summary_only=False,
        long_view=False,
        relative_paths=False,
        fetch=False,
        offline=False,
        verbosity=0,
    )

    captured = capsys.readouterr()
    expected_path = str(PrivatePath(repo_path))
    assert expected_path in captured.out
