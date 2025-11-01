"""Tests for vcspull utilities."""

from __future__ import annotations

import pathlib
import typing as t

from vcspull.util import contract_user_home, get_config_dir

if t.TYPE_CHECKING:
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


def test_contract_user_home_contracts_home_path() -> None:
    """Test contracting home directory to ~."""
    home = str(pathlib.Path.home())

    # Test full path
    assert contract_user_home(f"{home}/code/repo") == "~/code/repo"

    # Test home directory itself
    assert contract_user_home(home) == "~"

    # Test with pathlib.Path
    assert contract_user_home(pathlib.Path(home) / "code" / "repo") == "~/code/repo"


def test_contract_user_home_preserves_non_home_paths() -> None:
    """Test that non-home paths are not contracted."""
    # Test absolute paths outside home
    assert contract_user_home("/opt/project") == "/opt/project"
    assert contract_user_home("/usr/local/bin") == "/usr/local/bin"

    # Test relative paths
    assert contract_user_home("./relative/path") == "./relative/path"
    assert contract_user_home("relative/path") == "relative/path"


def test_contract_user_home_handles_edge_cases() -> None:
    """Test edge cases in path contraction."""
    home = str(pathlib.Path.home())

    # Test trailing slashes
    assert contract_user_home(f"{home}/code/") == "~/code/"

    # Test empty path
    assert contract_user_home("") == ""

    # Test path with ~ already in it (should pass through)
    assert contract_user_home("~/code/repo") == "~/code/repo"
