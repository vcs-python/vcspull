#!/usr/bin/env python
# -*- coding: utf-8 -*-


import unittest
import sys
import os
import kaptan
import glob
import tempfile
import shutil


TMP_DIR = tempfile.mkdtemp('analects')


def expand_config(config):
    '''Expand configuration into full form. Enables shorthand forms for
    analects config.
    :param config: the configuration for the session
    :type config: dict

    repo_name: http://myrepo.com/repo.git

    to

    repo_name: { repo: 'http://myrepo.com/repo.git' }

    also assures the repo is a :py:class:`dict`.
    '''

    def _expand(repo_data):
        if isinstance(repo_data, basestring):
            repo_data = {'repo': repo_data}

        return repo_data

    def _expand_shell_command_after(c):
        '''
        iterate through session, windows, and panes for
        ``shell_command_after``, if it is a string, turn to list.
        '''
        if ('shell_command_after' in c and
                isinstance(c['shell_command_after'], basestring)):
                c['shell_command_after'] = [c['shell_command_after']]

    for directory, repos in config.iteritems():
        for repo, repo_data in repos.iteritems():
            config[directory][repo] = _expand(repo_data)
            repo_data = _expand_shell_command_after(repo_data)

    return config


class ConfigTestCaseBase(unittest.TestCase):

    """ contains the fresh config dict/yaml's to test against.

    this is because running ConfigExpand on SAMPLECONFIG_DICT would alter
    it in later test cases. these configs are used throughout the tests.
    """

    def setUp(self):

        SAMPLECONFIG_YAML = """
        /home/user/study/:
            linux: git://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git
            freebsd: https://github.com/freebsd/freebsd.git
        /home/user/github_projects/:
            kaptan:
                repo: git@github.com:tony/kaptan.git
                remotes:
                    upstream: https://github.com/emre/kaptan
                    marksteve: https://github.com/marksteve/kaptan.git
        /home/tony/:
            .vim:
                repo: git@github.com:tony/vim-config.git
                shell_command_after: ln -sf /home/tony/.vim/.vimrc /home/tony/.vimrc
            .tmux:
                repo: git@github.com:tony/tmux-config.git
                shell_command_after:
                    - ln -sf /home/tony/.tmux/.tmux.conf /home/tony/.tmux.conf
        """

        SAMPLECONFIG_DICT = {
            '/home/user/study/': {
                'linux': 'git://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git',
                'freebsd': 'https://github.com/freebsd/freebsd.git'
            },
            '/home/user/github_projects/': {
                'kaptan': {
                    'repo': 'git@github.com:tony/kaptan.git',
                    'remotes': {
                        'upstream': 'https://github.com/emre/kaptan',
                        'marksteve': 'https://github.com/marksteve/kaptan.git'
                    }
                }
            },
            '/home/tony/': {
                '.vim': {
                    'repo': 'git@github.com:tony/vim-config.git',
                    'shell_command_after': 'ln -sf /home/tony/.vim/.vimrc /home/tony/.vimrc'
                },
                '.tmux': {
                    'repo': 'git@github.com:tony/tmux-config.git',
                    'shell_command_after': ['ln -sf /home/tony/.tmux/.tmux.conf /home/tony/.tmux.conf']
                }
            }
        }

        SAMPLECONFIG_FINAL_DICT = {
            '/home/user/study/': {
                'linux': {'repo': 'git://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git', },
                'freebsd': {'repo': 'https://github.com/freebsd/freebsd.git', }
            },
            '/home/user/github_projects/': {
                'kaptan': {
                    'repo': 'git@github.com:tony/kaptan.git',
                    'remotes': {
                        'upstream': 'https://github.com/emre/kaptan',
                        'marksteve': 'https://github.com/marksteve/kaptan.git'
                    }
                }
            },
            '/home/tony/': {
                '.vim': {
                    'repo': 'git@github.com:tony/vim-config.git',
                    'shell_command_after': ['ln -sf /home/tony/.vim/.vimrc /home/tony/.vimrc']
                },
                '.tmux': {
                    'repo': 'git@github.com:tony/tmux-config.git',
                    'shell_command_after': ['ln -sf /home/tony/.tmux/.tmux.conf /home/tony/.tmux.conf']
                }
            }
        }

        self.config_dict = SAMPLECONFIG_DICT
        self.config_dict_expanded = SAMPLECONFIG_FINAL_DICT
        self.config_yaml = SAMPLECONFIG_YAML


