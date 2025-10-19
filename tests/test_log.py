"""Tests for vcspull logging utilities."""

from __future__ import annotations

import logging
import typing as t

import pytest
from colorama import Fore

from vcspull.log import (
    LEVEL_COLORS,
    DebugLogFormatter,
    LogFormatter,
    RepoFilter,
    RepoLogFormatter,
    SimpleLogFormatter,
    get_cli_logger_names,
    setup_logger,
)

if t.TYPE_CHECKING:
    from _pytest.logging import LogCaptureFixture


@pytest.fixture(autouse=True)
def cleanup_loggers() -> t.Iterator[None]:
    """Clean up logger configuration after each test."""
    managed_loggers = [
        "",
        "vcspull",
        *get_cli_logger_names(include_self=True),
        "libvcs",
        "test_logger",
    ]

    for logger_name in managed_loggers:
        logger = logging.getLogger(logger_name)
        logger.handlers.clear()
        logger.setLevel(logging.NOTSET)
        logger.propagate = True

    yield

    for logger_name in managed_loggers:
        logger = logging.getLogger(logger_name)
        logger.handlers.clear()
        logger.setLevel(logging.NOTSET)
        logger.propagate = True


def test_level_colors_defined() -> None:
    """Test that all standard log levels have color mappings."""
    expected_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
    for level in expected_levels:
        assert level in LEVEL_COLORS


def test_level_color_values() -> None:
    """Test that color values are correct colorama constants."""
    assert LEVEL_COLORS["DEBUG"] == Fore.BLUE
    assert LEVEL_COLORS["INFO"] == Fore.GREEN
    assert LEVEL_COLORS["WARNING"] == Fore.YELLOW
    assert LEVEL_COLORS["ERROR"] == Fore.RED
    assert LEVEL_COLORS["CRITICAL"] == Fore.RED


class LogFormatterTestCase(t.NamedTuple):
    """Test case for log formatter behavior."""

    test_id: str
    level: str
    message: str
    logger_name: str
    expected_contains: list[str]
    expected_not_contains: list[str] = []  # noqa: RUF012


LOG_FORMATTER_TEST_CASES: list[LogFormatterTestCase] = [
    LogFormatterTestCase(
        test_id="info_level",
        level="INFO",
        message="test info message",
        logger_name="test.logger",
        expected_contains=["(INFO)", "test info message", "test.logger"],
    ),
    LogFormatterTestCase(
        test_id="debug_level",
        level="DEBUG",
        message="debug information",
        logger_name="debug.logger",
        expected_contains=["(DEBUG)", "debug information", "debug.logger"],
    ),
    LogFormatterTestCase(
        test_id="warning_level",
        level="WARNING",
        message="warning message",
        logger_name="warn.logger",
        expected_contains=["(WARNING)", "warning message", "warn.logger"],
    ),
    LogFormatterTestCase(
        test_id="error_level",
        level="ERROR",
        message="error occurred",
        logger_name="error.logger",
        expected_contains=["(ERROR)", "error occurred", "error.logger"],
    ),
]


def test_log_formatter_template_includes_required_elements() -> None:
    """Test that template includes all required formatting elements."""
    formatter = LogFormatter()
    record = logging.LogRecord(
        name="test.logger",
        level=logging.INFO,
        pathname="/test/path.py",
        lineno=42,
        msg="test message",
        args=(),
        exc_info=None,
    )

    template = formatter.template(record)

    # Should include levelname, asctime, and name placeholders
    assert "%(levelname)" in template
    assert "%(asctime)s" in template
    assert "%(name)s" in template


def test_log_formatter_basic_message() -> None:
    """Test formatting a basic log message."""
    formatter = LogFormatter()
    record = logging.LogRecord(
        name="test.logger",
        level=logging.INFO,
        pathname="/test/path.py",
        lineno=42,
        msg="test message",
        args=(),
        exc_info=None,
    )

    result = formatter.format(record)

    assert "test message" in result
    assert "test.logger" in result
    assert "(INFO)" in result


