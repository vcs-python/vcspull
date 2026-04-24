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
import os
import pathlib
import pkgutil
import sys
import tempfile
import time
import typing as t
from datetime import datetime
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


#: Format string for the debug log file. Verbose enough to trace a hang:
#: level, timestamp (to millisecond), logger, module:line, and the message.
_DEBUG_FILE_FORMAT = (
    "%(asctime)s.%(msecs)03d [%(levelname)s] %(name)s "
    "%(module)s:%(lineno)d -- %(message)s"
)

_DEBUG_FILE_DATE_FORMAT = "%Y-%m-%dT%H:%M:%S"


def default_debug_log_path() -> pathlib.Path:
    """Return the path where vcspull writes its per-invocation debug log.

    Mirrors the ``npm`` / ``pnpm`` convention of dropping a timestamped log
    file in the system temp directory on every run. The file is always created
    but its path is only surfaced to the user when something went wrong
    (failure or timeout), so clean runs stay quiet.
    """
    stamp = datetime.now().strftime("%Y%m%dT%H%M%S")
    pid = os.getpid()
    return pathlib.Path(tempfile.gettempdir()) / f"vcspull-debug-{stamp}-{pid}.log"


def setup_file_logger(
    path: pathlib.Path,
    *,
    level: int = logging.DEBUG,
) -> logging.FileHandler:
    """Attach a file handler to the ``vcspull`` and ``libvcs`` loggers.

    Unlike :func:`setup_logger`, this handler is not tied to stdout -- it
    captures the full debug trace so a post-mortem (npm/pnpm/yarn style) has
    enough context to diagnose a timeout even when the CLI output was
    aggressively summarised.

    Parameters
    ----------
    path : pathlib.Path
        Destination file. Parent directories are created as needed. An
        existing file is appended to so a single session that sets up logging
        multiple times does not clobber earlier context.
    level : int
        Threshold for the file handler. Defaults to :data:`logging.DEBUG`
        because the file is consulted only when diagnosing a failure.
    """
    path.parent.mkdir(parents=True, exist_ok=True)

    handler = logging.FileHandler(path, mode="a", encoding="utf-8")
    handler.setLevel(level)
    handler.setFormatter(
        logging.Formatter(_DEBUG_FILE_FORMAT, datefmt=_DEBUG_FILE_DATE_FORMAT),
    )

    # Attach to both loggers so libvcs's per-repo activity is captured alongside
    # vcspull's own structured events. Duplicate handlers are avoided by
    # checking the baseFilename before attaching.
    for logger_name in ("vcspull", "libvcs"):
        logger = logging.getLogger(logger_name)
        existing = next(
            (
                h
                for h in logger.handlers
                if isinstance(h, logging.FileHandler)
                and getattr(h, "baseFilename", None) == str(path)
            ),
            None,
        )
        if existing is None:
            logger.addHandler(handler)
        # Ensure the logger itself lets DEBUG records through to the handler.
        if logger.level == logging.NOTSET or logger.level > level:
            logger.setLevel(level)

    return handler


def teardown_file_logger(handler: logging.FileHandler) -> None:
    """Flush and detach ``handler`` from the vcspull/libvcs loggers."""
    try:
        handler.flush()
        handler.close()
    except ValueError:
        # Handler already closed; nothing to do.
        pass
    for logger_name in ("vcspull", "libvcs"):
        logger = logging.getLogger(logger_name)
        if handler in logger.handlers:
            logger.removeHandler(handler)
