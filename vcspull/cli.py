# -*- coding: utf-8 -*-
"""CLI utilities for vcspull.

vcspull.cli
~~~~~~~~~~~

"""
from __future__ import absolute_import, print_function

import logging

import click

from libvcs.shortcuts import create_repo_from_pip_url

from .__about__ import __version__
from .cli_defaultgroup import DefaultGroup
from .config import filter_repos, find_config_files, load_configs
from .log import DebugLogFormatter, RepoLogFormatter, RepoFilter

MIN_ASYNC = 3  # minimum amount of repos to sync concurrently
MAX_ASYNC = 8  # maximum processes to open:w

log = logging.getLogger(__name__)


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

        # setup styling for repo loggers
        repo_logger = logging.getLogger('libvcs')
        channel = logging.StreamHandler()
        channel.setFormatter(RepoLogFormatter())
        channel.addFilter(RepoFilter())
        repo_logger.setLevel(level)
        repo_logger.addHandler(channel)


@click.group(cls=DefaultGroup, default_if_no_args=True)
@click.option('--log-level', default='INFO',
              help='Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)')
@click.version_option(version=__version__, message='%(prog)s %(version)s')
def cli(log_level):
    setup_logger(log=log, level=log_level.upper())


@cli.command(name='update', default=True)
@click.argument('repo_terms', nargs=-1)
@click.option('--run-async', '-a', is_flag=True,
              help='Run repo syncing concurrently (experimental)')
@click.option('--log-level', default='INFO',
              help='Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)')
@click.option('config', '-c', type=click.Path(exists=True),
              help='Specify config')
def update(repo_terms, run_async, log_level, config):
    setup_logger(log=log, level=log_level.upper())

    if config:
        configs = load_configs([config])
    else:
        configs = load_configs(find_config_files(include_home=True))
    found_repos = []

    if repo_terms:
        for repo_term in repo_terms:
            repo_dir, vcs_url, name = None, None, None
            if any(repo_term.startswith(n) for n in ['./', '/', '~', '$HOME']):
                repo_dir = repo_term
            elif any(
                repo_term.startswith(n) for n in ['http', 'git', 'svn', 'hg']
            ):
                vcs_url = repo_term
            else:
                name = repo_term

            # collect the repos from the config files
            found_repos.extend(filter_repos(
                configs,
                repo_dir=repo_dir,
                vcs_url=vcs_url,
                name=name
            ))
    else:
        found_repos = configs

    found_repos_n = len(found_repos)
    # turn them into :class:`Repo` objects and clone/update them
    if run_async and found_repos_n >= MIN_ASYNC:
        from multiprocessing import Pool
        p = Pool(clamp(found_repos_n, MIN_ASYNC, MAX_ASYNC))
        p.map_async(update_repo, found_repos).get()
    else:
        list(map(update_repo, found_repos))


def clamp(n, _min, _max):
    return max(_min, min(n, _max))


def update_repo(repo_dict):
    repo_dict['pip_url'] = repo_dict.pop('url')
    r = create_repo_from_pip_url(**repo_dict)
    log.debug('%s' % r)
    r.update_repo()

cli.add_command(update)
