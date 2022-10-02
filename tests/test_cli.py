import pathlib
import shutil
import typing as t

import pytest

import yaml

from libvcs.sync.git import GitSync
from vcspull.__about__ import __version__
from vcspull.cli import cli
from vcspull.cli.sync import EXIT_ON_ERROR_MSG, NO_REPOS_FOR_TERM_MSG

if t.TYPE_CHECKING:
    from typing_extensions import TypeAlias

    ExpectedOutput: TypeAlias = t.Optional[t.Union[str, t.List[str]]]


class SyncCLINonExistentRepo(t.NamedTuple):
    test_id: str
    sync_args: list[str]
    expected_exit_code: int
    expected_in_out: "ExpectedOutput" = None
    expected_not_in_out: "ExpectedOutput" = None
    expected_in_err: "ExpectedOutput" = None
    expected_not_in_err: "ExpectedOutput" = None


SYNC_CLI_EXISTENT_REPO_FIXTURES = [
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
def test_sync_cli_repo_term_non_existent(
    tmp_path: pathlib.Path,
    capsys: pytest.CaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
    user_path: pathlib.Path,
    config_path: pathlib.Path,
    git_repo: GitSync,
    test_id: str,
    sync_args: list[str],
    expected_exit_code: int,
    expected_in_out: "ExpectedOutput",
    expected_not_in_out: "ExpectedOutput",
    expected_in_err: "ExpectedOutput",
    expected_not_in_err: "ExpectedOutput",
) -> None:
    config = {
        "~/github_projects/": {
            "my_git_project": {
                "url": f"git+file://{git_repo.dir}",
                "remotes": {"test_remote": f"git+file://{git_repo.dir}"},
            },
        }
    }
    yaml_config = config_path / ".vcspull.yaml"
    yaml_config_data = yaml.dump(config, default_flow_style=False)
    yaml_config.write_text(yaml_config_data, encoding="utf-8")

    monkeypatch.chdir(tmp_path)

    try:
        cli(["sync", *sync_args])
    except SystemExit:
        pass

    result = capsys.readouterr()
    output = "".join(list(result.out))

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
    test_id: str
    sync_args: list[str]
    expected_exit_code: int
    expected_in_out: "ExpectedOutput" = None
    expected_not_in_out: "ExpectedOutput" = None
    expected_in_err: "ExpectedOutput" = None
    expected_not_in_err: "ExpectedOutput" = None


SYNC_REPO_FIXTURES = [
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
        expected_exit_code=1,
        expected_in_out=(
            "sync: error: the following arguments are required: repo_terms"
        ),
        expected_not_in_out="positional arguments:",
    ),
    # Sync: Help
    SyncFixture(
        test_id="sync---help",
        sync_args=["sync", "--help"],
        expected_exit_code=0,
        expected_in_out=["repo_terms", "--exit-on-error"],
        expected_not_in_out="--version",
    ),
    SyncFixture(
        test_id="sync--h",
        sync_args=["sync", "-h"],
        expected_exit_code=0,
        expected_in_out=["repo_terms", "--exit-on-error"],
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


@pytest.mark.parametrize(
    list(SyncFixture._fields),
    SYNC_REPO_FIXTURES,
    ids=[test.test_id for test in SYNC_REPO_FIXTURES],
)
def test_sync(
    tmp_path: pathlib.Path,
    capsys: pytest.CaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
    user_path: pathlib.Path,
    config_path: pathlib.Path,
    git_repo: GitSync,
    test_id: str,
    sync_args: list[str],
    expected_exit_code: int,
    expected_in_out: "ExpectedOutput",
    expected_not_in_out: "ExpectedOutput",
    expected_in_err: "ExpectedOutput",
    expected_not_in_err: "ExpectedOutput",
) -> None:
    config = {
        "~/github_projects/": {
            "my_git_repo": {
                "url": f"git+file://{git_repo.dir}",
                "remotes": {"test_remote": f"git+file://{git_repo.dir}"},
            },
            "broken_repo": {
                "url": f"git+file://{git_repo.dir}",
                "remotes": {"test_remote": "git+file://non-existent-remote"},
            },
        }
    }
    yaml_config = config_path / ".vcspull.yaml"
    yaml_config_data = yaml.dump(config, default_flow_style=False)
    yaml_config.write_text(yaml_config_data, encoding="utf-8")

    # CLI can sync
    try:
        cli(sync_args)
    except SystemExit:
        pass

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
    test_id: str
    sync_args: list[str]
    expected_exit_code: int
    expected_in_out: "ExpectedOutput" = None
    expected_not_in_out: "ExpectedOutput" = None
    expected_in_err: "ExpectedOutput" = None
    expected_not_in_err: "ExpectedOutput" = None


SYNC_BROKEN_REPO_FIXTURES = [
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
    capsys: pytest.CaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
    user_path: pathlib.Path,
    config_path: pathlib.Path,
    git_repo: GitSync,
    test_id: str,
    sync_args: list[str],
    expected_exit_code: int,
    expected_in_out: "ExpectedOutput",
    expected_not_in_out: "ExpectedOutput",
    expected_in_err: "ExpectedOutput",
    expected_not_in_err: "ExpectedOutput",
) -> None:
    github_projects = user_path / "github_projects"
    my_git_repo = github_projects / "my_git_repo"
    if my_git_repo.is_dir():
        shutil.rmtree(my_git_repo)

    config = {
        "~/github_projects/": {
            "my_git_repo": {
                "url": f"git+file://{git_repo.dir}",
                "remotes": {"test_remote": f"git+file://{git_repo.dir}"},
            },
            "my_git_repo_not_found": {
                "url": "git+file:///dev/null",
            },
        }
    }
    yaml_config = config_path / ".vcspull.yaml"
    yaml_config_data = yaml.dump(config, default_flow_style=False)
    yaml_config.write_text(yaml_config_data, encoding="utf-8")

    # CLI can sync
    assert isinstance(sync_args, list)

    try:
        cli(["sync", *sync_args])
    except SystemExit:
        pass

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
