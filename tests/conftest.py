"""Shared pytest fixtures for snapshot testing."""

from __future__ import annotations

import pytest
from syrupy.assertion import SnapshotAssertion
from syrupy.extensions.json import JSONSnapshotExtension
from syrupy.extensions.single_file import SingleFileSnapshotExtension, WriteMode


class YamlSnapshotExtension(SingleFileSnapshotExtension):
    """Snapshot extension that persists plain-text YAML files."""

    file_extension = "yaml"
    _write_mode = WriteMode.TEXT


@pytest.fixture
def snapshot_json(snapshot: SnapshotAssertion) -> SnapshotAssertion:
    """JSON-formatted snapshot assertions."""
    return snapshot.with_defaults(extension_class=JSONSnapshotExtension)


@pytest.fixture
def snapshot_yaml(snapshot: SnapshotAssertion) -> SnapshotAssertion:
    """YAML-formatted snapshot assertions."""
    return snapshot.with_defaults(extension_class=YamlSnapshotExtension)
