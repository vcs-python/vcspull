"""Tests for configuration loader."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from vcspull.config import load_config, normalize_path, resolve_includes
from vcspull.config.models import Repository, Settings, VCSPullConfig


class TestNormalizePath:
    """Tests for normalize_path function."""

    def test_normalize_path_str(self) -> None:
        """Test normalizing a string path."""
        path = normalize_path("~/test")
        assert isinstance(path, Path)
        assert path == Path.home() / "test"

    def test_normalize_path_path(self) -> None:
        """Test normalizing a Path object."""
        original = Path("~/test")
        path = normalize_path(original)
        assert isinstance(path, Path)
        assert path == Path.home() / "test"


class TestLoadConfig:
    """Tests for load_config function."""

    def test_load_yaml_config(self, tmp_path: Path) -> None:
        """Test loading a YAML configuration file."""
        config_data = {
            "settings": {
                "sync_remotes": False,
                "default_vcs": "git",
            },
            "repositories": [
                {
                    "name": "repo1",
                    "url": "https://github.com/user/repo1.git",
                    "path": str(tmp_path / "repo1"),
                    "vcs": "git",
                },
            ],
        }

        config_file = tmp_path / "config.yaml"
        with config_file.open("w", encoding="utf-8") as f:
            yaml.dump(config_data, f)

        config = load_config(config_file)

        assert isinstance(config, VCSPullConfig)
        assert config.settings.sync_remotes is False
        assert config.settings.default_vcs == "git"
        assert len(config.repositories) == 1
        assert config.repositories[0].name == "repo1"
        assert config.repositories[0].url == "https://github.com/user/repo1.git"
        assert config.repositories[0].vcs == "git"

    def test_load_json_config(self, tmp_path: Path) -> None:
        """Test loading a JSON configuration file."""
        config_data = {
            "settings": {
                "sync_remotes": False,
                "default_vcs": "git",
            },
            "repositories": [
                {
                    "name": "repo1",
                    "url": "https://github.com/user/repo1.git",
                    "path": str(tmp_path / "repo1"),
                    "vcs": "git",
                },
            ],
        }

        config_file = tmp_path / "config.json"
        with config_file.open("w", encoding="utf-8") as f:
            json.dump(config_data, f)

        config = load_config(config_file)

        assert isinstance(config, VCSPullConfig)
        assert config.settings.sync_remotes is False
        assert config.settings.default_vcs == "git"
        assert len(config.repositories) == 1
        assert config.repositories[0].name == "repo1"
        assert config.repositories[0].url == "https://github.com/user/repo1.git"
        assert config.repositories[0].vcs == "git"

    def test_load_empty_config(self, tmp_path: Path) -> None:
        """Test loading an empty configuration file."""
        config_file = tmp_path / "empty.yaml"
        with config_file.open("w", encoding="utf-8") as f:
            f.write("")

        config = load_config(config_file)

        assert isinstance(config, VCSPullConfig)
        assert config.settings.sync_remotes is True
        assert config.settings.default_vcs is None
        assert len(config.repositories) == 0

    def test_file_not_found(self) -> None:
        """Test error when file is not found."""
        with pytest.raises(FileNotFoundError):
            load_config("/path/to/nonexistent/file.yaml")

    def test_unsupported_format(self, tmp_path: Path) -> None:
        """Test error for unsupported file format."""
        config_file = tmp_path / "config.txt"
        with config_file.open("w", encoding="utf-8") as f:
            f.write("This is not a valid config file")

        with pytest.raises(ValueError, match="Unsupported file format"):
            load_config(config_file)


class TestResolveIncludes:
    """Tests for resolve_includes function."""

    def test_no_includes(self) -> None:
        """Test resolving a configuration with no includes."""
        config = VCSPullConfig(
            repositories=[
                Repository(
                    name="repo1",
                    url="https://github.com/user/repo1.git",
                    path="~/code/repo1",
                    vcs="git",
                ),
            ],
        )

        resolved = resolve_includes(config, ".")

        assert len(resolved.repositories) == 1
        assert resolved.repositories[0].name == "repo1"
        assert len(resolved.includes) == 0

    def test_with_includes(self, tmp_path: Path) -> None:
        """Test resolving a configuration with includes."""
        # Create included config file
        included_config_data = {
            "settings": {
                "depth": 1,
            },
            "repositories": [
                {
                    "name": "included-repo",
                    "url": "https://github.com/user/included-repo.git",
                    "path": str(tmp_path / "included-repo"),
                    "vcs": "git",
                },
            ],
        }

        included_file = tmp_path / "included.yaml"
        with included_file.open("w", encoding="utf-8") as f:
            yaml.dump(included_config_data, f)

        # Create main config
        config = VCSPullConfig(
            settings=Settings(
                sync_remotes=False,
                default_vcs="git",
            ),
            repositories=[
                Repository(
                    name="main-repo",
                    url="https://github.com/user/main-repo.git",
                    path=str(tmp_path / "main-repo"),
                    vcs="git",
                ),
            ],
            includes=[
                str(included_file),
            ],
        )

        resolved = resolve_includes(config, tmp_path)

        # Check that repositories from both configs are present
        assert len(resolved.repositories) == 2
        assert resolved.repositories[0].name == "main-repo"
        assert resolved.repositories[1].name == "included-repo"

        # Check that settings are merged
        assert resolved.settings.sync_remotes is False
        assert resolved.settings.default_vcs == "git"
        assert resolved.settings.depth == 1

        # Check that includes are cleared
        assert len(resolved.includes) == 0

    def test_nested_includes(self, tmp_path: Path) -> None:
        """Test resolving a configuration with nested includes."""
        # Create nested included config file
        nested_config_data = {
            "repositories": [
                {
                    "name": "nested-repo",
                    "url": "https://github.com/user/nested-repo.git",
                    "path": str(tmp_path / "nested-repo"),
                    "vcs": "git",
                },
            ],
        }

        nested_file = tmp_path / "nested.yaml"
        with nested_file.open("w", encoding="utf-8") as f:
            yaml.dump(nested_config_data, f)

        # Create included config file with nested include
        included_config_data = {
            "repositories": [
                {
                    "name": "included-repo",
                    "url": "https://github.com/user/included-repo.git",
                    "path": str(tmp_path / "included-repo"),
                    "vcs": "git",
                },
            ],
            "includes": [
                str(nested_file),
            ],
        }

        included_file = tmp_path / "included.yaml"
        with included_file.open("w", encoding="utf-8") as f:
            yaml.dump(included_config_data, f)

        # Create main config
        config = VCSPullConfig(
            repositories=[
                Repository(
                    name="main-repo",
                    url="https://github.com/user/main-repo.git",
                    path=str(tmp_path / "main-repo"),
                    vcs="git",
                ),
            ],
            includes=[
                str(included_file),
            ],
        )

        resolved = resolve_includes(config, tmp_path)

        # Check that repositories from all configs are present
        assert len(resolved.repositories) == 3
        assert resolved.repositories[0].name == "main-repo"
        assert resolved.repositories[1].name == "included-repo"
        assert resolved.repositories[2].name == "nested-repo"

        # Check that includes are cleared
        assert len(resolved.includes) == 0

    def test_nonexistent_include(self, tmp_path: Path) -> None:
        """Test resolving a configuration with a nonexistent include."""
        config = VCSPullConfig(
            repositories=[
                Repository(
                    name="main-repo",
                    url="https://github.com/user/main-repo.git",
                    path=str(tmp_path / "main-repo"),
                    vcs="git",
                ),
            ],
            includes=[
                str(tmp_path / "nonexistent.yaml"),
            ],
        )

        resolved = resolve_includes(config, tmp_path)

        # Check that only the main repository is present
        assert len(resolved.repositories) == 1
        assert resolved.repositories[0].name == "main-repo"

        # Check that includes are cleared
        assert len(resolved.includes) == 0
