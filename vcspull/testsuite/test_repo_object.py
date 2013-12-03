# -*- coding: utf-8 -*-
"""Tests for placing config dicts into :py:class:`Repo` objects.

vcspull.testsuite.test_repo_object
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

:copyright: Copyright 2013 Tony Narlock.
:license: BSD, see LICENSE for details

"""

import os
import kaptan
from ..repo import BaseRepo, Repo, GitRepo, MercurialRepo, SubversionRepo
from ..util import expand_config, get_repos, run
from .helpers import ConfigExamples, RepoTest


class ConfigToObjectTest(ConfigExamples):

    """TestCase for converting config (dict) into Repo object."""

    def setUp(self):

        super(ConfigToObjectTest, self).setUp()

        SAMPLECONFIG_LIST = [
            {
                'name': None,
                'parent_path': None,
                'url': None,
                'remotes': []
            }
        ]

    def test_to_dictlist(self):
        """``get_repos`` pulls the repos in dict format from the config."""
        config = self.config_dict_expanded

        repo_list = get_repos(self.config_dict_expanded)

        for r in repo_list:
            self.assertIsInstance(r, dict)
            self.assertIn('name', r)
            self.assertIn('parent_path', r)
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

        git_repo = Repo({
            'url': 'git+git://git.myproject.org/MyProject.git@da39a3ee5e6b4b0d3255bfef95601890afd80709',
            'parent_path': self.TMP_DIR,
            'name': 'myproject1'
        })

        # TODO parent_path and name if duplicated should give an error

        self.assertIsInstance(git_repo, GitRepo)
        self.assertIsInstance(git_repo, BaseRepo)

        hg_repo = Repo({
            'url': 'hg+https://hg.myproject.org/MyProject#egg=MyProject',
            'parent_path': self.TMP_DIR,
            'name': 'myproject2'
        })

        self.assertIsInstance(hg_repo, MercurialRepo)
        self.assertIsInstance(hg_repo, BaseRepo)

        svn_repo = Repo({
            'url': 'svn+svn://svn.myproject.org/svn/MyProject#egg=MyProject',
            'parent_path': self.TMP_DIR,
            'name': 'myproject3'
        })

        self.assertIsInstance(svn_repo, SubversionRepo)
        self.assertIsInstance(svn_repo, BaseRepo)

    def test_to_repo_objects(self):
        """:py:obj:`dict` objects into Repo objects."""
        repo_list = get_repos(self.config_dict_expanded)
        for repo_dict in repo_list:
            r = Repo(repo_dict)

            self.assertIsInstance(r, BaseRepo)
            self.assertIn('name', r)
            self.assertEqual(r['name'], repo_dict['name'])
            self.assertIn('parent_path', r)
            self.assertEqual(r['parent_path'], repo_dict['parent_path'])
            self.assertIn('url', r)
            self.assertEqual(r['url'], repo_dict['url'])

            self.assertEqual(r['path'], os.path.join(
                r['parent_path'], r['name']))

            if 'remotes' in repo_dict:
                self.assertIsInstance(r['remotes'], list)
                for remote in r['remotes']:
                    self.assertIsInstance(remote, dict)
                    self.assertIn('remote_name', remote)
                    self.assertIn('url', remote)


class EnsureMakeDirsRecursively(RepoTest):

    """Ensure that directories in pull are made recursively."""

    YAML_CONFIG = """
    {TMP_DIR}/study/python:
        my_repo: svn+file://{REPO_DIR}
    """

    def test_makes_recursive(self):
        repo_dir, svn_repo = self.create_svn_repo()
        YAML_CONFIG = self.YAML_CONFIG.format(
            TMP_DIR=self.TMP_DIR,
            REPO_DIR=repo_dir
        )
        conf = kaptan.Kaptan(handler='yaml')
        conf.import_config(YAML_CONFIG)
        conf = conf.export('dict')
        repos = expand_config(conf)

        for r in get_repos(repos):
            repo = Repo(r)
            repo.obtain()

