"""Tests for the per-repo sync watchdog and rerun-recipe emitter."""

from __future__ import annotations

import importlib
import json
import signal
import socket
import sys
import textwrap
import time
import types
import typing as t

import pytest

from vcspull._internal import sync_process
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

    from libvcs.sync.git import GitSync
    from libvcs.sync.svn import SvnSync


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


@pytest.fixture
def worker_command(monkeypatch: pytest.MonkeyPatch) -> t.Any:
    """Inject deterministic fresh-interpreter workers at the launch boundary."""

    def install(body: str) -> None:
        prefix = """import datetime, json, os, pathlib, signal, subprocess, sys
fd = int(sys.argv[1])
os.set_inheritable(fd, False)
protocol = os.fdopen(fd, 'w')
def send(frame):
    protocol.write(json.dumps(frame) + '\\n')
    protocol.flush()
request = json.load(sys.stdin)
if request['operation'] == 'inspect':
    send({'event': 'result', 'ok': True,
          'recoveries': request['repo'].get('retained', [])})
else:
"""
        source = prefix + textwrap.indent(textwrap.dedent(body), "    ")
        monkeypatch.setattr(
            sync_process,
            "_worker_command",
            lambda fd: [sys.executable, "-u", "-c", source, str(fd)],
        )

    return install


@pytest.mark.parametrize("human", [False, True])
def test_watchdog_returns_synced_outcome_on_success(
    git_repo: GitSync, human: bool
) -> None:
    """A native worker returns its result without replacing parent streams."""
    stdout, stderr = sys.stdout, sys.stderr
    outcome = _sync_repo_with_watchdog(
        t.cast(
            "t.Any",
            {"name": "ok", "vcs": "git", "path": git_repo.path, "url": git_repo.url},
        ),
        progress_callback=_noop_progress,
        timeout=5,
        is_human=human,
    )
    assert outcome.status == "synced", (outcome.error, outcome.captured_output)
    assert outcome.result is not None and outcome.result.ok
    assert sys.stdout is stdout and sys.stderr is stderr


