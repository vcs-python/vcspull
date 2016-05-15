# -*- coding: utf-8 -*-
"""Utility functions for vcspull.

vcspull.util
~~~~~~~~~~~~

"""

from __future__ import (
    absolute_import, division, print_function, with_statement, unicode_literals
)

import subprocess
import collections
import os
import errno
import logging
import fnmatch

from . import exc
from ._compat import string_types

logger = logging.getLogger(__name__)


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


def lookup_repos(config, dirmatch=None, vcsurlmatch=None, namematch=None):
    """Return a :py:obj:`list` list of repos from (expanded) config file.

    :param config: the expanded repo config in :py:class:`dict` format.
    :type config: dict
    :param dirmatch: array of fnmatch's for directory
    :type dirmatch: str or None
    :param vcsurlmatch: array of fnmatch's for vcs url
    :type vcsurlmatch: str or None
    :param namematch: array of fnmatch's for project name
    :type namematch: str or None
    :rtype: list
    :todo: optimize performance, tests.

    """
    repo_list = []
    for repo_data in config:
        if dirmatch and not fnmatch.fnmatch(repo_data['cwd'], dirmatch):
            continue
        if vcsurlmatch and not fnmatch.fnmatch(
            repo_data.get('url', repo_data.get('repo')),
            vcsurlmatch
        ):
            continue
        if namematch and not fnmatch.fnmatch(repo_data.get('name'), namematch):
            continue
        repo_dict = {
            'name': repo_data['name'],
            'cwd': repo_data['cwd'],
            # Work with old format of repo url key, 'repo'
            'url': repo_data.get('url', repo_data.get('repo'))
        }

        if 'remotes' in repo_data:
            repo_dict['remotes'] = []
            for remote_name, url in repo_data['remotes'].items():
                remote_dict = {
                    'remote_name': remote_name,
                    'url': repo_data['url']
                }
                repo_dict['remotes'].append(remote_dict)
        repo_list.append(repo_dict)
    return repo_list


def run(
    cmd,
    cwd=None,
    stdin=None,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    shell=False,
    env=(),
    timeout=None
):
    """Return output of command. Based off salt's _run."""
    ret = {}

    if isinstance(cmd, string_types):
        cmd = cmd.split(' ')
    if isinstance(cmd, list):
        cmd[0] = which(cmd[0])

    # kwargs['stdin'] = subprocess.PIPE if 'stdin' not in kwargs else
    # kwargs['stdin']

    kwargs = {
        'cwd': cwd,
        'stdin': stdin,
        'stdout': stdout,
        'stderr': stderr,
        'shell': shell,
        'env': os.environ.copy(),
    }

    try:
        proc = subprocess.Popen(cmd, **kwargs)
    except (OSError, IOError) as exc:
        raise exc.VCSPullException('Unable to run command: {0}'.format(exc))

    proc.wait()

    stdout, stderr = proc.stdout.read(), proc.stderr.read()
    proc.stdout.close()
    proc.stderr.close()

    stdout = stdout.decode().split('\n')
    ret['stdout'] = list(filter(None, stdout))  # filter empty values

    stderr = stderr.decode().split('\n')
    ret['stderr'] = list(filter(None, stderr))  # filter empty values

    ret['pid'] = proc.pid
    ret['retcode'] = proc.returncode

    return ret


def which(exe=None):
    """Return path of bin. Python clone of /usr/bin/which.

    from salt.util - https://www.github.com/saltstack/salt - license apache

    :param exe: Application to search PATHs for.
    :type exe: string
    :rtype: string

    """
    if exe:
        if os.access(exe, os.X_OK):
            return exe

        # default path based on busybox's default
        default_path = '/bin:/sbin:/usr/bin:/usr/sbin:/usr/local/bin'
        search_path = os.environ.get('PATH', default_path)

        for path in search_path.split(os.pathsep):
            full_path = os.path.join(path, exe)
            if os.access(full_path, os.X_OK):
                return full_path
        raise exc.VCSPullException(
            '{0!r} could not be found in the following search '
            'path: {1!r}'.format(
                exe, search_path
            )
        )
    logger.error('No executable was passed to be searched by which')
    return None


def mkdir_p(path):
    """Make directories recursively.

    Source: http://stackoverflow.com/a/600612

    :param path: path to create
    :type path: string

    """
    try:
        os.makedirs(path)
    except OSError as exc:  # Python >2.5
        if exc.errno == errno.EEXIST and os.path.isdir(path):
            pass
        else:
            raise


def update_dict(d, u):
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
            r = update_dict(d.get(k, {}), v)
            d[k] = r
        else:
            d[k] = u[k]
    return d


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
