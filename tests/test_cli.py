import pathlib
import shutil
import typing as t

import pytest

import yaml
from click.testing import CliRunner

from libvcs._internal.run import run
from libvcs.sync.git import GitSync
from tests.conftest import DummyRepoProtocol
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


class SyncFixture(t.NamedTuple):
    test_id: str
    sync_args: list[str]
    expected_exit_code: int
    expected_in_output: "ExpectedOutput" = None
    expected_not_in_output: "ExpectedOutput" = None


SYNC_REPO_FIXTURES = [
    # Empty (root command)
    SyncFixture(
        test_id="empty",
        sync_args=[],
        expected_exit_code=0,
        expected_in_output=["Options:", "Commands:"],
    ),
    # Version
    SyncFixture(
        test_id="--version",
        sync_args=["--version"],
        expected_exit_code=0,
        expected_in_output=[__version__, ", libvcs"],
    ),
    SyncFixture(
        test_id="-V",
        sync_args=["-V"],
        expected_exit_code=0,
        expected_in_output=[__version__, ", libvcs"],
    ),
    # Help
    SyncFixture(
        test_id="--help",
        sync_args=["--help"],
        expected_exit_code=0,
        expected_in_output=["Options:", "Commands:"],
    ),
    SyncFixture(
        test_id="-h",
        sync_args=["-h"],
        expected_exit_code=0,
        expected_in_output=["Options:", "Commands:"],
    ),
    # Sync
    SyncFixture(
        test_id="sync--empty",
        sync_args=["sync"],
        expected_exit_code=0,
        expected_in_output="Options:",
        expected_not_in_output="Commands:",
    ),
    # Sync: Help
    SyncFixture(
        test_id="sync---help",
        sync_args=["sync", "--help"],
        expected_exit_code=0,
        expected_in_output="Options:",
        expected_not_in_output="Commands:",
    ),
    SyncFixture(
        test_id="sync--h",
        sync_args=["sync", "-h"],
        expected_exit_code=0,
        expected_in_output="Options:",
        expected_not_in_output="Commands:",
    ),
    # Sync: Repo terms
    SyncFixture(
        test_id="sync--one-repo-term",
        sync_args=["sync", "my_git_repo"],
        expected_exit_code=0,
        expected_in_output="my_git_repo",
    ),
]


@pytest.mark.parametrize(
    list(SyncFixture._fields),
    SYNC_REPO_FIXTURES,
    ids=[test.test_id for test in SYNC_REPO_FIXTURES],
)
def test_sync(
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
        result = runner.invoke(cli, sync_args)
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


# @pytest.mark.skip("No recreation yet, #366")
def test_broken_submodule(
    user_path: pathlib.Path,
    config_path: pathlib.Path,
    tmp_path: pathlib.Path,
    git_repo: GitSync,
    create_git_dummy_repo: DummyRepoProtocol,
) -> None:
    runner = CliRunner()

    deleted_submodule_repo = create_git_dummy_repo(
        repo_name="deleted_submodule_repo", testfile_filename="dummy_file.txt"
    )

    broken_repo = create_git_dummy_repo(
        repo_name="broken_repo", testfile_filename="dummy_file.txt"
    )

    # Try to recreated gitmodules by hand

    # gitmodules_file = pathlib.Path(broken_repo) / ".gitmodules"
    # gitmodules_file.write_text(
    #     """
    # [submodule "deleted_submodule_repo"]
    #         path = deleted_submodule_repo
    #         url = ../deleted_submodule_repo
    #     """,
    #     encoding="utf-8",
    # )
    #
    # run(
    #     [
    #         "git",
    #         "submodule",
    #         "init",
    #         "--",
    #         # "deleted_submodule_repo",
    #     ],
    #     cwd=str(broken_repo),
    # )

    run(
        [
            "git",
            "submodule",
            "add",
            "--",
            "../deleted_submodule_repo",
            "broken_submodule",
        ],
        cwd=str(broken_repo),
    )

    # Assure submodule exists
    gitmodules_file = pathlib.Path(broken_repo) / ".gitmodules"
    assert gitmodules_file.exists()
    assert "../deleted_submodule_repo" in gitmodules_file.read_text()

    github_projects = user_path / "github_projects"
    broken_repo_checkout = github_projects / "broken_repo"
    assert not broken_repo_checkout.exists()

    # Delete the submodule dependency
    shutil.rmtree(deleted_submodule_repo)
    assert not pathlib.Path(deleted_submodule_repo).exists()

    with runner.isolated_filesystem(temp_dir=tmp_path):
        config = {
            "~/github_projects/": {
                "my_git_repo": {
                    "url": f"git+file://{git_repo.dir}",
                    "remotes": {"test_remote": f"git+file://{git_repo.dir}"},
                },
                "broken_repo": {
                    "url": f"git+file://{broken_repo}",
                },
            }
        }
        yaml_config = config_path / ".vcspull.yaml"
        yaml_config_data = yaml.dump(config, default_flow_style=False)
        yaml_config.write_text(yaml_config_data, encoding="utf-8")

        # CLI can sync
        result = runner.invoke(cli, ["sync", "broken_repo"])
        output = "".join(list(result.output))

        assert broken_repo_checkout.exists()

        assert "No url found for submodule" == output
        assert result.exit_code == 1
