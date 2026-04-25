"""Shared pytest fixtures for snapshot testing."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from syrupy.extensions.json import JSONSnapshotExtension
from syrupy.extensions.single_file import SingleFileSnapshotExtension, WriteMode

if TYPE_CHECKING:
    from syrupy.assertion import SnapshotAssertion


class YamlSnapshotExtension(SingleFileSnapshotExtension):
    """Snapshot extension that persists plain-text YAML files."""

    _file_extension = "yaml"  # syrupy 4.x compatibility
    file_extension = "yaml"  # syrupy 5.x+
    _write_mode = WriteMode.TEXT


@pytest.fixture
def snapshot_json(snapshot: SnapshotAssertion) -> SnapshotAssertion:
    """JSON-formatted snapshot assertions."""
    return snapshot.with_defaults(extension_class=JSONSnapshotExtension)


@pytest.fixture
def snapshot_yaml(snapshot: SnapshotAssertion) -> SnapshotAssertion:
    """YAML-formatted snapshot assertions."""
    return snapshot.with_defaults(extension_class=YamlSnapshotExtension)


@pytest.fixture(autouse=True)
def _default_serial_jobs(monkeypatch: pytest.MonkeyPatch) -> None:
    """Default ``vcspull sync`` to serial mode in tests.

    Production defaults to ``--jobs min(8, CPU*2)`` for batch speedups,
    but most existing tests assert order-dependent behaviour (e.g.
    ``--exit-on-error`` fixtures that pair a "good first" repo with a
    "bad second" one). Pinning ``VCSPULL_JOBS=1`` here gives those
    tests deterministic ordering; new tests that exercise the parallel
    orchestrator override the env var inside their own scope.
    """
    monkeypatch.setenv("VCSPULL_JOBS", "1")
