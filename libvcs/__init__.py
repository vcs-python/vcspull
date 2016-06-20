# -*- coding: utf-8 -*-
"""Repo package for vcspull.

vcspull.repo
~~~~~~~~~~~~

"""
from __future__ import absolute_import, print_function, unicode_literals

import logging

from .log import RepoFilter, RepoLogFormatter
from .base import BaseRepo, RepoLoggingAdapter
from .git import GitRepo
from .hg import MercurialRepo
from .svn import SubversionRepo

__all__ = ['GitRepo', 'MercurialRepo', 'SubversionRepo', 'BaseRepo',
           'RepoLoggingAdapter', 'create_repo']

logger = logging.getLogger(__name__)

logger.propagate = False
channel = logging.StreamHandler()
channel.setFormatter(RepoLogFormatter())
channel.addFilter(RepoFilter())
logger.setLevel('INFO')
logger.addHandler(channel)


def create_repo(url, **kwargs):
    r"""Return object with base class :class:`BaseRepo` depending on url.

    Return instance of :class:`vcspull.repo.svn.SubversionRepo`,
    :class:`vcspull.repo.git.GitRepo` or
    :class:`vcspull.repo.hg.MercurialRepo`.
    The object returned is a child of :class:`vcspull.repo.base.BaseRepo`.

    Usage Example::

        In [1]: from vcspull.repo import create_repo

        In [2]: r = create_repo(url='git+https://www.github.com/you/myrepo',
                    parent_dir='/tmp/',
                    name='myrepo')

        In [3]: r.update_repo()
        |myrepo| (git)  Repo directory for myrepo (git) does not exist @ \
            /tmp/myrepo
        |myrepo| (git)  Cloning.
        |myrepo| (git)  git clone --progress https://www.github.com/tony/myrepo
            /tmp/myrepo
        Cloning into '/tmp/myrepo'...
        Checking connectivity... done.
        |myrepo| (git)  git fetch
        |myrepo| (git)  git pull
        Already up-to-date.
    """
    if url.startswith('git+'):
        if 'vcs' not in kwargs:
            kwargs['vcs'] = 'git'
        return GitRepo.from_pip_url(url, **kwargs)
    if url.startswith('hg+'):
        if 'vcs' not in kwargs:
            kwargs['vcs'] = 'hg'
        return MercurialRepo.from_pip_url(url, **kwargs)
    if url.startswith('svn+'):
        if 'vcs' not in kwargs:
            kwargs['vcs'] = 'svn'
        return SubversionRepo.from_pip_url(url, **kwargs)
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
