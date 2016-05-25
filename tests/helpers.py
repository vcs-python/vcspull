# -*- coding: utf-8 -*-
"""Tests for vcspull.

vcspull.testsuite.helpers
~~~~~~~~~~~~~~~~~~~~~~~~~

_CallableContext, WhateverIO, decorator and stdouts are from the case project,
https://github.com/celery/case, license BSD 3-clause.

"""
from __future__ import (absolute_import, division, print_function,
                        unicode_literals, with_statement)

import os

from vcspull.util import which


def has_exe(exe):
    try:
        which(exe)
        return True
    except Exception:
        return False


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


def get_config_dict(TMP_DIR):
    return {
        '{TMP_DIR}/study/'.format(TMP_DIR=TMP_DIR): {
            'linux': 'git+git://git.kernel.org/linux/torvalds/linux.git',
            'freebsd': 'git+https://github.com/freebsd/freebsd.git',
            'sphinx': 'hg+https://bitbucket.org/birkenfeld/sphinx',
            'docutils': 'svn+http://svn.code.sf.net/p/docutils/code/trunk',
        },
        '{TMP_DIR}/github_projects/'.format(TMP_DIR=TMP_DIR): {
            'kaptan': {
                'url': 'git+git@github.com:tony/kaptan.git',
                'remotes': {
                    'upstream': 'git+https://github.com/emre/kaptan',
                    'ms': 'git+https://github.com/ms/kaptan.git'
                }
            }
        },
        '{TMP_DIR}'.format(TMP_DIR=TMP_DIR): {
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


def get_config_dict_expanded(TMP_DIR):
    return [
        {
            'name': 'linux',
            'parent_dir': '{TMP_DIR}/study/'.format(TMP_DIR=TMP_DIR),
            'repo_dir': os.path.join(
                '{TMP_DIR}/study/'.format(TMP_DIR=TMP_DIR), 'linux'
            ),
            'url': 'git+git://git.kernel.org/linux/torvalds/linux.git',
        },
        {
            'name': 'freebsd',
            'parent_dir': '{TMP_DIR}/study/'.format(TMP_DIR=TMP_DIR),
            'repo_dir': os.path.join(
                '{TMP_DIR}/study/'.format(TMP_DIR=TMP_DIR), 'freebsd'
            ),
            'url': 'git+https://github.com/freebsd/freebsd.git',
        },
        {
            'name': 'sphinx',
            'parent_dir': '{TMP_DIR}/study/'.format(TMP_DIR=TMP_DIR),
            'repo_dir': os.path.join(
                '{TMP_DIR}/study/'.format(TMP_DIR=TMP_DIR), 'sphinx'
            ),
            'url': 'hg+https://bitbucket.org/birkenfeld/sphinx',
        },
        {
            'name': 'docutils',
            'parent_dir': '{TMP_DIR}/study/'.format(TMP_DIR=TMP_DIR),
            'repo_dir': os.path.join(
                '{TMP_DIR}/study/'.format(TMP_DIR=TMP_DIR),
                'docutils'
            ),
            'url': 'svn+http://svn.code.sf.net/p/docutils/code/trunk',
        },
        {
            'name': 'kaptan',
            'url': 'git+git@github.com:tony/kaptan.git',
            'parent_dir': '{TMP_DIR}/github_projects/'.format(
                TMP_DIR=TMP_DIR
            ),
            'repo_dir': os.path.join(
                '{TMP_DIR}/github_projects/'.format(TMP_DIR=TMP_DIR),
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
            'parent_dir': '{TMP_DIR}'.format(TMP_DIR=TMP_DIR),
            'repo_dir': os.path.join(
                '{TMP_DIR}'.format(TMP_DIR=TMP_DIR), '.vim'
            ),
            'url': 'git+git@github.com:tony/vim-config.git',
            'shell_command_after': [
                'ln -sf /home/u/.vim/.vimrc /home/u/.vimrc'
            ]
        },
        {
            'name': '.tmux',
            'parent_dir': '{TMP_DIR}'.format(TMP_DIR=TMP_DIR),
            'repo_dir': os.path.join(
                '{TMP_DIR}'.format(TMP_DIR=TMP_DIR), '.tmux'
            ),
            'url': 'git+git@github.com:tony/tmux-config.git',
            'shell_command_after': [
                'ln -sf /home/u/.tmux/.tmux.conf /home/u/.tmux.conf'
            ]
        }
    ]
