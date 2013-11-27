# -*- coding: utf-8 -*-
"""Tests for pullv.

pullv.tests.test_cli
~~~~~~~~~~~~~~~~~~~~

:copyright: Copyright 2013 Tony Narlock.
:license: BSD, see LICENSE for details

"""

import logging
import os
import tempfile
import copy
import kaptan
from pprint import pprint
from pullv.repo import BaseRepo, Repo, GitRepo, MercurialRepo, SubversionRepo
from pullv.util import expand_config, run, get_repos
from .helpers import RepoTest, ConfigTest
from .. import cli

logger = logging.getLogger(__name__)


class RepoIntegrationTest(RepoTest, ConfigTest):

    """TestCase base that prepares custom repos, configs.

    :var git_repo_path: git repo
    :var svn_repo_path: svn repo
    :var hg_repo_path: hg repo
    :var TMP_DIR: temporary directory for testcase
    :var CONFIG_DIR: the ``.pullv`` dir inside of ``TMP_DIR``.

    Create a local svn, git and hg repo. Create YAML config file with paths.

    """

    def setUp(self):

        ConfigTest.setUp(self)

        self.git_repo_path, self.git_repo = self.create_git_repo()
        self.hg_repo_path, self.hg_repo = self.create_mercurial_repo()
        self.svn_repo_path, self.svn_repo = self.create_svn_repo()

        self.CONFIG_DIR = os.path.join(self.TMP_DIR, '.pullv')

        os.makedirs(self.CONFIG_DIR)
        self.assertTrue(os.path.exists(self.CONFIG_DIR))

        config_yaml = """
        {TMP_DIR}/samedir/:
            docutils: svn+file://{svn_repo_path}
        {TMP_DIR}/github_projects/deeper/:
            kaptan:
                repo: git+file://{git_repo_path}
                remotes:
                    test_remote: git+file://{git_repo_path}
        {TMP_DIR}:
            samereponame: git+file://{git_repo_path}
            .tmux:
                repo: git+file://{git_repo_path}
        {TMP_DIR}/srv/www/test/:
            subrepodiffvcs:
                repo: svn+file://${git_repo_path}
        """

        config_json = """
        {
          "${TMP_DIR}/samedir/": {
            "sphinx": "hg+file://${hg_repo_path}",
            "linux": "git+file://${git_repo_path}"
          },
          "${TMP_DIR}/another_directory/": {
            "anotherkaptan": {
              "repo": "git+file://${git_repo_path}",
              "remotes": {
                "test_remote": "git+file://${git_repo_path}"
              }
            }
          },
          "${TMP_DIR}": {
            "samereponame": "git+file://{git_repo_path}",
            ".vim": {
              "repo": "git+file://${git_repo_path}"
            }
          },
          "${TMP_DIR}/srv/www/": {
            "test": {
              "repo": "git+file://${git_repo_path}"
            }
          },
          "${TMP_DIR}/srv/www/test/": {
            "subrepodiffvcs": {
              "repo": "svn+file://${git_repo_path}"
            }
          }

        }
        """

        config_yaml = config_yaml.format(
            svn_repo_path=self.svn_repo_path,
            hg_repo_path=self.hg_repo_path,
            git_repo_path=self.git_repo_path,
            TMP_DIR=self.TMP_DIR
        )

        from string import Template
        config_json = Template(config_json).substitute(
            svn_repo_path=self.svn_repo_path,
            hg_repo_path=self.hg_repo_path,
            git_repo_path=self.git_repo_path,
            TMP_DIR=self.TMP_DIR
        )

        self.config_yaml = copy.deepcopy(config_yaml)
        self.config_json = copy.deepcopy(config_json)

        conf = kaptan.Kaptan(handler='yaml')
        conf.import_config(self.config_yaml)
        self.config1 = conf.export('dict')

        self.config1_name = 'repos1.yaml'
        self.config1_file = os.path.join(self.CONFIG_DIR, self.config1_name)

        with open(self.config1_file, 'w') as buf:
            buf.write(self.config_yaml)

        conf = kaptan.Kaptan(handler='json')
        conf.import_config(self.config_json)
        self.config2 = conf.export('dict')

        self.assertTrue(os.path.exists(self.config1_file))

        self.config2_name = 'repos2.json'
        self.config2_file = os.path.join(self.CONFIG_DIR, self.config2_name)

        with open(self.config2_file, 'w') as buf:
            buf.write(self.config_json)

        self.assertTrue(os.path.exists(self.config2_file))


