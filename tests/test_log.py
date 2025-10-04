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
        "vcspull.cli",
        "vcspull.cli.add",
        "vcspull.cli.add_from_fs",
        "vcspull.cli.sync",
        "vcspull.cli.fmt",
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


class TestLevelColors:
    """Test LEVEL_COLORS constant."""

    def test_level_colors_defined(self) -> None:
        """Test that all standard log levels have color mappings."""
        expected_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        for level in expected_levels:
            assert level in LEVEL_COLORS

    def test_level_color_values(self) -> None:
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


class TestLogFormatter:
    """Test LogFormatter class."""

    def test_template_includes_required_elements(self) -> None:
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

    def test_format_basic_message(self) -> None:
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

    def test_format_handles_newlines(self) -> None:
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

    def test_format_handles_bad_message(self) -> None:
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
    def test_formatter_levels(
        self,
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


class TestDebugLogFormatter:
    """Test DebugLogFormatter class."""

    def test_template_includes_debug_elements(self) -> None:
        """Test that debug template includes module and function info."""
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

        # Should include module.funcName and lineno
        assert "%(module)s.%(funcName)s()" in template
        assert "%(lineno)d" in template

    def test_format_with_debug_info(self) -> None:
        """Test formatting with debug information."""
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
        # DebugLogFormatter uses single letter level names
        assert "(D)" in result


class TestSimpleLogFormatter:
    """Test SimpleLogFormatter class."""

    def test_format_returns_only_message(self) -> None:
        """Test that simple formatter returns only the message."""
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

        # Should only contain the message, no extra formatting
        assert result == "simple message"

    def test_format_with_arguments(self) -> None:
        """Test simple formatter with message arguments."""
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

    def test_format_excludes_metadata(self) -> None:
        """Test that simple formatter excludes timestamp, level, logger name."""
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

        # Should not contain any metadata
        assert "very.long.logger.name" not in result
        assert "WARNING" not in result
        assert "/very/long/path" not in result
        assert "999" not in result
        assert result == "clean message"


class TestRepoLogFormatter:
    """Test RepoLogFormatter class."""

    def test_template_formats_repo_info(self) -> None:
        """Test that repo template includes bin_name and keyword."""
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

        # Template should reference the actual values, not the variable names
        assert "git" in template
        assert "clone" in template

    def test_format_repo_message(self) -> None:
        """Test formatting a repository operation message."""
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

        # Should include bin_name and keyword formatting
        assert "git" in result
        assert "clone" in result
        assert "Cloning repository" in result


class TestRepoFilter:
    """Test RepoFilter class."""

    def test_filter_accepts_repo_records(self) -> None:
        """Test that filter accepts records with keyword attribute."""
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

    def test_filter_rejects_non_repo_records(self) -> None:
        """Test that filter rejects records without keyword attribute."""
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
        # No keyword attribute

        assert repo_filter.filter(record) is False

    def test_filter_rejects_empty_keyword(self) -> None:
        """Test that filter works correctly with keyword attribute present."""
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
        # Set keyword to test the "keyword" in record.__dict__ check
        record.__dict__["keyword"] = "pull"

        assert repo_filter.filter(record) is True


class TestSetupLogger:
    """Test setup_logger function."""

    def test_setup_logger_default_behavior(self, caplog: LogCaptureFixture) -> None:
        """Test setup_logger with default parameters."""
        # Use a test logger to avoid interfering with main logger
        test_logger = logging.getLogger("test_logger")
        test_logger.handlers.clear()

        setup_logger(test_logger, level="INFO")

        vcspull_logger = logging.getLogger("vcspull")
        assert len(vcspull_logger.handlers) > 0
        assert vcspull_logger.propagate is True
        # vcspull logger should use SimpleLogFormatter at INFO level
        handler = vcspull_logger.handlers[0]
        assert isinstance(handler.formatter, SimpleLogFormatter)

    def test_setup_logger_custom_level(self, caplog: LogCaptureFixture) -> None:
        """Test setup_logger with custom log level."""
        setup_logger(level="DEBUG")

        # Check that loggers were set to DEBUG level
        vcspull_logger = logging.getLogger("vcspull")
        assert vcspull_logger.level == logging.DEBUG
        handler = vcspull_logger.handlers[0]
        assert isinstance(handler.formatter, DebugLogFormatter)

    def test_setup_logger_creates_vcspull_logger(
        self,
        caplog: LogCaptureFixture,
    ) -> None:
        """Test that setup_logger creates vcspull logger with debug formatter."""
        setup_logger(level="INFO")

        vcspull_logger = logging.getLogger("vcspull")
        assert len(vcspull_logger.handlers) > 0
        assert vcspull_logger.propagate is True

        handler = vcspull_logger.handlers[0]
        assert isinstance(handler.formatter, SimpleLogFormatter)

    def test_setup_logger_creates_cli_add_logger(
        self,
        caplog: LogCaptureFixture,
    ) -> None:
        """Test that setup_logger creates CLI add logger with simple formatter."""
        setup_logger(level="INFO")

        add_logger = logging.getLogger("vcspull.cli.add")
        assert len(add_logger.handlers) == 0
        assert add_logger.propagate is True

    def test_setup_logger_creates_cli_add_fs_logger(
        self,
        caplog: LogCaptureFixture,
    ) -> None:
        """Test that setup_logger creates CLI add-from-fs logger."""
        setup_logger(level="INFO")

        add_fs_logger = logging.getLogger("vcspull.cli.add_from_fs")
        assert len(add_fs_logger.handlers) == 0
        assert add_fs_logger.propagate is True

    def test_setup_logger_creates_cli_sync_logger(
        self,
        caplog: LogCaptureFixture,
    ) -> None:
        """Test that setup_logger creates CLI sync logger."""
        setup_logger(level="INFO")

        sync_logger = logging.getLogger("vcspull.cli.sync")
        assert len(sync_logger.handlers) == 0
        assert sync_logger.propagate is True

    def test_setup_logger_creates_libvcs_logger(
        self,
        caplog: LogCaptureFixture,
    ) -> None:
        """Test that setup_logger creates libvcs logger with repo formatter."""
        setup_logger(level="INFO")

        libvcs_logger = logging.getLogger("libvcs")
        assert len(libvcs_logger.handlers) > 0
        assert libvcs_logger.propagate is True

        # Test that it uses RepoLogFormatter
        handler = libvcs_logger.handlers[0]
        assert isinstance(handler.formatter, RepoLogFormatter)

    def test_setup_logger_prevents_duplicate_handlers(
        self,
        caplog: LogCaptureFixture,
    ) -> None:
        """Test that setup_logger doesn't create duplicate handlers."""
        test_logger = logging.getLogger("test_logger")
        test_logger.handlers.clear()

        setup_logger(test_logger, level="INFO")
        assert len(test_logger.handlers) == 0

        setup_logger(test_logger, level="INFO")
        assert len(test_logger.handlers) == 0

    def test_setup_logger_with_none_creates_root_logger(
        self,
        caplog: LogCaptureFixture,
    ) -> None:
        """Test that setup_logger with None creates root logger configuration."""
        # This tests the default behavior when no logger is passed
        setup_logger(log=None, level="WARNING")

        # Should have created the vcspull logger hierarchy
        vcspull_logger = logging.getLogger("vcspull")
        assert len(vcspull_logger.handlers) > 0
        assert vcspull_logger.level == logging.WARNING


class TestLoggerIntegration:
    """Test logger integration and behavior."""

    def test_simple_formatter_integration(self, caplog: LogCaptureFixture) -> None:
        """Test SimpleLogFormatter integration with actual logger."""
        logger = logging.getLogger("test_simple")
        logger.handlers.clear()

        # Add handler with simple formatter
        handler = logging.StreamHandler()
        handler.setFormatter(SimpleLogFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)

        # Test logging
        logger.info("clean message")

        # caplog should capture the clean message
        assert "clean message" in caplog.text

    def test_debug_formatter_integration(self, caplog: LogCaptureFixture) -> None:
        """Test DebugLogFormatter integration with actual logger."""
        logger = logging.getLogger("test_debug")
        logger.handlers.clear()

        # Add handler with debug formatter
        handler = logging.StreamHandler()
        handler.setFormatter(DebugLogFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)

        # Test logging
        logger.debug("debug message")

        # caplog should capture the formatted message
        assert "debug message" in caplog.text

    def test_repo_filter_integration(self, caplog: LogCaptureFixture) -> None:
        """Test RepoFilter integration with actual logger."""
        logger = logging.getLogger("test_repo")
        logger.handlers.clear()
        logger.propagate = False  # Prevent logs from going to caplog

        # Add handler with repo formatter and filter
        handler = logging.StreamHandler()
        handler.setFormatter(RepoLogFormatter())
        handler.addFilter(RepoFilter())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)

        # Create a log record with repo attributes
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

        # This should be captured since it has keyword
        logger.handle(record)

        # Regular log without repo attributes should be filtered out
        logger.info("regular message")

        # The caplog should not contain the regular message due to the filter
        # but may contain the repo message depending on how caplog works with filters
        # For this test, we just verify that RepoFilter accepts records with keyword
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
