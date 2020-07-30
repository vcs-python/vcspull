# -*- coding: utf-8 -*-
"""Tests for placing config dicts into :py:class:`Repo` objects."""
from __future__ import absolute_import, print_function, unicode_literals

import os

from py._path.local import LocalPath

import kaptan

from libvcs import BaseRepo, GitRepo, MercurialRepo, SubversionRepo
from libvcs.shortcuts import create_repo_from_pip_url
from vcspull.cli import update_repo
from vcspull.config import extract_repos, filter_repos, load_configs

from .fixtures import example as fixtures


def test_filter_dir():
    """``filter_repos`` filter by dir"""

    repo_list = filter_repos(fixtures.config_dict_expanded, repo_dir="*github_project*")

    assert len(repo_list) == 1
    for r in repo_list:
        assert r['name'] == 'kaptan'


def test_filter_name():
    """``filter_repos`` filter by name"""
    repo_list = filter_repos(fixtures.config_dict_expanded, name=".vim")

    assert len(repo_list) == 1
    for r in repo_list:
        assert r['name'] == '.vim'


def test_filter_vcs():
    """``filter_repos`` filter by vcs remote url"""
    repo_list = filter_repos(fixtures.config_dict_expanded, vcs_url="*kernel.org*")

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
    git_repo = create_repo_from_pip_url(
        **{
            'pip_url': 'git+git://git.myproject.org/MyProject.git@da39a3ee5e6b4b',
            'repo_dir': str(tmpdir.join('myproject1')),
        }
    )

    # TODO cwd and name if duplicated should give an error

    assert isinstance(git_repo, GitRepo)
    assert isinstance(git_repo, BaseRepo)

    hg_repo = create_repo_from_pip_url(
        **{
            'pip_url': 'hg+https://hg.myproject.org/MyProject#egg=MyProject',
            'repo_dir': str(tmpdir.join('myproject2')),
        }
    )

    assert isinstance(hg_repo, MercurialRepo)
    assert isinstance(hg_repo, BaseRepo)

    svn_repo = create_repo_from_pip_url(
        **{
            'pip_url': 'svn+svn://svn.myproject.org/svn/MyProject#egg=MyProject',
            'repo_dir': str(tmpdir.join('myproject3')),
        }
    )

    assert isinstance(svn_repo, SubversionRepo)
    assert isinstance(svn_repo, BaseRepo)


def test_to_repo_objects(tmpdir):
    """:py:obj:`dict` objects into Repo objects."""
    repo_list = filter_repos(fixtures.config_dict_expanded)
    for repo_dict in repo_list:
        r = create_repo_from_pip_url(**repo_dict)

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
            for remote_name, remote_dict in r['remotes'].items():
                assert isinstance(remote_dict, dict)
                assert 'fetch_url' in remote_dict
                assert 'push_url' in remote_dict


def test_makes_recursive(tmpdir, git_dummy_repo_dir):
    """Ensure that directories in pull are made recursively."""

    YAML_CONFIG = """
    {TMP_DIR}/study/myrepo:
        my_url: git+file://{REPO_DIR}
    """

    YAML_CONFIG = YAML_CONFIG.format(TMP_DIR=str(tmpdir), REPO_DIR=git_dummy_repo_dir)

    conf = kaptan.Kaptan(handler='yaml')
    conf.import_config(YAML_CONFIG)
    conf = conf.export('dict')
    repos = extract_repos(conf)

    for r in filter_repos(repos):
        repo = create_repo_from_pip_url(**r)
        repo.obtain()


def test_updating_remote(tmpdir, create_git_dummy_repo):
    # type: (LocalPath, LocalPath)
    """Ensure that directories in pull are made recursively."""

    dummy_repo_name = 'dummy_repo'
    dummy_repo = create_git_dummy_repo(dummy_repo_name)  # type: LocalPath

    def create_and_load_configs(repo_dir, clone_name):
        YAML_CONFIG = """
        {TMP_DIR}/study/myrepo:
            {CLONE_NAME}: git+file://{REPO_DIR}
            {CLONE_NAME}_style_two:
               repo: git+file://{REPO_DIR}
            {CLONE_NAME}_style_two_with_remotes:
               repo: git+file://{REPO_DIR}
               remotes:
                   secondremote: git+file://{REPO_DIR}
        """

        YAML_CONFIG = YAML_CONFIG.format(
            TMP_DIR=str(tmpdir), REPO_DIR=repo_dir, CLONE_NAME=clone_name
        )
        CONFIG_FILENAME = 'myrepos.yaml'
        config_file = tmpdir.join(CONFIG_FILENAME)
        config_file.write(YAML_CONFIG)
        repo_parent = tmpdir.join('study/myrepo')
        repo_parent.ensure(dir=True)
        return config_file

    config_file = create_and_load_configs(repo_dir=dummy_repo, clone_name='myclone')
    configs = load_configs([str(config_file)])

    for repo_dict in filter_repos(configs, repo_dir='*', vcs_url='*', name='*'):
        old_repo_remotes = update_repo(repo_dict).remotes()['origin']

    # Later: Copy dummy repo somewhere else so the commits are common
    config_file = create_and_load_configs(
        repo_dir=dummy_repo, clone_name='anotherclone'
    )
    configs = load_configs([str(config_file)])

    for repo_dict in filter_repos(configs, repo_dir='*', vcs_url='*', name='*'):
        repo_url = repo_dict['url'].replace('git+', '')
        r = update_repo(repo_dict)
        remotes = r.remotes() or {}
        for remote_name, remote_data in remotes.items():
            current_remote_url = r.remotes()[remote_name]
            assert current_remote_url['fetch_url'] == repo_url
            assert current_remote_url['push_url'] == repo_url
            assert set(old_repo_remotes).issubset(set(current_remote_url))
