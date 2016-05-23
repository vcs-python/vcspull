# -*- coding: utf-8 -*-
"""Tests for vcspull config loading."""
from __future__ import (absolute_import, division, print_function,
                        unicode_literals, with_statement)

import copy
import os
import tempfile
import unittest

import kaptan
import pytest

from vcspull import config, exc
from vcspull.config import expand_config

from .fixtures import example as fixtures
from .fixtures._util import loadfixture
from .helpers import (ConfigTestCase, ConfigTestMixin, EnvironmentVarGuard,
                      RepoIntegrationTest)


def test_dict_equals_yaml():
    """Verify that example YAML is returning expected dict format."""
    config = kaptan.Kaptan(handler='yaml')
    config.import_config(loadfixture('example1.yaml'))

    assert fixtures.config_dict == config.export('dict')


def test_export_json(tmpdir):
    json_config_file = str(tmpdir.join('.vcspull.json'))

    config = kaptan.Kaptan()
    config.import_config(fixtures.config_dict)

    json_config_data = config.export('json', indent=2)

    with open(json_config_file, 'w') as buf:
        buf.write(json_config_data)

    new_config = kaptan.Kaptan()
    new_config_data = new_config.import_config(json_config_file).get()
    assert fixtures.config_dict == new_config_data


def test_export_yaml(tmpdir):
    yaml_config_file = str(tmpdir.join('.vcspull.yaml'))

    config = kaptan.Kaptan()
    config.import_config(fixtures.config_dict)

    yaml_config_data = config.export('yaml', indent=2)

    with open(yaml_config_file, 'w') as buf:
        buf.write(yaml_config_data)

    new_config = kaptan.Kaptan()
    new_config_data = new_config.import_config(yaml_config_file).get()
    assert fixtures.config_dict == new_config_data


def test_scan_config(tmpdir):
    configs = []

    garbage_file = tmpdir.join('.vcspull.psd')
    garbage_file.write('wat')

    for r, d, f in os.walk(str(tmpdir)):
        for filela in (x for x in f if x.endswith(('.json', 'yaml')) and
                       x.startswith('.vcspull')):
            configs.append(str(tmpdir.join(filela)))

    files = 0
    if os.path.exists(str(tmpdir.join('.vcspull.json'))):
        files += 1
        assert str(tmpdir.join('.vcspull.json')) in configs

    if os.path.exists(str(tmpdir.join('.vcspull.yaml'))):
        files += 1
        assert str(tmpdir.join('.vcspull.json')) in configs

    assert len(configs) == files


def test_expand_shell_command_after():
    """Expand configuration into full form."""
    # Expand shell commands from string to list."""
    config = expand_config(fixtures.config_dict)

    assert config, fixtures.config_dict_expanded


class ExpandUserExpandVars(ConfigTestCase, ConfigTestMixin):

    """Verify .expandvars and .expanduser works with configs."""

    def setUp(self):
        ConfigTestCase.setUp(self)
        ConfigTestMixin.setUp(self)

        path_ = loadfixture('expand.yaml')
        config_yaml = path_

        config_json = loadfixture("expand.json")

        self.config_yaml = copy.deepcopy(config_yaml)

        conf = kaptan.Kaptan(handler='yaml')
        conf.import_config(self.config_yaml)
        self.config1 = conf.export('dict')

        self.config_json = copy.deepcopy(config_json)

        conf = kaptan.Kaptan(handler='json')
        conf.import_config(self.config_json)
        self.config2 = conf.export('dict')

    def test_this(self):
        config1_expanded = expand_config(self.config1)
        config2_expanded = expand_config(self.config2)

        paths = [r['parent_dir'] for r in config1_expanded]
        assert os.path.expanduser(
            os.path.expandvars('${HOME}/github_projects/')) in paths
        assert os.path.expanduser('~/study/') in paths
        assert os.path.expanduser('~') in paths

        paths = [r['parent_dir'] for r in config2_expanded]
        assert os.path.expandvars('${HOME}/github_projects/') in paths
        assert os.path.expanduser('~/study/') in paths


class InDirTest(ConfigTestCase):

    def setUp(self):

        ConfigTestCase.setUp(self)

        self.CONFIG_DIR = os.path.join(self.TMP_DIR, '.vcspull')

        os.makedirs(self.CONFIG_DIR)
        assert os.path.exists(self.CONFIG_DIR)

        self.config_file1 = tempfile.NamedTemporaryFile(
            dir=self.CONFIG_DIR, delete=False, suffix=".yaml"
        )
        self.config_file2 = tempfile.NamedTemporaryFile(
            dir=self.CONFIG_DIR, delete=False, suffix=".json"
        )

    def tearDown(self):
        os.remove(self.config_file1.name)
        os.remove(self.config_file2.name)
        ConfigTestCase.tearDown(self)

    def test_in_dir(self):
        expected = [
            os.path.basename(self.config_file1.name),
            os.path.basename(self.config_file2.name),
        ]
        result = config.in_dir(self.CONFIG_DIR)

        assert len(expected) == len(result)


