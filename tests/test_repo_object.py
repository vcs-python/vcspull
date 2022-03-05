"""Tests for placing config dicts into :py:class:`Repo` objects."""
import os
import textwrap
from typing import Callable

import pytest

import kaptan
from _pytest.compat import LEGACY_PATH

from libvcs import BaseRepo, GitRepo, MercurialRepo, SubversionRepo
from libvcs.git import GitRemote
from libvcs.shortcuts import create_repo_from_pip_url
from vcspull.cli.sync import update_repo
from vcspull.config import extract_repos, filter_repos, load_configs

from .fixtures import example as fixtures


def test_filter_dir():
    """``filter_repos`` filter by dir"""
    repo_list = filter_repos(fixtures.config_dict_expanded, repo_dir="*github_project*")

    assert len(repo_list) == 1
    for r in repo_list:
        assert r["name"] == "kaptan"


def test_filter_name():
    """``filter_repos`` filter by name"""
    repo_list = filter_repos(fixtures.config_dict_expanded, name=".vim")

    assert len(repo_list) == 1
    for r in repo_list:
        assert r["name"] == ".vim"


def test_filter_vcs():
    """``filter_repos`` filter by vcs remote url"""
    repo_list = filter_repos(fixtures.config_dict_expanded, vcs_url="*kernel.org*")

    assert len(repo_list) == 1
    for r in repo_list:
        assert r["name"] == "linux"


def test_to_dictlist():
    """``filter_repos`` pulls the repos in dict format from the config."""
    repo_list = filter_repos(fixtures.config_dict_expanded)

    for r in repo_list:
        assert isinstance(r, dict)
        assert "name" in r
        assert "parent_dir" in r
        assert "url" in r

        if "remotes" in r:
            assert isinstance(r["remotes"], list)
            for remote in r["remotes"]:
                assert isinstance(remote, dict)
                assert "remote_name" == remote
                assert "url" == remote


def test_vcs_url_scheme_to_object(tmpdir: LEGACY_PATH):
    """Verify ``url`` return {Git,Mercurial,Subversion}Repo.

    :class:`GitRepo`, :class:`MercurialRepo` or :class:`SubversionRepo`
    object based on the pip-style URL scheme.

    """
    git_repo = create_repo_from_pip_url(
        **{
            "pip_url": "git+git://git.myproject.org/MyProject.git@da39a3ee5e6b4b",
            "repo_dir": str(tmpdir.join("myproject1")),
        }
    )

    # TODO cwd and name if duplicated should give an error

    assert isinstance(git_repo, GitRepo)
    assert isinstance(git_repo, BaseRepo)

    hg_repo = create_repo_from_pip_url(
        **{
            "pip_url": "hg+https://hg.myproject.org/MyProject#egg=MyProject",
            "repo_dir": str(tmpdir.join("myproject2")),
        }
    )

    assert isinstance(hg_repo, MercurialRepo)
    assert isinstance(hg_repo, BaseRepo)

    svn_repo = create_repo_from_pip_url(
        **{
            "pip_url": "svn+svn://svn.myproject.org/svn/MyProject#egg=MyProject",
            "repo_dir": str(tmpdir.join("myproject3")),
        }
    )

    assert isinstance(svn_repo, SubversionRepo)
    assert isinstance(svn_repo, BaseRepo)


def test_to_repo_objects(tmpdir: LEGACY_PATH):
    """:py:obj:`dict` objects into Repo objects."""
    repo_list = filter_repos(fixtures.config_dict_expanded)
    for repo_dict in repo_list:
        r = create_repo_from_pip_url(**repo_dict)

        assert isinstance(r, BaseRepo)
        assert r.name
        assert r.name == repo_dict["name"]
        assert r.parent_dir
        assert r.parent_dir == repo_dict["parent_dir"]
        assert r.url
        assert r.url == repo_dict["url"]

        assert r.path == os.path.join(r.parent_dir, r.name)

        if "remotes" in repo_dict:
            assert isinstance(r.remotes, list)
            for remote_name, remote_dict in r.remotes.items():
                assert isinstance(remote_dict, dict)
                assert "fetch_url" in remote_dict
                assert "push_url" in remote_dict


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
    "config_tpl",
    [
        """
        {tmpdir}/study/myrepo:
            {CLONE_NAME}: git+file://{repo_dir}
        """,
        """
        {tmpdir}/study/myrepo:
            {CLONE_NAME}:
               repo: git+file://{repo_dir}
        """,
        """
        {tmpdir}/study/myrepo:
            {CLONE_NAME}:
                repo: git+file://{repo_dir}
                remotes:
                    secondremote: git+file://{repo_dir}
        """,
    ],
)
def test_config_variations(
    tmpdir: LEGACY_PATH,
    create_git_dummy_repo: Callable[[str], LEGACY_PATH],
    config_tpl: str,
):
    """Test config output with varation of config formats"""

    dummy_repo_name = "dummy_repo"
    dummy_repo = create_git_dummy_repo(dummy_repo_name)

    def write_config(repo_dir, clone_name):

        config = config_tpl.format(
            tmpdir=str(tmpdir), repo_dir=repo_dir, CLONE_NAME=clone_name
        )
        config_file = tmpdir.join("myrepos.yaml")
        config_file.write(config)
        repo_parent = tmpdir.join("study/myrepo")
        repo_parent.ensure(dir=True)
        return config_file

    config_file = write_config(repo_dir=dummy_repo, clone_name="myclone")
    configs = load_configs([str(config_file)])

    # Later: Copy dummy repo somewhere else so the commits are common
    config_file = write_config(repo_dir=dummy_repo, clone_name="anotherclone")
    configs = load_configs([str(config_file)])

    for repo_dict in filter_repos(configs, repo_dir="*", vcs_url="*", name="*"):
        repo_url = repo_dict["url"].replace("git+", "")
        r = update_repo(repo_dict)
        remotes = r.remotes or []
        for remote_name, remote_info in remotes().items():
            current_remote = r.remote(remote_name)
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

    for repo_dict in filter_repos(configs, repo_dir="*", vcs_url="*", name="*"):
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

    repo_dict = filter_repos(configs, repo_dir="*", vcs_url="*", name="myclone")[0]
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