def test_watchdog_returns_timed_out_on_slow_update(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    worker_command: t.Any,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Sequential timeouts stop a TERM-resistant descendant and retain stdout."""
    child = """import os, pathlib, signal, socket, sys
signal.signal(signal.SIGTERM, signal.SIG_IGN)
root = pathlib.Path(sys.argv[1])
server = socket.socket(socket.AF_UNIX)
server.bind(str(root / 'late.sock'))
server.listen()
print('ready', flush=True)
connection, _ = server.accept()
(root / 'late-write').write_text('too late')
"""
    worker_command(f"""
root = pathlib.Path(request['repo']['path'])
child = subprocess.Popen(
    [sys.executable, '-u', '-c', {child!r}, str(root)], stdout=subprocess.PIPE
)
assert child.stdout.readline().strip() == b'ready'
send({{'event': 'progress', 'text': 'ready',
      'time': datetime.datetime.now().isoformat()}})
signal.pause()
""")
    offset = 0.0
    clock = time.monotonic
    monkeypatch.setattr(
        sync_process, "time", types.SimpleNamespace(monotonic=lambda: clock() + offset)
    )

    def ready(*args: t.Any) -> None:
        nonlocal offset
        offset += 100

    stdout, stderr = sys.stdout, sys.stderr
    for index in range(2):
        directory = tmp_path / str(index)
        directory.mkdir()
        outcome = _sync_repo_with_watchdog(
            t.cast("t.Any", {"name": "blocked", "path": directory}),
            progress_callback=ready,
            timeout=5,
            is_human=False,
        )
        assert outcome.status == "timed_out"
        assert outcome.result is not None
        assert outcome.result.update_state == "unknown"
        assert sys.stdout is stdout and sys.stderr is stderr
        with socket.socket(socket.AF_UNIX) as probe:
            probe.settimeout(0.2)
            with pytest.raises(ConnectionRefusedError):
                probe.connect(str(directory / "late.sock"))
        assert not (directory / "late-write").exists()
        print(json.dumps({"event": "timeout", "index": index}))
    assert len([json.loads(line) for line in capsys.readouterr().out.splitlines()]) == 2


def test_watchdog_preserves_failed_outcome(tmp_path: pathlib.Path) -> None:
    """Native failure messages and ordered result errors cross the worker boundary."""
    outcome = _sync_repo_with_watchdog(
        t.cast(
            "t.Any",
            {
                "name": "missing",
                "vcs": "git",
                "path": tmp_path / "checkout",
                "url": str(tmp_path / "missing"),
            },
        ),
        progress_callback=_noop_progress,
        timeout=5,
        is_human=False,
    )
    assert outcome.status == "failed"
    assert "does not exist" in str(outcome.error)
    assert outcome.result is not None and not outcome.result.ok
    assert outcome.result.errors[0].step == "obtain"


@pytest.mark.parametrize("failed", [False, True])
def test_watchdog_drains_output_and_retains_split_result(
    worker_command: t.Any, failed: bool, tmp_path: pathlib.Path
) -> None:
    """Pipe-sized output cannot hide a split UTF-8 result or its recovery token."""
    from libvcs import RecoveryToken, SyncConflict, SyncResult

    expected = SyncResult(
        recovery=RecoveryToken("owned-é", "git", str(tmp_path / "retained")),
        update_state="completed",
        preservation_state="restored",
    )
    if failed:
        expected.preservation_state = "conflicted"
        expected.conflicts = (SyncConflict("résumé.txt", "text"),)
        expected.add_error("update", "first error")
        expected.add_error("restore", "second error")
    data = sync_process._result_data(expected)
    worker_command(f"""
data = {data!r}
frame = json.dumps(
    {{'event': 'result', 'ok': {not failed!r},
      'error': {"conflict" if failed else None!r}, 'result': data}},
    ensure_ascii=False,
).encode() + b'\\n'
split = frame.index('é'.encode()) + 1
os.write(fd, frame[:split])
sys.stdout.write('O' * 131072)
sys.stdout.flush()
sys.stderr.write('E' * 131072)
sys.stderr.flush()
os.write(fd, frame[split:])
""")
    outcome = _sync_repo_with_watchdog(
        t.cast("t.Any", {"name": "streamed"}),
        progress_callback=_noop_progress,
        timeout=5,
        is_human=False,
    )
    assert outcome.status == ("failed" if failed else "synced")
    assert outcome.result == expected
    assert outcome.captured_output is not None
    assert outcome.captured_output.count("O") == 131072
    assert outcome.captured_output.count("E") == 131072


@pytest.mark.parametrize("fault", ["exit", "no-result", "partial-timeout"])
def test_watchdog_faults_retain_inspection(
    worker_command: t.Any, fault: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Exit/protocol failures retain complete tokens and still inspect owned records."""
    from libvcs import RecoveryToken, SyncResult

    expected = SyncResult(recovery=RecoveryToken("retained", "svn", "/retained/token"))
    data = sync_process._result_data(expected)
    if fault == "exit":
        body = (
            f"send({{'event': 'result', 'ok': True, 'result': {data!r}}})\nos._exit(17)"
        )
    elif fault == "no-result":
        body = "send({'event': 'result', 'ok': True})"
    else:
        body = """
frame = json.dumps({'event': 'progress', 'text': 'ready',
                   'time': datetime.datetime.now().isoformat()}).encode()
os.write(fd, frame + b'\\n' + b'{"event":')
signal.pause()
"""
    worker_command(body)
    offset = 0.0
    clock = time.monotonic
    monkeypatch.setattr(
        sync_process, "time", types.SimpleNamespace(monotonic=lambda: clock() + offset)
    )

    def ready(*args: t.Any) -> None:
        nonlocal offset
        offset += 100

    outcome = _sync_repo_with_watchdog(
        t.cast("t.Any", {"name": "fault", "retained": [data]}),
        progress_callback=ready,
        timeout=5,
        is_human=False,
    )
    assert outcome.status == ("timed_out" if fault == "partial-timeout" else "failed")
    assert outcome.retained_recoveries == (expected,)
    assert outcome.result is not None
    if fault == "exit":
        assert outcome.result.recovery == expected.recovery
    else:
        assert outcome.result.update_state == "unknown"
    if fault == "partial-timeout":
        assert any("incomplete" in error.message for error in outcome.result.errors)


def test_watchdog_missing_result_stays_unknown(worker_command: t.Any) -> None:
    """Worker death cannot fabricate successful or restored state."""
    worker_command("os._exit(7)")
    outcome = _sync_repo_with_watchdog(
        t.cast("t.Any", {"name": "died"}),
        progress_callback=_noop_progress,
        timeout=5,
        is_human=False,
    )
    assert outcome.status == "failed"
    assert outcome.result is not None
    assert outcome.result.update_state == "unknown"
    assert outcome.result.preservation_state == "unknown"


@pytest.mark.parametrize("worker_event", [False, True])
def test_watchdog_propagates_interrupt_during_inspection(
    monkeypatch: pytest.MonkeyPatch, worker_event: bool
) -> None:
    """Inspection cannot swallow either a parent or worker interrupt."""
    exchanges = iter(
        [
            sync_process._Exchange(None, "", True, -signal.SIGTERM, False, None),
            sync_process._Exchange(
                {"event": "interrupted"} if worker_event else None,
                "",
                False,
                0,
                not worker_event,
                None,
            ),
        ]
    )
    # The native signal test covers termination; isolate the two-exchange decision.
    monkeypatch.setattr(sync_process, "_exchange", lambda *a, **kw: next(exchanges))
    with pytest.raises(sync_process.SyncInterrupted) as caught:
        _sync_repo_with_watchdog(
            t.cast("t.Any", {"name": "interrupted-inspection"}),
            progress_callback=_noop_progress,
            timeout=5,
            is_human=False,
        )
    assert caught.value.outcome.result is not None
    assert caught.value.outcome.result.update_state == "unknown"
    assert any(
        error.step == "recovery-inspection"
        for error in caught.value.outcome.result.errors
    )


def test_recovery_inspection_finds_svn_after_source_loss(svn_repo: SvnSync) -> None:
    """The subprocess inspector retains SVN's source-independent recovery scope."""
    import shutil

    from libvcs import SyncPolicy, SyncTarget

    (svn_repo.path / "local").write_text("retained\n")
    result = svn_repo.update_repo(
        target=SyncTarget(rev=svn_repo.get_position().revision),
        policy=SyncPolicy(dirty="preserve"),
    )
    assert result.ok, result.errors
    assert result.recovery is not None
    shutil.rmtree(svn_repo.path)
    exchange = sync_process._exchange(
        {
            "operation": "inspect",
            "repo": {"vcs": "svn", "path": str(svn_repo.path), "url": svn_repo.url},
        },
        timeout=1,
        progress_callback=_noop_progress,
        is_human=False,
    )
    assert not exchange.timed_out
    assert exchange.returncode == 0
    assert exchange.terminal is not None
    assert exchange.terminal["recoveries"][0]["recovery"]["id"] == result.recovery.id
    assert not svn_repo.path.exists()


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
    worker_command: t.Any,
) -> None:
    """An interrupted worker stops the batch after process cleanup."""
    worker_command("send({'event': 'interrupted'})")
    with pytest.raises(KeyboardInterrupt):
        _sync_repo_with_watchdog(
            t.cast("t.Any", {"name": "interrupted"}),
            progress_callback=_noop_progress,
            timeout=5,
            is_human=True,
        )


