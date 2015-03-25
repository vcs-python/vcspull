# -*- coding: utf-8 -*-
"""Tests for vcspull.

vcspull.testsuite.repo_git
~~~~~~~~~~~~~~~~~~~~~~~~~~

"""
from __future__ import absolute_import, division, print_function, \
    with_statement, unicode_literals

import os
import logging
import tempfile


from . import unittest
from .helpers import RepoTest
from ..repo import Repo
from ..util import run, which
from ..exc import PullvException

logger = logging.getLogger(__name__)


def has_svn():
    try:
        which('svn')
        return True
    except PullvException:
        return False


@unittest.skipUnless(has_svn(), "requires SVN")
class RepoSVN(RepoTest):

    def test_repo_svn(self):
        repo_dir = os.path.join(self.TMP_DIR, '.repo_dir')
        repo_name = 'my_svn_project'

        svn_repo = Repo({
            'url': 'svn+file://' + os.path.join(repo_dir, repo_name),
            'parent_path': self.TMP_DIR,
            'name': repo_name
        })

        svn_checkout_dest = os.path.join(self.TMP_DIR, svn_repo['name'])

        os.mkdir(repo_dir)

        run(['svnadmin', 'create', svn_repo['name']], cwd=repo_dir)

        svn_repo.obtain()

        self.assertTrue(os.path.exists(svn_checkout_dest))

        tempFile = tempfile.NamedTemporaryFile(dir=svn_checkout_dest)

        run(['svn', 'add', tempFile.name], cwd=svn_checkout_dest)
        run(
            ['svn', 'commit', '-m', 'a test file for %s' % svn_repo['name']],
            cwd=svn_checkout_dest
        )
        self.assertEqual(svn_repo.get_revision(), 0)
        svn_repo.update_repo()

        self.assertEqual(
            os.path.join(svn_checkout_dest, tempFile.name),
            tempFile.name
        )
        self.assertEqual(svn_repo.get_revision(tempFile.name), 1)


def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(RepoSVN))
    return suite
