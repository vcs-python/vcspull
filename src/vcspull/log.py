"""Log utilities for formatting CLI output in vcspull.

This module containers special formatters for processing the additional context
information from :class:`libvcs.base.RepoLoggingAdapter`.

Colorized formatters for generic logging inside the application is also
provided.
"""

from __future__ import annotations

import contextlib
import importlib
import logging
import pkgutil
import sys
import time
import typing as t
from functools import lru_cache

from colorama import Fore, Style

LEVEL_COLORS = {
    "DEBUG": Fore.BLUE,  # Blue
    "INFO": Fore.GREEN,  # Green
    "WARNING": Fore.YELLOW,
    "ERROR": Fore.RED,
    "CRITICAL": Fore.RED,
}


@lru_cache(maxsize=1)
def get_cli_logger_names(include_self: bool = True) -> list[str]:
    """Return logger names under ``vcspull.cli``."""
    names: set[str] = set()
    exclude = {"vcspull.cli._formatter"}
    cli_module = importlib.import_module("vcspull.cli")
    if include_self:
        names.add(cli_module.__name__)

    if hasattr(cli_module, "__path__"):
        for module_info in pkgutil.walk_packages(
            cli_module.__path__,
            prefix="vcspull.cli.",
        ):
            if module_info.name in exclude:
                continue
            names.add(module_info.name)

    return sorted(names)


def setup_logger(
    log: logging.Logger | None = None,
    level: t.Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO",
) -> None:
    """Configure the vcspull logging hierarchy once and reuse it everywhere."""
    resolved_level = getattr(logging, level.upper(), logging.INFO)

    vcspull_logger = logging.getLogger("vcspull")

    # ``vcspull`` installs a NullHandler at import time so library consumers don't
    # see "No handler could be found" warnings.  When running the CLI we need a
    # real stream handler though, so treat a NullHandler-only configuration the
    # same as "no handlers" and replace it with our formatter-aware handler.
    existing_handlers = [
        handler
        for handler in vcspull_logger.handlers
        if not isinstance(handler, logging.NullHandler)
    ]
    if not existing_handlers:
        for handler in list(vcspull_logger.handlers):
            vcs_handler_is_null = isinstance(handler, logging.NullHandler)
            if vcs_handler_is_null:
                vcspull_logger.removeHandler(handler)
        stream_handler = logging.StreamHandler()
        stream_handler.stream = sys.stdout
        if resolved_level <= logging.DEBUG:
            stream_handler.setFormatter(DebugLogFormatter())
        else:
            stream_handler.setFormatter(SimpleLogFormatter())
        vcspull_logger.addHandler(stream_handler)
        existing_handlers = [stream_handler]
    else:
        # Update formatter to match requested verbosity
        formatter: logging.Formatter
        formatter = (
            DebugLogFormatter()
            if resolved_level <= logging.DEBUG
            else SimpleLogFormatter()
        )
        for handler in existing_handlers:
            if isinstance(handler, logging.StreamHandler):
                with contextlib.suppress(ValueError):
                    handler.flush()
                handler.stream = sys.stdout
            handler.setFormatter(formatter)

    vcspull_logger.setLevel(resolved_level)
    vcspull_logger.propagate = True

    # Ensure CLI modules bubble up to the main vcspull logger instead of
    # attaching their own handlers, which keeps output centralized and
    # prevents duplicate streams in tests.
    for logger_name in get_cli_logger_names(include_self=True):
        cli_logger = logging.getLogger(logger_name)
        for handler in list(cli_logger.handlers):
            if isinstance(handler, logging.StreamHandler) and isinstance(
                handler.formatter,
                (SimpleLogFormatter, DebugLogFormatter),
            ):
                cli_logger.removeHandler(handler)
        cli_logger.setLevel(resolved_level)
        cli_logger.propagate = True

    # Configure libvcs logger with repo formatting but keep propagation for caplog
    repo_logger = logging.getLogger("libvcs")
    if not repo_logger.handlers:
        repo_channel = logging.StreamHandler()
        repo_channel.setFormatter(RepoLogFormatter())
        repo_channel.addFilter(RepoFilter())
        repo_logger.addHandler(repo_channel)
    repo_logger.setLevel(resolved_level)
    repo_logger.propagate = True

    target_logger = log or vcspull_logger
    target_logger.setLevel(resolved_level)
    target_logger.propagate = True

    # Keep root logger at least aware of the desired level for debugging tools
    root_logger = logging.getLogger()
    if not root_logger.handlers:
        root_logger.setLevel(resolved_level)


class LogFormatter(logging.Formatter):
    """Log formatting for vcspull."""

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

        return "".join(reset + levelname + asctime + name + reset)

    def __init__(self, color: bool = True, **kwargs: t.Any) -> None:
        logging.Formatter.__init__(self, **kwargs)

    def format(self, record: logging.LogRecord) -> str:
        """Format log record."""
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

        return "".join(
            reset + levelname + asctime + name + module_funcName + lineno + reset,
        )


class RepoLogFormatter(LogFormatter):
    """Log message for VCS repository."""

    def template(self, record: logging.LogRecord) -> str:
        """Template for logging vcs bin name, along with a contextual hint."""
        record.message = (
            f"{Fore.MAGENTA}{Style.BRIGHT}{record.message}{Fore.RESET}{Style.RESET_ALL}"
        )
        return f"{Fore.GREEN + Style.DIM}|{record.bin_name}| {Fore.YELLOW}({record.keyword}) {Fore.RESET}"  # type:ignore # noqa: E501


class SimpleLogFormatter(logging.Formatter):
    """Simple formatter that outputs only the message, like print()."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record to just return the message."""
        return record.getMessage()


class RepoFilter(logging.Filter):
    """Only include repo logs for this type of record."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Only return a record if a keyword object."""
        return "keyword" in record.__dict__
