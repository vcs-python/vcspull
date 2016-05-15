# -*- coding: utf-8 -*-
"""Tests for vcspull.

vcspull.testsuite.repo_git
~~~~~~~~~~~~~~~~~~~~~~~~~~

"""
from __future__ import (absolute_import, division, print_function,
                        unicode_literals, with_statement)

import logging
import os
import tempfile
import unittest

from ..exc import VCSPullException
from ..repo import create_repo
from ..util import run, which
from .helpers import ConfigTestCase, RepoTestMixin

logger = logging.getLogger(__name__)


def has_svn():
    try:
        which('svn')
        return True
    except VCSPullException:
        return False


@unittest.skipUnless(has_svn(), "requires SVN")
class RepoSVN(RepoTestMixin, ConfigTestCase, unittest.TestCase):

    def test_repo_svn(self):
        repo_dir = os.path.join(self.TMP_DIR, '.repo_dir')
        repo_name = 'my_svn_project'

        svn_repo = create_repo(**{
            'url': 'svn+file://' + os.path.join(repo_dir, repo_name),
            'cwd': self.TMP_DIR,
            'name': repo_name
        })

        svn_checkout_dest = os.path.join(self.TMP_DIR, svn_repo['name'])

        os.mkdir(repo_dir)

        run(['svnadmin', 'create', svn_repo['name']], cwd=repo_dir)

        svn_repo.obtain()

        self.assertTrue(os.path.exists(svn_checkout_dest))

        tempFile = tempfile.NamedTemporaryFile(dir=svn_checkout_dest)

        run(['svn', 'add', '--non-interactive', tempFile.name],
            cwd=svn_checkout_dest)
        run(
            ['svn', 'commit', '-m', 'a test file for %s' % svn_repo['name']],
            cwd=svn_checkout_dest
        )
        self.assertEqual(svn_repo.get_revision(), 0)

        self.assertEqual(
            os.path.join(svn_checkout_dest, tempFile.name),
            tempFile.name
        )
        self.assertEqual(svn_repo.get_revision(tempFile.name), 1)


def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(RepoSVN))
    return suite
