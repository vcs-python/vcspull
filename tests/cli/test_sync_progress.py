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
    # The spinner line mentions the repo and has at least one Braille frame.
    assert "syncing codex" in out
    assert any(f in out for f in "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏")
    # Cursor hide / show sequences bracket the spinner so tmux / kitty don't
    # leak a missing cursor after vcspull exits.
    assert "\x1b[?25l" in out  # hide
    assert "\x1b[?25h" in out  # show
    # Frames are wrapped in ANSI synchronized-output markers so terminals
    # flip the spinner line atomically, preventing mid-frame tearing when a
    # concurrent writer hits stdout.
    assert "\x1b[?2026h" in out
    assert "\x1b[?2026l" in out
    # Decorative ornaments dropped in the prior polish pass must stay gone.
    for glyph in ("…", "·", "⏱"):
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


def test_write_clears_spinner_line_before_emitting_in_tty() -> None:
    r"""A concurrent writer clears the spinner's in-flight line first.

    Models the real-world interleave: libvcs emits a log record while the
    spinner is mid-draw. Without the clear-then-write sequence the log
    message would tack onto the spinner line and produce artefacts like
    ``Already on 'main'ec ...  1.1s``. The guard: every ``write()`` in a
    TTY must emit ``\r\033[2K`` when the spinner has a drawn line.
    """
    stream = io.StringIO()
    indicator = SyncStatusIndicator(enabled=True, stream=stream, tty=True)

    # Pretend the spinner has rendered a frame -- that's the state a
    # concurrent writer actually observes mid-sync.
    indicator._last_line_len = 40

    indicator.write("|git| (codex) Updating to 'main'\n")

    out = stream.getvalue()
    # CR + ERASE_LINE must appear before the message, not after it.
    clear_idx = out.find("\r\x1b[2K")
    msg_idx = out.find("Updating")
    assert clear_idx != -1, "expected clear-line sequence before the write"
    assert msg_idx > clear_idx, "clear must precede the actual text"
    # After a concurrent write, the spinner should redraw from scratch; the
    # lingering line-length counter is reset so the next frame does a full
    # render.
    assert indicator._last_line_len == 0


def test_write_non_tty_path_passes_through_untouched() -> None:
    """Non-TTY streams never see the clear-line escape sequence."""
    stream = io.StringIO()
    indicator = SyncStatusIndicator(enabled=True, stream=stream, tty=False)

    indicator.write("hello world\n")

    out = stream.getvalue()
    assert out == "hello world\n"
    assert "\x1b[2K" not in out


def test_tty_spinner_colours_the_frame_cell() -> None:
    """Just the Braille cell is colourised (tmuxp-style), not the whole line.

    The repo name and elapsed suffix stay in the terminal's default
    foreground so they don't collide with the ``✓ Synced`` / ``- Timed out``
    colouring emitted on the permanent line when a repo completes.
    """
    from vcspull.cli._colors import ColorMode, Colors

    stream = io.StringIO()
    indicator = SyncStatusIndicator(
        enabled=True,
        stream=stream,
        tty=True,
        colors=Colors(ColorMode.ALWAYS),
    )

    indicator.start_repo("codex")
    time.sleep(0.2)
    indicator.stop_repo()
    indicator.close()

    out = stream.getvalue()
    # A colour sequence appears immediately before at least one Braille frame.
    import re as _re

    pattern = _re.compile(r"\x1b\[[0-9;]*m[⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏]")
    assert pattern.search(out), "spinner frame must be wrapped in ANSI colour"
    # The repo name itself must not be inside a colour run -- look for the
    # literal "syncing codex" preceded by a reset (the info() helper closes
    # the colour right after the frame).
    assert "syncing codex" in out


def test_add_output_line_appends_and_bounds_panel_deque() -> None:
    """Panel buffer keeps only the last ``output_lines`` entries.

    Reporter's request: a 3-line live trail above the spinner that
    rolls under -- not an unbounded scroll. Locks in
    ``collections.deque(maxlen=output_lines)`` semantics: the 4th push
    drops the oldest line.
    """
    stream = io.StringIO()
    indicator = SyncStatusIndicator(
        enabled=True,
        stream=stream,
        tty=True,
        output_lines=3,
    )

    indicator.add_output_line("first\n")
    indicator.add_output_line("second\n")
    indicator.add_output_line("third\n")
    indicator.add_output_line("fourth\n")

    assert list(indicator._panel_buffer) == ["second", "third", "fourth"]


