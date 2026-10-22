"""Tests for the runtime dependency smoke test script.

These tests are intentionally isolated behind the
``scripts__runtime_dep_smoketest`` marker so they only run when explicitly
requested, e.g. ``pytest -m scripts__runtime_dep_smoketest``.
"""

from __future__ import annotations

import pathlib
import shutil
import subprocess
import sys

import pytest

pytestmark = pytest.mark.scripts__runtime_dep_smoketest


def test_runtime_smoke_test_script() -> None:
    """Run the installed wheel with only its locked runtime dependencies."""
    uv = shutil.which("uv")
    if uv is None:
        pytest.skip("uv is required to run the runtime dependency smoke test")

    repo_root = pathlib.Path(__file__).resolve().parents[1]
    script_path = repo_root / "scripts" / "runtime_dep_smoketest.py"

    result = subprocess.run(
        [
            uv,
            "run",
            "--isolated",
            "--no-cache",
            "--no-dev",
            "--no-editable",
            "--frozen",
            "python",
            str(script_path),
        ],
        capture_output=True,
        text=True,
        cwd=str(repo_root),
        check=False,
    )

    if result.returncode != 0:
        sys.stdout.write(result.stdout)
        sys.stderr.write(result.stderr)

    assert result.returncode == 0, "runtime dependency smoke test failed"
