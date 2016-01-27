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

from . import exc
from .__about__ import __version__
from .util import get_repos, in_dir
from .config import find_configs, load_configs
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


def get_parser():
    """Return :py:class:`argparse.ArgumentParser` instance for CLI."""
    main_parser.add_argument(
        '-c', '--config',
        dest='config',
        type=str,
        nargs='?',
        help='Pull the latest repositories from config(s)'
    ).completer = ConfigFileCompleter(
        allowednames=('.yaml', '.json'), directories=False
    )

    main_parser.add_argument(
        '-d', '--dirmatch',
        dest='dirmatch',
        type=str,
        nargs='?',
        help='Pull only from the directories. Accepts fnmatch(1)'
             'by commands'
    )

    main_parser.add_argument(
        '-r', '--repomatch',
        dest='repomatch',
        type=str,
        nargs='?',
        help='Pull only from the repository urls. Accepts fnmatch(1)'
    )

    main_parser.add_argument(
        dest='namematch',
        type=str,
        nargs='?',
        help='Pull only from project name. Accepts fnmatch(1)'
    )

    main_parser.set_defaults(callback=command_load)

    main_parser.add_argument(
        '-v', '--version', action='version',
        version='vcspull %s' % __version__,
        help='Prints the vcspull version',
    )

    return main_parser


@click.command()
@click.option('--log_level', default='INFO', help='log level you want')
@click.argument('repos', nargs=-1)
def cli(log_level, repos):
    setup_logger(
        level=log_level.upper()
    )
    configs = find_configs(include_home=True)
    configs = load_configs(configs)
    for repo in repos:
        dirmatch, repomatch = None, None
        if any(repo.startswith(n) for n in ['./', '/', '~', '$HOME']):
            dirmatch = repo
            repo = None
        elif any(repo.startswith(n) for n in ['http', 'git', 'svn']):
            dirmatch = repo
            repo = None

        repos = get_repos(
            configs,
            dirmatch=None,
            repomatch=None,
            namematch=repo
        )
        for repo_dict in repos:
            r = create_repo(**repo_dict)
            log.debug('%s' % r)
            r.update_repo()

def command_load(args):
    """Load YAML and JSON configs and begin creating / updating repos."""
    if not args.config or args.config == ['*']:
        configs = find_configs(include_home=True)
    else:
        configs = [args.config]

    configs = load_configs(configs)
    repos = get_repos(
        configs,
        dirmatch=args.dirmatch,
        repomatch=args.repomatch,
        namematch=args.namematch
    )

    for repo_dict in repos:
        r = create_repo(**repo_dict)
        log.debug('%s' % r)
        r.update_repo()

    if len(repos) == 0:
        raise exc.NoConfigsFound(NO_REPOS_FOUND)


class ConfigFileCompleter(object):

    """argcomplete completer for vcspull files."""

    def __call__(self, prefix, **kwargs):

        completion = argcomplete.completers.FilesCompleter.__call__(
            self, prefix, **kwargs
        )

        completion += [os.path.join(config_dir, c)
                       for c in in_dir(config_dir)]

        return completion