def test_log_formatter_handles_newlines() -> None:
    """Test that multiline messages are properly indented."""
    formatter = LogFormatter()
    record = logging.LogRecord(
        name="test.logger",
        level=logging.INFO,
        pathname="/test/path.py",
        lineno=42,
        msg="line 1\nline 2\nline 3",
        args=(),
        exc_info=None,
    )

    result = formatter.format(record)

    # Newlines should be replaced with newline + indent
    assert "\n    line 2" in result
    assert "\n    line 3" in result


def test_log_formatter_handles_bad_message() -> None:
    """Test formatter handles malformed log messages gracefully."""
    formatter = LogFormatter()

    # Create a record that will cause getMessage() to fail
    record = logging.LogRecord(
        name="test.logger",
        level=logging.INFO,
        pathname="/test/path.py",
        lineno=42,
        msg="bad format %s %s",  # Two placeholders
        args=("only_one_arg",),  # But only one argument
        exc_info=None,
    )

    result = formatter.format(record)

    assert "Bad message" in result


@pytest.mark.parametrize(
    list(LogFormatterTestCase._fields),
    LOG_FORMATTER_TEST_CASES,
    ids=[test.test_id for test in LOG_FORMATTER_TEST_CASES],
)
def test_log_formatter_levels(
    test_id: str,
    level: str,
    message: str,
    logger_name: str,
    expected_contains: list[str],
    expected_not_contains: list[str],
) -> None:
    """Test formatter with different log levels."""
    formatter = LogFormatter()
    level_int = getattr(logging, level)

    record = logging.LogRecord(
        name=logger_name,
        level=level_int,
        pathname="/test/path.py",
        lineno=42,
        msg=message,
        args=(),
        exc_info=None,
    )

    result = formatter.format(record)

    for expected in expected_contains:
        assert expected in result

    for not_expected in expected_not_contains:
        assert not_expected not in result


def test_debug_formatter_template_includes_debug_elements() -> None:
    """Debug template should include module and function info."""
    formatter = DebugLogFormatter()
    record = logging.LogRecord(
        name="test.logger",
        level=logging.INFO,
        pathname="/test/module.py",
        lineno=42,
        msg="test message",
        args=(),
        exc_info=None,
    )
    record.module = "test_module"
    record.funcName = "test_function"

    template = formatter.template(record)

    assert "%(module)s.%(funcName)s()" in template
    assert "%(lineno)d" in template


def test_debug_formatter_output_includes_debug_info() -> None:
    """Formatting should include debug metadata when level is DEBUG."""
    formatter = DebugLogFormatter()
    record = logging.LogRecord(
        name="test.logger",
        level=logging.DEBUG,
        pathname="/test/module.py",
        lineno=123,
        msg="debug message",
        args=(),
        exc_info=None,
    )
    record.module = "test_module"
    record.funcName = "test_function"

    result = formatter.format(record)

    assert "debug message" in result
    assert "test_module.test_function()" in result
    assert "123" in result
    assert "(D)" in result


def test_simple_formatter_returns_only_message() -> None:
    """Simple formatter should return only the message."""
    formatter = SimpleLogFormatter()
    record = logging.LogRecord(
        name="test.logger",
        level=logging.INFO,
        pathname="/test/path.py",
        lineno=42,
        msg="simple message",
        args=(),
        exc_info=None,
    )

    result = formatter.format(record)

    assert result == "simple message"


def test_simple_formatter_handles_arguments() -> None:
    """Simple formatter should expand arguments."""
    formatter = SimpleLogFormatter()
    record = logging.LogRecord(
        name="test.logger",
        level=logging.INFO,
        pathname="/test/path.py",
        lineno=42,
        msg="message with %s and %d",
        args=("text", 42),
        exc_info=None,
    )

    result = formatter.format(record)

    assert result == "message with text and 42"


def test_simple_formatter_excludes_metadata() -> None:
    """Simple formatter should exclude metadata such as logger name."""
    formatter = SimpleLogFormatter()
    record = logging.LogRecord(
        name="very.long.logger.name",
        level=logging.WARNING,
        pathname="/very/long/path/to/module.py",
        lineno=999,
        msg="clean message",
        args=(),
        exc_info=None,
    )

    result = formatter.format(record)

    assert "very.long.logger.name" not in result
    assert "WARNING" not in result
    assert "/very/long/path" not in result
    assert "999" not in result
    assert result == "clean message"


