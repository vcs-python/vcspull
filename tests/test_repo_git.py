# -*- coding: utf-8 -*-
"""Tests for vcspull git repos."""
from __future__ import absolute_import, print_function, unicode_literals

import os

import mock
import pytest

from libvcs import exc
from libvcs.shortcuts import create_repo_from_pip_url
from libvcs._compat import StringIO
from libvcs.util import run


def test_repo_git_obtain_initial_commit_repo(tmpdir):
    """initial commit repos return 'initial'.

    note: this behaviors differently from git(1)'s use of the word "bare".
    running `git rev-parse --is-bare-repository` would return false.
    """
    repo_name = 'my_git_project'

    run([  # init bare repo
        'git', 'init', repo_name
    ], cwd=str(tmpdir))

    bare_repo_dir = tmpdir.join(repo_name)

    git_repo = create_repo_from_pip_url(**{
        'url': 'git+file://' + str(bare_repo_dir),
        'parent_dir': str(tmpdir),
        'name': 'obtaining a bare repo'
    })

    git_repo.obtain(quiet=True)
    assert git_repo.get_revision() == 'initial'


def test_repo_git_obtain_full(tmpdir, git_dummy_repo_dir):
    remote_repo_dir = git_dummy_repo_dir

    test_repo_revision = run(
        ['git', 'rev-parse', 'HEAD'],
        cwd=remote_repo_dir,
    )

    # create a new repo with the repo as a remote
    git_repo = create_repo_from_pip_url(**{
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

    git_repo = create_repo_from_pip_url(**git_repo_kwargs)
    git_repo.obtain(quiet=True)
    assert remote_name in git_repo.remotes_get


def test_remotes_vcs_prefix(git_repo_kwargs):
    remote_url = 'https://localhost/my/git/repo.git'
    remote_vcs_url = 'git+' + remote_url

    git_repo_kwargs.update(**{
        'remotes': [{
            'remote_name': 'myrepo',
            'url': remote_vcs_url
        }]
    })

    git_repo = create_repo_from_pip_url(**git_repo_kwargs)
    git_repo.obtain(quiet=True)

    assert (remote_url, remote_url,) in git_repo.remotes_get.values()


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

    git_repo = create_repo_from_pip_url(**git_repo_kwargs)
    git_repo.obtain(quiet=True)

    assert (remote_url, remote_url,) in git_repo.remotes_get.values()


def test_private_ssh_format(git_repo_kwargs):
    git_repo_kwargs.update(**{
        'url': 'git+ssh://github.com:' + '/tmp/omg/private_ssh_repo',
    })

    with pytest.raises(exc.LibVCSException) as e:
        create_repo_from_pip_url(**git_repo_kwargs)
        assert e.match("is malformatted")


def test_ls_remotes(git_repo):
    remotes = git_repo.remotes_get

    assert 'origin' in remotes


def test_get_remotes(git_repo):

    assert 'origin' in git_repo.remotes_get


def test_set_remote(git_repo):
    mynewremote = git_repo.remote_set(
        name='myrepo',
        url='file:///'
    )

    assert 'file:///' in mynewremote, 'remote_set returns remote'

    assert 'file:///' in git_repo.remote_get(remote='myrepo'), \
        'remote_get returns remote'

    assert 'myrepo' in git_repo.remotes_get, \
        '.remotes_get() returns new remote'


@pytest.mark.skip(reason='needs to be ported to pytest, mock/raises issues.')
def test_repository_not_found_raises_exception(tmpdir):
    r"""Need to imitate git remote not found.

    |isobar-frontend| (git)  create_repo_from_pip_url directory for isobar-frontend (git) \
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
    repo_dir = str(tmpdir.join('.repo_dir'))
    repo_name = 'my_git_project'

    url = 'git+file://' + os.path.join(repo_dir, repo_name)
    git_repo = create_repo_from_pip_url(**{
        'url': url,
        'parent_dir': str(tmpdir),
        'name': repo_name
    })
    error_output = 'ERROR: hello mock subprocess stderr'

    with pytest.raises(exc.LibVCSException) as excinfo:
        with mock.patch(
            "vcspull.repo.base.subprocess.Popen"
        ) as mock_subprocess:
            mock_subprocess.return_value = mock.Mock(
                stdout=StringIO('hello mock subprocess stdout'),
                stderr=StringIO(error_output)
            )

            git_repo.obtain()
    assert excinfo.match(error_output)