class FindConfigsHome(ConfigTestCase, unittest.TestCase):

    """Test find_config_files in home directory."""

    def tearDown(self):
        ConfigTestCase.tearDown(self)

    def setUp(self):
        self._createConfigDirectory()

        self.config_file1_path = os.path.join(self.TMP_DIR, '.vcspull.yaml')
        self.config_file1 = open(self.config_file1_path, 'a').close()

    def test_find_config_files(self):

        with EnvironmentVarGuard() as env:
            env.set("HOME", self.TMP_DIR)
            os.environ.get("HOME") == self.TMP_DIR
            expectedIn = os.path.join(self.TMP_DIR, '.vcspull.yaml')
            results = config.find_home_config_files()

            assert expectedIn in results

    def test_multiple_configs_raises_exception(self):
        self.config_file2_path = os.path.join(self.TMP_DIR, '.vcspull.json')
        self.config_file2 = open(self.config_file2_path, 'a').close()

        with EnvironmentVarGuard() as env:
            with pytest.raises(exc.MultipleRootConfigs):
                env.set("HOME", self.TMP_DIR)
                assert os.environ.get("HOME") == self.TMP_DIR
                config.find_home_config_files()
        os.remove(self.config_file2_path)


class FindConfigs(ConfigTestCase, unittest.TestCase):

    """Test find_config_files."""

    def setUp(self):
        ConfigTestCase.setUp(self)

        self.CONFIG_DIR = os.path.join(self.TMP_DIR, '.vcspull')

        os.makedirs(self.CONFIG_DIR)
        assert os.path.exists(self.CONFIG_DIR)

        self.config_file1 = tempfile.NamedTemporaryFile(
            prefix="repos1",
            dir=self.CONFIG_DIR, delete=False, suffix=".yaml"
        )
        self.config_file1_filename = os.path.splitext(
            os.path.basename(self.config_file1.name)
        )[0]
        self.config_file2 = tempfile.NamedTemporaryFile(
            prefix="repos2",
            dir=self.CONFIG_DIR, delete=False, suffix=".json"
        )
        self.config_file2_filename, self.config_file2_fileext = \
            os.path.splitext(
                os.path.basename(self.config_file2.name)
            )

    def test_path_string(self):
        """path as a string."""
        configs = config.find_config_files(path=self.CONFIG_DIR)

        assert self.config_file1.name in configs
        assert self.config_file2.name in configs

    def test_path_list(self):
        configs = config.find_config_files(path=[self.CONFIG_DIR])

        assert self.config_file1.name in configs
        assert self.config_file2.name in configs

    def test_match_string(self):
        configs = config.find_config_files(
            path=[self.CONFIG_DIR],
            match=self.config_file1_filename
        )

        assert self.config_file1.name in configs
        assert self.config_file2.name not in configs

        configs = config.find_config_files(
            path=[self.CONFIG_DIR],
            match=self.config_file2_filename
        )

        assert self.config_file1.name not in configs
        assert self.config_file2.name in configs

        configs = config.find_config_files(
            path=[self.CONFIG_DIR],
            match='randomstring'
        )

        assert self.config_file1.name not in configs
        assert self.config_file2.name not in configs

        configs = config.find_config_files(
            path=[self.CONFIG_DIR],
            match='*'
        )

        assert self.config_file1.name in configs
        assert self.config_file2.name in configs

        configs = config.find_config_files(
            path=[self.CONFIG_DIR],
            match='repos*'
        )

        assert self.config_file1.name in configs
        assert self.config_file2.name in configs

        configs = config.find_config_files(
            path=[self.CONFIG_DIR],
            match='repos[1-9]*'
        )

        assert len([c for c in configs if self.config_file1.name in c]) == 1

        assert self.config_file1.name in configs
        assert self.config_file2.name in configs

    def test_match_list(self):
        configs = config.find_config_files(
            path=[self.CONFIG_DIR],
            match=[self.config_file1_filename, self.config_file2_filename]
        )

        assert self.config_file1.name in configs
        assert self.config_file2.name in configs

        configs = config.find_config_files(
            path=[self.CONFIG_DIR],
            match=[self.config_file1_filename]
        )

        assert self.config_file1.name in configs
        assert len([c for c in configs if self.config_file1.name in c]) == 1
        assert self.config_file2.name not in configs
        assert len([c for c in configs if self.config_file2.name in c]) == 0

    def test_filetype_string(self):
        configs = config.find_config_files(
            path=[self.CONFIG_DIR],
            match=self.config_file1_filename,
            filetype='yaml',
        )

        assert self.config_file1.name in configs
        assert self.config_file2.name not in configs

        configs = config.find_config_files(
            path=[self.CONFIG_DIR],
            match=self.config_file1_filename,
            filetype='json',
        )

        assert self.config_file1.name not in configs
        assert self.config_file2.name not in configs

        configs = config.find_config_files(
            path=[self.CONFIG_DIR],
            match='repos*',
            filetype='json',
        )

        assert self.config_file1.name not in configs
        assert self.config_file2.name in configs

        configs = config.find_config_files(
            path=[self.CONFIG_DIR],
            match='repos*',
            filetype='*',
        )

        assert self.config_file1.name in configs
        assert self.config_file2.name in configs

    def test_filetype_list(self):
        configs = config.find_config_files(
            path=[self.CONFIG_DIR],
            match=['repos*'],
            filetype=['*'],
        )

        assert self.config_file1.name in configs
        assert self.config_file2.name in configs

        configs = config.find_config_files(
            path=[self.CONFIG_DIR],
            match=['repos*'],
            filetype=['json', 'yaml'],
        )

        assert self.config_file1.name in configs
        assert self.config_file2.name in configs

        configs = config.find_config_files(
            path=[self.CONFIG_DIR],
            filetype=['json', 'yaml'],
        )

        assert self.config_file1.name in configs
        assert self.config_file2.name in configs

    def test_include_home_configs(self):
        with EnvironmentVarGuard() as env:
            env.set("HOME", self.TMP_DIR)
            configs = config.find_config_files(
                path=[self.CONFIG_DIR],
                match='*',
                include_home=True
            )

            assert self.config_file1.name in configs
            assert self.config_file2.name in configs

            self.config_file3_path = os.path.join(
                self.TMP_DIR, '.vcspull.json'
            )
            self.config_file3 = open(self.config_file3_path, 'a').close()

            results = config.find_config_files(
                path=[self.CONFIG_DIR],
                match='*',
                include_home=True
            )
            expectedIn = os.path.join(self.TMP_DIR, '.vcspull.json')

            assert expectedIn in results
            assert self.config_file1.name in results
            assert self.config_file2.name in results

            os.remove(self.config_file3_path)


