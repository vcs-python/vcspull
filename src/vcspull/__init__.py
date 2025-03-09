#!/usr/bin/env python
"""Manage multiple git, mercurial, svn repositories from a YAML / JSON file.

:copyright: Copyright 2013-2024 Tony Narlock.
:license: MIT, see LICENSE for details
"""

# Set default logging handler to avoid "No handler found" warnings.
from __future__ import annotations

import logging
from logging import NullHandler

from . import cli
from .__about__ import __version__
from .config import load_config

logging.getLogger(__name__).addHandler(NullHandler())

__all__ = ["__version__", "cli", "load_config"]
