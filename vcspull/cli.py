# -*- coding: utf-8 -*-
"""CLI utilities for vcspull.

vcspull.cli
~~~~~~~~~~~

"""

from __future__ import absolute_import, division, print_function, \
    with_statement

import os
import logging

import click

from .__about__ import __version__
from .util import get_repos
from .config import find_config_files, load_configs
from .log import DebugLogFormatter
from .repo import create_repo

log = logging.getLogger(__name__)

NO_REPOS_FOUND = """
    No repositories found.

    Check out the documentation at http://vcspull.rtfd.org for
    examples.
"""

config_dir = os.path.expanduser('~/.vcspull/')


def setup_logger(log=None, level='INFO'):
    """Setup logging for CLI use.

    :param log: instance of logger
    :type log: :py:class:`Logger`

    """
    if not log:
        log = logging.getLogger()
    if not log.handlers:
        channel = logging.StreamHandler()
        channel.setFormatter(DebugLogFormatter())

        log.setLevel(level)
        log.addHandler(channel)


@click.command()
@click.option('--log_level', default='INFO',
              help='Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)')
@click.option('--version', is_flag=True, help='Print version info')
@click.argument('repos', nargs=-1)
def cli(log_level, repos, version):
    setup_logger(
        level=log_level.upper()
    )

    if version:
        print('vcspull %s' % __version__)
        return

    configs = load_configs(find_config_files(include_home=True))
    for repo in repos:
        dirmatch, vcsurlmatch = None, None
        if any(repo.startswith(n) for n in ['./', '/', '~', '$HOME']):
            dirmatch = repo
            repo = None
        elif any(repo.startswith(n) for n in ['http', 'git', 'svn']):
            vcsurlmatch = repo
            repo = None

        repos = get_repos(
            configs,
            dirmatch=dirmatch,
            vcsurlmatch=vcsurlmatch,
            namematch=repo
        )
        for repo_dict in repos:
            r = create_repo(**repo_dict)
            log.debug('%s' % r)
            r.update_repo()
