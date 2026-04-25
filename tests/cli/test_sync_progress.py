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
    # Capital ``Syncing`` matches the permanent ``Synced``/``Timed out``
    # leading-cap pattern so the in-flight + completion lines read as a
    # consistent badge family.
    assert "Syncing codex" in stream.getvalue()

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
    # The heartbeat line begins with ``...`` so ``still syncing`` stays
    # lowercase as a sentence continuation, not a status badge.
    assert "still syncing codex" in out
    # Heartbeat must not duplicate the start line; the only lines are
    # start (``Syncing codex``) + one heartbeat (``... still syncing codex``).
    # Match case-insensitively to count both spellings together.
    assert out.lower().count("syncing codex") == 2


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
    # Capital ``Syncing`` matches the permanent ``Synced`` leading-cap
    # pattern; locks in that consistency.
    assert "Syncing" in out
    assert "codex" in out
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


def test_tty_spinner_colours_the_frame_cell_and_name() -> None:
    """Spinner cell AND repo name are colourised; ``Syncing`` is plain.

    Reporter pointed out that the in-flight line ``Syncing flume`` had a
    plain repo name while the permanent ``✓ Synced fish-shell`` line
    had ``fish-shell`` in cyan. Match the pattern: colour the Braille
    cell (info / cyan) and the repo name (also info / cyan), leaving
    the verb and elapsed-time suffix in the terminal's default
    foreground.
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
    import re as _re

    # A colour sequence appears immediately before at least one Braille frame.
    frame_pattern = _re.compile(r"\x1b\[[0-9;]*m[⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏]")
    assert frame_pattern.search(out), "spinner frame must be wrapped in ANSI colour"
    # The repo name is also wrapped in a colour run (matches the
    # permanent ``✓ Synced <name>`` style); search for any colour escape
    # immediately before ``codex``.
    name_pattern = _re.compile(r"\x1b\[[0-9;]*mcodex")
    assert name_pattern.search(out), "spinner repo name must be wrapped in ANSI colour"
    # The status verb (``Syncing``) stays in the terminal default and is
    # capitalised to match ``Synced`` / ``Timed out`` on permanent lines.
    assert "Syncing" in out


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


def test_stop_repo_with_final_line_writes_atomically_and_returns_true() -> None:
    r"""``stop_repo(final_line=...)`` writes one atomic clear+replace.

    Regression for the user-reported flicker where ``Syncing flume``
    transitioning to ``✓ Synced flume`` flashed through a blank state.
    Today's fix: ``stop_repo`` accepts the permanent line and emits the
    panel-erase + spinner-replacement inside a single ``\x1b[?2026h ...
    \x1b[?2026l`` synchronized-output bracket so the terminal flips the
    whole region atomically.

    The method returns ``True`` to tell the caller it has owned the
    print, so the sync loop skips its own ``formatter.emit_text`` and
    avoids the double-emit that produced ``✓ Synced clap`` on two rows.
    """
    stream = io.StringIO()
    indicator = SyncStatusIndicator(
        enabled=True,
        stream=stream,
        tty=True,
        output_lines=3,
    )

    indicator.start_repo("clap")
    # Pretend a render happened so ``had_render`` is true.
    indicator._last_line_len = 25
    indicator._panel_visible_lines = 2

    wrote = indicator.stop_repo(final_line="✓ Synced clap → ~/study/rust/clap")

    assert wrote is True
    out = stream.getvalue()
    # The atomic write block contains both the synchronized-output
    # bracket and the permanent line.
    assert "\x1b[?2026h" in out
    assert "\x1b[?2026l" in out
    assert "✓ Synced clap" in out
    # Internal counters reset so the next ``start_repo`` starts clean.
    assert indicator._panel_visible_lines == 0
    assert indicator._last_line_len == 0
    indicator.close()


def test_stop_repo_without_final_line_returns_false() -> None:
    """No ``final_line`` means caller still owns the permanent print.

    The non-atomic path stays available for callers that don't have a
    completion line to provide -- e.g. an early teardown on
    KeyboardInterrupt. ``stop_repo()`` returns False so the existing
    ``formatter.emit_text`` flow keeps working.
    """
    stream = io.StringIO()
    indicator = SyncStatusIndicator(
        enabled=True,
        stream=stream,
        tty=True,
        output_lines=3,
    )

    indicator.start_repo("clap")
    indicator._last_line_len = 10
    indicator._panel_visible_lines = 1

    wrote = indicator.stop_repo()
    assert wrote is False
    assert indicator._panel_visible_lines == 0
    indicator.close()


def test_stop_repo_non_tty_always_returns_false() -> None:
    """Non-TTY indicators leave printing to the caller's formatter.

    In headless mode (pipes, CI, capsys), nothing was drawn to erase
    and the spinner thread never started; the caller is responsible
    for printing the permanent line via ``formatter.emit_text``. Even
    when ``final_line`` is passed in, ``stop_repo`` returns False so
    the caller fires its own emit_text and the headless capture
    receives the line.
    """
    stream = io.StringIO()
    indicator = SyncStatusIndicator(
        enabled=True,
        stream=stream,
        tty=False,
        output_lines=3,
    )

    indicator.start_repo("clap")
    wrote = indicator.stop_repo(final_line="✓ Synced clap → ~/")
    assert wrote is False
    # The non-TTY path emitted the start line on ``start_repo``; it
    # does NOT emit the permanent line here -- the caller owns that.
    assert "Syncing clap" in stream.getvalue()
    assert "✓ Synced clap" not in stream.getvalue()


def test_stop_repo_collapses_panel_rows_via_dl() -> None:
    r"""``stop_repo(final_line=...)`` deletes panel rows with DL, not erase.

    Regression: an earlier implementation walked up to the first panel
    row and emitted ``\x1b[2K\n`` per row to "clear" the panel. That
    only erased the row content -- the rows stayed in the buffer as
    blanks, so successive ``✓ Synced ...`` lines were separated by
    visible gaps proportional to whatever the previous repo's panel
    height was at completion time (reported when chaining
    ``vcspull sync ...; vcspull sync ...``).

    Today's fix: after walking up, emit ``\x1b[Pn M`` (DL) once to
    physically delete the panel rows from the buffer; the spinner
    row's content scrolls up to the cursor and the subsequent
    ``erase + final_line + \n`` morphs that row into the permanent
    line in place. This test asserts the DL escape lands in the
    output AND that the regressed ``\x1b[2K\n`` per-row pattern is
    NOT present.
    """
    stream = io.StringIO()
    indicator = SyncStatusIndicator(
        enabled=True,
        stream=stream,
        tty=True,
        output_lines=3,
    )

    indicator.start_repo("clap")
    indicator._last_line_len = 25
    indicator._panel_visible_lines = 3

    indicator.stop_repo(final_line="✓ Synced clap → ~/study/rust/clap")

    out = stream.getvalue()
    # Walk up panel_visible rows, then DL panel_visible rows.
    assert "\x1b[3A" in out
    assert "\x1b[3M" in out
    # The regressed pattern: ``\x1b[2K\n`` per panel row would appear
    # at least 3 times back-to-back. The new path uses DL once.
    assert out.count("\x1b[2K\n") <= 1, (
        "panel rows are being erased+newlined instead of DL'd; this "
        "leaves blanks in scrollback"
    )
    indicator.close()


def test_stop_repo_no_panel_skips_dl() -> None:
    r"""``stop_repo`` omits DL when there are no panel rows to delete.

    With ``_panel_visible_lines == 0`` only the spinner row needs to
    be replaced; emitting ``\x1b[0M`` is meaningless (DL of zero
    rows) and even ``\x1b[A`` would walk above the spinner, so the
    walk-up + DL pair is skipped entirely.
    """
    stream = io.StringIO()
    indicator = SyncStatusIndicator(
        enabled=True,
        stream=stream,
        tty=True,
        output_lines=3,
    )

    indicator.start_repo("clap")
    indicator._last_line_len = 25
    indicator._panel_visible_lines = 0

    indicator.stop_repo(final_line="✓ Synced clap → ~/study/rust/clap")

    out = stream.getvalue()
    # No panel-collapse machinery should appear when there's nothing
    # to collapse: no upward walk, no DL.
    assert "\x1b[0A" not in out
    assert "\x1b[0M" not in out
    # The spinner-row replacement still lands.
    assert "✓ Synced clap" in out
    indicator.close()


def test_stop_repo_panel_with_no_final_line_still_collapses() -> None:
    r"""``stop_repo()`` (no ``final_line``) still collapses panel rows.

    The early-teardown path (e.g. KeyboardInterrupt before the outcome
    is known) calls ``stop_repo()`` with no replacement line. The
    panel must still be DL'd so the caller's subsequent
    ``formatter.emit_text`` lands without a stack of blank rows above
    it.
    """
    stream = io.StringIO()
    indicator = SyncStatusIndicator(
        enabled=True,
        stream=stream,
        tty=True,
        output_lines=3,
    )

    indicator.start_repo("clap")
    indicator._last_line_len = 25
    indicator._panel_visible_lines = 2

    wrote = indicator.stop_repo()

    out = stream.getvalue()
    assert wrote is False  # caller still owns the permanent print
    assert "\x1b[2A" in out
    assert "\x1b[2M" in out
    assert indicator._panel_visible_lines == 0
    indicator.close()


def test_clear_block_uses_dl_to_remove_panel_and_spinner() -> None:
    r"""``_clear_block`` deletes panel rows + spinner via a single DL.

    Used from ``close()`` (and historically from teardown paths).
    Walks up to the first panel row, then DLs ``panel + 1`` rows so
    the entire frame is removed from the buffer in one operation.
    """
    stream = io.StringIO()
    indicator = SyncStatusIndicator(
        enabled=True,
        stream=stream,
        tty=True,
        output_lines=3,
    )

    indicator._panel_visible_lines = 3
    indicator._clear_block()

    out = stream.getvalue()
    # Walk up panel rows, then DL panel + spinner together.
    assert "\x1b[3A" in out
    assert "\x1b[4M" in out
    assert indicator._panel_visible_lines == 0
    indicator.close()


def test_render_tty_skips_stale_tick_when_active_repo_changed() -> None:
    """``_render_tty`` must skip writes for a stale (now-cleared) repo.

    Reproduces the race where the spinner thread captured ``name`` =
    "clap" before ``stop_repo`` cleared it; the prior render path then
    wrote a stale frame on top of the new state. The fix: re-check
    ``self._active_repo`` under the lock at the start of ``_render_tty``.
    """
    stream = io.StringIO()
    indicator = SyncStatusIndicator(
        enabled=True,
        stream=stream,
        tty=True,
        output_lines=3,
    )

    # Pretend the spinner thread captured ``name="clap"`` and is about
    # to render, but ``stop_repo`` has just cleared ``_active_repo``.
    indicator._active_repo = None
    before = stream.getvalue()
    indicator._render_tty(frame="⠋", name="clap", elapsed=0.5)
    after = stream.getvalue()
    # Stale tick: nothing should land on the stream.
    assert after == before
