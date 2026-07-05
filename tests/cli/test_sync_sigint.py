"""Subprocess-based tests asserting real ``WIFSIGNALED(SIGINT)`` termination."""

from __future__ import annotations

import importlib.util
import os
import pathlib
import signal
import subprocess
import sys

import pytest


@pytest.mark.skipif(
    sys.platform == "win32",
    reason="POSIX signal semantics only; Windows uses exit-code 130",
)
def test_exit_on_sigint_produces_wifsignaled_sigint() -> None:
    """``_exit_on_sigint`` makes the process terminate via ``WIFSIGNALED(SIGINT)``.

    Bash's ``cmd1; cmd2`` sequential-list abort only kicks in when the
    child was killed by a signal -- a clean ``SystemExit(130)`` leaves
    the shell no reason to stop and the chain keeps running. This
    assertion locks in the actual kernel signal bit, not just the exit
    code.

    Why a subprocess: the production helper ends with
    ``signal.raise_signal(SIGINT)`` under ``SIG_DFL``, which would take
    the pytest runner down with us if we called it in-process. The only
    reliable observation point is ``subprocess.Popen.returncode``,
    which CPython stores as the *negative* of the terminating signal
    number when ``os.waitstatus_to_exitcode`` reports ``WIFSIGNALED``.

    Scope: we target ``_exit_on_sigint`` directly in a fresh interpreter
    rather than driving ``vcspull sync`` end-to-end, because getting the
    sync loop into a deterministic mid-flight state where SIGINT lands
    on the watchdog's ``done.wait(...)`` requires either a blocking fake
    remote or a monkey-patched ``update_repo`` -- both reintroduce
    flake and add nothing over the existing in-process control-flow
    tests in ``test_sync_watchdog.py`` (which use the
    ``_fake_sigint_escalation`` fixture). The one thing those tests
    can't show is that the kernel actually marks the exit as
    WIFSIGNALED(SIGINT); that's what this subprocess proves.
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
    assert vcspull_spec is not None
    assert vcspull_spec.origin is not None
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
