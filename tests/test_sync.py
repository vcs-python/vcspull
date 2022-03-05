import textwrap
from typing import Callable, List

import pytest

import kaptan
from _pytest.compat import LEGACY_PATH

from libvcs.git import GitRemote
from libvcs.shortcuts import create_repo_from_pip_url
from vcspull.cli.sync import update_repo
from vcspull.config import extract_repos, filter_repos, load_configs

from .helpers import write_config


def test_makes_recursive(
    tmpdir: LEGACY_PATH,
    git_dummy_repo_dir: LEGACY_PATH,
):
    """Ensure that directories in pull are made recursively."""
    conf = kaptan.Kaptan(handler="yaml")
    conf.import_config(
        textwrap.dedent(
            """
        {tmpdir}/study/myrepo:
            my_url: git+file://{repo_dir}
    """
        ).format(tmpdir=str(tmpdir), repo_dir=git_dummy_repo_dir)
    )
    conf = conf.export("dict")
    repos = extract_repos(conf)

    for r in filter_repos(repos):
        repo = create_repo_from_pip_url(**r)
        repo.obtain()


@pytest.mark.parametrize(
    "config_tpl,remote_list",
    [
        [
            """
        {tmpdir}/study/myrepo:
            {CLONE_NAME}: git+file://{repo_dir}
        """,
            ["origin"],
        ],
        [
            """
        {tmpdir}/study/myrepo:
            {CLONE_NAME}:
               repo: git+file://{repo_dir}
        """,
            ["repo"],
        ],
        [
            """
        {tmpdir}/study/myrepo:
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
    tmpdir: LEGACY_PATH,
    create_git_dummy_repo: Callable[[str], LEGACY_PATH],
    config_tpl: str,
    capsys: pytest.LogCaptureFixture,
    remote_list: List[str],
):
    """Test config output with varation of config formats"""
    dummy_repo_name = "dummy_repo"
    dummy_repo = create_git_dummy_repo(dummy_repo_name)

    def ensure_parent_dir(repo_dir, clone_name):
        return write_config(
            tmpdir,
            "myrepos.yaml",
            config_tpl.format(
                tmpdir=str(tmpdir), repo_dir=repo_dir, CLONE_NAME=clone_name
            ),
        )

    config_file = ensure_parent_dir(repo_dir=dummy_repo, clone_name="myclone")
    configs = load_configs([str(config_file)])

    # TODO: Merge repos
    repos = filter_repos(configs, repo_dir="*")
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
        {tmpdir}/study/myrepo:
            {CLONE_NAME}: git+file://{repo_dir}
        """,
            False,
        ],
        [
            """
        {tmpdir}/study/myrepo:
            {CLONE_NAME}:
               repo: git+file://{repo_dir}
        """,
            False,
        ],
        [
            """
        {tmpdir}/study/myrepo:
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
    tmpdir: LEGACY_PATH,
    create_git_dummy_repo: Callable[[str], LEGACY_PATH],
    config_tpl: str,
    has_extra_remotes,
):
    """Ensure additions/changes to yaml config are reflected"""

    dummy_repo_name = "dummy_repo"
    dummy_repo = create_git_dummy_repo(dummy_repo_name)

    repo_parent = tmpdir.join("study/myrepo")
    repo_parent.ensure(dir=True)

    base_config = {
        "name": "myclone",
        "repo_dir": "{tmpdir}/study/myrepo/myclone".format(tmpdir=tmpdir),
        "parent_dir": "{tmpdir}/study/myrepo".format(tmpdir=tmpdir),
        "url": "git+file://{repo_dir}".format(repo_dir=dummy_repo),
        "remotes": {
            "secondremote": GitRemote(
                name="secondremote",
                fetch_url="git+file://{repo_dir}".format(repo_dir=dummy_repo),
                push_url="git+file://{repo_dir}".format(repo_dir=dummy_repo),
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

    expected_remote_url = "git+file://{repo_dir}/moo".format(repo_dir=dummy_repo)

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
