#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Manage multiple git, mercurial, svn repositories from a YAML / JSON file.

vcspull
~~~~~~~

:copyright: Copyright 2013-2015 Tony Narlock.
:license: BSD, see LICENSE for details

"""

from __future__ import absolute_import, print_function, unicode_literals

# Set default logging handler to avoid "No handler found" warnings.
import logging
from logging import NullHandler

logging.getLogger(__name__).addHandler(NullHandler())
