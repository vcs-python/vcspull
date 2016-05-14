# -*- coding: utf-8 -*-
"""Tests for vcspull.

vcspull.testsuite.config
~~~~~~~~~~~~~~~~~~~~~~~~

"""
from __future__ import (
    absolute_import, division, print_function, with_statement, unicode_literals
)

import tempfile
import os
import copy
import logging

import kaptan

from testfixtures import compare

from .. import exc
from ..config import expand_config, flatten_config

from . import unittest
from .helpers import (
    ConfigTestMixin, ConfigTestCase, RepoIntegrationTest, EnvironmentVarGuard
)

from .. import config

logger = logging.getLogger(__name__)


class ConfigFormatTest(ConfigTestCase, unittest.TestCase):

    """Verify that example YAML is returning expected dict format."""

    def test_dict_equals_yaml(self):
        config = kaptan.Kaptan(handler='yaml')
        config.import_config(self.config_yaml)

        self.maxDiff = None

        self.assertDictEqual(self.config_dict, config.export('dict'))


class ConfigImportExportTest(ConfigTestCase):

    def test_export_json(self):
        TMP_DIR = self.TMP_DIR
        json_config_file = os.path.join(TMP_DIR, '.vcspull.json')

        config = kaptan.Kaptan()
        config.import_config(self.config_dict)

        json_config_data = config.export('json', indent=2)

        with open(json_config_file, 'w') as buf:
            buf.write(json_config_data)

        new_config = kaptan.Kaptan()
        new_config_data = new_config.import_config(json_config_file).get()
        self.assertDictEqual(self.config_dict, new_config_data)

    def test_export_yaml(self):
        yaml_config_file = os.path.join(self.TMP_DIR, '.vcspull.yaml')

        config = kaptan.Kaptan()
        config.import_config(self.config_dict)

        yaml_config_data = config.export('yaml', indent=2)

        with open(yaml_config_file, 'w') as buf:
            buf.write(yaml_config_data)

        new_config = kaptan.Kaptan()
        new_config_data = new_config.import_config(yaml_config_file).get()
        self.assertDictEqual(self.config_dict, new_config_data)

    def test_scan_config(self):
        configs = []

        garbage_file = os.path.join(self.TMP_DIR, '.vcspull.psd')
        with open(garbage_file, 'w') as buf:
            buf.write('wat')

        for r, d, f in os.walk(self.TMP_DIR):
            for filela in (x for x in f if x.endswith(('.json', 'yaml'))and
                           x.startswith('.vcspull')):
                configs.append(os.path.join(self.TMP_DIR, filela))

        files = 0
        if os.path.exists(os.path.join(self.TMP_DIR, '.vcspull.json')):
            files += 1
            self.assertIn(os.path.join(self.TMP_DIR, '.vcspull.json'), configs)

        if os.path.exists(os.path.join(self.TMP_DIR, '.vcspull.yaml')):
            files += 1
            self.assertIn(os.path.join(self.TMP_DIR, '.vcspull.yaml'), configs)

        self.assertEqual(len(configs), files)


class ConfigExpandTest(ConfigTestCase, unittest.TestCase):

    """Expand configuration into full form."""

    def test_expand_shell_command_after(self):
        """Expand shell commands from string to list."""

        self.maxDiff = None

        config = expand_config(self.config_dict)

        self.assertDictEqual(config, self.config_dict_expanded)


