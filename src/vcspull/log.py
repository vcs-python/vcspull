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
import typing as t

from colorama import Fore, Style

LEVEL_COLORS = {
    "DEBUG": Fore.BLUE,  # Blue
    "INFO": Fore.GREEN,  # Green
    "WARNING": Fore.YELLOW,
    "ERROR": Fore.RED,
    "CRITICAL": Fore.RED,
}


def setup_logger(
    log: t.Optional[logging.Logger] = None,
    level: t.Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO",
) -> None:
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


class LogFormatter(logging.Formatter):
    def template(self, record: logging.LogRecord) -> str:
        """Return the prefix for the log message. Template for Formatter.

        Parameters
        ----------
        record : :py:class:`logging.LogRecord`
            Passed in from inside the :py:meth:`logging.Formatter.format` record.
        """
        reset = [Style.RESET_ALL]
        levelname = [
            LEVEL_COLORS.get(record.levelname, ""),
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

    def __init__(self, color: bool = True, **kwargs: t.Any) -> None:
        logging.Formatter.__init__(self, **kwargs)

    def format(self, record: logging.LogRecord) -> str:
        try:
            record.message = record.getMessage()
        except Exception as e:
            record.message = f"Bad message ({e!r}): {record.__dict__!r}"

        date_format = "%H:%m:%S"
        formatting = self.converter(record.created)
        record.asctime = time.strftime(date_format, formatting)
        prefix = self.template(record) % record.__dict__

        formatted = prefix + " " + record.message
        return formatted.replace("\n", "\n    ")


class DebugLogFormatter(LogFormatter):
    """Provides greater technical details than standard log Formatter."""

    def template(self, record: logging.LogRecord) -> str:
        """Return the prefix for the log message. Template for Formatter.

        Parameters
        ----------
        record : :class:`logging.LogRecord`
            Passed from inside the :py:meth:`logging.Formatter.format` record.
        """

        reset = [Style.RESET_ALL]
        levelname = [
            LEVEL_COLORS.get(record.levelname, ""),
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

        tpl = "".join(
            reset + levelname + asctime + name + module_funcName + lineno + reset
        )

        return tpl


class RepoLogFormatter(LogFormatter):
    def template(self, record: logging.LogRecord) -> str:
        record.message = "".join(
            [Fore.MAGENTA, Style.BRIGHT, record.message, Fore.RESET, Style.RESET_ALL]
        )
        return "{}|{}| {}({}) {}".format(
            Fore.GREEN + Style.DIM,
            record.bin_name,  # type:ignore
            Fore.YELLOW,
            record.keyword,  # type:ignore
            Fore.RESET,
        )


class RepoFilter(logging.Filter):
    """Only include repo logs for this type of record."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Only return a record if a keyword object."""
        return "keyword" in record.__dict__