@pytest.fixture
def _fake_sigint_escalation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Convert ``_exit_on_sigint`` into ``SystemExit(130)`` for in-process tests.

    The real implementation re-raises SIGINT under ``SIG_DFL`` so the
    parent shell sees ``WIFSIGNALED(SIGINT)``. Running that in-process
    would kill the pytest runner. Unit tests that only want to verify the
    control flow through the ``except KeyboardInterrupt`` clauses opt in
    to this fixture; the real signal semantics live in a subprocess test
    (``tests/cli/test_sync_sigint.py``).
    """

    def _fake() -> t.NoReturn:
        raise SystemExit(130)

    monkeypatch.setattr(sync_module, "_exit_on_sigint", _fake)


def test_sync_handles_keyboard_interrupt_during_config_load(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    _fake_sigint_escalation: None,
) -> None:
    """Ctrl-C during pre-loop work (e.g. YAML parse) exits cleanly with 130.

    Regression for the observed traceback where a KeyboardInterrupt raised
    inside ``load_configs`` escaped all the way through ``cli.sync`` and
    out to the top-level ``sys.exit`` as an unhandled exception, dumping
    the entire yaml parser stack to the terminal. The outer ``sync()``
    entry point must catch the interrupt, emit a short notice, and exit
    via ``_exit_on_sigint()``. The ``_fake_sigint_escalation`` fixture
    swaps the real ``_exit_on_sigint`` (which re-raises SIGINT under
    ``SIG_DFL`` and would kill the test runner) for a plain
    ``SystemExit(130)``.
    """
    from vcspull.cli.sync import sync as sync_fn

    def _raising_load(*_args: t.Any, **_kwargs: t.Any) -> t.Any:
        raise KeyboardInterrupt

    monkeypatch.setattr(sync_module, "load_configs", _raising_load)

    with pytest.raises(SystemExit) as excinfo:
        sync_fn(
            repo_patterns=[],
            config=None,
            workspace_root=None,
            dry_run=False,
            output_json=False,
            output_ndjson=False,
            color="never",
            exit_on_error=False,
            show_unchanged=False,
            summary_only=False,
            long_view=False,
            relative_paths=False,
            fetch=False,
            offline=False,
            verbosity=0,
            sync_all=True,
        )

    assert excinfo.value.code == 130
    err = capsys.readouterr().err
    assert "Interrupted by user." in err


def test_exit_on_sigint_posix_installs_sig_dfl_and_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``_exit_on_sigint`` installs SIG_IGN, then SIG_DFL, then self-SIGINTs.

    Locks in the order from git's ``sigchain.h:20-34`` pattern and proves
    the helper would make the kernel deliver SIGINT to ourselves -- which
    is what the parent shell's ``WIFSIGNALED`` check keys off to abort a
    ``;`` chain. We can't let ``raise_signal`` actually fire (it would
    take pytest down with us), so we intercept both stdlib calls and
    assert on the recorded sequence.
    """
    monkeypatch.setattr(sys, "platform", "linux")

    calls: list[tuple[str, t.Any, t.Any]] = []

    def _fake_signal(sig: int, handler: t.Any) -> t.Any:
        calls.append(("signal", sig, handler))
        return None

    def _fake_raise(sig: int) -> None:
        calls.append(("raise_signal", sig, None))
        # Simulate ``SIG_DFL`` termination by exiting -- the real call
        # never returns on POSIX; here we just prove the ordering.
        raise SystemExit(130)

    monkeypatch.setattr(signal, "signal", _fake_signal)
    monkeypatch.setattr(signal, "raise_signal", _fake_raise)

    with pytest.raises(SystemExit) as excinfo:
        sync_module._exit_on_sigint()

    assert excinfo.value.code == 130
    assert calls == [
        ("signal", signal.SIGINT, signal.SIG_IGN),
        ("signal", signal.SIGINT, signal.SIG_DFL),
        ("raise_signal", signal.SIGINT, None),
    ]


