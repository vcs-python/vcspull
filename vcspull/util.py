# -*- coding: utf-8 -*-
"""Utility functions for vcspull.

vcspull.util
~~~~~~~~~~~~

"""
from __future__ import absolute_import, print_function, unicode_literals

import collections
import errno
import logging
import os
import re
import subprocess

from . import exc
from ._compat import PY2, console_to_str, string_types

CONFIG_DIR = os.path.expanduser('~/.vcspull/')  # remove dupes of this

logger = logging.getLogger(__name__)


def remove_tracebacks(output):
    pattern = (r'(?:\W+File "(?:.*)", line (?:.*)\W+(?:.*)\W+\^\W+)?'
               r'Syntax(?:Error|Warning): (?:.*)')
    output = re.sub(pattern, '', output)
    if PY2:
        return output
    # compileall.compile_dir() prints different messages to stdout
    # in Python 3
    return re.sub(r"\*\*\* Error compiling (?:.*)", '', output)


def run(
    cmd,
    cwd=None,
    stdin=None,
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    shell=False,
    env=os.environ.copy(),
    timeout=None
):
    """Run command and return output.

    :returns: combined stdout/stderr in a big string, \n's retained
    :rtype: str
    """
    if isinstance(cmd, string_types):
        cmd = cmd.split(' ')
    if isinstance(cmd, list):
        cmd[0] = which(cmd[0])

    try:
        process = subprocess.Popen(
            cmd,
            stdout=stdout,
            stderr=stderr,
            env=env, cwd=cwd
        )
    except (OSError, IOError) as e:
        raise exc.VCSPullException('Unable to run command: %s' % e)

    process.wait()
    all_output = []
    while True:
        line = console_to_str(process.stdout.readline())
        if not line:
            break
        line = line.rstrip()
        all_output.append(line + '\n')
    all_output = ''.join(all_output)

    if process.returncode:
        logging.error(all_output)
        raise exc.VCSPullSubprocessException(
            returncode=process.returncode,
            cmd=cmd,
            output=all_output,
        )

    return remove_tracebacks(all_output).rstrip()


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
