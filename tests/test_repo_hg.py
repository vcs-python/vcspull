# -*- coding: utf-8 -*-
"""Tests for vcspull hg repos."""
from __future__ import (absolute_import, division, print_function,
                        unicode_literals, with_statement)

import os
import pytest

from vcspull import exc
from vcspull.repo import create_repo
from vcspull.util import run, which

try:
    which('hg')
except exc.VCSPullException:
    pytestmark = pytest.mark.skip(reason="hg is not available")


@pytest.fixture
def hg_dummy_repo_dir(tmpdir_repoparent, scope='session'):
    """Create a git repo with 1 commit, used as a remote."""
    name = 'dummyrepo'
    repo_path = str(tmpdir_repoparent.join(name))

    run(['hg', 'init', name], cwd=str(tmpdir_repoparent))

    testfile_filename = 'testfile.test'

    run(['touch', testfile_filename],
        cwd=repo_path)
    run(['hg', 'add', testfile_filename],
        cwd=repo_path)
    run(['hg', 'commit', '-m', 'test file for %s' % name],
        cwd=repo_path)

    return repo_path


def test_repo_mercurial(tmpdir, hg_dummy_repo_dir):
    repo_name = 'my_mercurial_project'

    mercurial_repo = create_repo(**{
        'url': 'hg+file://' + hg_dummy_repo_dir,
        'parent_dir': str(tmpdir),
        'name': repo_name
    })

    run(['hg', 'init', mercurial_repo['name']],
        cwd=str(tmpdir))

    mercurial_repo.obtain()
    mercurial_repo.update_repo()

    test_repo_revision = run(
        ['hg', 'parents', '--template={rev}'],
        cwd=str(tmpdir.join(repo_name)),
    )

    assert mercurial_repo.get_revision() == test_repo_revision
    assert os.path.exists(str(tmpdir.join(repo_name)))
