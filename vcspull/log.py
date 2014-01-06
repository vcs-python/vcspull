# -*- coding: utf8 - *-
"""Log utilities for vcspull.

vcspull.log
~~~~~~~~~~~

"""

from __future__ import absolute_import, division, print_function, \
    with_statement, unicode_literals

import logging
import os
import sys
import time

from ._vendor import colorama
from ._vendor.colorama import init, Fore, Back, Style

LEVEL_COLORS = {
    'DEBUG': Fore.BLUE,  # Blue
    'INFO': Fore.GREEN,  # Green
    'WARNING': Fore.YELLOW,
    'ERROR': Fore.RED,
    'CRITICAL': Fore.RED
}


def default_log_template(self, record):
    """Return the prefix for the log message. Template for Formatter.

    :param: record: :py:class:`logging.LogRecord` object. this is passed in
    from inside the :py:meth:`logging.Formatter.format` record.

    """

    reset = Style.RESET_ALL
    levelname = [
        LEVEL_COLORS.get(record.levelname), Style.BRIGHT,
        '(%(levelname)s)',
        Style.RESET_ALL, ' '
    ]
    asctime = [
        '[', Fore.BLACK, Style.DIM, Style.BRIGHT,
        '%(asctime)s',
        Fore.RESET, Style.RESET_ALL, ']'
    ]
    name = [
        ' ', Fore.WHITE, Style.DIM, Style.BRIGHT,
        '%(name)s',
        Fore.RESET, Style.RESET_ALL, ' '
    ]

    tpl = "".join(reset + levelname + asctime + name + reset)

    return tpl


class LogFormatter(logging.Formatter):

    template = default_log_template

    def __init__(self, color=True, *args, **kwargs):
        logging.Formatter.__init__(self, *args, **kwargs)

    def format(self, record):
        try:
            record.message = record.getMessage()
        except Exception as e:
            record.message = "Bad message (%r): %r" % (e, record.__dict__)

        date_format = '%H:%m:%S'
        record.asctime = time.strftime(
            date_format, self.converter(record.created)
        )

        prefix = self.template(record) % record.__dict__

        formatted = prefix + " " + record.message
        return formatted.replace("\n", "\n    ")


def debug_log_template(self, record):
    """ Return the prefix for the log message. Template for Formatter.

    :param: record: :py:class:`logging.LogRecord` object. this is passed in
    from inside the :py:meth:`logging.Formatter.format` record.

    """

    reset = Style.RESET_ALL
    levelname = [
        LEVEL_COLORS.get(record.levelname), Style.BRIGHT,
        '(%(levelname)1.1s)',
        Style.RESET_ALL, ' '
    ]
    asctime = [
        '[', Fore.BLACK, Style.DIM, Style.BRIGHT,
        '%(asctime)s', Fore.RESET, Style.RESET_ALL, ']'
    ]
    name = [
        ' ', Fore.WHITE, Style.DIM, Style.BRIGHT,
        '%(name)s',
        Fore.RESET, Style.RESET_ALL, ' '
    ]
    module_funcName = [
        Fore.GREEN, Style.BRIGHT,
        '%(module)s.%(funcName)s()'
    ]
    lineno = [
        Fore.BLACK, Style.DIM, Style.BRIGHT, ':', Style.RESET_ALL,
        Fore.CYAN, '%(lineno)d'
    ]

    tpl = ''.join(
        reset + levelname + asctime + name + module_funcName + lineno + reset
    )

    return tpl


class DebugLogFormatter(LogFormatter):

    """Provides greater technical details than standard log Formatter."""

    template = debug_log_template


class RepoLogFormatter(LogFormatter):

    def template(self, record):
        record.message = ''.join([
            Fore.MAGENTA, Style.BRIGHT,
            record.message,
            Fore.RESET,
            Style.RESET_ALL
        ])
        return '%s|%s| %s(%s) %s' % (
            Fore.GREEN + Style.DIM,
            record.repo_name,
            Fore.YELLOW,
            record.repo_vcs,
            Fore.RESET
        )


class RepoFilter(logging.Filter):

    """Only include repo logs for this type of record."""

    def filter(self, record):
        """Only return a record if a repo_vcs object."""
        return True if 'repo_vcs' in record.__dict__ else False


# Below is MIT-code from pip/pip

def _color_wrap(*colors):
    def wrapped(inp):
        return "".join(list(colors) + [inp, colorama.Style.RESET_ALL])
    return wrapped


def should_color(consumer, environ, std=(sys.stdout, sys.stderr)):
    real_consumer = (
        consumer if not isinstance(consumer, colorama.AnsiToWin32)
                    else consumer.wrapped
    )

    # If consumer isn't stdout or stderr we shouldn't colorize it
    if real_consumer not in std:
        return False

    # If consumer is a tty we should color it
    if hasattr(real_consumer, "isatty") and real_consumer.isatty():
        return True

    # If we have an ASNI term we should color it
    if environ.get("TERM") == "ANSI":
        return True

    # If anything else we should not color it
    return False