class ConfigFlattenTest(ConfigTestCase, unittest.TestCase):

    """Expand configuration into its flattened / list form."""

    def get_flattened_config(self):
        return [
            {
                'name': 'linux',
                'url': 'git+git://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git',
                'cwd': '{TMP_DIR}/study/'.format(TMP_DIR=self.TMP_DIR),
                'full_path': os.path.join('{TMP_DIR}/study/'.format(TMP_DIR=self.TMP_DIR), 'linux')
            },
            {
                'name': 'freebsd',
                'url': 'git+https://github.com/freebsd/freebsd.git',
                'cwd': '{TMP_DIR}/study/'.format(TMP_DIR=self.TMP_DIR),
                'full_path': os.path.join('{TMP_DIR}/study/'.format(TMP_DIR=self.TMP_DIR), 'freebsd')
            },
            {
                'name': 'sphinx',
                'url': 'hg+https://bitbucket.org/birkenfeld/sphinx',
                'cwd': '{TMP_DIR}/study/'.format(TMP_DIR=self.TMP_DIR),
                'full_path': os.path.join('{TMP_DIR}/study/'.format(TMP_DIR=self.TMP_DIR), 'sphinx'),
            },
            {
                'name': 'docutils',
                'url': 'svn+http://svn.code.sf.net/p/docutils/code/trunk',
                'cwd': '{TMP_DIR}/study/'.format(TMP_DIR=self.TMP_DIR),
                'full_path': os.path.join('{TMP_DIR}/study/'.format(TMP_DIR=self.TMP_DIR), 'docutils'),
            },
            {
                'name': 'kaptan',
                'cwd': '{TMP_DIR}/github_projects/'.format(TMP_DIR=self.TMP_DIR),
                'full_path': os.path.join('{TMP_DIR}/github_projects/'.format(TMP_DIR=self.TMP_DIR), 'kaptan'),
                'url': 'git+git@github.com:tony/kaptan.git',
                'remotes': {
                    'upstream': 'git+https://github.com/emre/kaptan',
                    'marksteve': 'git+https://github.com/marksteve/kaptan.git'
                }
            },
            {
                'name': '.vim',
                'cwd': '{TMP_DIR}'.format(TMP_DIR=self.TMP_DIR),
                'full_path': os.path.join('{TMP_DIR}'.format(TMP_DIR=self.TMP_DIR), '.vim'),
                'url': 'git+git@github.com:tony/vim-config.git',
                'shell_command_after': ['ln -sf /home/tony/.vim/.vimrc /home/tony/.vimrc']
            },
            {
                'name': '.tmux',
                'cwd': '{TMP_DIR}'.format(TMP_DIR=self.TMP_DIR),
                'full_path': os.path.join('{TMP_DIR}'.format(TMP_DIR=self.TMP_DIR), '.tmux'),
                'url': 'git+git@github.com:tony/tmux-config.git',
                'shell_command_after': ['ln -sf /home/tony/.tmux/.tmux.conf /home/tony/.tmux.conf']
            }
        ]

    def test_flatten_config(self):
        self.maxDiff = None

        config = expand_config(self.config_dict)
        config = flatten_config(config)

        self.assertIsInstance(config, list)
        self.assertEqual(len(config), len(self.get_flattened_config()))
        compare(
            sorted(config, key=lambda k: k['name']),
            sorted(self.get_flattened_config(), key=lambda k: k['name'])
        )

    def assertListDictEqual(self, conf1, conf2):
        self.assertCountEqual(conf1, conf2)

