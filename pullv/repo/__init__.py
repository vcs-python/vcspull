#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
    pullv
    ~~~~~

    :copyright: Copyright 2013 Tony Narlock.
    :license: BSD, see LICENSE for details
"""

from __future__ import absolute_import, division, print_function, with_statement
import collections
import os
import sys
import subprocess
import fnmatch
import logging
import urlparse
import re
import kaptan
from .. import util
from .. import log
from .. import timed_subprocess

from .git import GitRepo
from .hg import MercurialRepo
from .svn import SubversionRepo
from .base import BaseRepo
logger = logging.getLogger(__name__)


class Repo(object):

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

