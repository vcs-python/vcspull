#!/usr/bin/env python
"""Manage multiple git, mercurial, svn repositories from a YAML / JSON file.

:copyright: Copyright 2013-2024 Tony Narlock.
:license: MIT, see LICENSE for details
"""

# Set default logging handler to avoid "No handler found" warnings.
from __future__ import annotations

import logging
import typing as t
from logging import NullHandler

# Import CLI entrypoints
from . import cli
from .__about__ import __author__, __description__, __version__
from .config import load_config, resolve_includes
from .operations import detect_repositories, sync_repositories

logging.getLogger(__name__).addHandler(NullHandler())

__all__ = [
    "__author__",
    "__description__",
    "__version__",
    "detect_repositories",
    "load_config",
    "resolve_includes",
    "sync_repositories",
]