class ExpandUserExpandVars(ConfigTestCase, ConfigTestMixin):
    """Verify .expandvars and .expanduser works with configs."""

    def setUp(self):
        ConfigTestCase.setUp(self)
        ConfigTestMixin.setUp(self)

        path_ = """
        '~/study/':
            sphinx: hg+file://{hg_repo_path}
            docutils: svn+file://{svn_repo_path}
            linux: git+file://{git_repo_path}
        '${HOME}/github_projects/':
            kaptan:
                url: git+file://{git_repo_path}
                remotes:
                    test_remote: git+file://{git_repo_path}
        '~':
            .vim:
                url: git+file://{git_repo_path}
            .tmux:
                url: git+file://{git_repo_path}
        """
        config_yaml = path_

        config_json = """
        {
          "~/study/": {
            "sphinx": "hg+file://${hg_repo_path}",
            "docutils": "svn+file://${svn_repo_path}",
            "linux": "git+file://${git_repo_path}"
          },
          "${HOME}/github_projects/": {
            "kaptan": {
              "url": "git+file://${git_repo_path}",
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

    def test_this(self):
        config1_expanded = expand_config(self.config1)
        config2_expanded = expand_config(self.config2)

        paths = [path for path, v in config1_expanded.items()]
        self.assertIn(os.path.expandvars('${HOME}/github_projects/'), paths)
        self.assertIn(os.path.expanduser('~/study/'), paths)
        self.assertIn(os.path.expanduser('~'), paths)

        paths = [path for path, v in config2_expanded.items()]
        self.assertIn(os.path.expandvars('${HOME}/github_projects/'), paths)
        self.assertIn(os.path.expanduser('~/study/'), paths)


class InDirTest(ConfigTestCase):

    def setUp(self):

        ConfigTestCase.setUp(self)

        self.CONFIG_DIR = os.path.join(self.TMP_DIR, '.vcspull')

        os.makedirs(self.CONFIG_DIR)
        self.assertTrue(os.path.exists(self.CONFIG_DIR))

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

        try:
            self.assertItemsEqual(expected, result)
        except AttributeError:
            self.assertCountEqual(expected, result)


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
            self.assertEqual(os.environ.get("HOME"), self.TMP_DIR)
            expectedIn = os.path.join(self.TMP_DIR, '.vcspull.yaml')
            results = config.find_home_config_files()

            self.assertIn(expectedIn, results)

    def test_multiple_configs_raises_exception(self):
        self.config_file2_path = os.path.join(self.TMP_DIR, '.vcspull.json')
        self.config_file2 = open(self.config_file2_path, 'a').close()

        with EnvironmentVarGuard() as env:
            with self.assertRaises(exc.MultipleRootConfigs):
                env.set("HOME", self.TMP_DIR)
                self.assertEqual(os.environ.get("HOME"), self.TMP_DIR)
                config.find_home_config_files()
        os.remove(self.config_file2_path)


class FindConfigs(ConfigTestCase, unittest.TestCase):

    """Test find_config_files."""

    def setUp(self):
        ConfigTestCase.setUp(self)

        self.CONFIG_DIR = os.path.join(self.TMP_DIR, '.vcspull')

        os.makedirs(self.CONFIG_DIR)
        self.assertTrue(os.path.exists(self.CONFIG_DIR))

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

        self.assertIn(self.config_file1.name, configs)
        self.assertIn(self.config_file2.name, configs)

    def test_path_list(self):
        configs = config.find_config_files(path=[self.CONFIG_DIR])

        self.assertIn(self.config_file1.name, configs)
        self.assertIn(self.config_file2.name, configs)

    def test_match_string(self):
        configs = config.find_config_files(
            path=[self.CONFIG_DIR],
            match=self.config_file1_filename
        )

        self.assertIn(self.config_file1.name, configs)
        self.assertNotIn(self.config_file2.name, configs)

        configs = config.find_config_files(
            path=[self.CONFIG_DIR],
            match=self.config_file2_filename
        )

        self.assertNotIn(self.config_file1.name, configs)
        self.assertIn(self.config_file2.name, configs)

        configs = config.find_config_files(
            path=[self.CONFIG_DIR],
            match='randomstring'
        )

        self.assertNotIn(self.config_file1.name, configs)
        self.assertNotIn(self.config_file2.name, configs)

        configs = config.find_config_files(
            path=[self.CONFIG_DIR],
            match='*'
        )

        self.assertIn(self.config_file1.name, configs)
        self.assertIn(self.config_file2.name, configs)

        configs = config.find_config_files(
            path=[self.CONFIG_DIR],
            match='repos*'
        )

        self.assertIn(self.config_file1.name, configs)
        self.assertIn(self.config_file2.name, configs)

        configs = config.find_config_files(
            path=[self.CONFIG_DIR],
            match='repos[1-9]*'
        )

        self.assertEqual(
            len([c for c in configs if self.config_file1.name in c]), 1
        )

        self.assertIn(self.config_file1.name, configs)
        self.assertIn(self.config_file2.name, configs)

    def test_match_list(self):
        configs = config.find_config_files(
            path=[self.CONFIG_DIR],
            match=[self.config_file1_filename, self.config_file2_filename]
        )

        self.assertIn(self.config_file1.name, configs)
        self.assertIn(self.config_file2.name, configs)

        configs = config.find_config_files(
            path=[self.CONFIG_DIR],
            match=[self.config_file1_filename]
        )

        self.assertIn(self.config_file1.name, configs)
        self.assertEqual(
            len([c for c in configs if self.config_file1.name in c]), 1
        )
        self.assertNotIn(self.config_file2.name, configs)
        self.assertEqual(
            len([c for c in configs if self.config_file2.name in c]), 0
        )

    def test_filetype_string(self):
        configs = config.find_config_files(
            path=[self.CONFIG_DIR],
            match=self.config_file1_filename,
            filetype='yaml',
        )

        self.assertIn(self.config_file1.name, configs)
        self.assertNotIn(self.config_file2.name, configs)

        configs = config.find_config_files(
            path=[self.CONFIG_DIR],
            match=self.config_file1_filename,
            filetype='json',
        )

        self.assertNotIn(self.config_file1.name, configs)
        self.assertNotIn(self.config_file2.name, configs)

        configs = config.find_config_files(
            path=[self.CONFIG_DIR],
            match='repos*',
            filetype='json',
        )

        self.assertNotIn(self.config_file1.name, configs)
        self.assertIn(self.config_file2.name, configs)

        configs = config.find_config_files(
            path=[self.CONFIG_DIR],
            match='repos*',
            filetype='*',
        )

        self.assertIn(self.config_file1.name, configs)
        self.assertIn(self.config_file2.name, configs)

    def test_filetype_list(self):
        configs = config.find_config_files(
            path=[self.CONFIG_DIR],
            match=['repos*'],
            filetype=['*'],
        )

        self.assertIn(self.config_file1.name, configs)
        self.assertIn(self.config_file2.name, configs)

        configs = config.find_config_files(
            path=[self.CONFIG_DIR],
            match=['repos*'],
            filetype=['json', 'yaml'],
        )

        self.assertIn(self.config_file1.name, configs)
        self.assertIn(self.config_file2.name, configs)

        configs = config.find_config_files(
            path=[self.CONFIG_DIR],
            filetype=['json', 'yaml'],
        )

        self.assertIn(self.config_file1.name, configs)
        self.assertIn(self.config_file2.name, configs)

    def test_include_home_configs(self):
        with EnvironmentVarGuard() as env:
            env.set("HOME", self.TMP_DIR)
            configs = config.find_config_files(
                path=[self.CONFIG_DIR],
                match='*',
                include_home=True
            )

            self.assertIn(self.config_file1.name, configs)
            self.assertIn(self.config_file2.name, configs)

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

            self.assertIn(expectedIn, results)
            self.assertIn(self.config_file1.name, results)
            self.assertIn(self.config_file2.name, results)

            os.remove(self.config_file3_path)


class LoadConfigs(RepoIntegrationTest):

    def test_load(self):
        """Load a list of file into dict."""
        configs = config.find_config_files(
            path=self.CONFIG_DIR
        )

        try:
            config.load_configs(configs)
        except Exception as e:
            self.fail(e)


class RepoIntegrationDuplicateTest(RepoIntegrationTest, unittest.TestCase):

    def setUp(self):

        super(RepoIntegrationDuplicateTest, self).setUp()

        config_yaml3 = """
        {TMP_DIR}/srv/www/test/:
            subRepoDiffVCS:
                url: svn+file://${svn_repo_path}
            subRepoSameVCS: git+file://${git_repo_path}
            vcsOn1: svn+file://${svn_repo_path}
        """

        config_yaml4 = """
        {TMP_DIR}/srv/www/test/:
            subRepoDiffVCS:
                url: git+file://${git_repo_path}
            subRepoSameVCS: git+file://${git_repo_path}
            vcsOn2: svn+file://${svn_repo_path}
        """

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

        self.assertIn(
            'vcsOn1',
            self.config3[os.path.join(self.TMP_DIR, 'srv/www/test/')]
        )
        self.assertNotIn(
            'vcsOn2',
            self.config3[os.path.join(self.TMP_DIR, 'srv/www/test/')]
        )
        self.assertIn(
            'vcsOn2',
            self.config4[os.path.join(self.TMP_DIR, 'srv/www/test/')]
        )


class LoadConfigsDuplicate(RepoIntegrationDuplicateTest):

    def test_duplicate_path_diff_vcs(self):
        """Duplicate path + name with different repo URL / remotes raises."""

        configs = config.find_config_files(
            path=self.CONFIG_DIR,
            match="repoduplicate[1-2]"
        )

        with self.assertRaises(Exception):
            config.load_configs(configs)

    @unittest.skip("Not implemented")
    def test_duplicate_path_same_vcs(self):
        """Raise no warning if duplicate path same vcs."""
        pass


def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(ConfigExpandTest))
    suite.addTest(unittest.makeSuite(ConfigFormatTest))
    suite.addTest(unittest.makeSuite(ConfigFlattenTest))
    suite.addTest(unittest.makeSuite(ConfigImportExportTest))
    suite.addTest(unittest.makeSuite(ExpandUserExpandVars))
    suite.addTest(unittest.makeSuite(RepoIntegrationTest))
    suite.addTest(unittest.makeSuite(FindConfigs))
    suite.addTest(unittest.makeSuite(FindConfigsHome))
    suite.addTest(unittest.makeSuite(LoadConfigs))
    suite.addTest(unittest.makeSuite(InDirTest))
    suite.addTest(unittest.makeSuite(RepoIntegrationDuplicateTest))
    suite.addTest(unittest.makeSuite(LoadConfigsUpdateDepth))
    suite.addTest(unittest.makeSuite(LoadConfigsDuplicate))

    return suite
