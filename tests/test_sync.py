import pathlib
import textwrap
from typing import Callable, List

import pytest

import kaptan

from libvcs.shortcuts import create_repo_from_pip_url
from libvcs.states.git import GitRemote
from vcspull.cli.sync import update_repo
from vcspull.config import extract_repos, filter_repos, load_configs

from .helpers import write_config


def test_makes_recursive(
    tmp_path: pathlib.Path,
    git_dummy_repo_dir: pathlib.Path,
):
    """Ensure that directories in pull are made recursively."""
    conf = kaptan.Kaptan(handler="yaml")
    conf.import_config(
        textwrap.dedent(
            f"""
        {tmp_path}/study/myrepo:
            my_url: git+file://{git_dummy_repo_dir}
    """
        )
    )
    conf = conf.export("dict")
    repos = extract_repos(conf)

    for r in filter_repos(repos):
        repo = create_repo_from_pip_url(**r)
        repo.obtain()


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
    create_git_dummy_repo: Callable[[str], pathlib.Path],
    config_tpl: str,
    capsys: pytest.LogCaptureFixture,
    remote_list: List[str],
):
    """Test config output with variation of config formats"""
    dummy_repo_name = "dummy_repo"
    dummy_repo = create_git_dummy_repo(dummy_repo_name)

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
        repo = update_repo(repo_dict)
        remotes = repo.remotes() or []
        remote_names = set(remotes.keys())
        assert set(remote_list).issubset(remote_names) or {"origin"}.issubset(
            remote_names
        )

        for remote_name, remote_info in remotes.items():
            current_remote = repo.remote(remote_name)
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
    create_git_dummy_repo: Callable[[str], pathlib.Path],
    config_tpl: str,
    has_extra_remotes,
):
    """Ensure additions/changes to yaml config are reflected"""

    dummy_repo_name = "dummy_repo"
    dummy_repo = create_git_dummy_repo(dummy_repo_name)

    mirror_name = "mirror_repo"
    mirror_repo = create_git_dummy_repo(mirror_name)

    repo_parent = tmp_path / "study" / "myrepo"
    repo_parent.mkdir(parents=True)

    initial_config = {
        "name": "myclone",
        "dir": f"{tmp_path}/study/myrepo/myclone",
        "parent_dir": f"{tmp_path}/study/myrepo",
        "url": f"git+file://{dummy_repo}",
        "remotes": {
            mirror_name: {
                "name": mirror_name,
                "fetch_url": f"git+file://{dummy_repo}",
                "push_url": f"git+file://{dummy_repo}",
            }
        },
    }

    for repo_dict in filter_repos(
        [initial_config],
    ):
        local_git_remotes = update_repo(repo_dict).remotes()
        assert "origin" in local_git_remotes

    expected_remote_url = f"git+file://{mirror_repo}"

    config = initial_config | {
        "remotes": {
            mirror_name: GitRemote(
                name=mirror_name,
                fetch_url=expected_remote_url,
                push_url=expected_remote_url,
            )
        }
    }

    repo_dict = filter_repos([config], name="myclone")[0]
    repo = update_repo(repo_dict)
    for remote_name, remote_info in repo.remotes().items():
        current_remote_url = repo.remote(remote_name).fetch_url.replace("git+", "")
        if remote_name in config["remotes"]:
            assert (
                config["remotes"][remote_name].fetch_url.replace("git+", "")
                == current_remote_url
            )

        elif remote_name == "origin":
            assert config["url"].replace("git+", "") == current_remote_url
