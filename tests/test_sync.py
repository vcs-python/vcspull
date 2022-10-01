import pathlib
import textwrap
import typing as t

import pytest

from libvcs._internal.shortcuts import create_project
from libvcs.pytest_plugin import CreateProjectCallbackFixtureProtocol
from libvcs.sync.git import GitRemote, GitSync
from vcspull._internal.config_reader import ConfigReader
from vcspull.cli.sync import update_repo
from vcspull.config import extract_repos, filter_repos, load_configs
from vcspull.types import ConfigDict

from .helpers import write_config


def test_makes_recursive(
    tmp_path: pathlib.Path,
    git_remote_repo: pathlib.Path,
):
    """Ensure that directories in pull are made recursively."""
    conf = ConfigReader._load(
        format="yaml",
        content=textwrap.dedent(
            f"""
        {tmp_path}/study/myrepo:
            my_url: git+file://{git_remote_repo}
    """
        ),
    )
    repos = extract_repos(conf)
    assert len(repos) > 0

    filtered_repos = filter_repos(repos, dir="*")
    assert len(filtered_repos) > 0

    for r in filtered_repos:
        assert isinstance(r, dict)
        repo = create_project(**r)  # type: ignore
        repo.obtain()

        assert repo.dir.exists()


def write_config_remote(
    config_path: pathlib.Path, tmp_path: pathlib.Path, config_tpl, dir, clone_name
):
    return write_config(
        config_path=config_path,
        content=config_tpl.format(
            tmp_path=str(tmp_path.parent), dir=dir, CLONE_NAME=clone_name
        ),
    )


@pytest.mark.parametrize(
    "config_tpl,remote_list",
    [
        [
            """
        {tmp_path}/study/myrepo:
            {CLONE_NAME}: git+file://{dir}
        """,
            ["origin"],
        ],
        [
            """
        {tmp_path}/study/myrepo:
            {CLONE_NAME}:
               repo: git+file://{dir}
        """,
            ["repo"],
        ],
        [
            """
        {tmp_path}/study/myrepo:
            {CLONE_NAME}:
                repo: git+file://{dir}
                remotes:
                  secondremote: git+file://{dir}
        """,
            ["secondremote"],
        ],
    ],
)
def test_config_variations(
    tmp_path: pathlib.Path,
    create_git_remote_repo: CreateProjectCallbackFixtureProtocol,
    config_tpl: str,
    capsys: pytest.CaptureFixture[str],
    remote_list: t.List[str],
) -> None:
    """Test config output with variation of config formats"""
    dummy_repo_name = "dummy_repo"
    dummy_repo = create_git_remote_repo(remote_repo_name=dummy_repo_name)

    config_file = write_config_remote(
        config_path=tmp_path / "myrepos.yaml",
        tmp_path=tmp_path,
        config_tpl=config_tpl,
        dir=dummy_repo,
        clone_name="myclone",
    )
    configs = load_configs([str(config_file)])

    # TODO: Merge repos
    repos = filter_repos(configs, dir="*")
    assert len(repos) == 1

    for repo_dict in repos:
        repo_url = repo_dict["url"].replace("git+", "")
        repo: GitSync = update_repo(repo_dict)
        remotes = repo.remotes() or {}
        remote_names = set(remotes.keys())
        assert set(remote_list).issubset(remote_names) or {"origin"}.issubset(
            remote_names
        )

        for remote_name, remote_info in remotes.items():
            current_remote = repo.remote(remote_name)
            assert current_remote is not None
            assert current_remote.fetch_url == repo_url


@pytest.mark.parametrize(
    "config_tpl,has_extra_remotes",
    [
        [
            """
        {tmp_path}/study/myrepo:
            {CLONE_NAME}: git+file://{dir}
        """,
            False,
        ],
        [
            """
        {tmp_path}/study/myrepo:
            {CLONE_NAME}:
               repo: git+file://{dir}
        """,
            False,
        ],
        [
            """
        {tmp_path}/study/myrepo:
            {CLONE_NAME}:
                repo: git+file://{dir}
                remotes:
                  mirror_repo: git+file://{dir}
        """,
            True,
        ],
    ],
)
def test_updating_remote(
    tmp_path: pathlib.Path,
    create_git_remote_repo: CreateProjectCallbackFixtureProtocol,
    config_tpl: str,
    has_extra_remotes: bool,
) -> None:
    """Ensure additions/changes to yaml config are reflected"""

    dummy_repo_name = "dummy_repo"
    dummy_repo = create_git_remote_repo(remote_repo_name=dummy_repo_name)

    mirror_name = "mirror_repo"
    mirror_repo = create_git_remote_repo(remote_repo_name=mirror_name)

    repo_parent = tmp_path / "study" / "myrepo"
    repo_parent.mkdir(parents=True)

    initial_config: ConfigDict = {
        "vcs": "git",
        "name": "myclone",
        "dir": f"{tmp_path}/study/myrepo/myclone",
        "url": f"git+file://{dummy_repo}",
        "remotes": {
            mirror_name: GitRemote(
                name=mirror_name,
                fetch_url=f"git+file://{dummy_repo}",
                push_url=f"git+file://{dummy_repo}",
            )
        },
    }

    for repo_dict in filter_repos(
        [initial_config],
    ):
        local_git_remotes = update_repo(repo_dict).remotes()
        assert "origin" in local_git_remotes

    expected_remote_url = f"git+file://{mirror_repo}"

    expected_config: ConfigDict = initial_config.copy()
    assert isinstance(expected_config["remotes"], dict)
    expected_config["remotes"][mirror_name] = GitRemote(
        name=mirror_name,
        fetch_url=expected_remote_url,
        push_url=expected_remote_url,
    )

    repo_dict = filter_repos([expected_config], name="myclone")[0]
    repo = update_repo(repo_dict)
    for remote_name, remote_info in repo.remotes().items():
        remote = repo.remote(remote_name)
        if remote is not None:
            current_remote_url = remote.fetch_url.replace("git+", "")
            if remote_name in expected_config["remotes"]:
                assert (
                    expected_config["remotes"][remote_name].fetch_url.replace(
                        "git+", ""
                    )
                    == current_remote_url
                )

            elif remote_name == "origin" and remote_name in expected_config["remotes"]:
                assert (
                    expected_config["remotes"]["origin"].fetch_url.replace("git+", "")
                    == current_remote_url
                )
