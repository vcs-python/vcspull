# -*- coding: utf-8 -*-
"""Tests for pullv.

pullv.tests.helpers
~~~~~~~~~~~~~~~~~~~

:copyright: Copyright 2013 Tony Narlock.
:license: BSD, see LICENSE for details

"""

import unittest
import os
import logging
import tempfile
import shutil
from ..repo import Repo
from ..util import run

logger = logging.getLogger(__name__)


class ConfigTest(unittest.TestCase):

    """Contains the fresh config dict/yaml's to test against.

    This is because running ConfigExpand on SAMPLECONFIG_DICT would alter
    it in later test cases. these configs are used throughout the tests.

    """

    def tearDown(self):
        """Remove TMP_DIR."""
        if os.path.isdir(self.TMP_DIR):
            shutil.rmtree(self.TMP_DIR)
        logger.debug('wiped %s' % self.TMP_DIR)

    def setUp(self):
        """Create TMP_DIR for TestCase."""
        self.TMP_DIR = tempfile.mkdtemp(suffix='pullv')


class ConfigExamples(ConfigTest):

    """ConfigExamples mixin that creates test directory + sample configs."""

    def setUp(self):
        """Extend ConfigTest and add sample configs to class."""

        super(ConfigExamples, self).setUp()

        SAMPLECONFIG_YAML = """
        {TMP_DIR}/study/:
            linux: git+git://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git
            freebsd: git+https://github.com/freebsd/freebsd.git
            sphinx: hg+https://bitbucket.org/birkenfeld/sphinx
            docutils: svn+http://svn.code.sf.net/p/docutils/code/trunk
        {TMP_DIR}/github_projects/:
            kaptan:
                repo: git+git@github.com:tony/kaptan.git
                remotes:
                    upstream: git+https://github.com/emre/kaptan
                    marksteve: git+https://github.com/marksteve/kaptan.git
        {TMP_DIR}:
            .vim:
                repo: git+git@github.com:tony/vim-config.git
                shell_command_after: ln -sf /home/tony/.vim/.vimrc /home/tony/.vimrc
            .tmux:
                repo: git+git@github.com:tony/tmux-config.git
                shell_command_after:
                    - ln -sf /home/tony/.tmux/.tmux.conf /home/tony/.tmux.conf
        """

        SAMPLECONFIG_DICT = {
            '{TMP_DIR}/study/'.format(TMP_DIR=self.TMP_DIR): {
                'linux': 'git+git://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git',
                'freebsd': 'git+https://github.com/freebsd/freebsd.git',
                'sphinx': 'hg+https://bitbucket.org/birkenfeld/sphinx',
                'docutils': 'svn+http://svn.code.sf.net/p/docutils/code/trunk',
            },
            '{TMP_DIR}/github_projects/'.format(TMP_DIR=self.TMP_DIR): {
                'kaptan': {
                    'repo': 'git+git@github.com:tony/kaptan.git',
                    'remotes': {
                        'upstream': 'git+https://github.com/emre/kaptan',
                        'marksteve': 'git+https://github.com/marksteve/kaptan.git'
                    }
                }
            },
            '{TMP_DIR}'.format(TMP_DIR=self.TMP_DIR): {
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

        SAMPLECONFIG_YAML = SAMPLECONFIG_YAML.format(TMP_DIR=self.TMP_DIR)

        SAMPLECONFIG_FINAL_DICT = {
            '{TMP_DIR}/study/'.format(TMP_DIR=self.TMP_DIR): {
                'linux': {'repo': 'git+git://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git', },
                'freebsd': {'repo': 'git+https://github.com/freebsd/freebsd.git', },
                'sphinx': {'repo': 'hg+https://bitbucket.org/birkenfeld/sphinx', },
                'docutils': {'repo': 'svn+http://svn.code.sf.net/p/docutils/code/trunk', },
            },
            '{TMP_DIR}/github_projects/'.format(TMP_DIR=self.TMP_DIR): {
                'kaptan': {
                    'repo': 'git+git@github.com:tony/kaptan.git',
                    'remotes': {
                        'upstream': 'git+https://github.com/emre/kaptan',
                        'marksteve': 'git+https://github.com/marksteve/kaptan.git'
                    }
                }
            },
            '{TMP_DIR}'.format(TMP_DIR=self.TMP_DIR): {
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

        SAMPLECONFIG_YAML = SAMPLECONFIG_YAML.format(TMP_DIR=self.TMP_DIR)


class RepoTest(ConfigTest):

    """Create Repo's for test repository."""

    def create_svn_repo(self):
        """Create an svn repository for tests. Return SVN repo directory.

        :returns: directory of svn repository
        :rtype: string

        """

        svn_test_repo = os.path.join(self.TMP_DIR, '.svn_test_repo')
        svn_repo_name = 'my_svn_project'

        svn_repo = Repo({
            'url': 'svn+file://' + os.path.join(svn_test_repo, svn_repo_name),
            'parent_path': self.TMP_DIR,
            'name': svn_repo_name
        })

        os.mkdir(svn_test_repo)
        run([
            'svnadmin', 'create', svn_repo['name']
            ], cwd=svn_test_repo)
        self.assertTrue(os.path.exists(svn_test_repo))

        svn_checkout_dest = os.path.join(self.TMP_DIR, svn_repo['name'])
        svn_repo.obtain()

        return os.path.join(svn_test_repo, svn_repo_name), svn_repo

    def create_git_repo(self):
        """Create an git repository for tests. Return directory.

        :returns: directory of svn repository
        :rtype: string

        """

        git_test_repo = os.path.join(self.TMP_DIR, '.git_test_repo')
        git_repo_name = 'my_git_project'

        git_repo = Repo({
            'url': 'git+file://' + os.path.join(git_test_repo, git_repo_name),
            'parent_path': self.TMP_DIR,
            'name': git_repo_name
        })

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

        return os.path.join(git_test_repo, git_repo_name), git_repo

    def create_mercurial_repo(self):
        mercurial_test_repo = os.path.join(
            self.TMP_DIR, '.mercurial_test_repo')
        mercurial_repo_name = 'my_mercurial_project'

        mercurial_repo = Repo({
            'url': 'hg+file://' + os.path.join(mercurial_test_repo, mercurial_repo_name),
            'parent_path': self.TMP_DIR,
            'name': mercurial_repo_name
        })

        os.mkdir(mercurial_test_repo)
        run([
            'hg', 'init', mercurial_repo['name']], cwd=mercurial_test_repo
            )

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

        return os.path.join(mercurial_test_repo, mercurial_repo_name), mercurial_repo
