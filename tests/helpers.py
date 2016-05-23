# -*- coding: utf-8 -*-
"""Tests for vcspull.

vcspull.testsuite.helpers
~~~~~~~~~~~~~~~~~~~~~~~~~

_CallableContext, WhateverIO, decorator and stdouts are from the case project,
https://github.com/celery/case, license BSD 3-clause.

"""
from __future__ import (absolute_import, division, print_function,
                        unicode_literals, with_statement)

import copy
import functools
import inspect
import io
import logging
import os
import shutil
import sys
import tempfile
import unittest
import uuid
from contextlib import contextmanager

import kaptan

from testfixtures import compare

from vcspull.config import expand_config
from vcspull.repo import create_repo
from vcspull.util import run

logger = logging.getLogger(__name__)


class EnvironmentVarGuard(object):

    """Class to help protect the environment variable properly.

    May be used as context manager.
    Vendorize to fix issue with Anaconda Python 2 not
    including test module, see #121.
    """

    def __init__(self):
        self._environ = os.environ
        self._unset = set()
        self._reset = dict()

    def set(self, envvar, value):
        if envvar not in self._environ:
            self._unset.add(envvar)
        else:
            self._reset[envvar] = self._environ[envvar]
        self._environ[envvar] = value

    def unset(self, envvar):
        if envvar in self._environ:
            self._reset[envvar] = self._environ[envvar]
            del self._environ[envvar]

    def __enter__(self):
        return self

    def __exit__(self, *ignore_exc):
        for envvar, value in self._reset.items():
            self._environ[envvar] = value
        for unset in self._unset:
            del self._environ[unset]


