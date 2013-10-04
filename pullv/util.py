#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
    pullv
    ~~~~~

    :copyright: Copyright 2013 Tony Narlock.
    :license: BSD, see LICENSE for details
"""

from __future__ import absolute_import, division, print_function, with_statement
import subprocess
import os
import logging
logger = logging.getLogger(__name__)

from . import timed_subprocess


def expand_config(config):
    '''Expand configuration into full form.

    end-user configuration permit inline configuration shortcuts, expand to
    identical format for parsing.

    :param config: the repo config in :py:class:`dict` format.
    :type config: dict
    '''
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
                        repo_data['shell_command_after']]

    return config


def get_repos(config):
    """ return a :py:obj:`list` list of repos from (expanded) config file.

    :param config: the expanded repo config in :py:class:`dict` format.
    :type config: dict
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
    matches = []
    for root, dirnames, filenames in os.walk(dir):
        for filename in fnmatch.filter(filenames, '.git'):
            matches.append(os.path.join(root, filename))


def _run(cmd,
         cwd=None,
         stdin=None,
         stdout=subprocess.PIPE,
         stderr=subprocess.PIPE,
         shell=False,
         env=(),
         timeout=None):
    ''' based off salt's _run '''
    ret = {}

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
        proc = timed_subprocess.TimedProc(cmd, **kwargs)
    except (OSError, IOError) as exc:
        raise Error('Unable to urn command: {0}'.format(exc))

    try:
        proc.wait(timeout)
    except timed_subprocess.TimedProcTimeoutError as exc:
        ret['stdout'] = str(exc)
        ret['stderr'] = ''
        ret['pid'] = proc.process.pid
        ret['retcode'] = 1
        return ret

    out, err = proc.stdout, proc.stderr

    ret['stdout'] = out
    ret['stderr'] = err
    ret['pid'] = proc.process.pid
    ret['retcode'] = proc.process.returncode

    return ret