class LoadConfigs(RepoIntegrationTest):

    def test_load(self):
        """Load a list of file into dict."""
        configs = config.find_config_files(
            path=self.CONFIG_DIR
        )

        config.load_configs(configs)


class RepoIntegrationDuplicateTest(RepoIntegrationTest, unittest.TestCase):

    def setUp(self):

        super(RepoIntegrationDuplicateTest, self).setUp()

        config_yaml3 = loadfixture('repoduplicate1.yaml')

        config_yaml4 = loadfixture('repoduplicate2.yaml')

        config_yaml3 = config_yaml3.format(
            svn_repo_path=self.svn_repo_path,
            hg_repo_path=self.hg_repo_path,
            git_repo_path=self.git_repo_path,
            TMP_DIR=self.TMP_DIR
        )

        config_yaml4 = config_yaml4.format(
            svn_repo_path=self.svn_repo_path,
            hg_repo_path=self.hg_repo_path,
            git_repo_path=self.git_repo_path,
            TMP_DIR=self.TMP_DIR
        )

        config_yaml3 = copy.deepcopy(config_yaml3)
        config_yaml4 = copy.deepcopy(config_yaml4)

        self.config3_name = 'repoduplicate1.yaml'
        self.config3_file = os.path.join(self.CONFIG_DIR, self.config3_name)

        with open(self.config3_file, 'w') as buf:
            buf.write(config_yaml3)

        conf = kaptan.Kaptan(handler='yaml')
        conf.import_config(self.config3_file)
        self.config3 = conf.export('dict')

        self.config4_name = 'repoduplicate2.yaml'
        self.config4_file = os.path.join(self.CONFIG_DIR, self.config4_name)

        with open(self.config4_file, 'w') as buf:
            buf.write(config_yaml4)

        conf = kaptan.Kaptan(handler='yaml')
        conf.import_config(self.config4_file)
        self.config4 = conf.export('dict')


class LoadConfigsUpdateDepth(RepoIntegrationDuplicateTest):

    def test_merge_nested_dict(self):

        assert 'vcsOn1' in \
            self.config3[os.path.join(self.TMP_DIR, 'srv/www/test/')]
        assert 'vcsOn2' not in \
            self.config3[os.path.join(self.TMP_DIR, 'srv/www/test/')]
        assert 'vcsOn2' in \
            self.config4[os.path.join(self.TMP_DIR, 'srv/www/test/')]


class LoadConfigsDuplicate(RepoIntegrationDuplicateTest):

    def test_duplicate_path_diff_vcs(self):
        """Duplicate path + name with different repo URL / remotes raises."""
        configs = config.find_config_files(
            path=self.CONFIG_DIR,
            match="repoduplicate[1-2]"
        )

        assert self.config3_file in configs
        assert self.config4_file in configs
        with pytest.raises(Exception):
            config.load_configs(configs)

    @unittest.skip("Not implemented")
    def test_duplicate_path_same_vcs(self):
        """Raise no warning if duplicate path same vcs."""
        pass
