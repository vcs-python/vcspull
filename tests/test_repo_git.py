# -*- coding: utf-8 -*-
"""Tests for vcspull git repos."""
from __future__ import (absolute_import, division, print_function,
                        unicode_literals, with_statement)

import os
import unittest

import mock
import pytest

from vcspull import exc
from vcspull._compat import StringIO
from vcspull.repo import create_repo
from vcspull.util import run

from .helpers import ConfigTestCase, RepoTestMixin


@pytest.fixture
def tmpdir_repoparent(tmpdir_factory, scope='function'):
    """Return temporary directory for repository checkout guaranteed unique."""
    fn = tmpdir_factory.mktemp("repo")
    return fn


@pytest.fixture
def git_repo_kwargs(tmpdir_repoparent, git_dummy_repo_dir):
    """Return kwargs for :func:`create_repo`."""
    repo_name = 'repo_clone'
    return {
        'url': 'git+file://' + git_dummy_repo_dir,
        'parent_dir': str(tmpdir_repoparent),
        'name': repo_name
    }


@pytest.fixture
def git_repo(git_repo_kwargs):
    """Create an git repository for tests. Return repo."""
    git_repo = create_repo(**git_repo_kwargs)
    git_repo.obtain(quiet=True)
    return git_repo


@pytest.fixture
def git_dummy_repo_dir(tmpdir_repoparent, scope='session'):
    """Create a git repo with 1 commit, used as a remote."""
    name = 'dummyrepo'
    repo_path = str(tmpdir_repoparent.join(name))

    run(['git', 'init', name], cwd=str(tmpdir_repoparent))

    testfile_filename = 'testfile.test'

    run(['touch', testfile_filename],
        cwd=repo_path)
    run(['git', 'add', testfile_filename],
        cwd=repo_path)
    run(['git', 'commit', '-m', 'test file for %s' % name],
        cwd=repo_path)

    return repo_path


def test_repo_git_obtain_bare_repo(tmpdir):
    repo_name = 'my_git_project'

    run([  # init bare repo
        'git', 'init', repo_name
    ], cwd=str(tmpdir))

    bare_repo_dir = tmpdir.join(repo_name)

    git_repo = create_repo(**{
        'url': 'git+file://' + str(bare_repo_dir),
        'parent_dir': str(tmpdir),
        'name': 'obtaining a bare repo'
    })

    git_repo.obtain(quiet=True)
    assert git_repo.get_revision() == ['HEAD']


def test_repo_git_obtain_full(tmpdir, git_dummy_repo_dir):
    remote_repo_dir = git_dummy_repo_dir

    test_repo_revision = run(
        ['git', 'rev-parse', 'HEAD'],
        cwd=remote_repo_dir,
    )['stdout']

    # create a new repo with the repo as a remote
    git_repo = create_repo(**{
        'url': 'git+file://' + remote_repo_dir,
        'parent_dir': str(tmpdir),
        'name': 'myrepo'
    })

    git_repo.obtain(quiet=True)

    assert git_repo.get_revision() == test_repo_revision
    assert os.path.exists(str(tmpdir.join('myrepo')))


def test_remotes(git_repo_kwargs):
    remote_name = 'myrepo'
    git_repo_kwargs.update(**{
        'remotes': [
            {
                'remote_name': remote_name,
                'url': 'file:///'
            }
        ]
    })

    git_repo = create_repo(**git_repo_kwargs)
    git_repo.obtain(quiet=True)
    assert remote_name in git_repo.remotes_get()


def test_remotes_vcs_prefix(git_repo_kwargs):
    remote_url = 'https://localhost/my/git/repo.git'
    remote_vcs_url = 'git+' + remote_url

    git_repo_kwargs.update(**{
        'remotes': [{
            'remote_name': 'myrepo',
            'url': remote_vcs_url
        }]
    })

    git_repo = create_repo(**git_repo_kwargs)
    git_repo.obtain(quiet=True)

    assert (remote_url, remote_url,) in git_repo.remotes_get().values()


def test_remotes_preserves_git_ssh(git_repo_kwargs):
    # Regression test for #14
    remote_url = 'git+ssh://git@github.com/tony/AlgoXY.git'

    git_repo_kwargs.update(**{
        'name': 'moo',
        'remotes': [{
            'remote_name': 'myrepo',
            'url': remote_url
        }]
    })

    git_repo = create_repo(**git_repo_kwargs)
    git_repo.obtain(quiet=True)

    assert (remote_url, remote_url,) in git_repo.remotes_get().values()


def test_private_ssh_format(git_repo_kwargs):
    git_repo_kwargs.update(**{
        'url': 'git+ssh://github.com:' + '/tmp/omg/private_ssh_repo',
    })
    git_repo = create_repo(**git_repo_kwargs)

    with pytest.raises(exc.VCSPullException) as e:
        git_repo.obtain(quiet=True)
        assert e.match("is malformatted")


def test_ls_remotes(git_repo):
    remotes = git_repo.remotes_get()

    assert 'origin' in remotes


def test_get_remotes(git_repo):

    assert 'origin' in git_repo.remotes_get()


def test_set_remote(git_repo):
    mynewremote = git_repo.remote_set(
        name='myrepo',
        url='file:///'
    )

    assert 'file:///' in mynewremote, 'remote_set returns remote'

    assert 'file:///' in git_repo.remote_get(remote='myrepo'), \
        'remote_get returns remote'

    assert 'myrepo' in git_repo.remotes_get(), \
        '.remotes_get() returns new remote'


class ErrorInStdErrorRaisesException(RepoTestMixin, ConfigTestCase,
                                     unittest.TestCase):

    r"""Need to imitate git remote not found.

    |isobar-frontend| (git)  create_repo directory for isobar-frontend (git) \
        does not exist @ /home/tony/study/std/html/isobar-frontend
    |isobar-frontend| (git)  Cloning.
    |isobar-frontend| (git)  git clone --progress \
        https://github.com/isobar-idev/code-standards/ /\
        home/tony/study/std/html/isobar-frontend
    Cloning into '/home/tony/study/std/html/isobar-frontend'...
    ERROR: Repository not found.
    ad from remote repository.

    Please make sure you have the correct access rights
    and the repository exists.
    """

    def test_repository_not_found_raises_exception(self):
        repo_dir = os.path.join(self.TMP_DIR, '.repo_dir')
        repo_name = 'my_git_project'

        url = 'git+file://' + os.path.join(repo_dir, repo_name)
        git_repo = create_repo(**{
            'url': url,
            'parent_dir': self.TMP_DIR,
            'name': repo_name
        })
        error_output = 'ERROR: hello mock subprocess stderr'

        with self.assertRaisesRegexp(exc.VCSPullException, error_output):
            with mock.patch(
                "vcspull.repo.base.subprocess.Popen"
            ) as mock_subprocess:
                mock_subprocess.return_value = mock.Mock(
                    stdout=StringIO('hello mock subprocess stdout'),
                    stderr=StringIO(error_output)
                )

                git_repo.obtain()
