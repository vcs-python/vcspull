# -*- coding: utf-8 -*-
"""Utility functions for pullv.

pullv.util
~~~~~~~~~~

:copyright: Copyright 2013 Tony Narlock.
:license: BSD, see LICENSE for details

"""

from __future__ import absolute_import, division, print_function, with_statement
import subprocess
import os
import sys
import errno
import logging
import fnmatch
from .exc import PullvException

PY2 = sys.version_info[0] == 2

logger = logging.getLogger(__name__)

# http://www.rfk.id.au/blog/entry/preparing-pyenchant-for-python-3/
try:
    unicode = unicode
except NameError:
    # 'unicode' is undefined, must be Python 3
    str = str
    unicode = str
    bytes = bytes
    basestring = (str, bytes)
else:
    # 'unicode' exists, must be Python 2
    str = str
    unicode = unicode
    bytes = str
    basestring = basestring


if not PY2:
    input = input
    from string import ascii_lowercase
else:
    input = raw_input
    from string import lower as ascii_lowercase


def expand_config(config):
    """Return expanded configuration.

    end-user configuration permit inline configuration shortcuts, expand to
    identical format for parsing.

    :param config: the repo config in :py:class:`dict` format.
    :type config: dict
    :rtype: dict

    """
    for directory, repos in config.iteritems():
        for repo, repo_data in repos.iteritems():

            '''
            repo_name: http://myrepo.com/repo.git

            to

            repo_name: { repo: 'http://myrepo.com/repo.git' }

            also assures the repo is a :py:class:`dict`.
            '''

            if isinstance(repo_data, basestring):
                config[directory][repo] = {'repo': repo_data}

            '''
            ``shell_command_after``: if str, turn to list.
            '''
            if 'shell_command_after' in repo_data:
                if isinstance(repo_data['shell_command_after'], basestring):
                    repo_data['shell_command_after'] = [
                        repo_data['shell_command_after']
                    ]

    config = dict(
        (os.path.expandvars(directory), repo_data) for directory, repo_data in config.iteritems()
    )

    config = dict(
        (os.path.expanduser(directory), repo_data) for directory, repo_data in config.iteritems()
    )

    return config


def get_repos(config):
    """Return a :py:obj:`list` list of repos from (expanded) config file.

    :param config: the expanded repo config in :py:class:`dict` format.
    :type config: dict
    :rtype: list

    """
    repo_list = []
    for directory, repos in config.iteritems():
        for repo, repo_data in repos.iteritems():
            repo_dict = {
                'name': repo,
                'parent_path': directory,
                'url': repo_data['repo'],
            }

            if 'remotes' in repo_data:
                repo_dict['remotes'] = []
                for remote_name, url in repo_data['remotes'].iteritems():
                    remote_dict = {
                        'remote_name': remote_name,
                        'url': url
                    }
                    repo_dict['remotes'].append(remote_dict)
            repo_list.append(repo_dict)
    return repo_list


def scan(dir):
    """Return a list of repositories."""
    matches = []
    for root, dirnames, filenames in os.walk(dir):
        for filename in fnmatch.filter(filenames, '.git'):
            matches.append(os.path.join(root, filename))


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

    if isinstance(cmd, basestring):
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
        raise PullvException('Unable to run command: {0}'.format(exc))

    proc.wait()

    out, err = proc.stdout.read(), proc.stderr.read()

    ret['stdout'] = out
    ret['stderr'] = err
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
        raise PullvException(
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