def test_exit_on_sigint_windows_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Windows falls back to ``SystemExit(130)`` without touching signals.

    ``signal.raise_signal(SIGINT)`` under ``SIG_DFL`` on Windows raises
    ``KeyboardInterrupt`` back at the caller instead of terminating, so
    the POSIX re-raise would get us nowhere. The helper must short-circuit
    on ``sys.platform == "win32"`` and leave the signal handlers
    completely untouched.
    """
    monkeypatch.setattr(sys, "platform", "win32")

    def _fail_if_called(sig: int) -> None:
        msg = "raise_signal must not be called on the Windows fallback path"
        raise AssertionError(msg)

    def _fail_signal(sig: int, handler: t.Any) -> t.Any:
        msg = "signal.signal must not be called on the Windows fallback path"
        raise AssertionError(msg)

    monkeypatch.setattr(signal, "raise_signal", _fail_if_called)
    monkeypatch.setattr(signal, "signal", _fail_signal)

    with pytest.raises(SystemExit) as excinfo:
        sync_module._exit_on_sigint()

    assert excinfo.value.code == 130


def test_resolve_panel_lines_prefers_cli_flag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``--panel-lines N`` wins over the env var and the default."""
    from vcspull.cli.sync import _resolve_panel_lines

    monkeypatch.setenv("VCSPULL_PROGRESS_LINES", "9")
    assert _resolve_panel_lines(5) == 5


def test_resolve_panel_lines_falls_back_to_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Without a flag, ``VCSPULL_PROGRESS_LINES`` is honoured."""
    from vcspull.cli.sync import _resolve_panel_lines

    monkeypatch.setenv("VCSPULL_PROGRESS_LINES", "5")
    assert _resolve_panel_lines(None) == 5


def test_resolve_panel_lines_accepts_zero_and_negative(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``0`` (hide panel) and ``-1`` (unbounded) must round-trip cleanly."""
    from vcspull.cli.sync import _resolve_panel_lines

    monkeypatch.delenv("VCSPULL_PROGRESS_LINES", raising=False)
    assert _resolve_panel_lines(0) == 0
    assert _resolve_panel_lines(-1) == -1


def test_resolve_panel_lines_default_is_three(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Default panel height matches tmuxp's ``DEFAULT_OUTPUT_LINES``."""
    from vcspull.cli.sync import _resolve_panel_lines

    monkeypatch.delenv("VCSPULL_PROGRESS_LINES", raising=False)
    assert _resolve_panel_lines(None) == 3


def test_resolve_panel_lines_ignores_bogus_env_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A non-integer env value is logged and ignored; default applies."""
    from vcspull.cli.sync import _resolve_panel_lines

    monkeypatch.setenv("VCSPULL_PROGRESS_LINES", "many")
    assert _resolve_panel_lines(None) == 3