def test_add_output_line_panel_disabled_falls_back_to_write() -> None:
    """``output_lines=0`` makes ``add_output_line`` plain ``write()``.

    The 0-panel mode is the escape hatch for users who don't want a
    rolling region above the spinner: bytes still reach the terminal,
    just on their own row, with the same clear-the-spinner-first
    behaviour ``write()`` already provides.
    """
    stream = io.StringIO()
    indicator = SyncStatusIndicator(
        enabled=True,
        stream=stream,
        tty=True,
        output_lines=0,
    )

    indicator.add_output_line("From github.com/foo/bar\n")

    assert "From github.com/foo/bar" in stream.getvalue()
    # No panel deque ever populated.
    assert indicator._panel_buffer.maxlen == 0


def test_add_output_line_non_tty_writes_directly() -> None:
    """Non-TTY mode bypasses the panel entirely.

    The spinner thread never starts in non-TTY mode (pipes, CI, pytest
    capture). If ``add_output_line`` buffered into the deque on this
    path the bytes would never be rendered. Guard against that
    regression: lines must reach the stream synchronously.
    """
    stream = io.StringIO()
    indicator = SyncStatusIndicator(
        enabled=True,
        stream=stream,
        tty=False,
        output_lines=3,
    )

    indicator.add_output_line("From github.com/foo/bar\n")

    assert "From github.com/foo/bar" in stream.getvalue()
    # Deque stays empty -- the line went straight to the stream.
    assert list(indicator._panel_buffer) == []


def test_render_tty_writes_panel_above_spinner_atomically() -> None:
    r"""Spinner thread writes panel rows + spinner inside one sync bracket.

    The ANSI ``\x1b[?2026h`` / ``\x1b[?2026l`` pair tells modern
    terminals to buffer the whole region and flip it atomically. Locks
    in the contract for terminals that honour the bracket
    (kitty/iTerm2/WezTerm/recent xterm) and is benign elsewhere.
    """
    stream = io.StringIO()
    indicator = SyncStatusIndicator(
        enabled=True,
        stream=stream,
        tty=True,
        output_lines=3,
    )
    indicator.start_repo("codex")
    indicator.add_output_line("From github.com/openai/codex\n")
    indicator.add_output_line("   abc..def  main -> origin/main\n")
    # Let the spinner thread tick at least once.
    time.sleep(0.2)
    indicator.stop_repo()
    indicator.close()

    out = stream.getvalue()
    # Both panel lines made it to the stream during a render tick.
    assert "From github.com/openai/codex" in out
    assert "abc..def" in out
    # The synchronized-output bracket wraps each frame.
    assert "\x1b[?2026h" in out
    assert "\x1b[?2026l" in out


def test_stop_repo_collapses_the_panel() -> None:
    """``stop_repo`` resets the deque + visible-lines counter.

    The "trail collapses on completion" UX requirement: when the
    permanent ``✓ Synced`` line is about to print, the panel must be
    drained so it doesn't linger in scrollback.
    """
    stream = io.StringIO()
    indicator = SyncStatusIndicator(
        enabled=True,
        stream=stream,
        tty=True,
        output_lines=3,
    )
    indicator.start_repo("codex")
    indicator.add_output_line("a\nb\nc\n")
    # Pretend a render happened.
    indicator._panel_visible_lines = 3
    indicator.stop_repo()

    assert list(indicator._panel_buffer) == []
    assert indicator._panel_visible_lines == 0
    indicator.close()


def test_panel_clears_between_repos() -> None:
    """``start_repo`` empties any leftover deque from the prior repo."""
    stream = io.StringIO()
    indicator = SyncStatusIndicator(
        enabled=True,
        stream=stream,
        tty=True,
        output_lines=3,
    )
    indicator.start_repo("alpha")
    indicator.add_output_line("alpha-one\n")
    indicator.add_output_line("alpha-two\n")
    indicator.start_repo("beta")

    # Fresh trail per repo: alpha's panel must NOT bleed into beta's.
    assert list(indicator._panel_buffer) == []
    indicator.close()
