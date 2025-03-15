"""Tests for configuration models.

This module contains tests for the VCSPull configuration models.
"""

from __future__ import annotations

import pathlib

import pytest
from pydantic import ValidationError

from vcspull.config.models import Repository, Settings, VCSPullConfig


class TestRepository:
    """Tests for Repository model."""

    def test_minimal_repository(self) -> None:
        """Test creating a repository with minimal fields."""
        repo = Repository(
            url="https://github.com/user/repo.git",
            path="~/code/repo",
        )
        assert repo.url == "https://github.com/user/repo.git"
        assert repo.path.startswith("/")  # Path should be normalized
        assert repo.vcs is None
        assert repo.name is None
        assert len(repo.remotes) == 0
        assert repo.rev is None
        assert repo.web_url is None

    def test_full_repository(self) -> None:
        """Test creating a repository with all fields."""
        repo = Repository(
            name="test",
            url="https://github.com/user/repo.git",
            path="~/code/repo",
            vcs="git",
            remotes={"upstream": "https://github.com/upstream/repo.git"},
            rev="main",
            web_url="https://github.com/user/repo",
        )
        assert repo.name == "test"
        assert repo.url == "https://github.com/user/repo.git"
        assert repo.path.startswith("/")  # Path should be normalized
        assert repo.vcs == "git"
        assert repo.remotes == {"upstream": "https://github.com/upstream/repo.git"}
        assert repo.rev == "main"
        assert repo.web_url == "https://github.com/user/repo"

    def test_path_normalization(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that paths are normalized."""
        # Mock the home directory for testing
        test_home = "/mock/home"
        monkeypatch.setenv("HOME", test_home)

        repo = Repository(
            url="https://github.com/user/repo.git",
            path="~/code/repo",
        )

        assert repo.path.startswith("/")
        assert "~" not in repo.path
        assert repo.path == str(pathlib.Path(test_home) / "code/repo")

    def test_path_validation(self) -> None:
        """Test path validation."""
        repo = Repository(url="https://github.com/user/repo.git", path="~/code/repo")
        assert repo.path.startswith("/")
        assert "~" not in repo.path

    def test_missing_required_fields(self) -> None:
        """Test validation error when required fields are missing."""
        # Missing path parameter
        with pytest.raises(ValidationError):
            # We need to use model_construct to bypass validation and then
            # validate manually to check for specific missing fields
            repo_no_path = Repository.model_construct(
                url="https://github.com/user/repo.git",
            )
            Repository.model_validate(repo_no_path.model_dump())

        # Missing url parameter
        with pytest.raises(ValidationError):
            repo_no_url = Repository.model_construct(path="~/code/repo")
            Repository.model_validate(repo_no_url.model_dump())


class TestSettings:
    """Tests for Settings model."""

    def test_default_settings(self) -> None:
        """Test default settings values."""
        settings = Settings()
        assert settings.sync_remotes is True
        assert settings.default_vcs is None
        assert settings.depth is None

    def test_custom_settings(self) -> None:
        """Test custom settings values."""
        settings = Settings(
            sync_remotes=False,
            default_vcs="git",
            depth=1,
        )
        assert settings.sync_remotes is False
        assert settings.default_vcs == "git"
        assert settings.depth == 1


class TestVCSPullConfig:
    """Tests for VCSPullConfig model."""

    def test_empty_config(self) -> None:
        """Test creating an empty configuration."""
        config = VCSPullConfig()
        assert isinstance(config.settings, Settings)
        assert len(config.repositories) == 0
        assert len(config.includes) == 0

    def test_config_with_repositories(self) -> None:
        """Test creating a configuration with repositories."""
        config = VCSPullConfig(
            repositories=[
                Repository(
                    name="repo1",
                    url="https://github.com/user/repo1.git",
                    path="~/code/repo1",
                ),
                Repository(
                    name="repo2",
                    url="https://github.com/user/repo2.git",
                    path="~/code/repo2",
                ),
            ],
        )
        assert len(config.repositories) == 2
        assert config.repositories[0].name == "repo1"
        assert config.repositories[1].name == "repo2"

    def test_config_with_includes(self) -> None:
        """Test creating a configuration with includes."""
        config = VCSPullConfig(
            includes=["file1.yaml", "file2.yaml"],
        )
        assert len(config.includes) == 2
        assert config.includes[0] == "file1.yaml"
        assert config.includes[1] == "file2.yaml"

    def test_config_with_settings(self) -> None:
        """Test creating a configuration with settings."""
        config = VCSPullConfig(
            settings=Settings(
                sync_remotes=False,
                default_vcs="git",
                depth=1,
            ),
        )
        assert config.settings.sync_remotes is False
        assert config.settings.default_vcs == "git"
        assert config.settings.depth == 1
