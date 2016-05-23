# -*- coding: utf-8 -*-
"""Tests for vcspull git repos."""
from __future__ import (absolute_import, division, print_function,
                        unicode_literals, with_statement)

import os
import unittest

import mock

from vcspull import exc
from vcspull._compat import StringIO
from vcspull.repo import create_repo
from vcspull.util import run
from .helpers import (ConfigTestCase, RepoIntegrationTest, RepoTestMixin,
                      mute)


class RepoGit(RepoIntegrationTest, unittest.TestCase):

    """Integration level tests."""

    @mute
    def test_repo_git_update(self):
        repo_dir = os.path.join(self.TMP_DIR, '.repo_dir')
        repo_name = 'my_git_project'

        git_repo = create_repo(**{
            'url': 'git+file://' + os.path.join(repo_dir, repo_name),
            'parent_dir': self.TMP_DIR,
            'name': repo_name
        })

        os.mkdir(repo_dir)
        run([
            'git', 'init', git_repo['name']
        ], cwd=repo_dir)
        git_checkout_dest = os.path.join(self.TMP_DIR, git_repo['name'])
        git_repo.obtain(quiet=True)

        testfile = 'testfile.test'

        run(['touch', testfile], cwd=os.path.join(repo_dir, repo_name))
        run([
            'git', 'add', testfile
        ], cwd=os.path.join(repo_dir, repo_name))
        run([
            'git', 'commit', '-m', 'a test file for %s' % git_repo['name']
        ], cwd=os.path.join(repo_dir, repo_name))
        git_repo.update_repo()

        test_repo_revision = run(
            ['git', 'rev-parse', 'HEAD'],
            cwd=os.path.join(repo_dir, repo_name),
        )['stdout']

        self.assertEqual(
            git_repo.get_revision(),
            test_repo_revision
        )
        self.assertTrue(os.path.exists(git_checkout_dest))


class GitRepoRemotes(RepoIntegrationTest, unittest.TestCase):

    @mute
    def test_remotes(self):
        repo_dir, git_repo = self.create_git_repo(create_temp_repo=True)

        git_checkout_dest = os.path.join(self.TMP_DIR, 'dontmatta')

        git_repo = create_repo(**{
            'url': 'git+file://' + git_checkout_dest,
            'parent_dir': os.path.dirname(repo_dir),
            'name': os.path.basename(os.path.normpath(repo_dir)),
            'remotes': [
                {
                    'remote_name': 'myrepo',
                    'url': 'file:///'
                }
            ]

        })

        git_repo.obtain(quiet=True)
        self.assertIn('myrepo', git_repo.remotes_get())

    @mute
    def test_remotes_vcs_prefix(self):
        repo_dir, git_repo = self.create_git_repo(create_temp_repo=True)

        git_checkout_dest = os.path.join(self.TMP_DIR, 'dontmatta')

        remote_url = 'https://localhost/my/git/repo.git'
        remote_vcs_url = 'git+' + remote_url

        git_repo = create_repo(**{
            'url': 'git+file://' + git_checkout_dest,
            'parent_dir': os.path.dirname(repo_dir),
            'name': os.path.basename(os.path.normpath(repo_dir)),
            'remotes': [{
                'remote_name': 'myrepo',
                'url': remote_vcs_url
            }]
        })

        git_repo.obtain(quiet=True)
        self.assertIn((remote_url, remote_url,),
                      git_repo.remotes_get().values())

    @mute
    def test_remotes_preserves_git_ssh(self):
        # Regression test for #14
        repo_dir, git_repo = self.create_git_repo(create_temp_repo=True)

        git_checkout_dest = os.path.join(self.TMP_DIR, 'dontmatta')
        remote_url = 'git+ssh://git@github.com/tony/AlgoXY.git'

        git_repo = create_repo(**{
            'url': 'git+file://' + git_checkout_dest,
            'parent_dir': os.path.dirname(repo_dir),
            'name': os.path.basename(os.path.normpath(repo_dir)),
            'remotes': [{
                'remote_name': 'myrepo',
                'url': remote_url
            }]
        })

        git_repo.obtain(quiet=True)
        self.assertIn((remote_url, remote_url,),
                      git_repo.remotes_get().values())


class GitRepoSSHUrl(RepoTestMixin, ConfigTestCase, unittest.TestCase):

    def test_private_ssh_format(self):
        repo_dir, git_repo = self.create_git_repo()

        git_checkout_dest = os.path.join(self.TMP_DIR, 'private_ssh_repo')

        git_repo = create_repo(**{
            'url': 'git+ssh://github.com:' + git_checkout_dest,
            'parent_dir': os.path.dirname(repo_dir),
            'name': os.path.basename(os.path.normpath(repo_dir)),
        })

        with self.assertRaisesRegexp(exc.VCSPullException, "is malformatted"):
            git_repo.obtain(quiet=True)


class TestRemoteGit(RepoTestMixin, ConfigTestCase, unittest.TestCase):

    @mute
    def test_ls_remotes(self):
        repo_dir, git_repo = self.create_git_repo(create_temp_repo=True)

        remotes = git_repo.remotes_get()

        self.assertIn('origin', remotes)

    @mute
    def test_get_remotes(self):
        repo_dir, git_repo = self.create_git_repo(create_temp_repo=True)

        self.assertIn(
            'origin',
            git_repo.remotes_get()
        )

    @mute
    def test_set_remote(self):
        repo_dir, git_repo = self.create_git_repo(create_temp_repo=True)

        mynewremote = git_repo.remote_set(
            name='myrepo',
            url='file:///'
        )

        self.assertIn(
            'file:///',
            mynewremote,
            msg='remote_set returns remote'
        )

        self.assertIn(
            'file:///',
            git_repo.remote_get(remote='myrepo'),
            msg='remote_get returns remote'
        )

        self.assertIn(
            'myrepo',
            git_repo.remotes_get(),
            msg='.remotes_get() returns new remote'
        )


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
