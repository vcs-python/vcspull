# -*- coding: utf-8 -*-
"""Repo package for vcspull.

vcspull.repo
~~~~~~~~~~~~

"""
from __future__ import absolute_import, division, print_function, \
    with_statement, unicode_literals

import logging

from ..log import RepoLogFormatter, RepoFilter

from .git import GitRepo
from .hg import MercurialRepo
from .svn import SubversionRepo
from .base import BaseRepo, RepoLoggingAdapter

__all__ = ['GitRepo', 'MercurialRepo', 'SubversionRepo', 'BaseRepo', 'Repo',
           'RepoLoggingAdapter']

logger = logging.getLogger(__name__)

logger.propagate = False
channel = logging.StreamHandler()
channel.setFormatter(RepoLogFormatter())
channel.addFilter(RepoFilter())
logger.setLevel('INFO')
logger.addHandler(channel)


class Repo(object):

    """Return an object with a base class of :class:`Repo` depending on url.

    Return instance of :class:`vcspull.repo.svn.SubversionRepo`,
    :class:`vcspull.repo.git.GitRepo` or :class:`vcspull.repo.hg.MercurialRepo`.
    The object returned is a child of :class:`vcspull.repo.base.BaseRepo`.

    Usage Example::

        In [1]: from vcspull.repo import Repo

        In [2]: r = Repo(url='git+https://www.github.com/tony/vim-config', cwd='/tmp/',
                    name='vim-config')

        In [3]: r.update_repo()
        |vim-config| (git)  Repo directory for vim-config (git) does not exist @ /tmp/vim-config
        |vim-config| (git)  Cloning.
        |vim-config| (git)  git clone --progress https://www.github.com/tony/vim-config /tmp/vim-config
        Cloning into '/tmp/vim-config'...
        Checking connectivity... done.
        |vim-config| (git)  git fetch
        |vim-config| (git)  git pull
        Already up-to-date.
    """

    def __new__(cls, url, **kwargs):

        if url.startswith('git+'):
            if 'vcs' not in kwargs:
                kwargs['vcs'] = 'git'
            return GitRepo(url, **kwargs)
        if url.startswith('hg+'):
            if 'vcs' not in kwargs:
                kwargs['vcs'] = 'hg'
            return MercurialRepo(url, **kwargs)
        if url.startswith('svn+'):
            if 'vcs' not in kwargs:
                kwargs['vcs'] = 'svn'
            return SubversionRepo(url, **kwargs)
        else:
            raise Exception(
                'repo URL %s requires a vcs scheme. Prepend hg+,'
                ' git+, svn+ to the repo URL. Examples:\n'
                '\t %s\n'
                '\t %s\n'
                '\t %s\n' % (
                    url,
                    'git+https://github.com/freebsd/freebsd.git',
                    'hg+https://bitbucket.org/birkenfeld/sphinx',
                    'svn+http://svn.code.sf.net/p/docutils/code/trunk'
                )
            )
