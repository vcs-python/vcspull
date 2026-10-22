"""Own CLI sync workers, native descendants, and streamed output."""

from __future__ import annotations

import codecs
import contextlib
import dataclasses
import datetime
import json
import logging
import os
import pathlib
import selectors
import signal
import subprocess
import sys
import time
import typing as t
from collections.abc import Callable, Mapping

from libvcs import RecoveryToken, SyncConflict, SyncResult
from libvcs.sync.git import GitRemote
from libvcs.sync.hg import HgRemote

from vcspull._internal.sync import sync_result_data


@dataclasses.dataclass
class SyncOutcome:
    """Keep completed results separate from forced termination and inspection."""

    status: t.Literal["synced", "failed", "timed_out"]
    captured_output: str | None = None
    error: BaseException | None = None
    duration: float = 0.0
    result: SyncResult | None = None
    retained_recoveries: tuple[SyncResult, ...] = ()
    worktree: dict[str, t.Any] | None = None


class SyncInterrupted(KeyboardInterrupt):
    """Carry retained recovery information through CLI interrupt cleanup."""

    def __init__(self, outcome: SyncOutcome) -> None:
        self.outcome = outcome
        super().__init__()


@dataclasses.dataclass
class _Exchange:
    terminal: dict[str, t.Any] | None
    output: str
    timed_out: bool
    returncode: int | None
    interrupted: bool
    protocol_error: str | None


def _result_from_data(data: dict[str, t.Any]) -> SyncResult:
    if (
        type(data["ok"]) is not bool
        or data["update_state"] not in ("not-started", "completed", "failed", "unknown")
        or data["preservation_state"]
        not in ("not-needed", "saved", "restored", "conflicted", "failed", "unknown")
    ):
        message = "invalid sync result state"
        raise ValueError(message)
    result = SyncResult(
        ok=data["ok"],
        update_state=data["update_state"],
        preservation_state=data["preservation_state"],
        recovery=RecoveryToken(**data["recovery"]) if data["recovery"] else None,
        conflicts=tuple(SyncConflict(**item) for item in data["conflicts"]),
    )
    for error in data["errors"]:
        result.add_error(error["step"], error["message"])
    return result


def _result_data(result: SyncResult) -> dict[str, t.Any]:
    return {"ok": result.ok, **sync_result_data(result)}


def _worker_command(control_fd: int) -> list[str]:
    return [
        sys.executable,
        "-u",
        "-c",
        "from vcspull._internal.sync_process import _main; _main()",
        str(control_fd),
    ]


def _json_default(value: t.Any) -> str | dict[str, t.Any]:
    if isinstance(value, os.PathLike):
        return str(os.fspath(value))
    if isinstance(value, (GitRemote, HgRemote)):
        return {"fetch_url": value.fetch_url, "push_url": value.push_url}
    message = f"sync request contains unsupported {type(value).__name__}"
    raise TypeError(message)


def _stop_process(process: subprocess.Popen[bytes]) -> None:
    """Stop the owned session before reaping its leader or returning to the batch."""
    with contextlib.suppress(ProcessLookupError):
        os.killpg(process.pid, signal.SIGTERM)
    try:
        process.wait(timeout=0.2)
    except subprocess.TimeoutExpired:
        pass
    finally:
        # Descendants can outlive a leader that handles TERM promptly.
        with contextlib.suppress(ProcessLookupError):
            os.killpg(process.pid, signal.SIGKILL)
    try:
        process.wait(timeout=0.5)
    except subprocess.TimeoutExpired as error:
        message = "sync worker could not be stopped; repository state is unknown"
        raise RuntimeError(message) from error


