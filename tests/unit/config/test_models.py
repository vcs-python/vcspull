"""Tests for configuration models."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from vcspull.config.models import Repository, Settings, VCSPullConfig


class TestRepository:
    """Tests for the Repository model."""

    def test_minimal_repository(self) -> None:
        """Test creating a repository with minimal fields."""
        repo = Repository(url="https://github.com/user/repo.git", path="~/code/repo")
        assert repo.url == "https://github.com/user/repo.git"
        assert str(Path("~/code/repo").expanduser().resolve()) in repo.path
        assert repo.vcs is None
        assert repo.name is None
        assert repo.remotes == {}
        assert repo.rev is None
        assert repo.web_url is None

    def test_full_repository(self) -> None:
        """Test creating a repository with all fields."""
        repo = Repository(
            name="test-repo",
            url="https://github.com/user/repo.git",
            path="~/code/repo",
            vcs="git",
            remotes={"upstream": "https://github.com/upstream/repo.git"},
            rev="main",
            web_url="https://github.com/user/repo",
        )
        assert repo.name == "test-repo"
        assert repo.url == "https://github.com/user/repo.git"
        assert str(Path("~/code/repo").expanduser().resolve()) in repo.path
        assert repo.vcs == "git"
        assert repo.remotes == {"upstream": "https://github.com/upstream/repo.git"}
        assert repo.rev == "main"
        assert repo.web_url == "https://github.com/user/repo"

    def test_path_validation(self) -> None:
        """Test path validation."""
        repo = Repository(url="https://github.com/user/repo.git", path="~/code/repo")
        assert str(Path("~/code/repo").expanduser().resolve()) in repo.path

    def test_missing_required_fields(self) -> None:
        """Test validation error when required fields are missing."""
        # Missing path parameter
        with pytest.raises(ValidationError):
            # We need to use model_construct to bypass validation and then
            # validate manually to check for specific missing fields
            repo_no_path = Repository.model_construct(
                url="https://github.com/user/repo.git"
            )
            Repository.model_validate(repo_no_path.model_dump())

        # Missing url parameter
        with pytest.raises(ValidationError):
            repo_no_url = Repository.model_construct(path="~/code/repo")
            Repository.model_validate(repo_no_url.model_dump())


class TestSettings:
    """Tests for the Settings model."""

    def test_default_settings(self) -> None:
        """Test default settings."""
        settings = Settings()
        assert settings.sync_remotes is True
        assert settings.default_vcs is None
        assert settings.depth is None

    def test_custom_settings(self) -> None:
        """Test custom settings."""
        settings = Settings(
            sync_remotes=False,
            default_vcs="git",
            depth=1,
        )
        assert settings.sync_remotes is False
        assert settings.default_vcs == "git"
        assert settings.depth == 1


class TestVCSPullConfig:
    """Tests for the VCSPullConfig model."""

    def test_empty_config(self) -> None:
        """Test empty configuration."""
        config = VCSPullConfig()
        assert isinstance(config.settings, Settings)
        assert config.repositories == []
        assert config.includes == []

    def test_full_config(self) -> None:
        """Test full configuration."""
        config = VCSPullConfig(
            settings=Settings(
                sync_remotes=False,
                default_vcs="git",
                depth=1,
            ),
            repositories=[
                Repository(
                    name="repo1",
                    url="https://github.com/user/repo1.git",
                    path="~/code/repo1",
                    vcs="git",
                ),
                Repository(
                    name="repo2",
                    url="https://github.com/user/repo2.git",
                    path="~/code/repo2",
                    vcs="git",
                ),
            ],
            includes=[
                "~/other-config.yaml",
            ],
        )

        assert config.settings.sync_remotes is False
        assert config.settings.default_vcs == "git"
        assert config.settings.depth == 1

        assert len(config.repositories) == 2
        assert config.repositories[0].name == "repo1"
        assert config.repositories[1].name == "repo2"

        assert len(config.includes) == 1
        assert config.includes[0] == "~/other-config.yaml"
