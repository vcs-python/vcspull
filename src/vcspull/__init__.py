#!/usr/bin/env python
"""Manage multiple git, mercurial, svn repositories from a YAML / JSON file.

:copyright: Copyright 2013-2018 Tony Narlock.
:license: MIT, see LICENSE for details
"""

# Set default logging handler to avoid "No handler found" warnings.
from __future__ import annotations

import logging
from logging import NullHandler

from . import cli
from .url import enable_ssh_style_url_detection  # Import custom URL handling

logging.getLogger(__name__).addHandler(NullHandler())
