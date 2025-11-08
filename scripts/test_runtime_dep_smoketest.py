"""Tests for the runtime dependency smoke test script.

These tests are intentionally isolated behind the
``scripts__runtime_dep_smoketest`` marker so they only run when explicitly
requested, e.g. ``pytest -m scripts__runtime_dep_smoketest``.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.scripts__runtime_dep_smoketest


def test_runtime_smoke_test_script() -> None:
    """Run ``scripts/runtime_dep_smoketest.py`` in a clean uvx environment."""
    uvx = shutil.which("uvx")
    if uvx is None:
        pytest.skip("uvx is required to run the runtime dependency smoke test")

    repo_root = Path(__file__).resolve().parents[1]
    script_path = repo_root / "scripts" / "runtime_dep_smoketest.py"

    result = subprocess.run(
        [
            uvx,
            "--isolated",
            "--reinstall",
            "--from",
            str(repo_root),
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
