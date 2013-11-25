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
from pullv.repo import BaseRepo, Repo, GitRepo, MercurialRepo, SubversionRepo
from pullv.util import expand_config, run, get_repos
from .helpers import RepoTest, ConfigTest

logger = logging.getLogger(__name__)


class LoadRepos(RepoTest, ConfigTest):

    """Integration: Verify load_repos() load functionality.

    Create a local svn, git and hg repo. Create YAML config file with paths.

    Test load_repos arguments to filter.

    """

    def setUp(self):

        ConfigTest.setUp(self)

        self.git_repo_path, self.git_repo = self.create_git_repo()
        self.hg_repo_path, self.hg_repo = self.create_mercurial_repo()
        self.svn_repo_path, self.svn_repo = self.create_svn_repo()

        config_yaml = """
        {TMP_DIR}/study/:
            sphinx: hg+file://{hg_repo_path}
            docutils: svn+file://{svn_repo_path}
            linux: git+file://{git_repo_path}
        {TMP_DIR}/github_projects/:
            kaptan:
                repo: git+file://{git_repo_path}
                remotes:
                    test_remote: git+file://{git_repo_path}
        {TMP_DIR}:
            .vim:
                repo: git+file://{git_repo_path}
            .tmux:
                repo: git+file://{git_repo_path}
        """

        config_json = """
        {
          "${TMP_DIR}/study/": {
            "sphinx": "hg+file://${hg_repo_path}",
            "docutils": "svn+file://${svn_repo_path}",
            "linux": "git+file://${git_repo_path}"
          },
          "${TMP_DIR}/github_projects/": {
            "kaptan": {
              "repo": "git+file://${git_repo_path}",
              "remotes": {
                "test_remote": "git+file://${git_repo_path}"
              }
            }
          },
          "${TMP_DIR}": {
            ".vim": {
              "repo": "git+file://${git_repo_path}"
            },
            ".tmux": {
              "repo": git+file://${git_repo_path}
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

        print(config_json)

        self.config_yaml = copy.deepcopy(config_yaml)
        self.config_json = copy.deepcopy(config_json)

    def test_load_repos(self):
        """Load all repos from all configs."""
        self.maxDiff = None

        conf = kaptan.Kaptan(handler='yaml')
        conf.import_config(self.config_yaml)
        conf = conf.export('dict')
        repos = expand_config(conf)
