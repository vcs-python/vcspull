#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Manage multiple git, mercurial, svn repositories from a YAML / JSON file.

vcspull
~~~~~~~

:copyright: Copyright 2013 Tony Narlock.
:license: BSD, see LICENSE for details

"""

from __future__ import absolute_import, division, print_function, with_statement

__version__ = '0.0.5'

from .util import expand_config, get_repos, mkdir_p, run, scan, which
from .log import LogFormatter, DebugLogFormatter, RepoLogFormatter
from .cli import ConfigFileCompleter, command_load, find_configs, get_parser, \
    get_repos_new, in_dir, is_config_file, load_configs, main, scan_repos, \
    setup_logger, update, validate_schema
