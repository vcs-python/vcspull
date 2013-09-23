#!/usr/bin/env python
# -*- coding: utf-8 -*-


import unittest
import sys
import os
import kaptan
import glob
import tempfile
import shutil


class TestTravis(unittest.TestCase):
    def test_travis(self):
        self.assertEqual(2, 2)


TMP_DIR = tempfile.mkdtemp('analects')

sampleyamlconfig = """
    /home/user/study/:
      linux: git://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git
      freebsd: https://github.com/freebsd/freebsd.git
    /home/user/github_projects/:
      kaptan:
        repo: git@github.com:tony/kaptan.git
        remotes:
          upstream: https://github.com/emre/kaptan
          marksteve: https://github.com/marksteve/kaptan.git
"""

sampleconfigdict = {
    'session_name': 'sampleconfig',
    'start_directory': '~',
    'windows': [{
        'window_name': 'editor',
        'panes': [
            {
                'start_directory': '~', 'shell_command': ['vim'],
                },  {
                'shell_command': ['cowsay "hey"']
            },
        ],
        'layout': 'main-verticle'},
        {'window_name': 'logging', 'panes': [
         {'shell_command': ['tail -F /var/log/syslog'],
          'start_directory':'/var/log'}
         ]}, {
            'automatic_rename': True,
            'panes': [
                {'shell_command': ['htop']}
            ]
        }]
}


class ConfigImportExportTestCase(unittest.TestCase):

    def test_export_json(self):
        json_config_file = os.path.join(TMP_DIR, '.analects.json')

        config = kaptan.Kaptan()
        config.import_config(sampleconfigdict)

        json_config_data = config.export('json', indent=2)

        buf = open(json_config_file, 'w')
        buf.write(json_config_data)
        buf.close()

        new_config = kaptan.Kaptan()
        new_config_data = new_config.import_config(json_config_file).get()
        self.assertDictEqual(sampleconfigdict, new_config_data)

    def test_export_yaml(self):
        yaml_config_file = os.path.join(TMP_DIR, '.analects.yaml')

        config = kaptan.Kaptan()
        config.import_config(sampleconfigdict)

        yaml_config_data = config.export('yaml', indent=2)

        buf = open(yaml_config_file, 'w')
        buf.write(yaml_config_data)
        buf.close()

        new_config = kaptan.Kaptan()
        new_config_data = new_config.import_config(yaml_config_file).get()
        self.assertDictEqual(sampleconfigdict, new_config_data)

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


class ConfigExpandTestCase(unittest.TestCase):

    '''
    assumes the configuration has been imported into a python dict correctly.
    '''

    before_config = {
        'session_name': 'sampleconfig',
        'start_directory': '~',
        'windows': [{
            'shell_command': 'top',
            'window_name': 'editor',
            'panes': [
                {
                    'start_directory': '~', 'shell_command': ['vim'],
                    },  {
                    'shell_command': 'cowsay "hey"'
                },
            ],
            'layout': 'main-verticle'},
            {
                'window_name': 'logging',
                'panes': [
                    {'shell_command': ['tail -F /var/log/syslog'],
                     'start_directory':'/var/log'}
                ]
            },
            {
                'automatic_rename': True,
                'panes': [
                    {'shell_command': 'htop'}
                ]
            }]
    }

    before_config = {
        '/home/uesr/study': {
            'linux': 'git://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git',
            'freebsd': 'https://github.com/freebsd/freebsd.git'
        },
        '/home/user/github_projects': {
            'kaptan': {
                'repo': 'git@github.com/emre/kaptan',
                'remotes': {
                    'upstream': 'https://github.com/emre/kaptan',
                    'marksteve': 'https://github.com/marksteve/kaptan.git'
                }
            }
        }
    }

    after_config = {

    }

    @unittest.skip("not implemented yet")
    def test_expand_shell_commands(self):
        '''
        expands shell commands from string to list
        '''
        config = analects_expand(self.before_config).expand().config
        self.assertDictEqual(config, self.after_config)


class TestFabric(object):
    """ we may want to skip testing in travis, and offer conditions to pass
    if there is no SSH server on the local machine.

    see: https://github.com/fabric/fabric/blob/master/.travis.yml
    """
    pass


class TestVCS(object):

    def test_can_get_repository(self):
        raise NotImplementedError


class TestGit(TestVCS):
    pass

if __name__ == '__main__':
    unittest.main()

if __name__ == '__main__':
    unittest.main()
