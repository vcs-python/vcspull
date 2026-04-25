"""Live status indicator for ``vcspull sync``.

Shows the user which repository is currently being synced and how long it has
been running. In a TTY a single-line braille spinner refreshes every ~100 ms;
elsewhere (pipes, CI logs) a once-on-start line is followed by periodic
"still syncing" heartbeats so the output stream keeps moving without flooding
the log.

Inspired by ``tmuxp``'s spinner module -- stdlib + ANSI only, no ``rich``
dependency.
"""

from __future__ import annotations

import atexit
import collections
import io
import itertools
import logging
import sys
import threading
import time
import typing as t

from ._colors import ColorMode, Colors, get_color_mode

log = logging.getLogger(__name__)


# ANSI escape sequences
_HIDE_CURSOR = "\033[?25l"
_SHOW_CURSOR = "\033[?25h"
_ERASE_LINE = "\033[2K"
_CURSOR_TO_COL0 = "\r"
#: Synchronized-output bracket -- modern terminals (kitty, iTerm2, WezTerm,
#: recent xterm) buffer everything between these markers and flip to the
#: new state atomically. Terminals that don't recognise the sequence ignore
#: it, so this is a safe belt-and-braces against mid-frame tearing when the
#: spinner redraws while ``progress_cb`` writes from another thread.
_SYNC_START = "\x1b[?2026h"
_SYNC_END = "\x1b[?2026l"

#: Braille spinner frames -- same glyphs tmuxp uses; modern terminals
#: render them crisply and the rotation reads cleaner than the
#: ASCII ``|/-\`` set. On exotic terminals that can't render Unicode the
#: cells fall back to their Braille block without breaking output.
_SPINNER_FRAMES = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"

#: Default panel height for the live trail above the spinner. Same value
#: tmuxp uses for ``before_script`` script output (see
#: ``~/work/python/tmuxp/src/tmuxp/cli/_progress.py:42``). 3 rows is enough
#: to give the user "what just happened" + a couple of lines of context
#: without dominating the screen. ``0`` hides the panel entirely.
_DEFAULT_OUTPUT_LINES = 3

#: How often to refresh the spinner line in the TTY path.
_TTY_REFRESH_INTERVAL = 0.1

#: How often to emit a "still syncing" heartbeat line in the non-TTY path.
_HEARTBEAT_INTERVAL = 30.0

# Track indicators that have hidden the cursor so we can restore it on atexit
# even if the interpreter crashes mid-sync and no ``finally`` block fires.
_ACTIVE_INDICATORS: set[SyncStatusIndicator] = set()


def _restore_cursors_on_exit() -> None:
    """Restore the cursor for every indicator that still has it hidden."""
    for indicator in list(_ACTIVE_INDICATORS):
        # atexit handlers that raise are swallowed by the interpreter, so we
        # log-and-swallow here to leave a breadcrumb for debugging without
        # masking other shutdown tasks.
        _close_indicator_quietly(indicator)


def _close_indicator_quietly(indicator: SyncStatusIndicator) -> None:
    try:
        indicator.close()
    except Exception as exc_obj:
        log.debug("Error restoring spinner cursor: %s", exc_obj)


atexit.register(_restore_cursors_on_exit)