class ConfigFormatTestCase(ConfigTestCaseBase):

    """ verify that example YAML is returning expected dict format """

    def test_dict_equals_yaml(self):
        config = kaptan.Kaptan(handler='yaml')
        config.import_config(self.config_yaml)

        self.maxDiff = None

        self.assertDictEqual(self.config_dict, config.export('dict'))


class ConfigImportExportTestCase(ConfigTestCaseBase):

    def test_export_json(self):
        json_config_file = os.path.join(TMP_DIR, '.analects.json')

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
        yaml_config_file = os.path.join(TMP_DIR, '.analects.yaml')

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

        garbage_file = os.path.join(TMP_DIR, '.analects.psd')
        buf = open(garbage_file, 'w')
        buf.write('wat')
        buf.close()

        if os.path.exists(TMP_DIR):
            for r, d, f in os.walk(TMP_DIR):
                for filela in (x for x in f if x.endswith(('.json', '.ini', 'yaml')) and x.startswith('.analects')):
                    configs.append(os.path.join(
                        TMP_DIR, filela))

        files = 0
        if os.path.exists(os.path.join(TMP_DIR, '.analects.json')):
            files += 1
            self.assertIn(os.path.join(
                TMP_DIR, '.analects.json'), configs)

        if os.path.exists(os.path.join(TMP_DIR, '.analects.yaml')):
            files += 1
            self.assertIn(os.path.join(
                TMP_DIR, '.analects.yaml'), configs)

        if os.path.exists(os.path.join(TMP_DIR, '.analects.ini')):
            files += 1
            self.assertIn(os.path.join(TMP_DIR, '.analects.ini'), configs)

        self.assertEqual(len(configs), files)

    @classmethod
    def tearDownClass(cls):
        if os.path.isdir(TMP_DIR):
            shutil.rmtree(TMP_DIR)


class ConfigExpandTestCase(ConfigTestCaseBase):

    '''
    assumes the configuration has been imported into a python dict correctly.
    '''

    def test_expand_shell_command_after(self):
        '''
        expands shell commands from string to list
        '''

        self.maxDiff = None

        config = expand_config(self.config_dict)

        self.assertDictEqual(config, self.config_dict_expanded)


class ConfigToObjectTestCase(ConfigTestCaseBase):
    '''create an individual dictionary for each repository'''

    def setUp(self):
        SAMPLECONFIG_LIST = [
        {
            'name': None,
            'parent_path': None,
            'remote_location': None,
            'remotes': []
        }
        ]

        super(ConfigToObjectTestCase, self).setUp()

    def test_to_objects(self):
        pass


class TestFabric(object):

    """ we may want to skip testing in travis, and offer conditions to pass
    if there is no SSH server on the local machine.

    see: https://github.com/fabric/fabric/blob/master/.travis.yml
    """
    pass


class TestIterateThroughEachObject(object):

    """todo:
    iterate through each object and return a list of them.

    look into being able to use variation of https://github.com/serkanyersen/underscore.py/blob/master/src/underscore.py

    .find / .findWhere to easily look up results in collection lf repos.

    """
    pass


class TestVCS(object):

    def test_can_get_repository(self):
        raise NotImplementedError


class TestGit(TestVCS):
    pass

if __name__ == '__main__':
    unittest.main(verbosity=2)
