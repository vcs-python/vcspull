"""Log utilities for formatting CLI output.

vcspull.log
~~~~~~~~~~~

This module containers special formatters for processing the additional context
information from :class:`libvcs.base.RepoLoggingAdapter`.

Colorized formatters for generic logging inside the application is also
provided.

"""
import logging
import time

from colorama import Fore, Style

LEVEL_COLORS = {
    "DEBUG": Fore.BLUE,  # Blue
    "INFO": Fore.GREEN,  # Green
    "WARNING": Fore.YELLOW,
    "ERROR": Fore.RED,
    "CRITICAL": Fore.RED,
}


def setup_logger(log=None, level="INFO"):
    """Setup logging for CLI use.

    Parameters
    ----------
    log : :py:class:`logging.Logger`
        instance of logger
    """
    if not log:
        log = logging.getLogger()
    if not log.handlers:
        channel = logging.StreamHandler()
        channel.setFormatter(DebugLogFormatter())

        log.setLevel(level)
        log.addHandler(channel)

        # setup styling for repo loggers
        repo_logger = logging.getLogger("libvcs")
        channel = logging.StreamHandler()
        channel.setFormatter(RepoLogFormatter())
        channel.addFilter(RepoFilter())
        repo_logger.setLevel(level)
        repo_logger.addHandler(channel)


def default_log_template(self, record):
    """Return the prefix for the log message. Template for Formatter.

    Parameters
    ----------
    record : :py:class:`logging.LogRecord`
        This is passed in from inside the :py:meth:`logging.Formatter.format` record.
    """
    reset = [Style.RESET_ALL]
    levelname = [
        LEVEL_COLORS.get(record.levelname),
        Style.BRIGHT,
        "(%(levelname)s)",
        Style.RESET_ALL,
        " ",
    ]
    asctime = [
        "[",
        Fore.BLACK,
        Style.DIM,
        Style.BRIGHT,
        "%(asctime)s",
        Fore.RESET,
        Style.RESET_ALL,
        "]",
    ]
    name = [
        " ",
        Fore.WHITE,
        Style.DIM,
        Style.BRIGHT,
        "%(name)s",
        Fore.RESET,
        Style.RESET_ALL,
        " ",
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
            record.message = f"Bad message ({e!r}): {record.__dict__!r}"

        date_format = "%H:%m:%S"
        record.asctime = time.strftime(date_format, self.converter(record.created))

        prefix = self.template(record) % record.__dict__

        formatted = prefix + " " + record.message
        return formatted.replace("\n", "\n    ")


def debug_log_template(self, record):
    """Return the prefix for the log message. Template for Formatter.

    Parameters
    ----------
    record : :class:`logging.LogRecord`
        This is passed in from inside the :py:meth:`logging.Formatter.format` record.
    """

    reset = [Style.RESET_ALL]
    levelname = [
        LEVEL_COLORS.get(record.levelname),
        Style.BRIGHT,
        "(%(levelname)1.1s)",
        Style.RESET_ALL,
        " ",
    ]
    asctime = [
        "[",
        Fore.BLACK,
        Style.DIM,
        Style.BRIGHT,
        "%(asctime)s",
        Fore.RESET,
        Style.RESET_ALL,
        "]",
    ]
    name = [
        " ",
        Fore.WHITE,
        Style.DIM,
        Style.BRIGHT,
        "%(name)s",
        Fore.RESET,
        Style.RESET_ALL,
        " ",
    ]
    module_funcName = [Fore.GREEN, Style.BRIGHT, "%(module)s.%(funcName)s()"]
    lineno = [
        Fore.BLACK,
        Style.DIM,
        Style.BRIGHT,
        ":",
        Style.RESET_ALL,
        Fore.CYAN,
        "%(lineno)d",
    ]

    tpl = "".join(reset + levelname + asctime + name + module_funcName + lineno + reset)

    return tpl


class DebugLogFormatter(LogFormatter):
    """Provides greater technical details than standard log Formatter."""

    template = debug_log_template


class RepoLogFormatter(LogFormatter):
    def template(self, record):
        record.message = "".join(
            [Fore.MAGENTA, Style.BRIGHT, record.message, Fore.RESET, Style.RESET_ALL]
        )
        return "{}|{}| {}({}) {}".format(
            Fore.GREEN + Style.DIM,
            record.bin_name,
            Fore.YELLOW,
            record.keyword,
            Fore.RESET,
        )


class RepoFilter(logging.Filter):
    """Only include repo logs for this type of record."""

    def filter(self, record):
        """Only return a record if a keyword object."""
        return True if "keyword" in record.__dict__ else False