class SyncStatusIndicator:
    """Owns the "which repo is running now" UI for a sync session.

    Exactly one repo is considered "active" at a time -- this matches the
    current sequential sync loop. Callers drive the indicator with
    :meth:`start_repo` / :meth:`stop_repo`, or via the context manager
    returned by :meth:`repo`.
    """

    def __init__(
        self,
        *,
        enabled: bool = True,
        stream: t.TextIO | None = None,
        tty: bool | None = None,
        colors: Colors | None = None,
        output_lines: int = _DEFAULT_OUTPUT_LINES,
    ) -> None:
        self._stream = stream if stream is not None else sys.stdout
        # Respect the explicit tty override (tests, ``--color=never``) but
        # default to whatever the stream actually reports.
        self._tty = (
            tty
            if tty is not None
            else bool(getattr(self._stream, "isatty", lambda: False)())
        )
        # A disabled indicator is a no-op -- it still honours the public API so
        # callers don't need if/else ladders around every sync.
        self._enabled = enabled
        # Default to a NEVER-colour palette so a caller that builds an
        # indicator without wiring in the shared ``Colors`` still gets sane
        # plain-text output -- nothing worse than ANSI codes leaking into
        # captured streams in tests.
        self._colors = colors if colors is not None else Colors(ColorMode.NEVER)

        # Live-trail panel above the spinner. ``0`` disables the panel and
        # ``add_output_line`` falls back to plain ``write()`` semantics.
        # ``-1`` means unbounded -- rare; useful when piping ``-vv`` output
        # through a pager.
        self._output_lines = output_lines
        if output_lines > 0:
            self._panel_buffer: collections.deque[str] = collections.deque(
                maxlen=output_lines,
            )
        elif output_lines < 0:
            self._panel_buffer = collections.deque()
        else:
            # Zero-capacity sentinel so ``maxlen == 0`` is the disabled signal.
            self._panel_buffer = collections.deque(maxlen=0)
        # Number of panel rows physically rendered last tick. The next
        # render walks back this many lines (plus one for the spinner) to
        # erase the previous frame.
        self._panel_visible_lines = 0

        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._active_repo: str | None = None
        self._repo_started_at: float | None = None
        self._last_heartbeat_at: float | None = None
        self._last_line_len = 0
        self._cursor_hidden = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start_repo(self, name: str) -> None:
        """Mark ``name`` as the currently-running repository."""
        if not self._enabled:
            return

        with self._lock:
            self._active_repo = name
            now = time.monotonic()
            self._repo_started_at = now
            self._last_heartbeat_at = now
            # Fresh trail per repo: drop any leftover panel lines from
            # the previous repository so the user only sees activity for
            # the active one.
            self._panel_buffer.clear()

        if self._tty:
            self._ensure_tty_thread()
        else:
            # Emit a single start line so even log-collecting CI shows which
            # repo is in flight. Capital ``Syncing`` matches the permanent
            # ``Synced``/``Timed out`` leading-cap pattern.
            self._emit_line(f"Syncing {name}")

    def stop_repo(self) -> None:
        """Stop showing any active-repo indicator and collapse the panel."""
        if not self._enabled:
            return

        with self._lock:
            self._active_repo = None
            self._repo_started_at = None
            self._last_heartbeat_at = None
            self._panel_buffer.clear()

        if self._tty:
            # Erase the panel + spinner row entirely; the main sync loop
            # then prints the permanent ``✓ Synced ...`` line on a clean
            # row, giving the "trail collapses" effect.
            self._clear_block()

    def add_output_line(self, text: str) -> None:
        """Push streamed subprocess output into the live trail panel.

        ``text`` may contain multiple newline-separated lines (libvcs's
        progress callback delivers chunks, not whole lines). We split,
        drop blank-only fragments, and append each non-blank line to the
        bounded deque. The spinner thread redraws on its own cadence, so
        a chatty subprocess doesn't pace itself against the terminal.

        When the panel is disabled (``output_lines=0``) or the indicator
        is disabled (non-TTY, JSON output, ``--color=never``), fall back
        to :meth:`write` so the bytes still appear -- just without the
        in-place rewriting.
        """
        if not text:
            return
        # The panel only makes sense in a TTY where the spinner thread
        # actually renders the deque. When the indicator is disabled
        # (JSON / NDJSON / colour=never), or running headless (pipe, CI,
        # capsys), or when the panel is explicitly hidden
        # (``output_lines=0``), fall through to the plain ``write()``
        # path so the bytes still reach the user / test capture.
        if not self._enabled or not self._tty or self._panel_buffer.maxlen == 0:
            payload = text if text.endswith("\n") else text + "\n"
            self.write(payload)
            return
        with self._lock:
            for line in text.splitlines():
                stripped = line.rstrip()
                if stripped:
                    self._panel_buffer.append(stripped)

    def repo(self, name: str) -> _RepoContext:
        """Context manager form of :meth:`start_repo` / :meth:`stop_repo`."""
        return _RepoContext(self, name)

    @property
    def enabled(self) -> bool:
        """Whether the indicator is drawing (TTY + human output + colour)."""
        return self._enabled

    def write(self, text: str) -> None:
        """Emit ``text`` without clobbering (or being clobbered by) the spinner.

        When the spinner's TTY loop has drawn a frame, the cursor sits at the
        end of that line and a raw write from another thread would either
        tack onto the spinner line or race the next redraw. We hold the same
        lock the redraw loop does, clear any in-flight line, write, then let
        the next tick redraw cleanly.

        Used by the sync loop to route libvcs log output and libvcs's
        progress callback through a single coordinated channel.
        """
        if not text:
            return
        with self._lock:
            try:
                if self._tty and (self._last_line_len or self._panel_visible_lines):
                    # Walk back over the panel + spinner before printing
                    # so the log record lands on a fresh row instead of
                    # over-writing the trail. The next render redraws the
                    # whole frame from scratch.
                    self._stream.write(_CURSOR_TO_COL0 + _ERASE_LINE)
                    for _ in range(self._panel_visible_lines):
                        self._stream.write("\x1b[1A" + _ERASE_LINE)
                self._stream.write(text)
                self._stream.flush()
                self._last_line_len = 0
                self._panel_visible_lines = 0
            except (OSError, ValueError):
                pass

    def close(self) -> None:
        """Stop the background thread and release the TTY cursor.

        Safe to call multiple times; calls after the first are no-ops. Always
        invoked on interpreter shutdown via :mod:`atexit`.
        """
        if not self._enabled:
            return

        self._stop_event.set()
        thread = self._thread
        self._thread = None
        if thread is not None:
            thread.join(timeout=1.0)
        # Erase the whole frame (panel + spinner) on close, not just the
        # spinner row -- otherwise leftover panel rows linger in
        # scrollback when the indicator is closed mid-repo (e.g. on
        # KeyboardInterrupt before ``stop_repo``).
        self._clear_block()
        if self._cursor_hidden:
            try:
                self._stream.write(_SHOW_CURSOR)
                self._stream.flush()
            except (OSError, ValueError):
                pass
            self._cursor_hidden = False
        _ACTIVE_INDICATORS.discard(self)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _ensure_tty_thread(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return

        if not self._cursor_hidden:
            try:
                self._stream.write(_HIDE_CURSOR)
                self._stream.flush()
            except (OSError, ValueError):
                return
            self._cursor_hidden = True
            _ACTIVE_INDICATORS.add(self)

        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._tty_loop,
            daemon=True,
            name="vcspull-sync-indicator",
        )
        self._thread.start()

    def _tty_loop(self) -> None:
        frames = itertools.cycle(_SPINNER_FRAMES)
        while not self._stop_event.is_set():
            frame = next(frames)
            with self._lock:
                name = self._active_repo
                started = self._repo_started_at
            if name is not None and started is not None:
                elapsed = time.monotonic() - started
                self._render_tty(frame, name, elapsed)
            else:
                self._clear_line()
            self._stop_event.wait(_TTY_REFRESH_INTERVAL)

    def _render_tty(self, frame: str, name: str, elapsed: float) -> None:
        # Colour the spinner cell AND the repo name so the in-flight line
        # matches the visual rhythm of the permanent ``✓ Synced <name>``
        # line emitted on completion (which uses ``colors.info(name)``).
        # The ``Syncing`` verb stays capitalised for the same reason: on
        # screen ``Syncing flume`` reads as a status badge alongside
        # ``Synced fish-shell`` and ``Timed out codex`` -- consistent
        # leading-cap on the status word.
        coloured_frame = self._colors.info(frame)
        coloured_name = self._colors.info(name)
        visible = f"{frame} Syncing {name} ... {elapsed:4.1f}s"
        line = f"{coloured_frame} Syncing {coloured_name} ... {elapsed:4.1f}s"
        pad = max(self._last_line_len - len(visible), 0)
        # Holding the lock around the actual write ensures a concurrent
        # ``write()`` / ``add_output_line()`` (called by the stdout
        # diverter on the main thread) can't begin mid-frame and end up
        # fighting with the ``\r`` redraw. Also: snapshot the panel buffer
        # under the lock so the deque can't mutate mid-render.
        with self._lock:
            panel_lines = list(self._panel_buffer)
        # Cap the rendered panel at its declared height so a concurrent
        # ``add_output_line`` racing the deque can't make us write more
        # rows than ``stop_repo`` will later erase.
        cap = self._panel_buffer.maxlen
        if cap and cap > 0 and len(panel_lines) > cap:
            panel_lines = panel_lines[-cap:]
        new_panel_height = len(panel_lines)

        # Build the frame as a single string so the synchronized-output
        # bracket wraps the whole region atomically. Layout:
        #
        #   <move cursor up to top-of-previous-frame>
        #   <erase + panel row 1>\n
        #   <erase + panel row 2>\n
        #   ...
        #   <erase + spinner line>   (no trailing newline; cursor stays here)
        parts: list[str] = [_SYNC_START]
        if self._panel_visible_lines:
            # Cursor sits at the spinner row; walk up to the first panel
            # row of the previous frame.
            parts.append(f"\x1b[{self._panel_visible_lines}A")
        parts.append(_CURSOR_TO_COL0)
        parts.extend(_ERASE_LINE + panel_line + "\n" for panel_line in panel_lines)
        parts.append(_ERASE_LINE + line + (" " * pad))
        parts.append(_SYNC_END)
        try:
            self._stream.write("".join(parts))
            self._stream.flush()
            # Track the *visible* column count (not the string length with
            # ANSI codes), so the next frame's padding calculation clears
            # exactly the on-screen cells the previous frame occupied.
            self._last_line_len = len(visible)
            self._panel_visible_lines = new_panel_height
        except (OSError, ValueError):
            pass

    def _emit_line(self, line: str) -> None:
        try:
            self._stream.write(line + "\n")
            self._stream.flush()
        except (OSError, ValueError):
            pass

    def _clear_line(self) -> None:
        """Erase only the spinner row (legacy; ``write()`` calls this)."""
        if not self._tty or self._last_line_len == 0:
            return
        try:
            self._stream.write(_CURSOR_TO_COL0 + _ERASE_LINE)
            self._stream.flush()
        except (OSError, ValueError):
            pass
        self._last_line_len = 0

    def _clear_block(self) -> None:
        """Erase the spinner row AND any rendered panel rows above it.

        Used by :meth:`stop_repo` (and :meth:`close`) to collapse the
        live trail so the next ``formatter.emit_text("✓ Synced ...")``
        call lands on a clean row. Without this, the panel rows would
        stay sticky in scrollback and the ``stop_repo`` -> permanent-line
        transition would scroll-leak history.
        """
        if not self._tty:
            return
        try:
            # Walk up panel rows + the spinner row, erasing each.
            self._stream.write(_CURSOR_TO_COL0 + _ERASE_LINE)
            for _ in range(self._panel_visible_lines):
                self._stream.write("\x1b[1A" + _ERASE_LINE)
            self._stream.flush()
        except (OSError, ValueError):
            pass
        self._last_line_len = 0
        self._panel_visible_lines = 0

    def heartbeat(self) -> None:
        """Emit a non-TTY heartbeat if enough time has passed.

        Called from the main sync loop whenever the caller wants to give the
        user a "still working" signal (e.g. between repositories, or during
        the watchdog poll). The TTY path ignores this because the spinner
        refresh already provides the signal.
        """
        if not self._enabled or self._tty:
            return

        with self._lock:
            name = self._active_repo
            started = self._repo_started_at
            last = self._last_heartbeat_at
        if name is None or started is None or last is None:
            return
        now = time.monotonic()
        if now - last < _HEARTBEAT_INTERVAL:
            return

        elapsed = now - started
        self._emit_line(f"... still syncing {name} ({elapsed:.0f}s elapsed)")
        with self._lock:
            self._last_heartbeat_at = now