def _exchange(
    request: dict[str, t.Any],
    *,
    timeout: float,
    progress_callback: Callable[[str, datetime.datetime], None],
    is_human: bool,
) -> _Exchange:
    payload = memoryview(json.dumps(request, default=_json_default).encode())
    read_fd, write_fd = os.pipe()
    control = bytearray()
    captured: list[str] = []
    terminal: dict[str, t.Any] | None = None
    timed_out = False
    stopped = False
    interrupted = False
    protocol_error: str | None = None
    deadline = time.monotonic() + timeout
    environment = {
        **os.environ,
        "PYTHONPATH": os.pathsep.join(
            part
            for part in (
                str(pathlib.Path(__file__).resolve().parents[2]),
                os.environ.get("PYTHONPATH", ""),
            )
            if part
        ),
    }
    try:
        process = subprocess.Popen(
            _worker_command(write_fd),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
            pass_fds=(write_fd,),
            env=environment,
        )
    except BaseException:
        os.close(read_fd)
        raise
    finally:
        os.close(write_fd)
    assert process.stdin is not None
    assert process.stdout is not None
    assert process.stderr is not None
    decoders = {
        "stdout": codecs.getincrementaldecoder("utf-8")("replace"),
        "stderr": codecs.getincrementaldecoder("utf-8")("replace"),
    }

    def accept(frame: dict[str, t.Any]) -> None:
        nonlocal terminal
        event = frame["event"]
        if event == "progress":
            if not timed_out:
                progress_callback(
                    frame["text"], datetime.datetime.fromisoformat(frame["time"])
                )
        elif event == "log":
            record = logging.makeLogRecord(frame["record"])
            logger: logging.Logger | None = logging.getLogger(record.name)
            assert logger is not None
            if is_human and logger.isEnabledFor(record.levelno):
                logger.handle(record)
            elif not is_human:
                if record.levelno >= logging.WARNING:
                    captured.append(record.getMessage() + "\n")
                while logger is not None:
                    for handler in logger.handlers:
                        if (
                            isinstance(handler, logging.FileHandler)
                            and record.levelno >= handler.level
                        ):
                            handler.handle(record)
                    logger = logger.parent if logger.propagate else None
        elif event in {"result", "interrupted"}:
            if terminal is not None:
                message = "sync worker sent more than one terminal result"
                raise ValueError(message)
            terminal = frame
        else:
            message = f"unknown sync worker event: {event}"
            raise ValueError(message)

    try:
        with selectors.DefaultSelector() as selector:
            for stream, name in (
                (read_fd, "control"),
                (process.stdout, "stdout"),
                (process.stderr, "stderr"),
                (process.stdin, "request"),
            ):
                descriptor = stream if isinstance(stream, int) else stream.fileno()
                os.set_blocking(descriptor, False)
                selector.register(
                    stream,
                    selectors.EVENT_WRITE
                    if name == "request"
                    else selectors.EVENT_READ,
                    name,
                )
            while selector.get_map():
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    if stopped:
                        message = (
                            "sync descendants retained output pipes after termination"
                        )
                        raise RuntimeError(message)
                    timed_out = True
                    _stop_process(process)
                    stopped = True
                    deadline = time.monotonic() + 0.2
                    remaining = 0.2
                for key, _ in selector.select(remaining):
                    name = key.data
                    if name == "request":
                        try:
                            count = os.write(key.fd, payload)
                        except BrokenPipeError:
                            payload = memoryview(b"")
                        else:
                            payload = payload[count:]
                        if not payload:
                            selector.unregister(key.fileobj)
                            process.stdin.close()
                        continue
                    chunk = os.read(key.fd, 65536)
                    if not chunk:
                        selector.unregister(key.fileobj)
                    if name == "control":
                        control.extend(chunk)
                        while b"\n" in control:
                            line, _, rest = control.partition(b"\n")
                            control[:] = rest
                            try:
                                accept(json.loads(line))
                            except (ValueError, TypeError, KeyError) as error:
                                protocol_error = str(error)
                        if not chunk and control:
                            protocol_error = (
                                "sync worker ended with an incomplete result frame"
                            )
                        if protocol_error and not stopped:
                            _stop_process(process)
                            stopped = True
                            deadline = time.monotonic() + 0.2
                    else:
                        output = decoders[name].decode(chunk, final=not chunk)
                        if output:
                            captured.append(output)
                            if is_human:
                                progress_callback(
                                    output, datetime.datetime.now(datetime.timezone.utc)
                                )
            if not stopped:
                try:
                    process.wait(timeout=max(0, deadline - time.monotonic()))
                except subprocess.TimeoutExpired:
                    timed_out = True
    except KeyboardInterrupt:
        interrupted = True
    finally:
        try:
            if not stopped:
                _stop_process(process)
        finally:
            os.close(read_fd)
            process.stdin.close()
            process.stdout.close()
            process.stderr.close()
    return _Exchange(
        terminal,
        "".join(captured),
        timed_out,
        process.returncode,
        interrupted,
        protocol_error,
    )