class ConfigTestMixin(unittest.TestCase):

    """Contains the fresh config dict/yaml's to test against.

    This is because running ConfigExpand on config_dict would alter
    it in later test cases. these configs are used throughout the tests.

    """

    def _removeConfigDirectory(self):
        """Remove TMP_DIR."""
        if os.path.isdir(self.TMP_DIR):
            shutil.rmtree(self.TMP_DIR)
        logger.debug('wiped %s' % self.TMP_DIR)

    def _createConfigDirectory(self):
        """Create TMP_DIR for TestCase."""
        self.TMP_DIR = tempfile.mkdtemp(suffix='vcspull')

    def _seedConfigExampleMixin(self):

        config_yaml = """
        {TMP_DIR}/study/:
            linux: git+git://git.kernel.org/linux/torvalds/linux.git
            freebsd: git+https://github.com/freebsd/freebsd.git
            sphinx: hg+https://bitbucket.org/birkenfeld/sphinx
            docutils: svn+http://svn.code.sf.net/p/docutils/code/trunk
        {TMP_DIR}/github_projects/:
            kaptan:
                url: git+git@github.com:tony/kaptan.git
                remotes:
                    upstream: git+https://github.com/emre/kaptan
                    ms: git+https://github.com/ms/kaptan.git
        {TMP_DIR}:
            .vim:
                url: git+git@github.com:tony/vim-config.git
                shell_command_after: ln -sf /home/u/.vim/.vimrc /home/u/.vimrc
            .tmux:
                url: git+git@github.com:tony/tmux-config.git
                shell_command_after:
                    - ln -sf /home/u/.tmux/.tmux.conf /home/u/.tmux.conf
        """

        config_dict = {
            '{TMP_DIR}/study/'.format(TMP_DIR=self.TMP_DIR): {
                'linux': 'git+git://git.kernel.org/linux/torvalds/linux.git',
                'freebsd': 'git+https://github.com/freebsd/freebsd.git',
                'sphinx': 'hg+https://bitbucket.org/birkenfeld/sphinx',
                'docutils': 'svn+http://svn.code.sf.net/p/docutils/code/trunk',
            },
            '{TMP_DIR}/github_projects/'.format(TMP_DIR=self.TMP_DIR): {
                'kaptan': {
                    'url': 'git+git@github.com:tony/kaptan.git',
                    'remotes': {
                        'upstream': 'git+https://github.com/emre/kaptan',
                        'ms': 'git+https://github.com/ms/kaptan.git'
                    }
                }
            },
            '{TMP_DIR}'.format(TMP_DIR=self.TMP_DIR): {
                '.vim': {
                    'url': 'git+git@github.com:tony/vim-config.git',
                    'shell_command_after':
                    'ln -sf /home/u/.vim/.vimrc /home/u/.vimrc'
                },
                '.tmux': {
                    'url': 'git+git@github.com:tony/tmux-config.git',
                    'shell_command_after': [
                        'ln -sf /home/u/.tmux/.tmux.conf /home/u/.tmux.conf'
                    ]
                }
            }
        }

        config_yaml = config_yaml.format(TMP_DIR=self.TMP_DIR)

        config_dict_expanded = [
            {
                'name': 'linux',
                'parent_dir': '{TMP_DIR}/study/'.format(TMP_DIR=self.TMP_DIR),
                'repo_dir': os.path.join(
                    '{TMP_DIR}/study/'.format(TMP_DIR=self.TMP_DIR), 'linux'
                ),
                'url': 'git+git://git.kernel.org/linux/torvalds/linux.git',
            },
            {
                'name': 'freebsd',
                'parent_dir': '{TMP_DIR}/study/'.format(TMP_DIR=self.TMP_DIR),
                'repo_dir': os.path.join(
                    '{TMP_DIR}/study/'.format(TMP_DIR=self.TMP_DIR), 'freebsd'
                ),
                'url': 'git+https://github.com/freebsd/freebsd.git',
            },
            {
                'name': 'sphinx',
                'parent_dir': '{TMP_DIR}/study/'.format(TMP_DIR=self.TMP_DIR),
                'repo_dir': os.path.join(
                    '{TMP_DIR}/study/'.format(TMP_DIR=self.TMP_DIR), 'sphinx'
                ),
                'url': 'hg+https://bitbucket.org/birkenfeld/sphinx',
            },
            {
                'name': 'docutils',
                'parent_dir': '{TMP_DIR}/study/'.format(TMP_DIR=self.TMP_DIR),
                'repo_dir': os.path.join(
                    '{TMP_DIR}/study/'.format(TMP_DIR=self.TMP_DIR),
                    'docutils'
                ),
                'url': 'svn+http://svn.code.sf.net/p/docutils/code/trunk',
            },
            {
                'name': 'kaptan',
                'url': 'git+git@github.com:tony/kaptan.git',
                'parent_dir': '{TMP_DIR}/github_projects/'.format(
                    TMP_DIR=self.TMP_DIR
                ),
                'repo_dir': os.path.join(
                    '{TMP_DIR}/github_projects/'.format(TMP_DIR=self.TMP_DIR),
                    'kaptan'
                ),
                'remotes': [
                    {
                        'remote_name': 'upstream',
                        'url': 'git+https://github.com/emre/kaptan',
                    },
                    {
                        'remote_name': 'ms',
                        'url': 'git+https://github.com/ms/kaptan.git'
                    }
                ]
            },
            {
                'name': '.vim',
                'parent_dir': '{TMP_DIR}'.format(TMP_DIR=self.TMP_DIR),
                'repo_dir': os.path.join(
                    '{TMP_DIR}'.format(TMP_DIR=self.TMP_DIR), '.vim'
                ),
                'url': 'git+git@github.com:tony/vim-config.git',
                'shell_command_after': [
                    'ln -sf /home/u/.vim/.vimrc /home/u/.vimrc'
                ]
            },
            {
                'name': '.tmux',
                'parent_dir': '{TMP_DIR}'.format(TMP_DIR=self.TMP_DIR),
                'repo_dir': os.path.join(
                    '{TMP_DIR}'.format(TMP_DIR=self.TMP_DIR), '.tmux'
                ),
                'url': 'git+git@github.com:tony/tmux-config.git',
                'shell_command_after': [
                    'ln -sf /home/u/.tmux/.tmux.conf /home/u/.tmux.conf'
                ]
            }
        ]

        self.config_dict = config_dict

        cdict = copy.deepcopy(config_dict)
        assertConfigList(expand_config(cdict), config_dict_expanded)

        self.config_dict_expanded = config_dict_expanded
        self.config_yaml = config_yaml


class ConfigTestCase(ConfigTestMixin, unittest.TestCase):
    def tearDown(self):
        self._removeConfigDirectory()

    def setUp(self):
        self._createConfigDirectory()
        self._seedConfigExampleMixin()


