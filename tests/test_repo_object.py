# -*- coding: utf-8 -*-
"""Tests for placing config dicts into :py:class:`Repo` objects.

vcspull.testsuite.repo_object
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

"""
from __future__ import (absolute_import, division, print_function,
                        unicode_literals, with_statement)

import os
import unittest

import kaptan

from vcspull.config import expand_config
from vcspull.repo import (BaseRepo, GitRepo, MercurialRepo, SubversionRepo,
                          create_repo)
from vcspull.util import filter_repos

from .helpers import ConfigTestCase, RepoTestMixin


class GetReposTest(ConfigTestCase, unittest.TestCase):

    def test_filter_dir(self):
        """``filter_repos`` filter by dir"""
        self.config_dict_expanded

        repo_list = filter_repos(
            self.config_dict_expanded,
            repo_dir="*github_project*"
        )

        self.assertEqual(len(repo_list), 1)
        for r in repo_list:
            self.assertEqual(r['name'], 'kaptan')

    def test_filter_name(self):
        """``filter_repos`` filter by name"""
        self.config_dict_expanded

        repo_list = filter_repos(
            self.config_dict_expanded,
            name=".vim"
        )

        self.assertEqual(len(repo_list), 1)
        for r in repo_list:
            self.assertEqual(r['name'], '.vim')

    def test_filter_vcs(self):
        """``filter_repos`` filter by vcs remote url"""
        self.config_dict_expanded

        repo_list = filter_repos(
            self.config_dict_expanded,
            vcs_url="*kernel.org*"
        )

        self.assertEqual(len(repo_list), 1)
        for r in repo_list:
            self.assertEqual(r['name'], 'linux')


class ConfigToObjectTest(ConfigTestCase, unittest.TestCase):

    """TestCase for converting config (dict) into Repo object."""

    def setUp(self):

        super(ConfigToObjectTest, self).setUp()

    def test_to_dictlist(self):
        """``filter_repos`` pulls the repos in dict format from the config."""
        self.config_dict_expanded

        repo_list = filter_repos(self.config_dict_expanded)

        for r in repo_list:
            self.assertIsInstance(r, dict)
            self.assertIn('name', r)
            self.assertIn('parent_dir', r)
            self.assertIn('url', r)

            if 'remotes' in r:
                self.assertIsInstance(r['remotes'], list)
                for remote in r['remotes']:
                    self.assertIsInstance(remote, dict)
                    self.assertIn('remote_name', remote)
                    self.assertIn('url', remote)

    def test_vcs_url_scheme_to_object(self):
        """Test that ``url`` return a GitRepo/MercurialRepo/SubversionRepo.

        :class:`GitRepo`, :class:`MercurialRepo` or :class:`SubversionRepo`
        object based on the pip-style URL scheme.

        """

        git_repo = create_repo(**{
            'url': 'git+git://git.myproject.org/MyProject.git@da39a3ee5e6b4b',
            'parent_dir': self.TMP_DIR,
            'name': 'myproject1'
        })

        # TODO cwd and name if duplicated should give an error

        self.assertIsInstance(git_repo, GitRepo)
        self.assertIsInstance(git_repo, BaseRepo)

        hg_repo = create_repo(**{
            'url': 'hg+https://hg.myproject.org/MyProject#egg=MyProject',
            'parent_dir': self.TMP_DIR,
            'name': 'myproject2'
        })

        self.assertIsInstance(hg_repo, MercurialRepo)
        self.assertIsInstance(hg_repo, BaseRepo)

        svn_repo = create_repo(**{
            'url': 'svn+svn://svn.myproject.org/svn/MyProject#egg=MyProject',
            'parent_dir': self.TMP_DIR,
            'name': 'myproject3'
        })

        self.assertIsInstance(svn_repo, SubversionRepo)
        self.assertIsInstance(svn_repo, BaseRepo)

    def test_to_repo_objects(self):
        """:py:obj:`dict` objects into Repo objects."""
        repo_list = filter_repos(self.config_dict_expanded)
        for repo_dict in repo_list:
            r = create_repo(**repo_dict)

            self.assertIsInstance(r, BaseRepo)
            self.assertIn('name', r)
            self.assertEqual(r['name'], repo_dict['name'])
            self.assertIn('parent_dir', r)
            self.assertEqual(r['parent_dir'], repo_dict['parent_dir'])
            self.assertIn('url', r)
            self.assertEqual(r['url'], repo_dict['url'])

            self.assertEqual(r['path'], os.path.join(
                r['parent_dir'], r['name']))

            if 'remotes' in repo_dict:
                self.assertIsInstance(r['remotes'], list)
                for remote in r['remotes']:
                    self.assertIsInstance(remote, dict)
                    self.assertIn('remote_name', remote)
                    self.assertIn('url', remote)


class EnsureMakeDirsRecursively(ConfigTestCase, RepoTestMixin,
                                unittest.TestCase):

    """Ensure that directories in pull are made recursively."""

    YAML_CONFIG = """
    {TMP_DIR}/study/python:
        my_url: svn+file://{REPO_DIR}
    """

    def test_makes_recursive(self):
        repo_dir, svn_repo = self.create_svn_repo(create_temp_repo=True)
        YAML_CONFIG = self.YAML_CONFIG.format(
            TMP_DIR=self.TMP_DIR,
            REPO_DIR=repo_dir
        )
        conf = kaptan.Kaptan(handler='yaml')
        conf.import_config(YAML_CONFIG)
        conf = conf.export('dict')
        repos = expand_config(conf)

        for r in filter_repos(repos):
            repo = create_repo(**r)
            repo.obtain()


def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(GetReposTest))
    suite.addTest(unittest.makeSuite(ConfigToObjectTest))
    suite.addTest(unittest.makeSuite(EnsureMakeDirsRecursively))
    return suite
