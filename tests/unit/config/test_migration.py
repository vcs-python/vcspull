"""Tests for configuration migration.

This module contains tests for the VCSPull configuration migration functionality.
"""

from __future__ import annotations

import pathlib

import pytest
import yaml

from vcspull.config.migration import (
    detect_config_version,
    migrate_all_configs,
    migrate_config_file,
    migrate_v1_to_v2,
)
from vcspull.config.models import Settings, VCSPullConfig


@pytest.fixture
def old_format_config(tmp_path: pathlib.Path) -> pathlib.Path:
    """Create a config file with old format.

    Parameters
    ----------
    tmp_path : pathlib.Path
        Temporary directory path

    Returns
    -------
    pathlib.Path
        Path to the created configuration file
    """
    # Create an old format config file
    config_data = {
        "/home/user/projects": {
            "repo1": "git+https://github.com/user/repo1.git",
            "repo2": {
                "url": "git+https://github.com/user/repo2.git",
                "remotes": {
                    "upstream": "git+https://github.com/upstream/repo2.git",
                },
            },
        },
        "/home/user/hg-projects": {
            "hg-repo": "hg+https://bitbucket.org/user/hg-repo",
        },
    }

    config_file = tmp_path / "old_config.yaml"
    with config_file.open("w", encoding="utf-8") as f:
        yaml.dump(config_data, f)

    return config_file


@pytest.fixture
def new_format_config(tmp_path: pathlib.Path) -> pathlib.Path:
    """Create a config file with new format.

    Parameters
    ----------
    tmp_path : pathlib.Path
        Temporary directory path

    Returns
    -------
    pathlib.Path
        Path to the created configuration file
    """
    # Create a new format config file
    config_data = {
        "settings": {
            "sync_remotes": True,
            "default_vcs": "git",
        },
        "repositories": [
            {
                "name": "repo1",
                "url": "https://github.com/user/repo1.git",
                "path": str(tmp_path / "repos" / "repo1"),
                "vcs": "git",
            },
            {
                "name": "repo2",
                "url": "https://github.com/user/repo2.git",
                "path": str(tmp_path / "repos" / "repo2"),
                "vcs": "git",
                "remotes": {
                    "upstream": "https://github.com/upstream/repo2.git",
                },
            },
        ],
    }

    config_file = tmp_path / "new_config.yaml"
    with config_file.open("w", encoding="utf-8") as f:
        yaml.dump(config_data, f)

    return config_file


class TestConfigVersionDetection:
    """Test the detection of configuration versions."""

    def test_detect_v1_config(self, old_format_config: pathlib.Path) -> None:
        """Test detection of v1 configuration format."""
        version = detect_config_version(old_format_config)
        assert version == "v1"

    def test_detect_v2_config(self, new_format_config: pathlib.Path) -> None:
        """Test detection of v2 configuration format."""
        version = detect_config_version(new_format_config)
        assert version == "v2"

    def test_detect_empty_config(self, tmp_path: pathlib.Path) -> None:
        """Test detection of empty configuration file."""
        empty_file = tmp_path / "empty.yaml"
        empty_file.touch()

        version = detect_config_version(empty_file)
        assert version == "v2"  # Empty file is considered v2

    def test_detect_invalid_config(self, tmp_path: pathlib.Path) -> None:
        """Test detection of invalid configuration file."""
        invalid_file = tmp_path / "invalid.yaml"
        with invalid_file.open("w", encoding="utf-8") as f:
            f.write("This is not a valid YAML file.")

        with pytest.raises(ValueError):
            detect_config_version(invalid_file)

    def test_detect_nonexistent_config(self, tmp_path: pathlib.Path) -> None:
        """Test detection of non-existent configuration file."""
        nonexistent_file = tmp_path / "nonexistent.yaml"

        with pytest.raises(FileNotFoundError):
            detect_config_version(nonexistent_file)