class RepoTestMixin(object):

    """Mixin for create Repo's for test repository."""

    def create_svn_repo(
        self, repo_name='my_svn_project', create_temp_repo=False
    ):
        """Create an svn repository for tests. Return SVN repo directory.

        :param repo_name:
        :type repo_name:
        :param create_temp_repo: If true, create repository
        :type create_temp_repo: bool
        :returns: directory of svn repository
        :rtype: string

        """
        repo_path = os.path.join(
            self.TMP_DIR, 'svnrepo_{0}'.format(uuid.uuid4())
        )

        svn_repo = create_repo(**{
            'url': 'svn+file://' + os.path.join(repo_path, repo_name),
            'parent_dir': self.TMP_DIR,
            'name': repo_name
        })

        if create_temp_repo:
            os.mkdir(repo_path)
            run(['svnadmin', 'create', svn_repo['name']],
                cwd=repo_path)
            self.assertTrue(os.path.exists(repo_path))

            svn_repo.obtain()

        return os.path.join(repo_path, repo_name), svn_repo

    def create_git_repo(
        self, repo_name='test git repo', create_temp_repo=False
    ):
        """Create an git repository for tests. Return directory.

        :param repo_name:
        :type repo_name:
        :param create_temp_repo: If true, create repository
        :type create_temp_repo: bool
        :returns: directory of svn repository
        :rtype: string

        """
        repo_path = os.path.join(
            self.TMP_DIR, 'gitrepo_{0}'.format(uuid.uuid4())
        )

        git_repo = create_repo(**{
            'url': 'git+file://' + os.path.join(repo_path, repo_name),
            'parent_dir': self.TMP_DIR,
            'name': repo_name
        })

        if create_temp_repo:
            os.mkdir(repo_path)
            run(['git', 'init', git_repo['name']],
                cwd=repo_path)
            self.assertTrue(os.path.exists(repo_path))

            git_repo.obtain(quiet=True)

            testfile_filename = 'testfile.test'

            run(['touch', testfile_filename],
                cwd=os.path.join(repo_path, repo_name))
            run(['git', 'add', testfile_filename],
                cwd=os.path.join(repo_path, repo_name))
            run(['git', 'commit', '-m', 'test file for %s' % git_repo['name']],
                cwd=os.path.join(repo_path, repo_name))
            git_repo.update_repo()

        return os.path.join(repo_path, repo_name), git_repo

    def create_mercurial_repo(
        self, repo_name='test hg repo', create_temp_repo=False
    ):
        """Create an hg repository for tests. Return directory.

        :param repo_name:
        :type repo_name:
        :param create_temp_repo: If true, create repository
        :type create_temp_repo: bool
        :returns: directory of hg repository
        :rtype: string

        """
        repo_path = os.path.join(
            self.TMP_DIR, 'hgrepo_{0}'.format(uuid.uuid4())
        )

        mercurial_repo = create_repo(**{
            'url': 'hg+file://' + os.path.join(repo_path, repo_name),
            'parent_dir': self.TMP_DIR,
            'name': repo_name
        })

        if create_temp_repo:
            os.mkdir(repo_path)
            run([
                'hg', 'init', mercurial_repo['name']], cwd=repo_path
                )

            mercurial_repo.obtain()

            testfile_filename = 'testfile.test'

            run(['touch', testfile_filename],
                cwd=os.path.join(repo_path, repo_name))
            run(['hg', 'add', testfile_filename],
                cwd=os.path.join(repo_path, repo_name))
            run(['hg', 'commit',
                '-m', 'a test file for %s' % mercurial_repo['name']],
                cwd=os.path.join(repo_path, repo_name))

        return os.path.join(repo_path, repo_name), mercurial_repo


