#!/usr/bin/env python
# -*- coding: utf-8 -*-


import unittest
import sys
import os
import kaptan
import glob
import tempfile
import shutil
import collections
from pprint import pprint

TMP_DIR = tempfile.mkdtemp('analects')


def expand_config(config):
    '''Expand configuration into full form. Enables shorthand forms for
    analects config.
    :param config: the configuration for the session
    :type config: dict
    '''
    for directory, repos in config.iteritems():
        for repo, repo_data in repos.iteritems():

            '''
            repo_name: http://myrepo.com/repo.git

            to

            repo_name: { repo: 'http://myrepo.com/repo.git' }

            also assures the repo is a :py:class:`dict`.
            '''

            if isinstance(repo_data, basestring):
                config[directory][repo] = {'repo': repo_data}

            '''
            ``shell_command_after``: if str, turn to list.
            '''
            if 'shell_command_after' in repo_data:
                if isinstance(repo_data['shell_command_after'], basestring):
                    repo_data['shell_command_after'] = [
                        repo_data['shell_command_after']]

    return config


class ConfigTestCaseBase(unittest.TestCase):

    """ contains the fresh config dict/yaml's to test against.

    this is because running ConfigExpand on SAMPLECONFIG_DICT would alter
    it in later test cases. these configs are used throughout the tests.
    """

    def setUp(self):

        SAMPLECONFIG_YAML = """
        /home/user/study/:
            linux: git+git://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git
            freebsd: git+https://github.com/freebsd/freebsd.git
            sqlalchemy: hg+https://bitbucket.org/zzzeek/sqlalchemy.git
            docutils: svn+http://svn.code.sf.net/p/docutils/code/trunk
        /home/user/github_projects/:
            kaptan:
                repo: git+git@github.com:tony/kaptan.git
                remotes:
                    upstream: git+https://github.com/emre/kaptan
                    marksteve: git+https://github.com/marksteve/kaptan.git
        /home/tony/:
            .vim:
                repo: git+git@github.com:tony/vim-config.git
                shell_command_after: ln -sf /home/tony/.vim/.vimrc /home/tony/.vimrc
            .tmux:
                repo: git+git@github.com:tony/tmux-config.git
                shell_command_after:
                    - ln -sf /home/tony/.tmux/.tmux.conf /home/tony/.tmux.conf
        """

        SAMPLECONFIG_DICT = {
            '/home/user/study/': {
                'linux': 'git+git://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git',
                'freebsd': 'git+https://github.com/freebsd/freebsd.git',
                'sqlalchemy': 'hg+https://bitbucket.org/zzzeek/sqlalchemy.git',
                'docutils': 'svn+http://svn.code.sf.net/p/docutils/code/trunk',
            },
            '/home/user/github_projects/': {
                'kaptan': {
                    'repo': 'git+git@github.com:tony/kaptan.git',
                    'remotes': {
                        'upstream': 'git+https://github.com/emre/kaptan',
                        'marksteve': 'git+https://github.com/marksteve/kaptan.git'
                    }
                }
            },
            '/home/tony/': {
                '.vim': {
                    'repo': 'git+git@github.com:tony/vim-config.git',
                    'shell_command_after': 'ln -sf /home/tony/.vim/.vimrc /home/tony/.vimrc'
                },
                '.tmux': {
                    'repo': 'git+git@github.com:tony/tmux-config.git',
                    'shell_command_after': ['ln -sf /home/tony/.tmux/.tmux.conf /home/tony/.tmux.conf']
                }
            }
        }

        SAMPLECONFIG_FINAL_DICT = {
            '/home/user/study/': {
                'linux': {'repo': 'git+git://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git', },
                'freebsd': {'repo': 'git+https://github.com/freebsd/freebsd.git', },
                'sqlalchemy': {'repo': 'hg+https://bitbucket.org/zzzeek/sqlalchemy.git', },
                'docutils': {'repo': 'svn+http://svn.code.sf.net/p/docutils/code/trunk', },
            },
            '/home/user/github_projects/': {
                'kaptan': {
                    'repo': 'git+git@github.com:tony/kaptan.git',
                    'remotes': {
                        'upstream': 'git+https://github.com/emre/kaptan',
                        'marksteve': 'git+https://github.com/marksteve/kaptan.git'
                    }
                }
            },
            '/home/tony/': {
                '.vim': {
                    'repo': 'git+git@github.com:tony/vim-config.git',
                    'shell_command_after': ['ln -sf /home/tony/.vim/.vimrc /home/tony/.vimrc']
                },
                '.tmux': {
                    'repo': 'git+git@github.com:tony/tmux-config.git',
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


class BackboneCollection(collections.MutableSequence):

    '''emulate backbone collection
    '''
    def __init__(self, models=None):
        self.attributes = list(models) if models is None else []

    def __getitem__(self, index):
        return self.attributes[index]

    def __setitem__(self, index, value):
        self.attributes[index] = value

    def __delitem__(self, index):
        del self.attributes[index]

    def insert(self, index, value):
        self.attributes.insert(index, value)

    def __len__(self):
        return len(self.attributes)


class BackboneModel(collections.MutableMapping):

    '''emulate backbone model
    '''
    def __init__(self, attributes=None):
        self.attributes = dict(attributes) if attributes is not None else {}

    def __getitem__(self, key):
        return self.attributes[key]

    def __setitem__(self, key, value):
        self.attributes[key] = value
        self.dirty = True

    def __delitem__(self, key):
        del self.attributes[key]
        self.dirty = True

    def keys(self):
        return self.attributes.keys()

    def __iter__(self):
        return self.attributes.__iter__()

    def __len__(self):
        return len(self.attributes.keys())


class Repos(BackboneCollection):

    """.find, .findWhere returns a ReposProxy class of filtered repos, these
    may be .update()'d.  make repos underscore.py compatible?

    """
    pass


class Repo(BackboneModel):

    def __new__(cls, attributes, *args, **kwargs):
        vcs_url = attributes['remote_location']
        if vcs_url.startswith('git+'):
            return super(Repo, cls).__new__(GitRepo, attributes, *args, **kwargs)
        if vcs_url.startswith('hg+'):
            return super(Repo, cls).__new__(MercurialRepo, attributes, *args, **kwargs)
        if vcs_url.startswith('svn+'):
            return super(Repo, cls).__new__(SubversionRepo, attributes, *args, **kwargs)
        else:
            return super(Repo, cls).__new__(cls, attributes, *args, **kwargs)

    def __init__(self, attributes=None):
        print("Repo __init__  %s" % (locals()))
        self.attributes = dict(attributes) if attributes is not None else {}


from pip.vcs.bazaar import Bazaar
from pip.vcs.git import Git
from pip.vcs.subversion import Subversion
from pip.vcs.mercurial import Mercurial
#git, mercurial, subversion
class GitRepo(Repo, Git):
    vcs = 'git'

    def __init__(self, arguments, *args, **kwargs):
        super(Repo, self).__init__(arguments, *args, **kwargs)
        super(Git, self).__init__(arguments.get('remote_location'), *args, **kwargs)


class MercurialRepo(Repo, Mercurial):
    vcs = 'hg'
    def __init__(self, arguments, *args, **kwargs):
        super(Repo, self).__init__(arguments, *args, **kwargs)
        super(Mercurial, self).__init__(arguments.get('remote_location'), *args, **kwargs)


class SubversionRepo(Repo, Subversion):
    vcs = 'svn'
    def __init__(self, arguments, *args, **kwargs):
        super(Repo, self).__init__(arguments, *args, **kwargs)
        super(Subversion, self).__init__(arguments.get('remote_location'), *args, **kwargs)

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

    @staticmethod
    def get_objects(config):
        repo_list = []
        for directory, repos in config.iteritems():
            for repo, repo_data in repos.iteritems():
                repo_dict = {
                    'name': repo,
                    'parent_path': directory,
                    'remote_location': repo_data['repo'],
                }

                if 'remotes' in repo_data:
                    repo_dict['remotes'] = []
                    for remote_name, remote_location in repo_data['remotes'].iteritems():
                        remote_dict = {
                            'remote_name': remote_name,
                            'remote_location': remote_location
                        }
                        repo_dict['remotes'].append(remote_dict)
                repo_list.append(repo_dict)
        return repo_list

    def test_to_dictlist(self):
        config = self.config_dict_expanded

        repo_list = self.get_objects(self.config_dict_expanded)

        for r in repo_list:
            self.assertIsInstance(r, dict)
            self.assertIn('name', r)
            self.assertIn('parent_path', r)
            self.assertIn('remote_location', r)

            if 'remotes' in r:
                self.assertIsInstance(r['remotes'], list)
                for remote in r['remotes']:
                    self.assertIsInstance(remote, dict)
                    self.assertIn('remote_name', remote)
                    self.assertIn('remote_location', remote)
        pprint(repo_list)

    def test_vcs_url_scheme_to_object(self):
        git_repo = Repo({
            'remote_location': 'git+git://git.myproject.org/MyProject.git@da39a3ee5e6b4b0d3255bfef95601890afd80709'
        })

        self.assertIsInstance(git_repo, GitRepo)
        self.assertIsInstance(git_repo, Repo)

        hg_repo = Repo({
            'remote_location': 'hg+https://hg.myproject.org/MyProject#egg=MyProject'
        })

        self.assertIsInstance(hg_repo, MercurialRepo)
        self.assertIsInstance(hg_repo, Repo)

        svn_repo = Repo({
            'remote_location': 'svn+svn://svn.myproject.org/svn/MyProject#egg=MyProject'
        })

        self.assertIsInstance(svn_repo, SubversionRepo)
        self.assertIsInstance(svn_repo, Repo)

    def test_to_repo_objects(self):
        repo_list = self.get_objects(self.config_dict_expanded)
        for repo_dict in repo_list:
            r = Repo(repo_dict)
            print r.get_url_rev()
            self.assertIsInstance(r, Repo)
            self.assertIn('name', r)
            self.assertIn('parent_path', r)
            self.assertIn('remote_location', r)

            if 'remotes' in r:
                self.assertIsInstance(r['remotes'], list)
                for remote in r['remotes']:
                    self.assertIsInstance(remote, dict)
                    self.assertIn('remote_name', remote)
                    self.assertIn('remote_location', remote)


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
