"""Subprocess-based tests asserting real ``WIFSIGNALED(SIGINT)`` termination."""

from __future__ import annotations

import contextlib
import importlib.util
import json
import os
import pathlib
import shlex
import signal
import socket
import subprocess
import sys
import typing as t

import pytest

if t.TYPE_CHECKING:
    from libvcs.sync.git import GitSync


@pytest.mark.skipif(os.name != "posix", reason="POSIX process-group supervision")
@pytest.mark.parametrize("mode", ["main", "included", "worktree"])
def test_sync_interrupt_stops_worker(
    git_repo: GitSync, tmp_path: pathlib.Path, mode: str
) -> None:
    """SIGINT stops an active native checkout and reports retained changes."""
    git_repo.run(["tag", "before-update"])
    git_repo.run(["commit", "--allow-empty", "-m", "advance"])
    from libvcs import GitSync

    checkout = git_repo
    entry: dict[str, t.Any] = {
        "repo": f"git+{git_repo.url}",
        "working_copy": {
            "tag": "before-update",
            "sync": {"dirty": "preserve"},
        },
    }
    arguments = ["sync", "--all", "--no-log-file", "--timeout", "30"]
    if mode != "main":
        path = tmp_path / "linked"
        git_repo.run(["worktree", "add", "--detach", str(path), "HEAD"])
        checkout = GitSync(url=git_repo.url, path=path)
        entry["working_copy"] = {
            "commit": git_repo.get_revision(),
            "sync": {"drift": "keep"},
        }
        entry["worktrees"] = [
            {"dir": str(path), "tag": "before-update", "sync": {"dirty": "preserve"}}
        ]
        if mode == "included":
            arguments.append("--include-worktrees")
        else:
            arguments = ["worktree", "sync"]
    (checkout.path / "local.txt").write_text("retain this\n")
    address = str(tmp_path / "s")
    helper = tmp_path / "hook.py"
    helper.write_text(
        "import json, os, socket\n"
        "channel = socket.socket(socket.AF_UNIX)\n"
        f"channel.connect({address!r})\n"
        "channel.sendall(json.dumps({'group': os.getpgrp()}).encode() + b'\\n')\n"
        "channel.recv(1)\n"
    )
    hook = git_repo.path / ".git" / "hooks" / "post-checkout"
    hook.write_text(
        f"#!/bin/sh\nexec {shlex.quote(sys.executable)} {shlex.quote(str(helper))}\n"
    )
    hook.chmod(0o700)
    config = tmp_path / "repos.json"
    config.write_text(
        json.dumps({str(git_repo.path.parent): {git_repo.path.name: entry}})
    )
    spec = importlib.util.find_spec("vcspull")
    assert spec is not None and spec.origin is not None
    group = None
    with socket.socket(socket.AF_UNIX) as server:
        server.bind(address)
        server.listen()
        server.settimeout(3)
        process = subprocess.Popen(
            [
                sys.executable,
                "-c",
                "from vcspull.cli import cli; cli()",
                *arguments,
                "--file",
                str(config),
                "--ndjson",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env={
                **os.environ,
                "PYTHONPATH": str(pathlib.Path(spec.origin).parent.parent),
            },
            start_new_session=True,
        )
        try:
            connection, _ = server.accept()
            with connection, connection.makefile("rb") as stream:
                group = json.loads(stream.readline())["group"]
                assert group != process.pid
                process.send_signal(signal.SIGINT)
                output, error = process.communicate(timeout=3)
                assert process.returncode == -signal.SIGINT, (output, error)
                assert connection.recv(1) == b""
            events = [json.loads(line) for line in output.splitlines()]
            event = next(item for item in events if item.get("status") == "interrupted")
            assert event["update_state"] == "unknown"
            if mode != "main":
                assert event["exists"] is None
                assert event["is_dirty"] is None
            retained = event["retained_recoveries"]
            assert len(retained) == 1
            discovered = checkout.list_recoveries()
            assert discovered[0].recovery is not None
            assert retained[0]["recovery"]["id"] == discovered[0].recovery.id
        finally:
            if group is not None:
                with contextlib.suppress(ProcessLookupError):
                    os.killpg(group, signal.SIGKILL)
            if process.poll() is None:
                process.kill()
            process.communicate(timeout=1)


@pytest.mark.skipif(
    sys.platform == "win32",
    reason="POSIX signal semantics only; Windows uses exit-code 130",
)
def test_exit_on_sigint_produces_wifsignaled_sigint() -> None:
    """The exit helper preserves POSIX signal termination for shell command lists.

    Run it in a child interpreter so the real signal cannot kill pytest.
    """
    # Simulate Ctrl-C in a fresh interpreter, then route it through the
    # real helper. We install ``default_int_handler`` explicitly because
    # pytest's parent may have fiddled with SIGINT -- this child is a
    # fresh Python process, but being explicit removes one variable.
    runner = (
        "import signal\n"
        "signal.signal(signal.SIGINT, signal.default_int_handler)\n"
        "from vcspull.cli.sync import _exit_on_sigint\n"
        "try:\n"
        "    signal.raise_signal(signal.SIGINT)\n"
        "except KeyboardInterrupt:\n"
        "    _exit_on_sigint()\n"
    )

    # Pin the child's import path to wherever the parent loaded vcspull from.
    # The root conftest's autouse ``cwd_default`` chdirs every test into a
    # per-test ``tmp_path``, which the subprocess inherits as its CWD. Build
    # environments that hand vcspull to pytest via a *relative* ``PYTHONPATH``
    # entry (e.g. Arch's ``tmp_install/usr/lib/pythonX.Y/site-packages``)
    # would then resolve that entry against the tmp dir and fail to import
    # vcspull. Prepending the parent's resolved package dir keeps the child
    # importable regardless of the surrounding install style.
    vcspull_spec = importlib.util.find_spec("vcspull")
    assert vcspull_spec is not None and vcspull_spec.origin is not None
    vcspull_parent = str(pathlib.Path(vcspull_spec.origin).resolve().parent.parent)
    env = {
        **os.environ,
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONPATH": os.pathsep.join(
            p for p in (vcspull_parent, os.environ.get("PYTHONPATH", "")) if p
        ),
    }

    proc = subprocess.run(
        [sys.executable, "-c", runner],
        env=env,
        capture_output=True,
        check=False,
        timeout=10,
    )

    assert proc.returncode == -signal.SIGINT, (
        f"expected WIFSIGNALED(SIGINT) (-{int(signal.SIGINT)}), "
        f"got returncode={proc.returncode}; stderr={proc.stderr!r}"
    )
