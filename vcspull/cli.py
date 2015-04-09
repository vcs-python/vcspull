# -*- coding: utf-8 -*-
"""CLI utilities for vcspull.

vcspull.cli
~~~~~~~~~~~

"""

from __future__ import absolute_import, division, print_function, \
    with_statement, unicode_literals

import os
import sys
import fnmatch
import glob
import logging
import re
import argparse

import kaptan
import argcomplete

from . import exc
from .__about__ import __version__
from ._compat import string_types
from .util import expand_config, get_repos, update_dict, in_dir
from .config import find_configs, load_configs
from .log import DebugLogFormatter
from .repo import Repo

log = logging.getLogger(__name__)


config_dir = os.path.expanduser('~/.vcspull/')
cwd_dir = os.getcwd() + '/'


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

    main_parser = argparse.ArgumentParser()

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


def main():
    """Main CLI application."""

    parser = get_parser()

    argcomplete.autocomplete(parser, always_complete_options=False)

    args = parser.parse_args()

    setup_logger(
        level=args.log_level.upper() if 'log_level' in args else 'INFO'
    )

    try:
        if not args.config or args.config and args.callback is command_load:
            command_load(args)
        else:
            parser.print_help()
    except KeyboardInterrupt:
        pass


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
        r = Repo(repo_dict)
        log.debug('%s' % r)
        r.update_repo()

    if len(repos) == 0:
        raise exc.NoConfigsFound(
            'No config file found. Your options are:'

            '1. Create a .vcspull.yaml or .vcspull.json in your $HOME '
            '   directory.'
            '2. Create .yaml or .json files in your $HOME/.vcspull '
            '   directory.'
            '\n'
            'Check out the documentation at http://vcspull.rtfd.org for '
            'examples.'
        )


class ConfigFileCompleter(argcomplete.completers.FilesCompleter):

    """argcomplete completer for vcspull files."""

    def __call__(self, prefix, **kwargs):

        completion = argcomplete.completers.FilesCompleter.__call__(
            self, prefix, **kwargs
        )

        completion += [os.path.join(config_dir, c)
                       for c in in_dir(config_dir)]

        return completion
