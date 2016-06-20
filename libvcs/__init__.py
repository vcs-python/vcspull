# -*- coding: utf-8 -*-
"""Repo package for vcspull.

libvcs
~~~~~~

"""
from __future__ import absolute_import, print_function, unicode_literals

import logging

from .base import BaseRepo, RepoLoggingAdapter
from .git import GitRepo
from .hg import MercurialRepo
from .log import RepoFilter, RepoLogFormatter
from .svn import SubversionRepo

__all__ = ['GitRepo', 'MercurialRepo', 'SubversionRepo', 'BaseRepo',
           'RepoLoggingAdapter']

logger = logging.getLogger(__name__)

logger.propagate = False
channel = logging.StreamHandler()
channel.setFormatter(RepoLogFormatter())
channel.addFilter(RepoFilter())
logger.setLevel('INFO')
logger.addHandler(channel)
