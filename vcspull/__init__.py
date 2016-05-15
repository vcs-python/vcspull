#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Manage multiple git, mercurial, svn repositories from a YAML / JSON file.

vcspull
~~~~~~~

:copyright: Copyright 2013-2015 Tony Narlock.
:license: BSD, see LICENSE for details

"""

from __future__ import (
    absolute_import, division, print_function, with_statement, unicode_literals
)

from .util import (
    lookup_repos, mkdir_p, run, which, update_dict, in_dir
)
from .log import (
    LogFormatter, DebugLogFormatter, RepoLogFormatter, RepoFilter
)
from .cli import (
    setup_logger
)
from .config import (
    is_config_file, load_configs, expand_config
)

# Set default logging handler to avoid "No handler found" warnings.
import logging
try:  # Python 2.7+
    from logging import NullHandler
except ImportError:
    class NullHandler(logging.Handler):
        def emit(self, record):
            pass

logging.getLogger(__name__).addHandler(NullHandler())
