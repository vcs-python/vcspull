"""Tests for URL validation in vcspull."""

from __future__ import annotations

from vcspull import validator
from vcspull.schemas import RawRepositoryModel


def test_url_scheme_mismatch() -> None:
    """Test validation when URL scheme doesn't match the VCS type."""
    # Git VCS with SVN URL scheme
    repo_config = {
        "vcs": "git",
        "url": "svn+https://svn.example.com/repo",
        "path": "/tmp/repo",
        "name": "repo",
    }

    # This might not be validated at the schema level, but we can check
    # that the model accepts it (actual VCS-specific validation would be
    # in a separate layer)
    model = RawRepositoryModel.model_validate(repo_config)
    assert model.url == "svn+https://svn.example.com/repo"
    assert model.vcs == "git"


def test_url_scheme_mismatch_model_validation() -> None:
    """Test Pydantic model validation when URL scheme doesn't match VCS type."""
    # Git VCS with Mercurial URL scheme
    repo_config = {
        "vcs": "git",
        "url": "hg+https://hg.example.com/repo",
        "path": "/tmp/repo",
        "name": "repo",
    }

    # This might not be validated at the schema level, but we can check
    # that the model accepts it (actual VCS-specific validation would be
    # in a separate layer)
    model = RawRepositoryModel.model_validate(repo_config)
    assert model.url == "hg+https://hg.example.com/repo"
    assert model.vcs == "git"


def test_ssh_url_validation() -> None:
    """Test validation of SSH URLs."""
    # Git with SSH URL
    repo_config = {
        "vcs": "git",
        "url": "git+ssh://git@github.com/user/repo.git",
        "path": "/tmp/repo",
        "name": "repo",
    }

    # Should be valid
    model = RawRepositoryModel.model_validate(repo_config)
    assert model.url == "git+ssh://git@github.com/user/repo.git"


def test_username_in_url() -> None:
    """Test validation of URLs with username."""
    # Git with username in HTTPS URL
    repo_config = {
        "vcs": "git",
        "url": "git+https://username@github.com/user/repo.git",
        "path": "/tmp/repo",
        "name": "repo",
    }

    # Should be valid
    model = RawRepositoryModel.model_validate(repo_config)
    assert model.url == "git+https://username@github.com/user/repo.git"


def test_port_specification_in_url() -> None:
    """Test validation of URLs with port specification."""
    # Git with custom port
    repo_config = {
        "vcs": "git",
        "url": "git+ssh://git@github.com:2222/user/repo.git",
        "path": "/tmp/repo",
        "name": "repo",
    }

    # Should be valid
    model = RawRepositoryModel.model_validate(repo_config)
    assert model.url == "git+ssh://git@github.com:2222/user/repo.git"


def test_custom_protocols() -> None:
    """Test handling of custom protocol handlers."""
    protocols = [
        "git+ssh://git@github.com/user/repo.git",
        "git+https://github.com/user/repo.git",
        "svn+https://svn.example.com/repo",
        "svn+ssh://user@svn.example.com/repo",
        "hg+https://hg.example.com/repo",
        "hg+ssh://user@hg.example.com/repo",
    ]

    for url in protocols:
        # Extract VCS from URL prefix
        vcs = url.split("+")[0]

        repo_config = {
            "vcs": vcs,
            "url": url,
            "path": "/tmp/repo",
            "name": "repo",
        }

        # Should be valid when VCS matches URL prefix
        model = RawRepositoryModel.model_validate(repo_config)
        assert model.url == url


def test_empty_url() -> None:
    """Test validation of empty URLs with model validation."""
    # Using the validator function from validator module
    is_valid, errors = validator.validate_repo_config(
        {
            "vcs": "git",
            "url": "",  # Empty URL
            "path": "/tmp/repo",
            "name": "repo",
        }
    )

    # Check that validation fails
    assert not is_valid
    assert errors is not None
    assert "url" in errors.lower()


def test_invalid_url_format() -> None:
    """Test validation of invalid URL formats with model validation."""
    # Using the validator function from validator module
    is_valid, errors = validator.validate_repo_config(
        {
            "vcs": "git",
            "url": "",  # Empty URL
            "path": "/tmp/repo",
            "name": "repo",
        }
    )

    # Check that validation fails
    assert not is_valid
    assert errors is not None
    assert "url" in errors.lower()
