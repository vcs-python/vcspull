# -*- coding: utf-8 -*-
"""Tests for vcspull svn repos."""
from __future__ import (absolute_import, division, print_function,
                        unicode_literals, with_statement)

import os

import pytest

from vcspull.repo import create_repo
from vcspull.util import run


@pytest.fixture
def svn_dummy_repo_dir(tmpdir_repoparent, scope='session'):
    """Create a git repo with 1 commit, used as a remote."""
    name = 'dummyrepo'
    repo_path = str(tmpdir_repoparent.join(name))

    run(['svnadmin', 'create', name], cwd=str(tmpdir_repoparent))

    testfile_filename = 'testfile.test'

    run(['touch', testfile_filename],
        cwd=repo_path)

    run(['svn', 'add', '--non-interactive', testfile_filename],
        cwd=repo_path)
    run(
        ['svn', 'commit', '-m', 'a test file for %s' % name],
        cwd=repo_path
    )

    return repo_path


def test_repo_svn(tmpdir, svn_dummy_repo_dir):
    repo_name = 'my_svn_project'

    svn_repo = create_repo(**{
        'url': 'svn+file://' + svn_dummy_repo_dir,
        'parent_dir': str(tmpdir),
        'name': repo_name
    })

    svn_repo.obtain()
    svn_repo.update_repo()

    assert svn_repo.get_revision() == 0

    assert os.path.exists(str(tmpdir.join(repo_name)))
