# -*- coding: utf-8 -*-
"""Tests for pullv.

pullv.tests.test_config
~~~~~~~~~~~~~~~~~~~~~~~

:copyright: Copyright 2013 Tony Narlock.
:license: BSD, see LICENSE for details

"""

import unittest
import os
import tempfile
import shutil
import kaptan
from pullv.repo import BaseRepo, Repo, GitRepo, MercurialRepo, SubversionRepo
from pullv.util import expand_config, get_repos, run


import logging

logger = logging.getLogger(__name__)


class RageRage(unittest.TestCase):
    def lol(self):
        # create a temporary folder and change dir into it
        tmp_dir = tempfile.mkdtemp(suffix='tmuxp')
        os.chdir(tmp_dir)

        try:
            config1 = open('.tmuxp.json', 'w+b')
            config1.close()

            configs_found = config.in_cwd()
        finally:
            os.remove(config1.name)

        self.assertEqual(len(configs_found), 1)
        self.assertIn('.tmuxp.json', configs_found)

        # clean up
        os.chdir(current_dir)
        if os.path.isdir(tmp_dir):
            shutil.rmtree(tmp_dir)

    @classmethod
    def tearDownClass(cls):
        if os.path.isdir(TMUXP_DIR):
            shutil.rmtree(TMUXP_DIR)
        logger.debug('wiped %s' % TMUXP_DIR)

import tempfile

