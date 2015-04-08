# -*- coding: utf-8 -*-
"""Tests for vcspull.

vcspull.testsuite.repo_git
~~~~~~~~~~~~~~~~~~~~~~~~~~

"""
from __future__ import absolute_import, division, print_function, \
    with_statement, unicode_literals

import os
import logging

from . import unittest
from .helpers import ConfigTestCase
from ..repo import Repo
from ..util import run, which

logger = logging.getLogger(__name__)


def has_mercurial():
    try:
        which('hg')
        return True
    except Exception:
        return False


@unittest.skipUnless(has_mercurial(), "requires Mercurial (hg)")
class RepoMercurial(ConfigTestCase, unittest.TestCase):

    def test_repo_mercurial(self):
        repo_dir = os.path.join(
            self.TMP_DIR, '.repo_dir'
        )
        repo_name = 'my_mercurial_project'

        mercurial_repo = Repo({
            'url': 'hg+file://' + os.path.join(repo_dir, repo_name),
            'parent_path': self.TMP_DIR,
            'name': repo_name
        })

        mercurial_checkout_dest = os.path.join(
            self.TMP_DIR, mercurial_repo['name']
        )

        os.mkdir(repo_dir)
        run(['hg', 'init', mercurial_repo['name']], cwd=repo_dir)

        mercurial_repo.obtain()

        testfile = 'testfile.test'

        run([
            'touch', testfile
            ], cwd=os.path.join(repo_dir, repo_name))
        run([
            'hg', 'add', testfile
            ], cwd=os.path.join(repo_dir, repo_name))
        run([
            'hg', 'commit', '-m', 'a test file for %s' % mercurial_repo['name']
            ], cwd=os.path.join(repo_dir, repo_name))

        mercurial_repo.update_repo()

        test_repo_revision = run(
            ['hg', 'parents', '--template={rev}'],
            cwd=os.path.join(repo_dir, repo_name),
        )['stdout']

        self.assertEqual(
            mercurial_repo.get_revision(),
            test_repo_revision
        )

        self.assertTrue(os.path.exists(mercurial_checkout_dest))


def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(RepoMercurial))
    return suite
