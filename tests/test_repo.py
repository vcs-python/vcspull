"""Tests for placing config dicts into :py:class:`Project` objects."""
import os

from _pytest.compat import LEGACY_PATH

from libvcs import BaseProject, GitProject, MercurialProject, SubversionProject
from libvcs.shortcuts import create_project_from_pip_url
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

        if "remotes" in r:
            assert isinstance(r["remotes"], list)
            for remote in r["remotes"]:
                assert isinstance(remote, dict)
                assert "remote_name" == remote
                assert "url" == remote


def test_vcs_url_scheme_to_object(tmpdir: LEGACY_PATH):
    """Verify `url` return {Git,Mercurial,Subversion}Project.

    :class:`GitProject`, :class:`MercurialProject` or :class:`SubversionProject`
    object based on the pip-style URL scheme.

    """
    git_repo = create_project_from_pip_url(
        **{
            "pip_url": "git+git://git.myproject.org/MyProject.git@da39a3ee5e6b4b",
            "dir": str(tmpdir.join("myproject1")),
        }
    )

    # TODO cwd and name if duplicated should give an error

    assert isinstance(git_repo, GitProject)
    assert isinstance(git_repo, BaseProject)

    hg_repo = create_project_from_pip_url(
        **{
            "pip_url": "hg+https://hg.myproject.org/MyProject#egg=MyProject",
            "dir": str(tmpdir.join("myproject2")),
        }
    )

    assert isinstance(hg_repo, MercurialProject)
    assert isinstance(hg_repo, BaseProject)

    svn_repo = create_project_from_pip_url(
        **{
            "pip_url": "svn+svn://svn.myproject.org/svn/MyProject#egg=MyProject",
            "dir": str(tmpdir.join("myproject3")),
        }
    )

    assert isinstance(svn_repo, SubversionProject)
    assert isinstance(svn_repo, BaseProject)


def test_to_repo_objects(tmpdir: LEGACY_PATH):
    """:py:obj:`dict` objects into Project objects."""
    repo_list = filter_repos(fixtures.config_dict_expanded)
    for repo_dict in repo_list:
        r = create_project_from_pip_url(**repo_dict)

        assert isinstance(r, BaseProject)
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
