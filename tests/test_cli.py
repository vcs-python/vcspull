import pathlib
import shutil
import typing as t

import pytest

import yaml
from click.testing import CliRunner

from libvcs.sync.git import GitSync
from vcspull.cli import cli
from vcspull.cli.sync import EXIT_ON_ERROR_MSG, NO_REPOS_FOR_TERM_MSG

if t.TYPE_CHECKING:
    from typing_extensions import TypeAlias

    ExpectedOutput: TypeAlias = t.Optional[t.Union[str, t.List[str]]]


class SyncCLINonExistentRepo(t.NamedTuple):
    test_id: str
    sync_args: list[str]
    expected_exit_code: int
    expected_in_output: "ExpectedOutput" = None
    expected_not_in_output: "ExpectedOutput" = None


SYNC_CLI_EXISTENT_REPO_FIXTURES = [
    SyncCLINonExistentRepo(
        test_id="exists",
        sync_args=["my_git_project"],
        expected_exit_code=0,
        expected_in_output="Already on 'master'",
        expected_not_in_output=NO_REPOS_FOR_TERM_MSG.format(name="my_git_repo"),
    ),
    SyncCLINonExistentRepo(
        test_id="non-existent-only",
        sync_args=["this_isnt_in_the_config"],
        expected_exit_code=0,
        expected_in_output=NO_REPOS_FOR_TERM_MSG.format(name="this_isnt_in_the_config"),
    ),
    SyncCLINonExistentRepo(
        test_id="non-existent-mixed",
        sync_args=["this_isnt_in_the_config", "my_git_project", "another"],
        expected_exit_code=0,
        expected_in_output=[
            NO_REPOS_FOR_TERM_MSG.format(name="this_isnt_in_the_config"),
            NO_REPOS_FOR_TERM_MSG.format(name="another"),
        ],
        expected_not_in_output=NO_REPOS_FOR_TERM_MSG.format(name="my_git_repo"),
    ),
]


@pytest.mark.parametrize(
    list(SyncCLINonExistentRepo._fields),
    SYNC_CLI_EXISTENT_REPO_FIXTURES,
    ids=[test.test_id for test in SYNC_CLI_EXISTENT_REPO_FIXTURES],
)
def test_sync_cli_repo_term_non_existent(
    user_path: pathlib.Path,
    config_path: pathlib.Path,
    tmp_path: pathlib.Path,
    git_repo: GitSync,
    test_id: str,
    sync_args: list[str],
    expected_exit_code: int,
    expected_in_output: "ExpectedOutput",
    expected_not_in_output: "ExpectedOutput",
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

    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        result = runner.invoke(cli, ["sync", *sync_args])
        assert result.exit_code == expected_exit_code
        output = "".join(list(result.output))

        if expected_in_output is not None:
            if isinstance(expected_in_output, str):
                expected_in_output = [expected_in_output]
            for needle in expected_in_output:
                assert needle in output

        if expected_not_in_output is not None:
            if isinstance(expected_not_in_output, str):
                expected_not_in_output = [expected_not_in_output]
            for needle in expected_not_in_output:
                assert needle not in output


def test_sync(
    user_path: pathlib.Path,
    config_path: pathlib.Path,
    tmp_path: pathlib.Path,
    git_repo: GitSync,
) -> None:
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
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
        result = runner.invoke(cli, ["sync", "my_git_repo"])
        assert result.exit_code == 0
        output = "".join(list(result.output))
        assert "my_git_repo" in output


class SyncBrokenFixture(t.NamedTuple):
    test_id: str
    sync_args: list[str]
    expected_exit_code: int
    expected_in_output: "ExpectedOutput" = None
    expected_not_in_output: "ExpectedOutput" = None


SYNC_BROKEN_REPO_FIXTURES = [
    SyncBrokenFixture(
        test_id="normal-checkout",
        sync_args=["my_git_repo"],
        expected_exit_code=0,
        expected_in_output="Already on 'master'",
    ),
    SyncBrokenFixture(
        test_id="normal-checkout--exit-on-error",
        sync_args=["my_git_repo", "--exit-on-error"],
        expected_exit_code=0,
        expected_in_output="Already on 'master'",
    ),
    SyncBrokenFixture(
        test_id="normal-checkout--x",
        sync_args=["my_git_repo", "-x"],
        expected_exit_code=0,
        expected_in_output="Already on 'master'",
    ),
    SyncBrokenFixture(
        test_id="normal-first-broken",
        sync_args=["my_git_repo_not_found", "my_git_repo"],
        expected_exit_code=0,
        expected_not_in_output=EXIT_ON_ERROR_MSG,
    ),
    SyncBrokenFixture(
        test_id="normal-last-broken",
        sync_args=["my_git_repo", "my_git_repo_not_found"],
        expected_exit_code=0,
        expected_not_in_output=EXIT_ON_ERROR_MSG,
    ),
    SyncBrokenFixture(
        test_id="exit-on-error--exit-on-error-first-broken",
        sync_args=["my_git_repo_not_found", "my_git_repo", "--exit-on-error"],
        expected_exit_code=1,
        expected_in_output=EXIT_ON_ERROR_MSG,
    ),
    SyncBrokenFixture(
        test_id="exit-on-error--x-first-broken",
        sync_args=["my_git_repo_not_found", "my_git_repo", "-x"],
        expected_exit_code=1,
        expected_in_output=EXIT_ON_ERROR_MSG,
        expected_not_in_output="master",
    ),
    #
    # Verify ordering
    #
    SyncBrokenFixture(
        test_id="exit-on-error--exit-on-error-last-broken",
        sync_args=["my_git_repo", "my_git_repo_not_found", "-x"],
        expected_exit_code=1,
        expected_in_output=[EXIT_ON_ERROR_MSG, "Already on 'master'"],
    ),
    SyncBrokenFixture(
        test_id="exit-on-error--x-last-item",
        sync_args=["my_git_repo", "my_git_repo_not_found", "--exit-on-error"],
        expected_exit_code=1,
        expected_in_output=[EXIT_ON_ERROR_MSG, "Already on 'master'"],
    ),
]


@pytest.mark.parametrize(
    list(SyncBrokenFixture._fields),
    SYNC_BROKEN_REPO_FIXTURES,
    ids=[test.test_id for test in SYNC_BROKEN_REPO_FIXTURES],
)
def test_sync_broken(
    user_path: pathlib.Path,
    config_path: pathlib.Path,
    tmp_path: pathlib.Path,
    git_repo: GitSync,
    test_id: str,
    sync_args: list[str],
    expected_exit_code: int,
    expected_in_output: "ExpectedOutput",
    expected_not_in_output: "ExpectedOutput",
) -> None:
    runner = CliRunner()

    github_projects = user_path / "github_projects"
    my_git_repo = github_projects / "my_git_repo"
    if my_git_repo.is_dir():
        shutil.rmtree(my_git_repo)

    with runner.isolated_filesystem(temp_dir=tmp_path):
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
        result = runner.invoke(cli, ["sync", *sync_args])
        assert result.exit_code == expected_exit_code
        output = "".join(list(result.output))

        if expected_in_output is not None:
            if isinstance(expected_in_output, str):
                expected_in_output = [expected_in_output]
            for needle in expected_in_output:
                assert needle in output

        if expected_not_in_output is not None:
            if isinstance(expected_not_in_output, str):
                expected_not_in_output = [expected_not_in_output]
            for needle in expected_not_in_output:
                assert needle not in output
