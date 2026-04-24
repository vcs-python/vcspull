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
import io
import itertools
import logging
import sys
import threading
import time
import typing as t

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

        if self._tty:
            self._ensure_tty_thread()
        else:
            # Emit a single start line so even log-collecting CI shows which
            # repo is in flight.
            self._emit_line(f"syncing {name}")

    def stop_repo(self) -> None:
        """Stop showing any active-repo indicator."""
        if not self._enabled:
            return

        with self._lock:
            self._active_repo = None
            self._repo_started_at = None
            self._last_heartbeat_at = None

        if self._tty:
            self._clear_line()

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
                if self._tty and self._last_line_len:
                    self._stream.write(_CURSOR_TO_COL0 + _ERASE_LINE)
                self._stream.write(text)
                self._stream.flush()
                self._last_line_len = 0
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
        self._clear_line()
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
        line = f"{frame} syncing {name} ... {elapsed:4.1f}s"
        pad = max(self._last_line_len - len(line), 0)
        # Holding the lock around the actual write ensures a concurrent
        # ``write()`` (called by the stdout diverter on the main thread)
        # can't begin mid-frame and end up fighting with the ``\r`` redraw.
        with self._lock:
            try:
                self._stream.write(
                    _SYNC_START + _CURSOR_TO_COL0 + line + (" " * pad) + _SYNC_END,
                )
                self._stream.flush()
                self._last_line_len = len(line)
            except (OSError, ValueError):
                pass

    def _emit_line(self, line: str) -> None:
        try:
            self._stream.write(line + "\n")
            self._stream.flush()
        except (OSError, ValueError):
            pass

    def _clear_line(self) -> None:
        if not self._tty or self._last_line_len == 0:
            return
        try:
            self._stream.write(_CURSOR_TO_COL0 + _ERASE_LINE)
            self._stream.flush()
        except (OSError, ValueError):
            pass
        self._last_line_len = 0

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
) -> SyncStatusIndicator:
    """Return a ``SyncStatusIndicator`` configured for the current session.

    Disabled when output is non-human (JSON/NDJSON) or when colours are turned
    off -- the latter implies the user wants quiet, machine-friendly output.
    """
    enabled = human and color != "never"
    # io.StringIO satisfies the TextIO protocol at runtime; tests use this to
    # capture spinner output without wrestling with subclassing.
    concrete_stream: t.Any = stream
    return SyncStatusIndicator(
        enabled=enabled,
        stream=concrete_stream,
        tty=tty,
    )
