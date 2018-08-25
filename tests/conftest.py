# -*- coding: utf-8 -*-
from __future__ import absolute_import, print_function, unicode_literals

import pytest

from libvcs.shortcuts import create_repo_from_pip_url
from libvcs.util import run


@pytest.fixture
def tmpdir_repoparent(tmpdir_factory, scope='function'):
    """Return temporary directory for repository checkout guaranteed unique."""
    fn = tmpdir_factory.mktemp("repo")
    return fn


@pytest.fixture
def git_repo_kwargs(tmpdir_repoparent, git_dummy_repo_dir):
    """Return kwargs for :func:`create_repo_from_pip_url`."""
    repo_name = 'repo_clone'
    return {
        'url': 'git+file://' + git_dummy_repo_dir,
        'parent_dir': str(tmpdir_repoparent),
        'name': repo_name,
    }


@pytest.fixture
def git_repo(git_repo_kwargs):
    """Create an git repository for tests. Return repo."""
    git_repo = create_repo_from_pip_url(**git_repo_kwargs)
    git_repo.obtain(quiet=True)
    return git_repo


@pytest.fixture
def git_dummy_repo_dir(tmpdir_repoparent, scope='session'):
    """Create a git repo with 1 commit, used as a remote."""
    name = 'dummyrepo'
    repo_path = str(tmpdir_repoparent.join(name))

    run(['git', 'init', name], cwd=str(tmpdir_repoparent))

    testfile_filename = 'testfile.test'

    run(['touch', testfile_filename], cwd=repo_path)
    run(['git', 'add', testfile_filename], cwd=repo_path)
    run(['git', 'commit', '-m', 'test file for %s' % name], cwd=repo_path)

    return repo_path