def run_sync_process(
    repo: Mapping[str, t.Any],
    *,
    progress_callback: Callable[[str, datetime.datetime], None],
    timeout: float,
    is_human: bool,
    yes: bool = False,
    worktree: Mapping[str, t.Any] | None = None,
) -> SyncOutcome:
    """Run one owned mutation process; inspect retained records after a timeout."""
    if os.name != "posix":
        message = "bounded CLI sync requires POSIX process-group ownership"
        raise RuntimeError(message)
    started = time.monotonic()
    exchange = _exchange(
        {
            "repo": dict(repo),
            "yes": yes,
            "operation": "worktree" if worktree is not None else "sync",
            "worktree": dict(worktree) if worktree is not None else None,
        },
        timeout=timeout,
        progress_callback=progress_callback,
        is_human=is_human,
    )
    terminal = exchange.terminal or {}
    interrupted = exchange.interrupted or terminal.get("event") == "interrupted"
    diagnostics = []
    result = None
    if terminal.get("result") is not None:
        try:
            result = _result_from_data(terminal["result"])
        except (TypeError, ValueError, KeyError) as error:
            diagnostics.append(f"invalid sync result: {error}")
    if exchange.protocol_error:
        diagnostics.append(exchange.protocol_error)
    if exchange.returncode != 0:
        diagnostics.append(f"sync worker exited with status {exchange.returncode}")
    if terminal.get("error"):
        diagnostics.append(str(terminal["error"]))
    if result is None:
        diagnostics.append("sync worker did not report a complete result")
    successful = (
        not interrupted
        and not exchange.timed_out
        and not diagnostics
        and terminal.get("ok") is True
        and result is not None
        and result.ok
    )
    retained: tuple[SyncResult, ...] = ()
    if (
        interrupted
        or exchange.timed_out
        or result is None
        or exchange.protocol_error
        or exchange.returncode != 0
    ):
        if result is None:
            result = SyncResult(update_state="unknown", preservation_state="unknown")
        for message in diagnostics:
            result.add_error("worker", message)
        if interrupted or exchange.timed_out:
            result.add_error(
                "interrupt" if interrupted else "timeout", "sync worker stopped"
            )
        inspection = _exchange(
            {"repo": dict(repo), "operation": "inspect"},
            timeout=1.0,
            progress_callback=lambda *args: None,
            is_human=False,
        )
        report = inspection.terminal or {}
        interrupted = (
            interrupted
            or inspection.interrupted
            or report.get("event") == "interrupted"
        )
        if (
            inspection.timed_out
            or inspection.interrupted
            or inspection.returncode != 0
            or inspection.protocol_error
        ):
            result.add_error(
                "recovery-inspection", "retained recovery inspection did not complete"
            )
        elif report.get("error"):
            result.add_error("recovery-inspection", report["error"])
        elif report.get("ok") is not True:
            result.add_error(
                "recovery-inspection", "inspection returned no complete result"
            )
        else:
            try:
                retained = tuple(
                    _result_from_data(item) for item in report["recoveries"]
                )
            except (TypeError, ValueError, KeyError) as error:
                result.add_error("recovery-inspection", str(error))
    status: t.Literal["synced", "failed", "timed_out"] = (
        "timed_out" if exchange.timed_out else "synced" if successful else "failed"
    )
    outcome = SyncOutcome(
        status=status,
        captured_output=exchange.output if not is_human else None,
        error=RuntimeError("; ".join(diagnostics) or "sync worker failed")
        if status == "failed"
        else None,
        duration=time.monotonic() - started,
        result=result,
        retained_recoveries=retained,
        worktree=terminal.get("worktree"),
    )
    if interrupted:
        raise SyncInterrupted(outcome)
    return outcome