class FindConfigs(RepoIntegrationTest):

    """Test find_configs."""

    def test_path_string(self):
        """path as a string."""
        configs = cli.find_configs(path=self.CONFIG_DIR)

        self.assertIn(self.config1_file, configs)
        self.assertIn(self.config2_file, configs)

    def test_path_list(self):
        configs = cli.find_configs(path=[self.CONFIG_DIR])

        self.assertIn(self.config1_file, configs)
        self.assertIn(self.config2_file, configs)

    def test_match_string(self):
        configs = cli.find_configs(
            path=[self.CONFIG_DIR],
            match='repos1'
        )

        self.assertIn(self.config1_file, configs)
        self.assertNotIn(self.config2_file, configs)

        configs = cli.find_configs(
            path=[self.CONFIG_DIR],
            match='repos2'
        )

        self.assertNotIn(self.config1_file, configs)
        self.assertIn(self.config2_file, configs)

        configs = cli.find_configs(
            path=[self.CONFIG_DIR],
            match='randomstring'
        )

        self.assertNotIn(self.config1_file, configs)
        self.assertNotIn(self.config2_file, configs)

        configs = cli.find_configs(
            path=[self.CONFIG_DIR],
            match='*'
        )

        self.assertIn(self.config1_file, configs)
        self.assertIn(self.config2_file, configs)

        configs = cli.find_configs(
            path=[self.CONFIG_DIR],
            match='repos*'
        )

        self.assertIn(self.config1_file, configs)
        self.assertIn(self.config2_file, configs)

        configs = cli.find_configs(
            path=[self.CONFIG_DIR],
            match='repos[1-9]'
        )

        self.assertEqual(
            len([c for c in configs if self.config1_file in c]), 1
        )

        self.assertIn(self.config1_file, configs)
        self.assertIn(self.config2_file, configs)

    def test_match_list(self):
        configs = cli.find_configs(
            path=[self.CONFIG_DIR],
            match=['repos1', 'repos2']
        )

        self.assertIn(self.config1_file, configs)
        self.assertIn(self.config2_file, configs)

        configs = cli.find_configs(
            path=[self.CONFIG_DIR],
            match=['repos1']
        )

        self.assertIn(self.config1_file, configs)
        self.assertEqual(
            len([c for c in configs if self.config1_file in c]), 1
        )
        self.assertNotIn(self.config2_file, configs)
        self.assertEqual(
            len([c for c in configs if self.config2_file in c]), 0
        )

    def test_filetype_string(self):
        configs = cli.find_configs(
            path=[self.CONFIG_DIR],
            match='repos1',
            filetype='yaml',
        )

        self.assertIn(self.config1_file, configs)
        self.assertNotIn(self.config2_file, configs)

        configs = cli.find_configs(
            path=[self.CONFIG_DIR],
            match='repos1',
            filetype='json',
        )

        self.assertNotIn(self.config1_file, configs)
        self.assertNotIn(self.config2_file, configs)

        configs = cli.find_configs(
            path=[self.CONFIG_DIR],
            match='repos*',
            filetype='json',
        )

        self.assertNotIn(self.config1_file, configs)
        self.assertIn(self.config2_file, configs)

        configs = cli.find_configs(
            path=[self.CONFIG_DIR],
            match='repos*',
            filetype='*',
        )

        self.assertIn(self.config1_file, configs)
        self.assertIn(self.config2_file, configs)

    def test_filetype_list(self):
        configs = cli.find_configs(
            path=[self.CONFIG_DIR],
            match=['repos*'],
            filetype=['*'],
        )

        self.assertIn(self.config1_file, configs)
        self.assertIn(self.config2_file, configs)

        configs = cli.find_configs(
            path=[self.CONFIG_DIR],
            match=['repos*'],
            filetype=['json', 'yaml'],
        )

        self.assertIn(self.config1_file, configs)
        self.assertIn(self.config2_file, configs)

        configs = cli.find_configs(
            path=[self.CONFIG_DIR],
            filetype=['json', 'yaml'],
        )

        self.assertIn(self.config1_file, configs)
        self.assertIn(self.config2_file, configs)


class LoadConfigs(RepoIntegrationTest):
    def test_load(self):
        """Load a list of file into dict."""
        configs = cli.find_configs(
            path=self.CONFIG_DIR
        )

        configdicts = cli.load_configs(configs)

        pprint(configs)
        pprint(configdicts)

    def test_duplicate_repos(self):
        """Duplicate path + name with different repo URL / remotes raises."""

        configs = cli.find_configs(
            path=self.CONFIG_DIR
        )

        config_yaml = """
        {TMP_DIR}/srv/www/test/:
            subrepodiffvcs:
                repo: svn+file://${git_repo_path}
        """

        config_yaml = config_yaml.format(
            svn_repo_path=self.svn_repo_path,
            hg_repo_path=self.hg_repo_path,
            git_repo_path=self.git_repo_path,
            TMP_DIR=self.TMP_DIR
        )

        conf = kaptan.Kaptan(handler='json')
        conf.import_config(self.config_json)
        self.config2 = conf.export('dict')

        configdicts = cli.load_configs(configs)

    def test_merges_same_duplicates(self):
        """Will merge same repos."""
        pass


class GetRepos(RepoIntegrationTest):

    pass


class ScanRepos(RepoIntegrationTest):

    pass
