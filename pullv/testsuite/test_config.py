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


class RepoSVN(RepoTest):

    def test_repo_svn(self):
        repo_dir = os.path.join(self.TMP_DIR, '.repo_dir')
        repo_name = 'my_svn_project'

        svn_repo = Repo({
            'url': 'svn+file://' + os.path.join(repo_dir, repo_name),
            'parent_path': self.TMP_DIR,
            'name': repo_name
        })

        svn_checkout_dest = os.path.join(self.TMP_DIR, svn_repo['name'])

        os.mkdir(repo_dir)

        run(['svnadmin', 'create', svn_repo['name']], cwd=repo_dir)

        svn_repo.obtain()

        tempFile = tempfile.NamedTemporaryFile(dir=svn_checkout_dest)

        run(['svn', 'add', tempFile.name], cwd=svn_checkout_dest)
        run(
            ['svn', 'commit', '-m', 'a test file for %s' % svn_repo['name']],
            cwd=svn_checkout_dest
        )
        self.assertEqual(svn_repo.get_revision(), 0)
        svn_repo.update_repo()

        self.assertEqual(
            os.path.join(svn_checkout_dest, tempFile.name),
            tempFile.name
        )
        self.assertEqual(svn_repo.get_revision(tempFile.name), 1)

        self.assertTrue(os.path.exists(svn_checkout_dest))


class RepoGit(ConfigTest):

    def test_repo_git(self):
        repo_dir = os.path.join(self.TMP_DIR, '.repo_dir')
        repo_name = 'my_git_project'

        git_repo = Repo({
            'url': 'git+file://' + os.path.join(repo_dir, repo_name),
            'parent_path': self.TMP_DIR,
            'name': repo_name
        })

        os.mkdir(repo_dir)
        run([
            'git', 'init', git_repo['name']
            ], cwd=repo_dir)
        git_checkout_dest = os.path.join(self.TMP_DIR, git_repo['name'])
        git_repo.obtain()

        testfile = 'testfile.test'

        run(['touch', testfile], cwd=os.path.join(repo_dir, repo_name))
        run([
            'git', 'add', testfile
            ], cwd=os.path.join(repo_dir, repo_name))
        run([
            'git', 'commit', '-m', 'a test file for %s' % git_repo['name']
            ], cwd=os.path.join(repo_dir, repo_name))
        git_repo.update_repo()

        test_repo_revision = run(
            ['git', 'rev-parse', 'HEAD'],
            cwd=os.path.join(repo_dir, repo_name),
        )['stdout']

        self.assertEqual(
            git_repo.get_revision(),
            test_repo_revision
        )
        self.assertTrue(os.path.exists(git_checkout_dest))


class RepoMercurial(ConfigTest):

    def test_repo_mercurial(self):
        repo_dir = os.path.join(
            self.TMP_DIR, '.repo_dir'
        )
        repo_name = 'my_mercurial_project'

        mercurial_repo = Repo({
            'url': 'hg+file://' + os.path.join(repo_dir, repo_name),
            'parent_path': self.TMP_DIR,
            'name': repo_name
        })

        mercurial_checkout_dest = os.path.join(
            self.TMP_DIR, mercurial_repo['name']
        )

        os.mkdir(repo_dir)
        run(['hg', 'init', mercurial_repo['name']], cwd=repo_dir)

        mercurial_repo.obtain()

        testfile = 'testfile.test'

        run([
            'touch', testfile
            ], cwd=os.path.join(repo_dir, repo_name))
        run([
            'hg', 'add', testfile
            ], cwd=os.path.join(repo_dir, repo_name))
        run([
            'hg', 'commit', '-m', 'a test file for %s' % mercurial_repo['name']
            ], cwd=os.path.join(repo_dir, repo_name))

        mercurial_repo.update_repo()

        test_repo_revision = run(
            ['hg', 'parents', '--template={rev}'],
            cwd=os.path.join(repo_dir, repo_name),
        )['stdout']

        self.assertEqual(
            mercurial_repo.get_revision(),
            test_repo_revision
        )

        self.assertTrue(os.path.exists(mercurial_checkout_dest))