def _main() -> None:
    descriptor = int(sys.argv[1])
    os.set_inheritable(descriptor, False)
    with os.fdopen(descriptor, "w", encoding="utf-8") as protocol:

        def send(data: dict[str, t.Any]) -> None:
            protocol.write(json.dumps(data) + "\n")
            protocol.flush()

        class LogHandler(logging.Handler):
            def emit(self, record: logging.LogRecord) -> None:
                data = {
                    key: value
                    for key, value in record.__dict__.items()
                    if value is None or isinstance(value, (str, int, float, bool))
                }
                data.update(msg=record.getMessage(), args=None, exc_info=None)
                send({"event": "log", "record": data})

        for name in ("libvcs", "vcspull"):
            logger = logging.getLogger(name)
            logger.handlers[:] = [LogHandler()]
            logger.setLevel(logging.DEBUG)
            logger.propagate = False
        request = json.load(sys.stdin)
        try:
            from vcspull.cli.sync import SyncFailedError, guess_vcs, update_repo

            if request["operation"] == "worktree":
                from vcspull._internal.worktree_sync import (
                    WorktreeAction,
                    sync_worktree,
                    worktree_entry_data,
                )

                settings = request["worktree"]
                entry = sync_worktree(
                    pathlib.Path(settings["repo_path"]),
                    settings["config"],
                    pathlib.Path(settings["workspace_root"]),
                    allow_discard=request["yes"],
                    repo_config=settings["repo_config"],
                )
                worktree_result = (
                    entry.result if entry.result is not None else SyncResult()
                )
                if (
                    entry.action in (WorktreeAction.ERROR, WorktreeAction.BLOCKED)
                    and worktree_result.ok
                ):
                    worktree_result.add_error(
                        "worktree", entry.error or entry.detail or "worktree failed"
                    )
                send(
                    {
                        "event": "result",
                        "ok": worktree_result.ok,
                        "error": entry.error,
                        "result": _result_data(worktree_result),
                        "worktree": worktree_entry_data(entry),
                    }
                )
                return
            if request["operation"] == "inspect":
                from vcspull._internal.sync import create_sync_project

                repo = request["repo"]
                vcs = repo.get("vcs") or guess_vcs(
                    repo.get("url", repo.get("pip_url", ""))
                )
                if vcs is None:
                    recoveries: tuple[SyncResult, ...] = ()
                else:
                    recoveries = create_sync_project(repo, vcs=vcs).list_recoveries()
                send(
                    {
                        "event": "result",
                        "ok": True,
                        "recoveries": [_result_data(item) for item in recoveries],
                    }
                )
                return
            execution = update_repo(
                request["repo"],
                progress_callback=lambda output, timestamp: send(
                    {"event": "progress", "text": output, "time": timestamp.isoformat()}
                ),
                yes=request["yes"],
            )
            send(
                {
                    "event": "result",
                    "ok": True,
                    "result": _result_data(execution.result),
                }
            )
        except KeyboardInterrupt:
            send({"event": "interrupted"})
        except BaseException as error:  # noqa: BLE001 - report failures across the process boundary
            result = error.result if isinstance(error, SyncFailedError) else None
            send(
                {
                    "event": "result",
                    "ok": False,
                    "error": str(error),
                    "result": _result_data(result) if result is not None else None,
                }
            )


if __name__ == "__main__":
    _main()
