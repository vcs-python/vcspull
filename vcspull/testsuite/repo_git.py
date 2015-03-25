# -*- coding: utf-8 -*-
"""Tests for vcspull.

vcspull.testsuite.repo_git
~~~~~~~~~~~~~~~~~~~~~~~~~~

"""
from __future__ import absolute_import, division, print_function, \
    with_statement, unicode_literals

import os
import logging
import unittest

from .helpers import ConfigTest, RepoTest
from .. import exc
from ..repo import Repo
from ..util import run

logger = logging.getLogger(__name__)


class RepoGit(ConfigTest):

    """Integration level tests."""

    def test_repo_git_update(self):
        repo_dir = os.path.join(self.TMP_DIR, '.repo_dir')
        repo_name = 'my_git_project'

        git_repo = Repo({
            'url': 'git+file://' + os.path.join(repo_dir, repo_name),
            'parent_path': self.TMP_DIR,
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


class GitRepoRemotes(RepoTest):
    def test_remotes(self):
        repo_dir, git_repo = self.create_git_repo()

        git_checkout_dest = os.path.join(self.TMP_DIR, 'dontmatta')

        git_repo = Repo({
            'url': 'git+file://' + git_checkout_dest,
            'parent_path': os.path.dirname(repo_dir),
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


class GitRepoSSHUrl(RepoTest):

    def test_private_ssh_format(self):
        repo_dir, git_repo = self.create_git_repo()

        git_checkout_dest = os.path.join(self.TMP_DIR, 'private_ssh_repo')

        git_repo = Repo({
            'url': 'git+ssh://github.com:' + git_checkout_dest,
            'parent_path': os.path.dirname(repo_dir),
            'name': os.path.basename(os.path.normpath(repo_dir)),
        })

        with self.assertRaisesRegexp(exc.PullvException, "is malformatted"):
            git_repo.obtain(quiet=True)


class TestRemoteGit(RepoTest):

    def test_ls_remotes(self):
        repo_dir, git_repo = self.create_git_repo()

        remotes = git_repo.remotes_get()

        self.assertIn('origin', remotes)

    def test_get_remotes(self):
        repo_dir, git_repo = self.create_git_repo()

        self.assertIn(
            'origin',
            git_repo.remotes_get()
        )

    def test_set_remote(self):
        repo_dir, git_repo = self.create_git_repo()

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


def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(GitRepoRemotes))
    suite.addTest(unittest.makeSuite(GitRepoSSHUrl))
    suite.addTest(unittest.makeSuite(RepoGit))
    suite.addTest(unittest.makeSuite(TestRemoteGit))
    return suite
