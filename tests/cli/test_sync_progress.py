"""Tests for ``vcspull.cli._progress.SyncStatusIndicator``."""

from __future__ import annotations

import io
import time
import typing as t

import pytest

from vcspull.cli._progress import (
    SyncStatusIndicator,
    build_indicator,
)

if t.TYPE_CHECKING:
    pass


def test_disabled_indicator_is_silent_noop() -> None:
    """An indicator with ``enabled=False`` writes nothing to the stream."""
    stream = io.StringIO()
    indicator = SyncStatusIndicator(enabled=False, stream=stream, tty=True)

    indicator.start_repo("codex")
    indicator.heartbeat()
    indicator.stop_repo()
    indicator.close()

    assert stream.getvalue() == ""


def test_non_tty_emits_once_on_start_and_honours_heartbeat() -> None:
    """Non-TTY path prints a single start line then a "still syncing" line."""
    stream = io.StringIO()
    indicator = SyncStatusIndicator(enabled=True, stream=stream, tty=False)

    indicator.start_repo("codex")
    assert "syncing codex" in stream.getvalue()

    # Pretend the repo has been running longer than the heartbeat interval so
    # the next heartbeat call emits. We go under the hood to avoid a slow
    # sleep in the test. After start_repo both timestamps are populated, so
    # the asserts below satisfy the type checker.
    assert indicator._last_heartbeat_at is not None
    assert indicator._repo_started_at is not None
    indicator._last_heartbeat_at -= 60.0
    indicator._repo_started_at -= 60.0
    indicator.heartbeat()
    indicator.stop_repo()
    indicator.close()

    out = stream.getvalue()
    assert "still syncing codex" in out
    # Heartbeat must not duplicate the start line; the only lines are
    # start + one heartbeat.
    assert out.count("syncing codex") == 2


def test_non_tty_heartbeat_throttles_below_interval() -> None:
    """Heartbeat does nothing if the interval hasn't elapsed yet."""
    stream = io.StringIO()
    indicator = SyncStatusIndicator(enabled=True, stream=stream, tty=False)

    indicator.start_repo("codex")
    initial_out = stream.getvalue()
    # Call heartbeat a bunch without advancing time -- nothing new should
    # land in the stream.
    for _ in range(5):
        indicator.heartbeat()
    indicator.stop_repo()
    indicator.close()

    # Still exactly one line: the start-of-repo notification.
    assert stream.getvalue() == initial_out
    assert stream.getvalue().count("\n") == 1


def test_tty_spinner_renders_active_repo(monkeypatch: pytest.MonkeyPatch) -> None:
    """In a TTY the spinner background thread writes to the stream."""
    stream = io.StringIO()
    indicator = SyncStatusIndicator(enabled=True, stream=stream, tty=True)

    indicator.start_repo("codex")
    # Give the spinner thread a slice of real time to tick at least once.
    time.sleep(0.2)
    indicator.stop_repo()
    indicator.close()

    out = stream.getvalue()
    # The spinner line mentions the repo and has at least one ASCII frame.
    assert "syncing codex" in out
    assert any(f in out for f in "|/-\\")
    # Cursor hide / show sequences bracket the spinner so tmux / kitty don't
    # leak a missing cursor after vcspull exits.
    assert "\x1b[?25l" in out  # hide
    assert "\x1b[?25h" in out  # show
    # No emoji / non-ASCII decoration leaks out of the spinner path.
    for glyph in ("⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏", "…", "·"):
        assert glyph not in out


def test_close_is_idempotent() -> None:
    """Calling ``close()`` more than once is safe."""
    stream = io.StringIO()
    indicator = SyncStatusIndicator(enabled=True, stream=stream, tty=True)

    indicator.start_repo("codex")
    indicator.close()
    indicator.close()  # must not raise
    indicator.close()  # still must not raise


def test_repo_context_manager_starts_and_stops() -> None:
    """The ``repo(name)`` context manager bookends the indicator state."""
    stream = io.StringIO()
    indicator = SyncStatusIndicator(enabled=True, stream=stream, tty=False)

    with indicator.repo("codex"):
        # While inside, the indicator considers 'codex' the active repo.
        # We peek at the internal slot rather than waiting for a render.
        assert indicator._active_repo == "codex"

    assert indicator._active_repo is None
    indicator.close()


def test_build_indicator_disables_in_machine_output_mode() -> None:
    """``build_indicator(human=False, ...)`` returns a disabled indicator."""
    indicator = build_indicator(human=False, color="auto")
    assert indicator._enabled is False


def test_build_indicator_disables_when_color_is_never() -> None:
    """``color=never`` implies quiet output -- the spinner stays off."""
    indicator = build_indicator(human=True, color="never")
    assert indicator._enabled is False


def test_build_indicator_enabled_in_human_mode() -> None:
    """Human output + auto/always colour turns the indicator on."""
    indicator = build_indicator(human=True, color="auto")
    assert indicator._enabled is True
    indicator.close()