class ConfigTest(unittest.TestCase):

    """Contains the fresh config dict/yaml's to test against.

    This is because running ConfigExpand on SAMPLECONFIG_DICT would alter
    it in later test cases. these configs are used throughout the tests.

    """

    def tearDown(self):
        if os.path.isdir(self.tmp_dir):
            shutil.rmtree(self.tmp_dir)
        logger.debug('wiped %s' % self.tmp_dir)

    def setUp(self):

        self.tmp_dir = tempfile.mkdtemp(suffix='tmuxp')

        SAMPLECONFIG_YAML = """
        {tmp_dir}/study/:
            linux: git+git://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git
            freebsd: git+https://github.com/freebsd/freebsd.git
            sphinx: hg+https://bitbucket.org/birkenfeld/sphinx
            docutils: svn+http://svn.code.sf.net/p/docutils/code/trunk
        {tmp_dir}/github_projects/:
            kaptan:
                repo: git+git@github.com:tony/kaptan.git
                remotes:
                    upstream: git+https://github.com/emre/kaptan
                    marksteve: git+https://github.com/marksteve/kaptan.git
        {tmp_dir}:
            .vim:
                repo: git+git@github.com:tony/vim-config.git
                shell_command_after: ln -sf /home/tony/.vim/.vimrc /home/tony/.vimrc
            .tmux:
                repo: git+git@github.com:tony/tmux-config.git
                shell_command_after:
                    - ln -sf /home/tony/.tmux/.tmux.conf /home/tony/.tmux.conf
        """

        SAMPLECONFIG_YAML = SAMPLECONFIG_YAML.format(tmp_dir= self.tmp_dir)

        SAMPLECONFIG_DICT = {
            '{tmp_dir}/study/'.format(tmp_dir=self.tmp_dir): {
                'linux': 'git+git://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git',
                'freebsd': 'git+https://github.com/freebsd/freebsd.git',
                'sphinx': 'hg+https://bitbucket.org/birkenfeld/sphinx',
                'docutils': 'svn+http://svn.code.sf.net/p/docutils/code/trunk',
            },
            '{tmp_dir}/github_projects/'.format(tmp_dir=self.tmp_dir): {
                'kaptan': {
                    'repo': 'git+git@github.com:tony/kaptan.git',
                    'remotes': {
                        'upstream': 'git+https://github.com/emre/kaptan',
                        'marksteve': 'git+https://github.com/marksteve/kaptan.git'
                    }
                }
            },
            '{tmp_dir}'.format(tmp_dir=self.tmp_dir): {
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

        SAMPLECONFIG_YAML = SAMPLECONFIG_YAML.format(tmp_dir= self.tmp_dir)


        SAMPLECONFIG_FINAL_DICT = {
            '{tmp_dir}/study/'.format(tmp_dir=self.tmp_dir): {
                'linux': {'repo': 'git+git://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git', },
                'freebsd': {'repo': 'git+https://github.com/freebsd/freebsd.git', },
                'sphinx': {'repo': 'hg+https://bitbucket.org/birkenfeld/sphinx', },
                'docutils': {'repo': 'svn+http://svn.code.sf.net/p/docutils/code/trunk', },
            },
            '{tmp_dir}/github_projects/'.format(tmp_dir=self.tmp_dir): {
                'kaptan': {
                    'repo': 'git+git@github.com:tony/kaptan.git',
                    'remotes': {
                        'upstream': 'git+https://github.com/emre/kaptan',
                        'marksteve': 'git+https://github.com/marksteve/kaptan.git'
                    }
                }
            },
            '{tmp_dir}'.format(tmp_dir=self.tmp_dir): {
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


class ConfigFormatTestCase(ConfigTest):

    """ verify that example YAML is returning expected dict format """

    def test_dict_equals_yaml(self):
        config = kaptan.Kaptan(handler='yaml')
        config.import_config(self.config_yaml)

        self.maxDiff = None

        self.assertDictEqual(self.config_dict, config.export('dict'))


class ConfigImportExportTestCase(ConfigTest):

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
        TMP_DIR = self.TMP_DIR
        yaml_config_file = os.path.join(TMP_DIR, '.pullv.yaml')

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
        TMP_DIR = self.TMP_DIR
        configs = []

        garbage_file = os.path.join(TMP_DIR, '.pullv.psd')
        buf = open(garbage_file, 'w')
        buf.write('wat')
        buf.close()

        for r, d, f in os.walk(TMP_DIR):
            for filela in (x for x in f if x.endswith(('.json', '.ini', 'yaml')) and x.startswith('.pullv')):
                configs.append(os.path.join(
                    TMP_DIR, filela))

        files = 0
        if os.path.exists(os.path.join(TMP_DIR, '.pullv.json')):
            files += 1
            self.assertIn(os.path.join(
                TMP_DIR, '.pullv.json'), configs)

        if os.path.exists(os.path.join(TMP_DIR, '.pullv.yaml')):
            files += 1
            self.assertIn(os.path.join(
                TMP_DIR, '.pullv.yaml'), configs)

        if os.path.exists(os.path.join(TMP_DIR, '.pullv.ini')):
            files += 1
            self.assertIn(os.path.join(TMP_DIR, '.pullv.ini'), configs)

        self.assertEqual(len(configs), files)

    @classmethod
    def setUpClass(cls):
        cls.TMP_DIR = tempfile.mkdtemp('pullv')

    @classmethod
    def tearDownClass(cls):
        if os.path.isdir(cls.TMP_DIR):
            shutil.rmtree(cls.TMP_DIR)


class ConfigExpandTestCase(ConfigTest):

    """Expand configuration into full form."""

    def test_expand_shell_command_after(self):
        """Expand shell commands from string to list."""

        self.maxDiff = None

        config = expand_config(self.config_dict)

        self.assertDictEqual(config, self.config_dict_expanded)


class ConfigToObjectTest(ConfigTest):

    """TestCase for converting config (dict) into Repo object."""

    def setUp(self):
        SAMPLECONFIG_LIST = [
            {
                'name': None,
                'parent_path': None,
                'url': None,
                'remotes': []
            }
        ]

        super(ConfigToObjectTest, self).setUp()

    def test_to_dictlist(self):
        """``get_repos`` pulls the repos in dict format from the config."""
        config = self.config_dict_expanded

        repo_list = get_repos(self.config_dict_expanded)

        for r in repo_list:
            self.assertIsInstance(r, dict)
            self.assertIn('name', r)
            self.assertIn('parent_path', r)
            self.assertIn('url', r)

            if 'remotes' in r:
                self.assertIsInstance(r['remotes'], list)
                for remote in r['remotes']:
                    self.assertIsInstance(remote, dict)
                    self.assertIn('remote_name', remote)
                    self.assertIn('url', remote)

    def test_vcs_url_scheme_to_object(self):
        """Test that ``url`` return a GitRepo/MercurialRepo/SubversionRepo.

        :class:`GitRepo`, :class:`MercurialRepo` or :class:`SubversionRepo`
        object based on the pip-style URL scheme.

        """

        git_repo = Repo({
            'url': 'git+git://git.myproject.org/MyProject.git@da39a3ee5e6b4b0d3255bfef95601890afd80709',
            'parent_path': self.TMP_DIR,
            'name': 'myproject1'
        })

        # TODO parent_path and name if duplicated should give an error

        self.assertIsInstance(git_repo, GitRepo)
        self.assertIsInstance(git_repo, BaseRepo)

        hg_repo = Repo({
            'url': 'hg+https://hg.myproject.org/MyProject#egg=MyProject',
            'parent_path': self.TMP_DIR,
            'name': 'myproject2'
        })

        self.assertIsInstance(hg_repo, MercurialRepo)
        self.assertIsInstance(hg_repo, BaseRepo)

        svn_repo = Repo({
            'url': 'svn+svn://svn.myproject.org/svn/MyProject#egg=MyProject',
            'parent_path': self.TMP_DIR,
            'name': 'myproject3'
        })

        self.assertIsInstance(svn_repo, SubversionRepo)
        self.assertIsInstance(svn_repo, BaseRepo)

    def test_repo_svn(self):
        svn_test_repo = os.path.join(self.TMP_DIR, '.svn_test_repo')
        svn_repo_name = 'my_svn_project'

        svn_repo = Repo({
            'url': 'svn+file://' + os.path.join(svn_test_repo, svn_repo_name),
            'parent_path': self.TMP_DIR,
            'name': svn_repo_name
        })

        self.assertIsInstance(svn_repo, SubversionRepo)
        self.assertIsInstance(svn_repo, BaseRepo)

        os.mkdir(svn_test_repo)
        run([
            'svnadmin', 'create', svn_repo['name']
            ], cwd=svn_test_repo)
        self.assertTrue(os.path.exists(svn_test_repo))

        svn_checkout_dest = os.path.join(self.TMP_DIR, svn_repo['name'])
        svn_repo.obtain()

        tempFile = tempfile.NamedTemporaryFile(dir=svn_checkout_dest)

        self.assertEqual(svn_repo.get_revision(), 0)
        run([
            'svn', 'add', tempFile.name
            ], cwd=svn_checkout_dest)
        run([
            'svn', 'commit', '-m', 'a test file for %s' % svn_repo['name']
            ], cwd=svn_checkout_dest)

        svn_repo.update_repo()
        self.assertEqual(os.path.join(
            svn_checkout_dest, tempFile.name), tempFile.name)
        self.assertEqual(svn_repo.get_revision(tempFile.name), 1)

        self.assertTrue(os.path.exists(svn_checkout_dest))

    def test_repo_git(self):
        git_test_repo = os.path.join(self.TMP_DIR, '.git_test_repo')
        git_repo_name = 'my_git_project'

        git_repo = Repo({
            'url': 'git+file://' + os.path.join(git_test_repo, git_repo_name),
            'parent_path': self.TMP_DIR,
            'name': git_repo_name
        })

        self.assertIsInstance(git_repo, GitRepo)
        self.assertIsInstance(git_repo, BaseRepo)

        os.mkdir(git_test_repo)
        run([
            'git', 'init', git_repo['name']
            ], cwd=git_test_repo)
        self.assertTrue(os.path.exists(git_test_repo))

        git_checkout_dest = os.path.join(self.TMP_DIR, git_repo['name'])
        git_repo.obtain()

        testfile_filename = 'testfile.test'

        run([
            'touch', testfile_filename
            ], cwd=os.path.join(git_test_repo, git_repo_name))
        run([
            'git', 'add', testfile_filename
            ], cwd=os.path.join(git_test_repo, git_repo_name))
        run([
            'git', 'commit', '-m', 'a test file for %s' % git_repo['name']
            ], cwd=os.path.join(git_test_repo, git_repo_name))
        git_repo.update_repo()

        test_repo_revision = run(
            ['git', 'rev-parse', 'HEAD'],
            cwd=os.path.join(git_test_repo, git_repo_name),
        )['stdout']

        self.assertEqual(
            git_repo.get_revision(),
            test_repo_revision
        )
        self.assertTrue(os.path.exists(git_checkout_dest))

    def test_repo_mercurial(self):
        mercurial_test_repo = os.path.join(
            self.TMP_DIR, '.mercurial_test_repo')
        mercurial_repo_name = 'my_mercurial_project'

        mercurial_repo = Repo({
            'url': 'hg+file://' + os.path.join(mercurial_test_repo, mercurial_repo_name),
            'parent_path': self.TMP_DIR,
            'name': mercurial_repo_name
        })

        self.assertIsInstance(mercurial_repo, MercurialRepo)
        self.assertIsInstance(mercurial_repo, BaseRepo)

        os.mkdir(mercurial_test_repo)
        run([
            'hg', 'init', mercurial_repo['name']], cwd=mercurial_test_repo
            )
        self.assertTrue(os.path.exists(mercurial_test_repo))

        mercurial_checkout_dest = os.path.join(
            self.TMP_DIR, mercurial_repo['name'])
        mercurial_repo.obtain()

        testfile_filename = 'testfile.test'

        run([
            'touch', testfile_filename
            ], cwd=os.path.join(mercurial_test_repo, mercurial_repo_name))
        run([
            'hg', 'add', testfile_filename
            ], cwd=os.path.join(mercurial_test_repo, mercurial_repo_name))
        run([
            'hg', 'commit', '-m', 'a test file for %s' % mercurial_repo['name']
            ], cwd=os.path.join(mercurial_test_repo, mercurial_repo_name))

        mercurial_repo.update_repo()

        test_repo_revision = run(
            ['hg', 'parents', '--template={rev}'],
            cwd=os.path.join(mercurial_test_repo, mercurial_repo_name),
        )['stdout']

        self.assertEqual(
            mercurial_repo.get_revision(),
            test_repo_revision
        )

        self.assertTrue(os.path.exists(mercurial_checkout_dest))

    def test_to_repo_objects(self):
        """:py:obj:`dict` objects into Repo objects."""
        repo_list = get_repos(self.config_dict_expanded)
        for repo_dict in repo_list:
            r = Repo(repo_dict)

            self.assertIsInstance(r, BaseRepo)
            self.assertIn('name', r)
            self.assertEqual(r['name'], repo_dict['name'])
            self.assertIn('parent_path', r)
            self.assertEqual(r['parent_path'], repo_dict['parent_path'])
            self.assertIn('url', r)
            self.assertEqual(r['url'], repo_dict['url'])

            self.assertEqual(r['path'], os.path.join(
                r['parent_path'], r['name']))

            if 'remotes' in r:
                self.assertIsInstance(r['remotes'], list)
                for remote in r['remotes']:
                    self.assertIsInstance(remote, dict)
                    self.assertIn('remote_name', remote)
                    self.assertIn('url', remote)

    @classmethod
    def setUpClass(cls):
        cls.TMP_DIR = tempfile.mkdtemp('pullv')

    @classmethod
    def tearDownClass(cls):
        if os.path.isdir(cls.TMP_DIR):
            shutil.rmtree(cls.TMP_DIR)
        pass