def test_repo_formatter_template_references_repo_info() -> None:
    """Repo template should inject bin_name and keyword values."""
    formatter = RepoLogFormatter()
    record = logging.LogRecord(
        name="libvcs.sync.git",
        level=logging.INFO,
        pathname="/libvcs/sync/git.py",
        lineno=42,
        msg="git operation",
        args=(),
        exc_info=None,
    )
    record.bin_name = "git"
    record.keyword = "clone"
    record.message = "git operation"  # RepoLogFormatter expects this

    template = formatter.template(record)

    assert "git" in template
    assert "clone" in template


def test_repo_formatter_formats_message() -> None:
    """Formatted repo log should include bin_name, keyword, and message."""
    formatter = RepoLogFormatter()
    record = logging.LogRecord(
        name="libvcs.sync.git",
        level=logging.INFO,
        pathname="/libvcs/sync/git.py",
        lineno=42,
        msg="Cloning repository",
        args=(),
        exc_info=None,
    )
    record.bin_name = "git"
    record.keyword = "clone"

    result = formatter.format(record)

    assert "git" in result
    assert "clone" in result
    assert "Cloning repository" in result


def test_repo_filter_accepts_repo_records() -> None:
    """Filter should accept records with keyword attribute."""
    repo_filter = RepoFilter()
    record = logging.LogRecord(
        name="libvcs.sync.git",
        level=logging.INFO,
        pathname="/libvcs/sync/git.py",
        lineno=42,
        msg="repo message",
        args=(),
        exc_info=None,
    )
    record.keyword = "clone"

    assert repo_filter.filter(record) is True


def test_repo_filter_rejects_non_repo_records() -> None:
    """Filter should reject records without keyword attribute."""
    repo_filter = RepoFilter()
    record = logging.LogRecord(
        name="regular.logger",
        level=logging.INFO,
        pathname="/regular/module.py",
        lineno=42,
        msg="regular message",
        args=(),
        exc_info=None,
    )

    assert repo_filter.filter(record) is False


def test_repo_filter_handles_keyword_in_dict() -> None:
    """Filter should honor keyword set directly on record dict."""
    repo_filter = RepoFilter()
    record = logging.LogRecord(
        name="libvcs.sync.git",
        level=logging.INFO,
        pathname="/libvcs/sync/git.py",
        lineno=42,
        msg="repo message",
        args=(),
        exc_info=None,
    )
    record.__dict__["keyword"] = "pull"

    assert repo_filter.filter(record) is True


def test_get_cli_logger_names_includes_base() -> None:
    """Helper returns expected CLI modules including base package."""
    names = get_cli_logger_names(include_self=True)
    expected = [
        "vcspull.cli",
        "vcspull.cli._colors",
        "vcspull.cli._output",
        "vcspull.cli.add",
        "vcspull.cli.discover",
        "vcspull.cli.fmt",
        "vcspull.cli.list",
        "vcspull.cli.status",
        "vcspull.cli.sync",
    ]
    assert names == expected


def test_get_cli_logger_names_without_base() -> None:
    """Helper omits base package when include_self is False."""
    names = get_cli_logger_names(include_self=False)
    assert "vcspull.cli" not in names
    assert all(name.startswith("vcspull.cli.") for name in names)


def test_setup_logger_default_behavior(caplog: LogCaptureFixture) -> None:
    """setup_logger should configure vcspull logger once at INFO level."""
    test_logger = logging.getLogger("test_logger")
    test_logger.handlers.clear()

    setup_logger(test_logger, level="INFO")

    vcspull_logger = logging.getLogger("vcspull")
    assert len(vcspull_logger.handlers) > 0
    assert vcspull_logger.propagate is True
    handler = vcspull_logger.handlers[0]
    assert isinstance(handler.formatter, SimpleLogFormatter)


def test_setup_logger_custom_level(caplog: LogCaptureFixture) -> None:
    """setup_logger should honor a DEBUG log level."""
    setup_logger(level="DEBUG")

    vcspull_logger = logging.getLogger("vcspull")
    assert vcspull_logger.level == logging.DEBUG
    handler = vcspull_logger.handlers[0]
    assert isinstance(handler.formatter, DebugLogFormatter)


