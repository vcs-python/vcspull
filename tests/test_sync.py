import pathlib
import textwrap
from typing import Callable, List

import pytest

import kaptan

from libvcs.git import GitRemote
from libvcs.shortcuts import create_repo_from_pip_url
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


def write_config_remote(tmp_path, config_tpl, repo_dir, clone_name):
    return write_config(
        tmp_path,
        "myrepos.yaml",
        config_tpl.format(
            tmp_path=str(tmp_path), repo_dir=repo_dir, CLONE_NAME=clone_name
        ),
    )


@pytest.mark.parametrize(
    "config_tpl,remote_list",
    [
        [
            """
        {tmp_path}/study/myrepo:
            {CLONE_NAME}: git+file://{repo_dir}
        """,
            ["origin"],
        ],
        [
            """
        {tmp_path}/study/myrepo:
            {CLONE_NAME}:
               repo: git+file://{repo_dir}
        """,
            ["repo"],
        ],
        [
            """
        {tmp_path}/study/myrepo:
            {CLONE_NAME}:
                repo: git+file://{repo_dir}
                remotes:
                    secondremote: git+file://{repo_dir}
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
        tmp_path=tmp_path,
        config_tpl=config_tpl,
        repo_dir=dummy_repo,
        clone_name="myclone",
    )
    configs = load_configs([str(config_file)])

    # TODO: Merge repos
    # repos = filter_repos(configs, repo_dir="*")
    from pprint import pprint

    pprint("configs", indent=2)
    pprint(configs, indent=2)
    repos = filter_repos(configs)
    assert len(repos) == 1

    for repo_dict in repos:
        repo_url = repo_dict["url"].replace("git+", "")
        repo = update_repo(repo_dict)
        remotes = repo.remotes() or []
        remote_names = set(remotes.keys())
        assert set(remote_list).issubset(remote_names) or {"origin"}.issubset(
            remote_names
        )
        captured = capsys.readouterr()
        assert f"Updating remote {list(remote_names)[0]}" in captured.out

        for remote_name, remote_info in remotes.items():
            current_remote = repo.remote(remote_name)
            assert current_remote.fetch_url == repo_url


@pytest.mark.parametrize(
    "config_tpl,has_extra_remotes",
    [
        [
            """
        {tmp_path}/study/myrepo:
            {CLONE_NAME}: git+file://{repo_dir}
        """,
            False,
        ],
        [
            """
        {tmp_path}/study/myrepo:
            {CLONE_NAME}:
               repo: git+file://{repo_dir}
        """,
            False,
        ],
        [
            """
        {tmp_path}/study/myrepo:
            {CLONE_NAME}:
                repo: git+file://{repo_dir}
                remotes:
                    secondremote: git+file://{repo_dir}
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

    repo_parent = tmp_path / "study" / "myrepo"
    repo_parent.mkdir(parents=True)

    base_config = {
        "name": "myclone",
        "repo_dir": f"{tmp_path}/study/myrepo/myclone",
        "parent_dir": f"{tmp_path}/study/myrepo",
        "url": f"git+file://{dummy_repo}",
        "remotes": {
            "secondremote": GitRemote(
                name="secondremote",
                fetch_url=f"git+file://{dummy_repo}",
                push_url=f"git+file://{dummy_repo}",
            )
        },
    }

    def merge_dict(_dict, extra):
        _dict = _dict.copy()
        _dict.update(**extra)
        return _dict

    configs = [base_config]

    for repo_dict in filter_repos(
        configs,
    ):
        update_repo(repo_dict).remotes()["origin"]

    expected_remote_url = f"git+file://{dummy_repo}/moo"

    config = merge_dict(
        base_config,
        extra={
            "remotes": {
                "secondremote": GitRemote(
                    name="secondremote",
                    fetch_url=expected_remote_url,
                    push_url=expected_remote_url,
                )
            }
        },
    )
    configs = [config]

    repo_dict = filter_repos(configs, name="myclone")[0]
    r = update_repo(repo_dict)
    for remote_name, remote_info in r.remotes().items():
        current_remote_url = r.remote(remote_name).fetch_url.replace("git+", "")
        config_remote_url = (
            next(
                (
                    r.fetch_url
                    for rname, r in config["remotes"].items()
                    if rname == remote_name
                ),
                None,
            )
            if remote_name != "origin"
            else config["url"]
        ).replace("git+", "")
        assert config_remote_url == current_remote_url


@pytest.mark.parametrize(
    "config_tpl",
    [
        """
        {tmp_path}/study/myrepo:
            {CLONE_NAME}: git+file://{repo_dir}
        """,
        """
        {tmp_path}/study/myrepo:
            {CLONE_NAME}: git+file://{repo_dir}
            remotes:
              mymirror: git+file://{repo_dir}
        """,
    ],
)
def test_simple_url(
    tmp_path: pathlib.Path,
    create_git_dummy_repo: Callable[[str], pathlib.Path],
    config_tpl: str,
    capsys: pytest.LogCaptureFixture,
):
    """Test config output with varation of config formats"""
    import random

    dummy_repo_name = f"dummy_repo_{random.randint(1,20)}"
    dummy_repo = create_git_dummy_repo(dummy_repo_name)

    config_file = write_config_remote(
        tmp_path=tmp_path,
        config_tpl=config_tpl,
        repo_dir=dummy_repo,
        clone_name=f"myclone {random.randint(1, 29)}",
    )
    configs = load_configs([str(config_file)])

    # TODO: Merge repos
    repos = filter_repos(configs, repo_dir="*")
    assert len(repos) == 1
    # from pprint import pprint
    # pprint(repos[0], indent=2)

    def update():

        for repo_dict in repos:
            repo_url = repo_dict["url"].replace("git+", "")
            repo = update_repo(repo_dict)
            remotes = repo.remotes() or []
            remote_names = set(remotes.keys())
            assert {"origin"}.issubset(remote_names)
            # captured = capsys.readouterr()
            # assert f"Updating remote {list(remote_names)[0]}" in captured.out

            for remote_name, remote_info in remotes.items():
                current_remote = repo.remote(remote_name)
                assert current_remote.fetch_url == repo_url

    update()
    # captured = capsys.readouterr()
    # assert "Updating remote " in captured.out

    update()
    captured = capsys.readouterr()
    assert (
        not "Updating remote " in captured.out
    ), "should not set overwrite remote a second time"
