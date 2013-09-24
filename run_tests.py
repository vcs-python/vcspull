#!/usr/bin/env python
# -*- coding: utf-8 -*-


import unittest
import sys
import os
import kaptan
import glob
import tempfile
import shutil



class ConfigExpand(object):
    '''Expand configuration into full form. Enables shorthand forms for
    tmuxinator config.

    This is necessary to keep the code in the :class:`Builder` clean and also
    allow for neat, short-hand configurations.

    As a simple example, internally, tmuxinator expects that config options
    like ``shell_command`` are a list (array)::

        'shell_command': ['htop']

    Tmuxinator configs allow for it to be simply a string::

        'shell_command': 'htop'

    Kaptan will load JSON/YAML/INI files into python dicts for you.

    For testability all expansion / shorthands are in methods here, each will
    check for any expandable config properties in the session, windows and
    their panes and apply the full form to self.config accordingly.

    self.expand will automatically expand all shortened config options. Adding
    ``.config`` will return the expanded config::

        ConfigExpand(config).expand().config

    They also return the context of self, so they are
    chainable.
    '''

    def __init__(self, config):
        '''
        :param config: the configuration for the session
        :type config: dict
        '''

        self.config = config

    def expand(self):
        return self.expand_shell_command().expand_shell_command_before()

    def expand_shell_command(self):
        '''
        iterate through session, windows, and panes for ``shell_command``, if
        it is a string, turn to list.
        '''
        config = self.config

        def _expand(c):
            '''any config section, session, window, pane that can
            contain the 'shell_command' value
            '''
            if ('shell_command' in c and
                    isinstance(c['shell_command'], basestring)):
                    c['shell_command'] = [c['shell_command']]

            return c

        config = _expand(config)
        for window in config['windows']:
            window = _expand(window)
            window['panes'] = [_expand(pane) for pane in window['panes']]

        self.config = config

        return self

    def expand_shell_command_before(self):
        '''
        iterate through session, windows, and panes for
        ``shell_command_before``, if it is a string, turn to list.
        '''
        config = self.config

        def _expand(c):
            '''any config section, session, window, pane that can
            contain the 'shell_command' value
            '''
            if ('shell_command_before' in c and
                    isinstance(c['shell_command_before'], basestring)):
                    c['shell_command_before'] = [c['shell_command_before']]

            return c

        config = _expand(config)
        for window in config['windows']:
            window = _expand(window)
            window['panes'] = [_expand(pane) for pane in window['panes']]

        self.config = config

        return self


class ConfigTrickleDown(object):
    '''Trickle down / inherit config values

    This will only work if config has been expand with ConfigExpand()

    tmuxp allows certain commands to be default at the session, window
    level. shell_command_before trickles down and prepends the
    ``shell_command`` for the pane.
    '''
    def __init__(self, config):
        '''
        :param config: the session configuration
        :type config: dict
        '''
        self.config = config

    def trickle(self):
        self.trickle_shell_command_before()
        return self

    def trickle_shell_command_before(self):
        '''
        prepends a pane's ``shell_command`` list with the window and sessions'
        ``shell_command_before``.
        '''
        config = self.config

        if 'shell_command_before' in config:
            self.assertIsInstance(config['shell_command_before'], list)
            session_shell_command_before = config['shell_command_before']
        else:
            session_shell_command_before = []

        for windowconfitem in config['windows']:
            window_shell_command_before = []
            if 'shell_command_before' in windowconfitem:
                window_shell_command_before = windowconfitem['shell_command_before']

            for paneconfitem in windowconfitem['panes']:
                pane_shell_command_before = []
                if 'shell_command_before' in paneconfitem:
                    pane_shell_command_before += paneconfitem['shell_command_before']

                if 'shell_command' not in paneconfitem:
                    paneconfitem['shell_command'] = list()

                paneconfitem['shell_command'] = session_shell_command_before + window_shell_command_before + pane_shell_command_before + paneconfitem['shell_command']

        self.config = config




class TestTravis(unittest.TestCase):
    def test_travis(self):
        self.assertEqual(2, 2)


TMP_DIR = tempfile.mkdtemp('analects')

sampleconfig_yaml = """
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
        shell_command_after: ln -sf /home/tony/.tmux/.tmux.conf /home/tony/.tmux.conf
"""


sampleconfig_dict = {
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
            'shell_command_after': 'ln -sf /home/tony/.tmux/.tmux.conf /home/tony/.tmux.conf'
        }
    }
}

class ConfigFormatTestCase(unittest.TestCase):
    """ verify that example YAML is returning expected dict format """

    def test_dict_equals_yaml(self):
        config = kaptan.Kaptan(handler='yaml')
        config.import_config(sampleconfig_yaml)

        self.maxDiff = None

        self.assertDictEqual(sampleconfig_dict, config.export('dict'))

class ConfigImportExportTestCase(unittest.TestCase):

    def test_export_json(self):
        json_config_file = os.path.join(TMP_DIR, '.analects.json')

        config = kaptan.Kaptan()
        config.import_config(sampleconfig_dict)

        json_config_data = config.export('json', indent=2)

        buf = open(json_config_file, 'w')
        buf.write(json_config_data)
        buf.close()

        new_config = kaptan.Kaptan()
        new_config_data = new_config.import_config(json_config_file).get()
        self.assertDictEqual(sampleconfig_dict, new_config_data)

    def test_export_yaml(self):
        yaml_config_file = os.path.join(TMP_DIR, '.analects.yaml')

        config = kaptan.Kaptan()
        config.import_config(sampleconfig_dict)

        yaml_config_data = config.export('yaml', indent=2)

        buf = open(yaml_config_file, 'w')
        buf.write(yaml_config_data)
        buf.close()

        new_config = kaptan.Kaptan()
        new_config_data = new_config.import_config(yaml_config_file).get()
        self.assertDictEqual(sampleconfig_dict, new_config_data)

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
        '/home/uesr/study/': {
            'linux': 'git://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git',
            'freebsd': 'https://github.com/freebsd/freebsd.git'
        },
        '/home/user/github_projects/': {
            'kaptan': {
                'repo': 'git@github.com/emre/kaptan',
                'remotes': {
                    'upstream': 'https://github.com/emre/kaptan',
                    'marksteve': 'https://github.com/marksteve/kaptan.git'
                }
            }
        },
        '~': {
            '.vim': {
                'repo': 'git@github.com:tony/vim-config.git',
                'after_shell_command': 'ln -sf /home/tony/.vim/.vimrc /home/tony/.vimrc'
            },
            '.tmux': {
                'repo': 'git@github.com:tony/tmux-config.git',
                'after_shell_command': 'ln -sf /home/tony/.tmux/.tmux.conf /home/tony/.tmux.conf'
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
