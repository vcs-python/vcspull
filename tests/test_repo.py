"""Tests for placing config dicts into :py:class:`Project` objects."""
import pathlib

from libvcs import BaseSync, GitSync, HgSync, SvnSync
from libvcs._internal.shortcuts import create_project
from vcspull.config import filter_repos

from .fixtures import example as fixtures


def test_filter_dir():
    """`filter_repos` filter by dir"""
    repo_list = filter_repos(fixtures.config_dict_expanded, dir="*github_project*")

    assert len(repo_list) == 1
    for r in repo_list:
        assert r["name"] == "kaptan"


def test_filter_name():
    """`filter_repos` filter by name"""
    repo_list = filter_repos(fixtures.config_dict_expanded, name=".vim")

    assert len(repo_list) == 1
    for r in repo_list:
        assert r["name"] == ".vim"


def test_filter_vcs():
    """`filter_repos` filter by vcs remote url"""
    repo_list = filter_repos(fixtures.config_dict_expanded, vcs_url="*kernel.org*")

    assert len(repo_list) == 1
    for r in repo_list:
        assert r["name"] == "linux"


def test_to_dictlist():
    """`filter_repos` pulls the repos in dict format from the config."""
    repo_list = filter_repos(fixtures.config_dict_expanded)

    for r in repo_list:
        assert isinstance(r, dict)
        assert "name" in r
        assert "parent_dir" in r
        assert "url" in r
        assert "vcs" in r

        if "remotes" in r:
            assert isinstance(r["remotes"], list)
            for remote in r["remotes"]:
                assert isinstance(remote, dict)
                assert "remote_name" == remote
                assert "url" == remote


def test_vcs_url_scheme_to_object(tmp_path: pathlib.Path):
    """Verify `url` return {Git,Mercurial,Subversion}Project.

    :class:`GitSync`, :class:`HgSync` or :class:`SvnSync`
    object based on the pip-style URL scheme.

    """
    git_repo = create_project(
        vcs="git",
        url="git+git://git.myproject.org/MyProject.git@da39a3ee5e6b4b",
        dir=str(tmp_path / "myproject1"),
    )

    # TODO cwd and name if duplicated should give an error

    assert isinstance(git_repo, GitSync)
    assert isinstance(git_repo, BaseSync)

    hg_repo = create_project(
        vcs="hg",
        url="hg+https://hg.myproject.org/MyProject#egg=MyProject",
        dir=str(tmp_path / "myproject2"),
    )

    assert isinstance(hg_repo, HgSync)
    assert isinstance(hg_repo, BaseSync)

    svn_repo = create_project(
        vcs="svn",
        url="svn+svn://svn.myproject.org/svn/MyProject#egg=MyProject",
        dir=str(tmp_path / "myproject3"),
    )

    assert isinstance(svn_repo, SvnSync)
    assert isinstance(svn_repo, BaseSync)


def test_to_repo_objects(tmp_path: pathlib.Path):
    """:py:obj:`dict` objects into Project objects."""
    repo_list = filter_repos(fixtures.config_dict_expanded)
    for repo_dict in repo_list:
        r = create_project(**repo_dict)  # type: ignore

        assert isinstance(r, BaseSync)
        assert r.repo_name
        assert r.repo_name == repo_dict["name"]
        assert r.dir.parent
        assert r.url
        assert r.url == repo_dict["url"]

        assert r.dir == r.dir / r.repo_name

        if hasattr(r, "remotes") and isinstance(r, GitSync):
            assert isinstance(r.remotes, dict)
            for remote_name, remote_dict in r.remotes.items():
                assert isinstance(remote_dict, dict)
                assert "fetch_url" in remote_dict
                assert "push_url" in remote_dict