class TestConfigMigration:
    """Test the migration of configurations from v1 to v2."""

    def test_migrate_v1_to_v2(
        self, old_format_config: pathlib.Path, tmp_path: pathlib.Path
    ) -> None:
        """Test migration from v1 to v2 format."""
        output_path = tmp_path / "migrated_config.yaml"

        # Migrate the configuration
        migrated_config = migrate_v1_to_v2(old_format_config, output_path)

        # Verify the migrated configuration
        assert isinstance(migrated_config, VCSPullConfig)
        assert len(migrated_config.repositories) == 3

        # Check that the output file was created
        assert output_path.exists()

        # Load the migrated file and verify structure
        with output_path.open("r", encoding="utf-8") as f:
            migrated_data = yaml.safe_load(f)

        assert "repositories" in migrated_data
        assert "settings" in migrated_data
        assert len(migrated_data["repositories"]) == 3

    def test_migrate_v1_with_default_settings(
        self, old_format_config: pathlib.Path
    ) -> None:
        """Test migration with custom default settings."""
        default_settings = {
            "sync_remotes": False,
            "default_vcs": "git",
            "depth": 1,
        }

        migrated_config = migrate_v1_to_v2(
            old_format_config,
            default_settings=default_settings,
        )

        # Verify settings were applied
        assert migrated_config.settings.sync_remotes is False
        assert migrated_config.settings.default_vcs == "git"
        assert migrated_config.settings.depth == 1

    def test_migrate_empty_config(self, tmp_path: pathlib.Path) -> None:
        """Test migration of empty configuration file."""
        empty_file = tmp_path / "empty.yaml"
        empty_file.touch()

        migrated_config = migrate_v1_to_v2(empty_file)

        # Empty config should result in empty repositories list
        assert len(migrated_config.repositories) == 0
        assert isinstance(migrated_config.settings, Settings)

    def test_migrate_invalid_repository(self, tmp_path: pathlib.Path) -> None:
        """Test migration with invalid repository definition."""
        # Create config with invalid repository (missing required url field)
        config_data = {
            "/home/user/projects": {
                "invalid-repo": {
                    "path": "/some/path",  # Missing url
                },
            },
        }

        config_file = tmp_path / "invalid_repo.yaml"
        with config_file.open("w", encoding="utf-8") as f:
            yaml.dump(config_data, f)

        # Migration should succeed but skip the invalid repository
        migrated_config = migrate_v1_to_v2(config_file)
        assert len(migrated_config.repositories) == 0  # Invalid repo is skipped

    def test_migrate_config_file(
        self, old_format_config: pathlib.Path, tmp_path: pathlib.Path
    ) -> None:
        """Test the migrate_config_file function."""
        output_path = tmp_path / "migrated_with_backup.yaml"

        # Test migration with backup
        success, message = migrate_config_file(
            old_format_config,
            output_path,
            create_backup=True,
        )

        assert success is True
        assert "Successfully migrated" in message
        assert output_path.exists()

        # Check that a backup was created for source
        backup_path = old_format_config.with_suffix(".yaml.bak")
        assert backup_path.exists()

    def test_migrate_config_file_no_backup(
        self, old_format_config: pathlib.Path, tmp_path: pathlib.Path
    ) -> None:
        """Test migration without creating a backup."""
        output_path = tmp_path / "migrated_no_backup.yaml"

        # Test migration without backup
        success, message = migrate_config_file(
            old_format_config,
            output_path,
            create_backup=False,
        )

        assert success is True
        assert "Successfully migrated" in message

        # Check that no backup was created
        backup_path = old_format_config.with_suffix(".yaml.bak")
        assert not backup_path.exists()

    def test_migrate_config_file_already_v2(
        self, new_format_config: pathlib.Path, tmp_path: pathlib.Path
    ) -> None:
        """Test migration of a file that's already in v2 format."""
        output_path = tmp_path / "already_v2.yaml"

        # Should not migrate without force
        success, message = migrate_config_file(
            new_format_config,
            output_path,
            create_backup=True,
            force=False,
        )

        assert success is True
        assert "already in latest format" in message
        assert not output_path.exists()  # File should not be created

        # Should migrate with force
        success, message = migrate_config_file(
            new_format_config,
            output_path,
            create_backup=True,
            force=True,
        )

        assert success is True
        assert output_path.exists()


class TestMultipleConfigMigration:
    """Test migration of multiple configuration files."""

    def setup_multiple_configs(self, base_dir: pathlib.Path) -> None:
        """Set up multiple configuration files for testing.

        Parameters
        ----------
        base_dir : pathlib.Path
            Base directory to create configuration files in
        """
        # Create directory structure
        configs_dir = base_dir / "configs"
        configs_dir.mkdir()

        nested_dir = configs_dir / "nested"
        nested_dir.mkdir()

        # Create old format configs
        old_config1 = {
            "/home/user/proj1": {
                "repo1": "git+https://github.com/user/repo1.git",
            },
        }

        old_config2 = {
            "/home/user/proj2": {
                "repo2": "git+https://github.com/user/repo2.git",
            },
        }

        # Create new format config
        new_config = {
            "settings": {"sync_remotes": True},
            "repositories": [
                {
                    "name": "repo3",
                    "url": "https://github.com/user/repo3.git",
                    "path": "/home/user/proj3/repo3",
                    "vcs": "git",
                },
            ],
        }

        # Write the files
        with (configs_dir / "old1.yaml").open("w", encoding="utf-8") as f:
            yaml.dump(old_config1, f)

        with (nested_dir / "old2.yaml").open("w", encoding="utf-8") as f:
            yaml.dump(old_config2, f)

        with (configs_dir / "new1.yaml").open("w", encoding="utf-8") as f:
            yaml.dump(new_config, f)

    def test_migrate_all_configs(self, tmp_path: pathlib.Path) -> None:
        """Test migrating all configurations in a directory structure."""
        self.setup_multiple_configs(tmp_path)

        # Run migration on the directory
        results = migrate_all_configs(
            [str(tmp_path / "configs")],
            create_backups=True,
            force=False,
        )

        # Should find 3 config files, 2 that need migration (old1.yaml, old2.yaml)
        assert len(results) == 3

        # Count migrations vs already up-to-date
        migrated_count = sum(
            1
            for _, success, msg in results
            if success and "Successfully migrated" in msg
        )
        skipped_count = sum(
            1
            for _, success, msg in results
            if success and "already in latest format" in msg
        )

        assert migrated_count == 2
        assert skipped_count == 1

        # Check that backups were created
        assert (tmp_path / "configs" / "old1.yaml.bak").exists()
        assert (tmp_path / "configs" / "nested" / "old2.yaml.bak").exists()

    def test_migrate_all_configs_force(self, tmp_path: pathlib.Path) -> None:
        """Test forced migration of all configurations."""
        self.setup_multiple_configs(tmp_path)

        # Run migration with force=True
        results = migrate_all_configs(
            [str(tmp_path / "configs")],
            create_backups=True,
            force=True,
        )

        # All 3 should be migrated when force=True
        assert len(results) == 3
        assert all(success for _, success, _ in results)

        # Check that all files have backups
        assert (tmp_path / "configs" / "old1.yaml.bak").exists()
        assert (tmp_path / "configs" / "nested" / "old2.yaml.bak").exists()
        assert (tmp_path / "configs" / "new1.yaml.bak").exists()

    def test_no_configs_found(self, tmp_path: pathlib.Path) -> None:
        """Test behavior when no configuration files are found."""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()

        results = migrate_all_configs([str(empty_dir)])

        assert len(results) == 0
