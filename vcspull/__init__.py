#!/usr/bin/env python
"""Manage multiple git, mercurial, svn repositories from a YAML / JSON file.

vcspull
~~~~~~~

:copyright: Copyright 2013-2018 Tony Narlock.
:license: MIT, see LICENSE for details

"""
# Set default logging handler to avoid "No handler found" warnings.
import logging
from logging import NullHandler

from . import cli  # NOQA

logging.getLogger(__name__).addHandler(NullHandler())
