# -*- coding: utf-8 -*-
"""CLI utilities for vcspull.

vcspull.cli
~~~~~~~~~~~

"""

from __future__ import absolute_import, division, print_function, \
    with_statement, unicode_literals

import os
import sys
import collections
import fnmatch
import glob
import logging
import re

import argparse
import kaptan
import argcomplete

from ._compat import string_types
from .util import expand_config, get_repos
from .log import DebugLogFormatter
from .repo import Repo

log = logging.getLogger(__name__)

VERSIONFILE = os.path.join(
    os.path.abspath(os.path.dirname(__file__)), '__init__.py'
)
verstrline = open(VERSIONFILE, "rt").read()
VSRE = r"^__version__ = ['\"]([^'\"]*)['\"]"
mo = re.search(VSRE, verstrline, re.M)
if mo:
    __version__ = mo.group(1)

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
        dest='config',
        type=str,
        nargs='?',
        help='Pull the latest repositories from config(s)'
    ).completer = ConfigFileCompleter(
        allowednames=('.yaml', '.json'), directories=False
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
    if not args.config or args.config == ['*']:
        yaml_config = os.path.expanduser('~/.vcspull.yaml')
        has_yaml_config = os.path.exists(yaml_config)
        json_config = os.path.expanduser('~/.vcspull.json')
        has_json_config = os.path.exists(json_config)
        if not has_yaml_config and not has_json_config:
            log.fatal(
                'No config file found. Create a .vcspull.{yaml,conf}'
                ' in your $HOME directory. http://vcspull.rtfd.org for a'
                ' quickstart.'
            )
        else:
            if sum(filter(None, [has_json_config, has_yaml_config])) > int(1):
                sys.exit(
                    'multiple configs found in home directory use only one.'
                    ' .yaml, .json.'
                )
            elif has_yaml_config:
                config_file = yaml_config
            elif has_json_config:
                config_file = json_config

            config = kaptan.Kaptan()
            config.import_config(config_file)

            logging.debug('%r' % config.get())
            logging.debug('%r' % expand_config(config.get()))
            logging.debug('%r' % get_repos(expand_config(config.get())))

            for repo_dict in get_repos(expand_config(config.get())):
                r = Repo(repo_dict)
                log.debug('%s' % r)
                r.update_repo()


class ConfigFileCompleter(argcomplete.completers.FilesCompleter):

    """argcomplete completer for vcspull files."""

    def __call__(self, prefix, **kwargs):

        completion = argcomplete.completers.FilesCompleter.__call__(
            self, prefix, **kwargs
        )

        completion += [os.path.join(config_dir, c)
                       for c in in_dir(config_dir)]

        return completion


def in_dir(
    config_dir=os.path.expanduser('~/.vcspull'),
    extensions=['.yml', '.yaml', '.json']
):
    """Return a list of configs in ``config_dir``.

    :param config_dir: directory to search
    :type config_dir: string
    :param extensions: filetypes to check (e.g. ``['.yaml', '.json']``).
    :type extensions: list
    :rtype: list

    """
    configs = []

    for filename in os.listdir(config_dir):
        if is_config_file(filename, extensions) and \
           not filename.startswith('.'):
            configs.append(filename)

    return configs


def is_config_file(filename, extensions=['.yml', '.yaml', '.json']):
    """Return True if file has a valid config file type.

    :param filename: filename to check (e.g. ``mysession.json``).
    :type filename: string
    :param extensions: filetypes to check (e.g. ``['.yaml', '.json']``).
    :type extensions: list or string
    :rtype: bool

    """

    extensions = [extensions] if isinstance(
        extensions, string_types) else extensions
    return any(filename.endswith(e) for e in extensions)


def find_configs(
    path=['~/.vcspull'],
    match=['*'],
    filetype=['json', 'yaml'],

):
    """Return repos from a directory and match. Not recursive.

    :param path: list of paths to search
    :type path: list
    :param match:
    :param filetype:
    :raises LoadConfigRepoConflict: There are two configs that have same path
        and name with different repo urls.
    :returns: list of absolute paths to config files.
    :rtype: list

    """

    configs = []

    if isinstance(path, list):
        for p in path:
            return find_configs(p, match, filetype)
    else:
        if isinstance(match, list):
            for m in match:
                configs.extend(find_configs(path, m, filetype))
        else:
            if isinstance(filetype, list):
                for f in filetype:
                    configs.extend(find_configs(path, match, f))
            else:
                match = os.path.join(path, match)
                match += ".{filetype}".format(filetype=filetype)

                configs = glob.glob(match)

    return configs


def update(d, u):
    """Return updated dict.

    http://stackoverflow.com/a/3233356

    :param d: dict
    :type d: dict
    :param u: updated dict.
    :type u: dict
    :rtype: dict

    """

    for k, v in u.items():
        if isinstance(v, collections.Mapping):
            r = update(d.get(k, {}), v)
            d[k] = r
        else:
            d[k] = u[k]
    return d


def load_configs(configs):
    """Return repos from a directory and fnmatch. Not recursive.

    :param configs: paths to config file
    :type path: list
    :returns: expanded config dict item
    :rtype: iter(dict)

    """

    #configs = [open(f).read() for f in configs]
    configdict = {}

    for config in configs:
        fName, fExt = os.path.splitext(config)
        conf = kaptan.Kaptan(handler=fExt.lstrip('.'))
        conf.import_config(config)

        newconfigdict = expand_config(conf.export('dict'))

        if configdict:
            for path in newconfigdict:
                if path in configdict:
                    for repo_name in newconfigdict[path]:
                        if repo_name in configdict[path]:
                            if newconfigdict[path][repo_name] != configdict[path][repo_name]:
                                print('same path + repo for %s' % repo_name)
                                if newconfigdict[path][repo_name]['repo'] != configdict[path][repo_name]['repo']:
                                    msg = (
                                        'same path + repo, different vcs (%s)\n'
                                        '%s\n%s' %
                                        (
                                            repo_name,
                                            configdict[path][repo_name]['repo'],
                                            newconfigdict[path][repo_name]['repo']
                                        )
                                    )
                                    raise Exception(msg)
        configdict = update(configdict, newconfigdict)
        # configdict.update(conf.export('dict'))

    #if configs load and validate_schema, then load.
    #configs = [config for config in configs if validate_schema(config)]

    configdict = expand_config(configdict)

    return configdict


def get_repos_new(
    vcs=['git', 'svn', 'hg'],  # repo types to match
    dir=['*'],  # pattern to match
    repo_names=['*']  # repo names to fnmatch
):
    """Return Repo objects from config.

    :param configs: list of config items
    :type: list
    :param vcs:
    :type vcs: list
    :param dir:
    :type vcs: list
    :param repo_names:
    :type repo_names: list
    :returns: list of Repos from config
    :rtype: iter(:class:`Repo`)

    """
    pass


def scan_repos(
    path='~',
    subrepos=False
):
    """Return repositories within directory.

    :param path: path to search
    :type path: string
    :param subrepos: search for repos within repos
    :type subrepos: bool
    :returns: list of Repos from file system
    :rtype: iter(:class:`Repo`)

    """
    pass


def validate_schema(conf):
    """Return True if valid vcspull schema.

    :param conf: configuration
    :type conf: string
    :rtype: bool

    """

    return True
