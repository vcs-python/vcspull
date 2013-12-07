# -*- coding: utf-8 -*-
"""Repo package for vcspull.

vcspull.repo
~~~~~~~~~~~~

:copyright: Copyright 2013 Tony Narlock.
:license: BSD, see LICENSE for details

"""

from __future__ import absolute_import, division, print_function, with_statement
import os
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

    Return instance of :class:`SubversionRepo`, :class:`GitRepo` or
    :class:`MercurialRepo`. The object returned is a child of :class:`BaseRepo`.

    For external API purposes.

    """

    def __new__(cls, attributes, *args, **kwargs):
        vcs_url = attributes['url']

        if vcs_url.startswith('git+'):
            attributes['vcs'] = 'git'
            return GitRepo(attributes, *args, **kwargs)
        if vcs_url.startswith('hg+'):
            attributes['vcs'] = 'hg'
            return MercurialRepo(attributes, *args, **kwargs)
        if vcs_url.startswith('svn+'):
            attributes['vcs'] = 'svn'
            return SubversionRepo(attributes, *args, **kwargs)
        else:
            raise Exception(
                'repo URL %s requires a vcs scheme. Prepend hg+,'
                ' git+, svn+ to the repo URL. Examples:\n'
                '\t %s\n'
                '\t %s\n'
                '\t %s\n' % (
                    attributes['url'],
                    'git+https://github.com/freebsd/freebsd.git',
                    'hg+https://bitbucket.org/birkenfeld/sphinx',
                    'svn+http://svn.code.sf.net/p/docutils/code/trunk'
                )
            )