def test_setup_logger_initializes_vcspull_logger(caplog: LogCaptureFixture) -> None:
    """Vcspull logger should exist with a simple formatter."""
    setup_logger(level="INFO")

    vcspull_logger = logging.getLogger("vcspull")
    assert len(vcspull_logger.handlers) > 0
    assert vcspull_logger.propagate is True
    handler = vcspull_logger.handlers[0]
    assert isinstance(handler.formatter, SimpleLogFormatter)


def test_setup_logger_leaves_cli_loggers_propagating(caplog: LogCaptureFixture) -> None:
    """CLI loggers should propagate without their own handlers."""
    setup_logger(level="INFO")

    for logger_name in [
        "vcspull.cli.add",
        "vcspull.cli.add_from_fs",
        "vcspull.cli.sync",
    ]:
        logger = logging.getLogger(logger_name)
        assert logger.propagate is True
        assert len(logger.handlers) == 0


def test_setup_logger_configures_libvcs_logger(caplog: LogCaptureFixture) -> None:
    """Libvcs logger should receive RepoLogFormatter handler."""
    setup_logger(level="INFO")

    libvcs_logger = logging.getLogger("libvcs")
    assert len(libvcs_logger.handlers) > 0
    assert libvcs_logger.propagate is True
    handler = libvcs_logger.handlers[0]
    assert isinstance(handler.formatter, RepoLogFormatter)


def test_setup_logger_avoids_duplicate_handlers(caplog: LogCaptureFixture) -> None:
    """setup_logger should not add handlers to the provided logger."""
    test_logger = logging.getLogger("test_logger")
    test_logger.handlers.clear()

    setup_logger(test_logger, level="INFO")
    assert len(test_logger.handlers) == 0

    setup_logger(test_logger, level="INFO")
    assert len(test_logger.handlers) == 0


def test_setup_logger_with_none_creates_root_logger(
    caplog: LogCaptureFixture,
) -> None:
    """When no logger is provided, vcspull logger should be configured."""
    setup_logger(log=None, level="WARNING")

    vcspull_logger = logging.getLogger("vcspull")
    assert len(vcspull_logger.handlers) > 0
    assert vcspull_logger.level == logging.WARNING


def test_simple_formatter_integration(caplog: LogCaptureFixture) -> None:
    """Simple formatter should integrate with logging.Logger."""
    logger = logging.getLogger("test_simple")
    logger.handlers.clear()

    handler = logging.StreamHandler()
    handler.setFormatter(SimpleLogFormatter())
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

    logger.info("clean message")

    assert "clean message" in caplog.text


def test_debug_formatter_integration(caplog: LogCaptureFixture) -> None:
    """Debug formatter should output debug metadata."""
    logger = logging.getLogger("test_debug")
    logger.handlers.clear()

    handler = logging.StreamHandler()
    handler.setFormatter(DebugLogFormatter())
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)

    logger.debug("debug message")

    assert "debug message" in caplog.text


def test_repo_filter_integration(caplog: LogCaptureFixture) -> None:
    """RepoFilter should pass repo logs and ignore others."""
    logger = logging.getLogger("test_repo")
    logger.handlers.clear()
    logger.propagate = False

    handler = logging.StreamHandler()
    handler.setFormatter(RepoLogFormatter())
    handler.addFilter(RepoFilter())
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

    record = logging.LogRecord(
        name="test_repo",
        level=logging.INFO,
        pathname="test.py",
        lineno=1,
        msg="repo operation",
        args=(),
        exc_info=None,
    )
    record.bin_name = "git"
    record.keyword = "clone"
    record.message = "repo operation"  # RepoLogFormatter expects this

    logger.handle(record)

    logger.info("regular message")

    repo_filter = RepoFilter()
    assert repo_filter.filter(record) is True

    regular_record = logging.LogRecord(
        name="test_repo",
        level=logging.INFO,
        pathname="test.py",
        lineno=1,
        msg="regular message",
        args=(),
        exc_info=None,
    )
    assert repo_filter.filter(regular_record) is False