class _RepoContext:
    """Context-manager helper returned by :meth:`SyncStatusIndicator.repo`."""

    __slots__ = ("_indicator", "_name")

    def __init__(self, indicator: SyncStatusIndicator, name: str) -> None:
        self._indicator = indicator
        self._name = name

    def __enter__(self) -> _RepoContext:
        self._indicator.start_repo(self._name)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: t.Any,
    ) -> None:
        self._indicator.stop_repo()


def build_indicator(
    *,
    human: bool,
    color: str,
    stream: t.TextIO | io.StringIO | None = None,
    tty: bool | None = None,
    colors: Colors | None = None,
    output_lines: int = _DEFAULT_OUTPUT_LINES,
) -> SyncStatusIndicator:
    """Return a ``SyncStatusIndicator`` configured for the current session.

    Disabled when output is non-human (JSON/NDJSON) or when colours are turned
    off -- the latter implies the user wants quiet, machine-friendly output.

    ``output_lines`` controls the live-trail panel above the spinner:
    ``3`` (default) shows the last 3 streamed lines; ``0`` hides the
    panel entirely; ``-1`` is unbounded.
    """
    enabled = human and color != "never"
    # io.StringIO satisfies the TextIO protocol at runtime; tests use this to
    # capture spinner output without wrestling with subclassing.
    concrete_stream: t.Any = stream
    # Resolve the palette from the CLI ``--color`` string when the caller
    # didn't hand us a shared ``Colors`` instance -- keeps ``build_indicator``
    # usable without threading colours through every call site.
    resolved_colors = colors if colors is not None else Colors(get_color_mode(color))
    return SyncStatusIndicator(
        enabled=enabled,
        stream=concrete_stream,
        tty=tty,
        colors=resolved_colors,
        output_lines=output_lines,
    )
