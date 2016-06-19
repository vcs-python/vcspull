# -*- coding: utf-8 -*-
"""Tests for placing config dicts into :py:class:`Repo` objects."""
from __future__ import absolute_import, print_function, unicode_literals

import os

import kaptan

from libvcs import (BaseRepo, GitRepo, MercurialRepo, SubversionRepo,
                    create_repo)
from vcspull.config import extract_repos, filter_repos

from .fixtures import example as fixtures


def test_filter_dir():
    """``filter_repos`` filter by dir"""

    repo_list = filter_repos(
        fixtures.config_dict_expanded,
        repo_dir="*github_project*"
    )

    assert len(repo_list) == 1
    for r in repo_list:
        assert r['name'] == 'kaptan'


def test_filter_name():
    """``filter_repos`` filter by name"""
    repo_list = filter_repos(
        fixtures.config_dict_expanded,
        name=".vim"
    )

    assert len(repo_list) == 1
    for r in repo_list:
        assert r['name'] == '.vim'


def test_filter_vcs():
    """``filter_repos`` filter by vcs remote url"""
    repo_list = filter_repos(
        fixtures.config_dict_expanded,
        vcs_url="*kernel.org*"
    )

    assert len(repo_list) == 1
    for r in repo_list:
        assert r['name'] == 'linux'


def test_to_dictlist():
    """``filter_repos`` pulls the repos in dict format from the config."""
    repo_list = filter_repos(fixtures.config_dict_expanded)

    for r in repo_list:
        assert isinstance(r, dict)
        assert 'name' in r
        assert 'parent_dir' in r
        assert 'url' in r

        if 'remotes' in r:
            assert isinstance(r['remotes'], list)
            for remote in r['remotes']:
                assert isinstance(remote, dict)
                assert 'remote_name' == remote
                assert 'url' == remote


def test_vcs_url_scheme_to_object(tmpdir):
    """Test that ``url`` return a GitRepo/MercurialRepo/SubversionRepo.

    :class:`GitRepo`, :class:`MercurialRepo` or :class:`SubversionRepo`
    object based on the pip-style URL scheme.

    """
    git_repo = create_repo(**{
        'url': 'git+git://git.myproject.org/MyProject.git@da39a3ee5e6b4b',
        'parent_dir': str(tmpdir),
        'name': 'myproject1'
    })

    # TODO cwd and name if duplicated should give an error

    assert isinstance(git_repo, GitRepo)
    assert isinstance(git_repo, BaseRepo)

    hg_repo = create_repo(**{
        'url': 'hg+https://hg.myproject.org/MyProject#egg=MyProject',
        'parent_dir': str(tmpdir),
        'name': 'myproject2'
    })

    assert isinstance(hg_repo, MercurialRepo)
    assert isinstance(hg_repo, BaseRepo)

    svn_repo = create_repo(**{
        'url': 'svn+svn://svn.myproject.org/svn/MyProject#egg=MyProject',
        'parent_dir': str(tmpdir),
        'name': 'myproject3'
    })

    assert isinstance(svn_repo, SubversionRepo)
    assert isinstance(svn_repo, BaseRepo)


def test_to_repo_objects(tmpdir):
    """:py:obj:`dict` objects into Repo objects."""
    repo_list = filter_repos(fixtures.config_dict_expanded)
    for repo_dict in repo_list:
        r = create_repo(**repo_dict)

        assert isinstance(r, BaseRepo)
        assert 'name' in r
        assert r['name'] == repo_dict['name']
        assert 'parent_dir' in r
        assert r['parent_dir'] == repo_dict['parent_dir']
        assert 'url' in r
        assert r['url'] == repo_dict['url']

        assert r['path'] == os.path.join(r['parent_dir'], r['name'])

        if 'remotes' in repo_dict:
            assert isinstance(r['remotes'], list)
            for remote in r['remotes']:
                assert isinstance(remote, dict)
                assert 'remote_name' in remote
                assert 'url' in remote


def test_makes_recursive(tmpdir, git_dummy_repo_dir):
    """Ensure that directories in pull are made recursively."""

    YAML_CONFIG = """
    {TMP_DIR}/study/myrepo:
        my_url: git+file://{REPO_DIR}
    """

    YAML_CONFIG = YAML_CONFIG.format(
        TMP_DIR=str(tmpdir),
        REPO_DIR=git_dummy_repo_dir
    )

    conf = kaptan.Kaptan(handler='yaml')
    conf.import_config(YAML_CONFIG)
    conf = conf.export('dict')
    repos = extract_repos(conf)

    for r in filter_repos(repos):
        repo = create_repo(**r)
        repo.obtain()
