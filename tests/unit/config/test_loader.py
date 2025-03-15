"""Tests for configuration loader.

This module contains tests for the VCSPull configuration loader.
"""

from __future__ import annotations

import pathlib

import pytest
from pytest import MonkeyPatch

# Import fixtures
pytest.importorskip("tests.fixtures.example_configs")

from vcspull.config.loader import load_config, resolve_includes, save_config
from vcspull.config.models import Repository, Settings, VCSPullConfig


def test_load_config_yaml(simple_yaml_config: pathlib.Path) -> None:
    """Test loading a YAML configuration file."""
    config = load_config(simple_yaml_config)
    assert isinstance(config, VCSPullConfig)
    assert len(config.repositories) == 1
    assert config.repositories[0].name == "example-repo"


def test_load_config_json(json_config: pathlib.Path) -> None:
    """Test loading a JSON configuration file."""
    config = load_config(json_config)
    assert isinstance(config, VCSPullConfig)
    assert len(config.repositories) == 1
    assert config.repositories[0].name == "json-repo"


def test_config_include_resolution(
    config_with_includes: tuple[pathlib.Path, pathlib.Path],
) -> None:
    """Test resolution of included configuration files."""
    main_file, included_file = config_with_includes

    # Load the main config
    config = load_config(main_file)
    assert len(config.repositories) == 1
    assert len(config.includes) == 1

    # Resolve includes
    resolved_config = resolve_includes(config, main_file.parent)
    assert len(resolved_config.repositories) == 2
    assert len(resolved_config.includes) == 0

    # Check that both repositories are present
    repo_names = [repo.name for repo in resolved_config.repositories]
    assert "main-repo" in repo_names
    assert "included-repo" in repo_names


def test_save_config(tmp_path: pathlib.Path) -> None:
    """Test saving a configuration to disk."""
    config = VCSPullConfig(
        settings=Settings(sync_remotes=True),
        repositories=[
            Repository(
                name="test-repo",
                url="https://github.com/example/test-repo.git",
                path=str(tmp_path / "repos" / "test-repo"),
                vcs="git",
            ),
        ],
    )

    # Test saving to YAML
    yaml_path = tmp_path / "config.yaml"
    saved_path = save_config(config, yaml_path, format_type="yaml")
    assert saved_path.exists()
    assert saved_path == yaml_path

    # Test saving to JSON
    json_path = tmp_path / "config.json"
    saved_path = save_config(config, json_path, format_type="json")
    assert saved_path.exists()
    assert saved_path == json_path

    # Load both configs and compare
    yaml_config = load_config(yaml_path)
    json_config = load_config(json_path)

    assert yaml_config.model_dump() == config.model_dump()
    assert json_config.model_dump() == config.model_dump()


def test_auto_format_detection(tmp_path: pathlib.Path) -> None:
    """Test automatic format detection based on file extension."""
    config = VCSPullConfig(
        settings=Settings(sync_remotes=True),
        repositories=[
            Repository(
                name="test-repo",
                url="https://github.com/example/test-repo.git",
                path=str(tmp_path / "repos" / "test-repo"),
                vcs="git",
            ),
        ],
    )

    # Test saving with format detection
    yaml_path = tmp_path / "config.yaml"
    save_config(config, yaml_path)
    json_path = tmp_path / "config.json"
    save_config(config, json_path)

    # Load both configs and compare
    yaml_config = load_config(yaml_path)
    json_config = load_config(json_path)

    assert yaml_config.model_dump() == config.model_dump()
    assert json_config.model_dump() == config.model_dump()


def test_config_path_expansion(
    monkeypatch: MonkeyPatch,
    tmp_path: pathlib.Path,
) -> None:
    """Test that user paths are expanded correctly."""
    # Mock the home directory for testing
    home_dir = tmp_path / "home" / "user"
    home_dir.mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home_dir))

    # Create a config with a path using ~
    config = VCSPullConfig(
        repositories=[
            Repository(
                name="home-repo",
                url="https://github.com/example/home-repo.git",
                path="~/repos/home-repo",
                vcs="git",
            ),
        ],
    )

    # Check that the path is expanded
    expanded_path = config.repositories[0].path
    assert "~" not in expanded_path
    assert str(home_dir) in expanded_path


def test_relative_includes(tmp_path: pathlib.Path) -> None:
    """Test that relative include paths work correctly."""
    # Create a nested directory structure
    subdir = tmp_path / "configs"
    subdir.mkdir()

    # Create an included config in the subdir
    included_config = VCSPullConfig(
        repositories=[
            Repository(
                name="included-repo",
                url="https://github.com/example/included-repo.git",
                path=str(tmp_path / "repos" / "included-repo"),
                vcs="git",
            ),
        ],
    )
    included_path = subdir / "included.yaml"
    save_config(included_config, included_path)

    # Create a main config with a relative include
    main_config = VCSPullConfig(
        repositories=[
            Repository(
                name="main-repo",
                url="https://github.com/example/main-repo.git",
                path=str(tmp_path / "repos" / "main-repo"),
                vcs="git",
            ),
        ],
        includes=["configs/included.yaml"],  # Relative path
    )
    main_path = tmp_path / "main.yaml"
    save_config(main_config, main_path)

    # Load and resolve the config
    config = load_config(main_path)
    resolved_config = resolve_includes(config, main_path.parent)

    # Check that both repositories are present
    assert len(resolved_config.repositories) == 2
    repo_names = [repo.name for repo in resolved_config.repositories]
    assert "main-repo" in repo_names
    assert "included-repo" in repo_names
