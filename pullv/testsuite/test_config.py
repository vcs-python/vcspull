# -*- coding: utf-8 -*-
"""Tests for pullv.

pullv.tests.test_config
~~~~~~~~~~~~~~~~~~~~~~~

:copyright: Copyright 2013 Tony Narlock.
:license: BSD, see LICENSE for details

"""

import logging
import os
import tempfile
import kaptan
from pullv.repo import BaseRepo, Repo, GitRepo, MercurialRepo, SubversionRepo
from pullv.util import expand_config, run, get_repos
from .helpers import ConfigTest, ConfigExamples, RepoTest

logger = logging.getLogger(__name__)


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
            print(repo)
            logger.error(repo)
            repo.obtain()


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
