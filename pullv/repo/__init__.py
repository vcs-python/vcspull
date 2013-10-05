#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
    pullv
    ~~~~~

    :copyright: Copyright 2013 Tony Narlock.
    :license: BSD, see LICENSE for details
"""

from __future__ import absolute_import, division, print_function, with_statement
import os
import logging

from .. import util
from .. import log
from .. import timed_subprocess

from .git import GitRepo
from .hg import MercurialRepo
from .svn import SubversionRepo
from .base import BaseRepo

logger = logging.getLogger()
from ..log import RepoLogFormatter

logger.propagate = False
channel = logging.StreamHandler()
channel.setFormatter(RepoLogFormatter())
logger.setLevel('INFO')
logger.addHandler(channel)


class Repo(object):

    """ Returns an instance of :class:`SubversionRepo`, :class:`GitRepo` or
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
            raise Exception('no scheme in repo URL found (hg+, git+, svn+. Prepend this'
                            ' to the repo\'s URL')
