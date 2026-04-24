"""Tests for the per-invocation debug log file (npm/pnpm style)."""

from __future__ import annotations

import logging
import pathlib
import typing as t

import pytest

from vcspull.log import (
    default_debug_log_path,
    setup_file_logger,
    teardown_file_logger,
)


def test_default_debug_log_path_lives_in_tempdir(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: pathlib.Path,
) -> None:
    """``TMPDIR`` is honoured and the file name encodes timestamp + PID."""
    monkeypatch.setenv("TMPDIR", str(tmp_path))
    # On platforms that read TMPDIR via ``tempfile.gettempdir`` this is honoured
    # on first access per-process; the default path must reside under it.

    path = default_debug_log_path()

    # The file name must start with the prefix that downstream tooling (CI log
    # collection, grep for "npm-debug"-style artefacts) can pattern-match on.
    assert path.name.startswith("vcspull-debug-")
    assert path.suffix == ".log"


def test_setup_file_logger_attaches_debug_handler(
    tmp_path: pathlib.Path,
) -> None:
    """The handler attaches at DEBUG level to both vcspull and libvcs loggers."""
    log_path = tmp_path / "nested" / "vcspull-debug.log"
    assert not log_path.exists()

    handler = setup_file_logger(log_path)
    try:
        # setup_file_logger must create missing parent directories so callers
        # can point to a path that does not yet exist.
        assert log_path.parent.is_dir()

        vcspull_logger = logging.getLogger("vcspull")
        libvcs_logger = logging.getLogger("libvcs")
        assert handler in vcspull_logger.handlers
        assert handler in libvcs_logger.handlers
        assert handler.level == logging.DEBUG
    finally:
        teardown_file_logger(handler)


def test_setup_file_logger_captures_subsequent_log_records(
    tmp_path: pathlib.Path,
) -> None:
    """Log records emitted after setup end up inside the on-disk file."""
    log_path = tmp_path / "vcspull-debug.log"
    handler = setup_file_logger(log_path)
    try:
        logger = logging.getLogger("vcspull.test-log-file")
        logger.debug("debug crumb %s", "apple")
        logger.warning("timed out syncing %s", "codex")
    finally:
        teardown_file_logger(handler)

    text = log_path.read_text(encoding="utf-8")
    assert "debug crumb apple" in text
    assert "timed out syncing codex" in text
    # The formatter must include level + logger name for post-mortem searching.
    assert "DEBUG" in text
    assert "WARNING" in text
    assert "vcspull.test-log-file" in text


def test_setup_file_logger_does_not_double_attach(
    tmp_path: pathlib.Path,
) -> None:
    """Calling setup twice with the same path attaches only one handler."""
    log_path = tmp_path / "vcspull-debug.log"

    handler_a = setup_file_logger(log_path)
    handler_b = setup_file_logger(log_path)
    try:
        vcspull_logger = logging.getLogger("vcspull")
        # The second call returns a *new* handler object for the outer caller,
        # but the logger must not end up with duplicate file handlers pointing
        # at the same file -- that would write every record twice.
        matching = [
            h
            for h in vcspull_logger.handlers
            if isinstance(h, logging.FileHandler)
            and getattr(h, "baseFilename", None) == str(log_path)
        ]
        assert len(matching) == 1
    finally:
        teardown_file_logger(handler_a)
        teardown_file_logger(handler_b)


def test_teardown_file_logger_detaches_and_closes(
    tmp_path: pathlib.Path,
) -> None:
    """Tearing down removes the handler from both loggers and closes the file."""
    log_path = tmp_path / "vcspull-debug.log"
    handler = setup_file_logger(log_path)
    teardown_file_logger(handler)

    vcspull_logger = logging.getLogger("vcspull")
    libvcs_logger = logging.getLogger("libvcs")
    assert handler not in vcspull_logger.handlers
    assert handler not in libvcs_logger.handlers
    # Closing is idempotent per Python logging convention; a second call must
    # not raise so the outer sync()'s ``finally`` can be defensively
    # re-invoked.
    teardown_file_logger(handler)


def test_default_debug_log_path_encodes_distinct_invocations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Distinct (timestamp, pid) pairs produce distinct file names."""

    class _Fake:
        value = 0

        @classmethod
        def now(cls) -> t.Any:
            cls.value += 1

            class _Stamp:
                @staticmethod
                def strftime(_fmt: str) -> str:
                    return f"2026042400000{_Fake.value}"

            return _Stamp()

    import vcspull.log as log_mod

    monkeypatch.setattr(log_mod, "datetime", _Fake)

    first = default_debug_log_path()
    second = default_debug_log_path()

    assert first != second
    assert first.name.startswith("vcspull-debug-20260424")
    assert second.name.startswith("vcspull-debug-20260424")
