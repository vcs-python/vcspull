"""Tests for the per-repo sync watchdog and rerun-recipe emitter."""

from __future__ import annotations

import importlib
import time
import typing as t

import pytest

from vcspull.cli._colors import ColorMode, Colors
from vcspull.cli._output import OutputFormatter, OutputMode
from vcspull.cli.sync import (
    _DEFAULT_REPO_TIMEOUT_SECONDS,
    _emit_rerun_recipe,
    _resolve_repo_timeout,
    _sync_repo_with_watchdog,
    _TimedOutRepo,
)

# ``vcspull.cli.__init__`` re-exports the ``sync`` function, which shadows the
# submodule of the same name in normal attribute access. Grab the module
# object directly so monkeypatch.setattr can install stubs on it.
sync_module = importlib.import_module("vcspull.cli.sync")

if t.TYPE_CHECKING:
    import pathlib


def _noop_progress(output: str, timestamp: t.Any) -> None:
    """Swallow libvcs progress output in tests."""
    return


def test_resolve_repo_timeout_prefers_cli_flag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CLI ``--timeout`` should win over the env var and the default."""
    monkeypatch.setenv("VCSPULL_SYNC_TIMEOUT_SECONDS", "99")

    assert _resolve_repo_timeout(5) == 5


def test_resolve_repo_timeout_falls_back_to_env_var(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Without a CLI flag, ``VCSPULL_SYNC_TIMEOUT_SECONDS`` takes over."""
    monkeypatch.setenv("VCSPULL_SYNC_TIMEOUT_SECONDS", "42")

    assert _resolve_repo_timeout(None) == 42


def test_resolve_repo_timeout_uses_default_when_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The module-level default applies when neither override is present."""
    monkeypatch.delenv("VCSPULL_SYNC_TIMEOUT_SECONDS", raising=False)

    assert _resolve_repo_timeout(None) == _DEFAULT_REPO_TIMEOUT_SECONDS


def test_resolve_repo_timeout_ignores_bogus_env_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A non-integer env value is logged and ignored; default applies."""
    monkeypatch.setenv("VCSPULL_SYNC_TIMEOUT_SECONDS", "forever")

    assert _resolve_repo_timeout(None) == _DEFAULT_REPO_TIMEOUT_SECONDS


def test_watchdog_returns_synced_outcome_on_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A fast ``update_repo`` returns ``status='synced'`` with no error."""
    # Replace update_repo with a stub so we can exercise the watchdog without
    # touching libvcs. The stub is fast, so the timeout branch never fires.
    calls: list[dict[str, t.Any]] = []

    def _stub_update_repo(repo: dict[str, t.Any], *, progress_callback: t.Any) -> None:
        calls.append(repo)

    monkeypatch.setattr(sync_module, "update_repo", _stub_update_repo)

    outcome = _sync_repo_with_watchdog(
        t.cast("t.Any", {"name": "ok"}),
        progress_callback=_noop_progress,
        timeout=5,
        is_human=True,
    )

    assert outcome.status == "synced"
    assert outcome.error is None
    assert calls == [{"name": "ok"}]


def test_watchdog_returns_timed_out_on_slow_update(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A slow ``update_repo`` is abandoned with ``status='timed_out'``."""

    def _slow_update_repo(repo: dict[str, t.Any], *, progress_callback: t.Any) -> None:
        # Far longer than the 0.2 s timeout below -- the watchdog must fire.
        time.sleep(10)

    monkeypatch.setattr(sync_module, "update_repo", _slow_update_repo)

    started = time.monotonic()
    outcome = _sync_repo_with_watchdog(
        t.cast("t.Any", {"name": "slow"}),
        progress_callback=_noop_progress,
        timeout=1,
        is_human=True,
    )
    elapsed = time.monotonic() - started

    assert outcome.status == "timed_out"
    # The watchdog should fire near the timeout -- give generous slack so CI
    # scheduling jitter doesn't flake the test.
    assert elapsed < 5.0
    assert outcome.duration >= 0.5


