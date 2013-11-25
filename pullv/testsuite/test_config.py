# -*- coding: utf-8 -*-
"""Tests for pullv.

pullv.tests.test_config
~~~~~~~~~~~~~~~~~~~~~~~

:copyright: Copyright 2013 Tony Narlock.
:license: BSD, see LICENSE for details

"""

import os
import copy
import logging
import kaptan
from pullv.repo import BaseRepo, Repo, GitRepo, MercurialRepo, SubversionRepo
from pullv.util import expand_config, run, get_repos
from .helpers import ConfigTest, ConfigExamples

logger = logging.getLogger(__name__)


class ConfigFormatTest(ConfigExamples):

    """Verify that example YAML is returning expected dict format."""

    def test_dict_equals_yaml(self):
        config = kaptan.Kaptan(handler='yaml')
        config.import_config(self.config_yaml)

        self.maxDiff = None

        self.assertDictEqual(self.config_dict, config.export('dict'))


class ConfigImportExportTest(ConfigExamples):

    def test_export_json(self):
        TMP_DIR = self.TMP_DIR
        json_config_file = os.path.join(TMP_DIR, '.pullv.json')

        config = kaptan.Kaptan()
        config.import_config(self.config_dict)

        json_config_data = config.export('json', indent=2)

        buf = open(json_config_file, 'w')
        buf.write(json_config_data)
        buf.close()

        new_config = kaptan.Kaptan()
        new_config_data = new_config.import_config(json_config_file).get()
        self.assertDictEqual(self.config_dict, new_config_data)

    def test_export_yaml(self):
        yaml_config_file = os.path.join(self.TMP_DIR, '.pullv.yaml')

        config = kaptan.Kaptan()
        config.import_config(self.config_dict)

        yaml_config_data = config.export('yaml', indent=2)

        buf = open(yaml_config_file, 'w')
        buf.write(yaml_config_data)
        buf.close()

        new_config = kaptan.Kaptan()
        new_config_data = new_config.import_config(yaml_config_file).get()
        self.assertDictEqual(self.config_dict, new_config_data)

    def test_scan_config(self):
        configs = []

        garbage_file = os.path.join(self.TMP_DIR, '.pullv.psd')
        buf = open(garbage_file, 'w')
        buf.write('wat')
        buf.close()

        for r, d, f in os.walk(self.TMP_DIR):
            for filela in (x for x in f if x.endswith(('.json', 'yaml')) and x.startswith('.pullv')):
                configs.append(os.path.join(self.TMP_DIR, filela))

        files = 0
        if os.path.exists(os.path.join(self.TMP_DIR, '.pullv.json')):
            files += 1
            self.assertIn(os.path.join(self.TMP_DIR, '.pullv.json'), configs)

        if os.path.exists(os.path.join(self.TMP_DIR, '.pullv.yaml')):
            files += 1
            self.assertIn(os.path.join(self.TMP_DIR, '.pullv.yaml'), configs)

        self.assertEqual(len(configs), files)


class ConfigExpandTest(ConfigExamples):

    """Expand configuration into full form."""

    def test_expand_shell_command_after(self):
        """Expand shell commands from string to list."""

        self.maxDiff = None

        config = expand_config(self.config_dict)

        self.assertDictEqual(config, self.config_dict_expanded)


class ExpandUserExpandVars(ConfigTest):

    """Verify .expandvars and .expanduser works with configs."""

    def setUp(self):

        ConfigTest.setUp(self)

        config_yaml = """
        '{TMP_DIR}/study/':
            sphinx: hg+file://{hg_repo_path}
            docutils: svn+file://{svn_repo_path}
            linux: git+file://{git_repo_path}
        '{TMP_DIR}/github_projects/':
            kaptan:
                repo: git+file://{git_repo_path}
                remotes:
                    test_remote: git+file://{git_repo_path}
        '{TMP_DIR}':
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
          }
        }
        """

        self.config_yaml = copy.deepcopy(config_yaml)

        conf = kaptan.Kaptan(handler='yaml')
        conf.import_config(self.config_yaml)
        self.config1 = conf.export('dict')

        self.config_json = copy.deepcopy(config_json)

        conf = kaptan.Kaptan(handler='json')
        conf.import_config(self.config_json)
        self.config2 = conf.export('dict')

    def testing_this(self):
        config1_expanded = expand_config(self.config1)
        config2_expanded = expand_config(self.config2)