class RepoIntegrationTest(RepoTestMixin, ConfigTestCase, unittest.TestCase):

    """TestCase base that prepares custom repos, configs.

    :var git_repo_path: git repo
    :var svn_repo_path: svn repo
    :var hg_repo_path: hg repo
    :var TMP_DIR: temporary directory for testcase
    :var CONFIG_DIR: the ``.vcspull`` dir inside of ``TMP_DIR``.

    Create a local svn, git and hg repo. Create YAML config file with paths.

    """

    def setUp(self):

        ConfigTestCase.setUp(self)

        self.git_repo_path, self.git_repo = self.create_git_repo()
        self.hg_repo_path, self.hg_repo = self.create_mercurial_repo()
        self.svn_repo_path, self.svn_repo = self.create_svn_repo()

        self.CONFIG_DIR = os.path.join(self.TMP_DIR, '.vcspull')

        os.makedirs(self.CONFIG_DIR)
        self.assertTrue(os.path.exists(self.CONFIG_DIR))

        config_yaml = """
        {TMP_DIR}/samedir/:
            docutils: svn+file://{svn_repo_path}
        {TMP_DIR}/github_projects/deeper/:
            kaptan:
                url: git+file://{git_repo_path}
                remotes:
                    test_remote: git+file://{git_repo_path}
        {TMP_DIR}:
            samereponame: git+file://{git_repo_path}
            .tmux:
                url: git+file://{git_repo_path}
        """

        config_json = """
        {
          "${TMP_DIR}/samedir/": {
            "sphinx": "hg+file://${hg_repo_path}",
            "linux": "git+file://${git_repo_path}"
          },
          "${TMP_DIR}/another_directory/": {
            "anotherkaptan": {
              "url": "git+file://${git_repo_path}",
              "remotes": {
                "test_remote": "git+file://${git_repo_path}"
              }
            }
          },
          "${TMP_DIR}": {
            "samereponame": "git+file://${git_repo_path}",
            ".vim": {
              "url": "git+file://${git_repo_path}"
            }
          },
          "${TMP_DIR}/srv/www/": {
            "test": {
              "url": "git+file://${git_repo_path}"
            }
          }
        }
        """

        config_yaml = config_yaml.format(
            svn_repo_path=self.svn_repo_path,
            hg_repo_path=self.hg_repo_path,
            git_repo_path=self.git_repo_path,
            TMP_DIR=self.TMP_DIR
        )

        from string import Template
        config_json = Template(config_json).substitute(
            svn_repo_path=self.svn_repo_path,
            hg_repo_path=self.hg_repo_path,
            git_repo_path=self.git_repo_path,
            TMP_DIR=self.TMP_DIR
        )

        self.config_yaml = copy.deepcopy(config_yaml)
        self.config_json = copy.deepcopy(config_json)

        conf = kaptan.Kaptan(handler='yaml')
        conf.import_config(self.config_yaml)
        self.config1 = conf.export('dict')

        self.config1_name = 'repos1.yaml'
        self.config1_file = os.path.join(self.CONFIG_DIR, self.config1_name)

        with open(self.config1_file, 'w') as buf:
            buf.write(self.config_yaml)

        conf = kaptan.Kaptan(handler='json')
        conf.import_config(self.config_json)
        self.config2 = conf.export('dict')

        self.assertTrue(os.path.exists(self.config1_file))

        self.config2_name = 'repos2.json'
        self.config2_file = os.path.join(self.CONFIG_DIR, self.config2_name)

        with open(self.config2_file, 'w') as buf:
            buf.write(self.config_json)

        self.assertTrue(os.path.exists(self.config2_file))


def assertConfigList(list1, list2):
    """Assert content of two unordered dicts (sorted by repo_dir value).

    :param list1: List of configs
    :type list1: List of :py:`dict`
    :param list2: List of configs
    :type list2: List of :py:`dict`
    :raises: Exception
    """
    compare(
        sorted(list1, key=lambda x: sorted(x.get('repo_dir'))),
        sorted(list2, key=lambda x: sorted(x.get('repo_dir')))
    )


StringIO = io.StringIO
_SIO_write = StringIO.write
_SIO_init = StringIO.__init__


def update_wrapper(wrapper, wrapped, *args, **kwargs):
    wrapper = functools.update_wrapper(wrapper, wrapped, *args, **kwargs)
    wrapper.__wrapped__ = wrapped
    return wrapper


def wraps(wrapped,
          assigned=functools.WRAPPER_ASSIGNMENTS,
          updated=functools.WRAPPER_UPDATES):
    return functools.partial(update_wrapper, wrapped=wrapped,
                             assigned=assigned, updated=updated)