def test_watchdog_preserves_failed_outcome(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Synchronous exceptions from ``update_repo`` surface as ``failed``."""

    class _Boom(RuntimeError):
        """Sentinel used to trace exception propagation."""

    def _raising_update_repo(
        repo: dict[str, t.Any], *, progress_callback: t.Any
    ) -> None:
        msg = "remote exploded"
        raise _Boom(msg)

    monkeypatch.setattr(sync_module, "update_repo", _raising_update_repo)

    outcome = _sync_repo_with_watchdog(
        t.cast("t.Any", {"name": "boom"}),
        progress_callback=_noop_progress,
        timeout=5,
        is_human=True,
    )

    assert outcome.status == "failed"
    assert isinstance(outcome.error, _Boom)
    assert "remote exploded" in str(outcome.error)


def test_rerun_recipe_emits_one_line_per_workspace(
    capsys: pytest.CaptureFixture[str],
    tmp_path: pathlib.Path,
) -> None:
    """Repositories are grouped by workspace root in the suggested rerun."""
    formatter = OutputFormatter(OutputMode.HUMAN)
    colors = Colors(ColorMode.NEVER)

    rust_workspace = tmp_path / "rust"
    otel_workspace = tmp_path / "otel"
    rust_workspace.mkdir()
    otel_workspace.mkdir()

    timed_out = [
        _TimedOutRepo(
            name="codex",
            path=str(rust_workspace / "codex"),
            workspace_root=str(rust_workspace),
            duration=10.2,
        ),
        _TimedOutRepo(
            name="rust",
            path=str(rust_workspace / "rust"),
            workspace_root=str(rust_workspace),
            duration=10.5,
        ),
        _TimedOutRepo(
            name="opentelemetry-rust",
            path=str(otel_workspace / "opentelemetry-rust"),
            workspace_root=str(otel_workspace),
            duration=10.1,
        ),
    ]

    _emit_rerun_recipe(
        formatter,
        colors,
        timed_out_repos=timed_out,
        timeout=10,
    )
    formatter.finalize()

    captured = capsys.readouterr().out
    # One rerun command per distinct workspace root, with the repo names
    # appended as positional args -- this is what the user copy-pastes.
    assert "vcspull sync --workspace" in captured
    assert "codex" in captured and "rust" in captured
    assert "opentelemetry-rust" in captured
    # Suggest 10x the current timeout, clamped to 120 s minimum.
    assert "--timeout 120" in captured
    # Include a verbose-logging variant for diagnosis.
    assert "-vv" in captured
    # Include a manual git probe so the user can isolate the failure mode.
    assert "GIT_TERMINAL_PROMPT=0" in captured
    assert "git -C" in captured
    # The rerun recipe itself must stay emoji-free -- plain ASCII markers
    # only. Clock/stopwatch emoji had shipped as the prior prefix; guard it.
    assert "⏱" not in captured


def test_rerun_recipe_is_noop_when_no_timeouts(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A clean run with no timeouts emits nothing extra."""
    formatter = OutputFormatter(OutputMode.HUMAN)
    colors = Colors(ColorMode.NEVER)

    _emit_rerun_recipe(
        formatter,
        colors,
        timed_out_repos=[],
        timeout=10,
    )
    formatter.finalize()

    captured = capsys.readouterr().out
    assert "Timed out" not in captured
    assert "vcspull sync" not in captured


def test_rerun_recipe_scales_timeout_suggestion(
    capsys: pytest.CaptureFixture[str],
    tmp_path: pathlib.Path,
) -> None:
    """When the user already passed a long timeout, we suggest 10x it."""
    formatter = OutputFormatter(OutputMode.HUMAN)
    colors = Colors(ColorMode.NEVER)

    _emit_rerun_recipe(
        formatter,
        colors,
        timed_out_repos=[
            _TimedOutRepo(
                name="huge",
                path=str(tmp_path / "huge"),
                workspace_root=str(tmp_path),
                duration=60.0,
            ),
        ],
        timeout=30,
    )
    formatter.finalize()

    captured = capsys.readouterr().out
    # max(120, 30 * 10) = 300
    assert "--timeout 300" in captured


def test_watchdog_propagates_keyboard_interrupt_from_worker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A ``KeyboardInterrupt`` in the worker bubbles out of the watchdog.

    ``_sync_repo_with_watchdog`` runs the libvcs call on a daemon thread. If
    the main thread receives Ctrl-C (normal case) it never reaches this code
    path, but a worker-side ``KeyboardInterrupt`` (rare, via
    ``PyThreadState_SetAsyncExc``) must NOT be laundered into a per-repo
    "failed" outcome -- it has to propagate so the outer loop can tear the
    batch down cleanly. This locks down the narrowed catch (``Exception``,
    not ``BaseException``).
    """

    def _raising(repo: dict[str, t.Any], *, progress_callback: t.Any) -> None:
        raise KeyboardInterrupt

    monkeypatch.setattr(sync_module, "update_repo", _raising)

    with pytest.raises(KeyboardInterrupt):
        _sync_repo_with_watchdog(
            t.cast("t.Any", {"name": "kb"}),
            progress_callback=_noop_progress,
            timeout=5,
            is_human=True,
        )
