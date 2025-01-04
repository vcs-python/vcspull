"""Tests for vcspull utilities."""

from __future__ import annotations

from typing import TYPE_CHECKING

from vcspull.util import get_config_dir

if TYPE_CHECKING:
    import pathlib

    import pytest


def test_vcspull_configdir_env_var(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test retrieving config directory with VCSPULL_CONFIGDIR set."""
    monkeypatch.setenv("VCSPULL_CONFIGDIR", str(tmp_path))

    assert get_config_dir() == tmp_path


def test_vcspull_configdir_xdg_config_dir(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test retrieving config directory with XDG_CONFIG_HOME set."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    vcspull_dir = tmp_path / "vcspull"
    vcspull_dir.mkdir()

    assert get_config_dir() == vcspull_dir


def test_vcspull_configdir_no_xdg(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test retrieving config directory without XDG_CONFIG_HOME set."""
    monkeypatch.delenv("XDG_CONFIG_HOME")
    assert get_config_dir()