class _CallableContext(object):

    def __init__(self, context, cargs, ckwargs, fun):
        self.context = context
        self.cargs = cargs
        self.ckwargs = ckwargs
        self.fun = fun

    def __call__(self, *args, **kwargs):
        return self.fun(*args, **kwargs)

    def __enter__(self):
        self.ctx = self.context(*self.cargs, **self.ckwargs)
        return self.ctx.__enter__()

    def __exit__(self, *einfo):
        if self.ctx:
            return self.ctx.__exit__(*einfo)


def decorator(predicate):
    context = contextmanager(predicate)

    @wraps(predicate)
    def take_arguments(*pargs, **pkwargs):

        @wraps(predicate)
        def decorator(cls):
            if inspect.isclass(cls):
                orig_setup = cls.setUp
                orig_teardown = cls.tearDown

                @wraps(cls.setUp)
                def around_setup(*args, **kwargs):
                    try:
                        contexts = args[0].__rb3dc_contexts__
                    except AttributeError:
                        contexts = args[0].__rb3dc_contexts__ = []
                    p = context(*pargs, **pkwargs)
                    p.__enter__()
                    contexts.append(p)
                    return orig_setup(*args, **kwargs)
                around_setup.__wrapped__ = cls.setUp
                cls.setUp = around_setup

                @wraps(cls.tearDown)
                def around_teardown(*args, **kwargs):
                    try:
                        contexts = args[0].__rb3dc_contexts__
                    except AttributeError:
                        pass
                    else:
                        for context in contexts:
                            context.__exit__(*sys.exc_info())
                    orig_teardown(*args, **kwargs)
                around_teardown.__wrapped__ = cls.tearDown
                cls.tearDown = around_teardown

                return cls
            else:
                @wraps(cls)
                def around_case(self, *args, **kwargs):
                    with context(*pargs, **pkwargs) as context_args:
                        context_args = context_args or ()
                        if not isinstance(context_args, tuple):
                            context_args = (context_args,)
                        return cls(*(self,) + args + context_args, **kwargs)
                return around_case

        if len(pargs) == 1 and callable(pargs[0]):
            fun, pargs = pargs[0], ()
            return decorator(fun)
        return _CallableContext(context, pargs, pkwargs, decorator)
    assert take_arguments.__wrapped__
    return take_arguments


class WhateverIO(StringIO):

    def __init__(self, v=None, *a, **kw):
        _SIO_init(self, v.decode() if isinstance(v, bytes) else v, *a, **kw)

    def write(self, data):
        _SIO_write(self, data.decode() if isinstance(data, bytes) else data)


@decorator
def stdouts():
    """Override `sys.stdout` and `sys.stderr` with `StringIO`
    instances.
    Decorator example::
        @mock.stdouts
        def test_foo(self, stdout, stderr):
            something()
            self.assertIn('foo', stdout.getvalue())
    Context example::
        with mock.stdouts() as (stdout, stderr):
            something()
            self.assertIn('foo', stdout.getvalue())
    """
    prev_out, prev_err = sys.stdout, sys.stderr
    prev_rout, prev_rerr = sys.__stdout__, sys.__stderr__
    mystdout, mystderr = WhateverIO(), WhateverIO()
    sys.stdout = sys.__stdout__ = mystdout
    sys.stderr = sys.__stderr__ = mystderr

    try:
        yield mystdout, mystderr
    finally:
        sys.stdout = prev_out
        sys.stderr = prev_err
        sys.__stdout__ = prev_rout
        sys.__stderr__ = prev_rerr


@decorator
def mute():
    """Redirect `sys.stdout` and `sys.stderr` to /dev/null, silencent them.
    Decorator example::
        @mute
        def test_foo(self):
            something()
    Context example::
        with mute():
            something()
    """
    prev_out, prev_err = sys.stdout, sys.stderr
    prev_rout, prev_rerr = sys.__stdout__, sys.__stderr__
    devnull = open(os.devnull, 'w')
    mystdout, mystderr = devnull, devnull
    sys.stdout = sys.__stdout__ = mystdout
    sys.stderr = sys.__stderr__ = mystderr

    try:
        yield
    finally:
        sys.stdout = prev_out
        sys.stderr = prev_err
        sys.__stdout__ = prev_rout
        sys.__stderr__ = prev_rerr
