"""Tests for vcspull validation functionality."""

from __future__ import annotations

import os
import pathlib
import typing as t

import pytest

from pydantic import ValidationError
from vcspull import exc, validator
from vcspull.schemas import (
    RawRepositoryModel,
    is_valid_repo_config,
)


# Create a more flexible version of RawConfigDict for testing
# Adding _TestRaw prefix to avoid pytest collecting this as a test class
class _TestRawConfigDict(t.TypedDict, total=False):
    """Flexible config dict for testing."""

    vcs: t.Literal["git", "hg", "svn"] | str  # Allow empty string for tests
    name: str
    path: str | pathlib.Path
    url: str
    remotes: dict[str, t.Any]
    shell_command_after: list[str]
    custom_field: str


def test_is_valid_config_valid() -> None:
    """Test valid configurations with is_valid_config."""
    # Valid minimal config
    config = {
        "section1": {
            "repo1": {
                "vcs": "git",
                "url": "https://example.com/repo.git",
                "path": "/tmp/path",
                "name": "repo1",
            },
        },
    }
    assert validator.is_valid_config(config)


def test_is_valid_config_invalid() -> None:
    """Test invalid configurations with is_valid_config."""
    # None instead of dict
    assert not validator.is_valid_config(None)  # type: ignore

    # None key
    invalid_config1 = {None: {}}  # type: ignore
    assert not validator.is_valid_config(invalid_config1)  # type: ignore

    # None value
    invalid_config2 = {"section1": None}  # type: ignore
    assert not validator.is_valid_config(invalid_config2)  # type: ignore

    # Non-string key
    invalid_config3 = {123: {}}  # type: ignore
    assert not validator.is_valid_config(invalid_config3)  # type: ignore

    # Non-dict value
    invalid_config4 = {"section1": "not-a-dict"}  # type: ignore
    assert not validator.is_valid_config(invalid_config4)  # type: ignore

    # Non-dict repo
    config_with_non_dict_repo: dict[str, dict[str, t.Any]] = {
        "section1": {
            "repo1": "not-a-dict-or-url-string",
        },
    }
    assert not validator.is_valid_config(config_with_non_dict_repo)

    # Missing required fields in repo dict
    config_with_missing_fields: dict[str, dict[str, dict[str, t.Any]]] = {
        "section1": {
            "repo1": {
                # Missing vcs, url, path
            },
        },
    }
    assert not validator.is_valid_config(config_with_missing_fields)


def test_validate_repo_config_valid() -> None:
    """Test valid repository configuration validation."""
    valid_repo = {
        "vcs": "git",
        "url": "https://example.com/repo.git",
        "path": "/tmp/repo",
        "name": "repo1",
    }
    valid, message = validator.validate_repo_config(valid_repo)
    assert valid
    assert message is None


def test_validate_repo_config_missing_keys() -> None:
    """Test repository validation with missing keys."""
    # Missing vcs
    repo_missing_vcs = {
        "url": "https://example.com/repo.git",
        "path": "/tmp/repo",
        "name": "repo1",
    }
    valid, message = validator.validate_repo_config(repo_missing_vcs)
    assert not valid
    assert message is not None
    assert "vcs" in message.lower()

    # Missing url
    repo_missing_url = {
        "vcs": "git",
        "path": "/tmp/repo",
        "name": "repo1",
    }
    valid, message = validator.validate_repo_config(repo_missing_url)
    assert not valid
    assert message is not None
    assert "url" in message.lower()

    # Missing path
    repo_missing_path = {
        "vcs": "git",
        "url": "https://example.com/repo.git",
        "name": "repo1",
    }
    valid, message = validator.validate_repo_config(repo_missing_path)
    assert not valid
    assert message is not None
    assert "path" in message.lower()

    # Missing name
    repo_missing_name = {
        "vcs": "git",
        "url": "https://example.com/repo.git",
        "path": "/tmp/repo",
    }
    valid, message = validator.validate_repo_config(repo_missing_name)
    assert not valid
    assert message is not None
    assert "name" in message.lower()


def test_validate_repo_config_empty_values() -> None:
    """Test repository validation with empty values."""
    # Empty vcs
    repo_empty_vcs = {
        "vcs": "",
        "url": "https://example.com/repo.git",
        "path": "/tmp/repo",
        "name": "repo1",
    }
    valid, message = validator.validate_repo_config(repo_empty_vcs)
    assert not valid
    assert message is not None
    assert "vcs" in message.lower()

    # Empty url
    repo_empty_url = {
        "vcs": "git",
        "url": "",
        "path": "/tmp/repo",
        "name": "repo1",
    }
    valid, message = validator.validate_repo_config(repo_empty_url)
    assert not valid
    assert message is not None
    assert "url" in message.lower()

    # Empty path
    repo_empty_path = {
        "vcs": "git",
        "url": "https://example.com/repo.git",
        "path": "",
        "name": "repo1",
    }
    valid, message = validator.validate_repo_config(repo_empty_path)
    assert not valid
    assert message is not None
    assert "path" in message.lower()

    # Empty name (shouldn't be allowed)
    repo_empty_name = {
        "vcs": "git",
        "url": "https://example.com/repo.git",
        "path": "/tmp/repo",
        "name": "",
    }
    valid, message = validator.validate_repo_config(repo_empty_name)
    assert not valid
    assert message is not None
    assert "name" in message.lower()


def test_validate_path_valid(tmp_path: pathlib.Path) -> None:
    """Test valid path validation."""
    path_str = str(tmp_path)
    valid, message = validator.validate_path(path_str)
    assert valid
    assert message is None

    # Test with Path object
    valid, message = validator.validate_path(tmp_path)
    assert valid
    assert message is None


def test_validate_path_invalid() -> None:
    """Test invalid path validation."""
    # Invalid path characters (platform-specific)
    if os.name == "nt":  # Windows
        invalid_path = "C:\\invalid\\path\\with\\*\\character"
    else:
        invalid_path = "/invalid/path/with/\0/character"

    valid, message = validator.validate_path(invalid_path)
    assert not valid
    assert message is not None
    assert "invalid" in message.lower()

    # Test with None
    valid, message = validator.validate_path(None)  # type: ignore
    assert not valid
    assert message is not None


def test_validate_config_structure_valid() -> None:
    """Test valid configuration structure validation."""
    # Basic valid structure
    valid_config = {
        "section1": {
            "repo1": {
                "vcs": "git",
                "url": "https://example.com/repo.git",
                "path": "/tmp/repo1",
                "name": "repo1",
            },
        },
        "section2": {
            "repo2": {
                "vcs": "hg",
                "url": "https://example.com/repo2",
                "path": "/tmp/repo2",
                "name": "repo2",
            },
        },
    }
    valid, message = validator.validate_config_structure(valid_config)
    assert valid
    assert message is None


def test_validate_config_structure_invalid() -> None:
    """Test invalid configuration structure validation."""
    # Not a dict
    non_dict_config = "not-a-dict"
    valid, message = validator.validate_config_structure(non_dict_config)
    assert not valid
    assert message is not None

    # None config
    valid, message = validator.validate_config_structure(None)
    assert not valid
    assert message is not None

    # Section name not string
    config_with_non_string_section: dict[t.Any, dict[str, t.Any]] = {
        123: {  # type: ignore
            "repo1": {
                "vcs": "git",
                "url": "https://example.com/repo.git",
                "path": "/tmp/repo1",
            },
        },
    }
    valid, message = validator.validate_config_structure(config_with_non_string_section)
    assert not valid
    assert message is not None

    # Section not dict
    config_with_non_dict_section: dict[str, t.Any] = {"section1": "not-a-dict"}
    valid, message = validator.validate_config_structure(config_with_non_dict_section)
    assert not valid
    assert message is not None

    # Repo name not string
    config_with_non_string_repo_name: dict[str, dict[t.Any, t.Any]] = {
        "section1": {
            123: {  # type: ignore
                "vcs": "git",
                "url": "https://example.com/repo.git",
                "path": "/tmp/repo1",
            },
        },
    }
    valid, message = validator.validate_config_structure(
        config_with_non_string_repo_name,
    )
    assert not valid
    assert message is not None


def test_validate_config_raises_exceptions() -> None:
    """Test validate_config raises appropriate exceptions."""
    # Invalid structure
    invalid_config = "not-a-dict"
    with pytest.raises(exc.ConfigValidationError) as excinfo:
        validator.validate_config(invalid_config)
    assert "structure" in str(excinfo.value).lower()

    # Missing required fields
    missing_fields_config: dict[str, dict[str, dict[str, t.Any]]] = {
        "section1": {
            "repo1": {
                # Missing required fields vcs, url, path
            },
        },
    }
    with pytest.raises(exc.ConfigValidationError) as excinfo:
        validator.validate_config(missing_fields_config)
    # Check that error message mentions the missing fields
    error_msg = str(excinfo.value)
    assert "missing" in error_msg.lower()

    # Invalid repository configuration
    invalid_repo_config = {
        "section1": {
            "repo1": {
                "vcs": "unsupported-vcs",  # Invalid VCS
                "url": "https://example.com/repo.git",
                "path": "/tmp/repo1",
                "name": "repo1",
            },
        },
    }
    with pytest.raises(exc.ConfigValidationError) as excinfo:
        validator.validate_config(invalid_repo_config)
    assert "vcs" in str(excinfo.value).lower()


def test_validate_config_with_valid_config() -> None:
    """Test validate_config with a valid configuration."""
    valid_config = {
        "section1": {
            "repo1": {
                "vcs": "git",
                "url": "https://example.com/repo.git",
                "path": "/tmp/repo1",
                "name": "repo1",
            },
        },
        "section2": {
            "repo2": {
                "vcs": "hg",
                "url": "https://example.com/repo2",
                "path": "/tmp/repo2",
                "name": "repo2",
            },
        },
    }
    # Should not raise exception
    validator.validate_config(valid_config)

    # Test with extra fields (should be allowed in raw config)
    valid_config_with_extra = {
        "section1": {
            "repo1": {
                "vcs": "git",
                "url": "https://example.com/repo.git",
                "path": "/tmp/repo1",
                "name": "repo1",
                "extra_field": "value",
            },
        },
    }
    # Should not raise exception
    validator.validate_config(valid_config_with_extra)


def test_validate_config_with_complex_config() -> None:
    """Test validate_config with a more complex configuration."""
    complex_config = {
        "section1": {
            "repo1": {
                "vcs": "git",
                "url": "https://example.com/repo.git",
                "path": "/tmp/repo1",
                "name": "repo1",
                "remotes": {
                    "origin": {"url": "https://example.com/repo.git"},
                    "upstream": {"url": "https://upstream.com/repo.git"},
                },
                "shell_command_after": ["echo 'Repo updated'", "git status"],
            },
        },
    }
    # Should not raise exception
    validator.validate_config(complex_config)


def test_validate_config_nested_validation_errors() -> None:
    """Test validate_config with nested validation errors."""
    config_with_invalid_nested = {
        "section1": {
            "repo1": {
                "vcs": "git",
                "url": "https://example.com/repo.git",
                "path": "/tmp/repo1",
                "name": "repo1",
                "remotes": {
                    "origin": "not-a-dict",  # Should be a dict, not a string
                },
            },
        },
    }
    with pytest.raises(exc.ConfigValidationError) as excinfo:
        validator.validate_config(config_with_invalid_nested)
    error_msg = str(excinfo.value)
    assert "remotes" in error_msg.lower() or "origin" in error_msg.lower()


def test_validate_path_with_resolved_path(tmp_path: pathlib.Path) -> None:
    """Test validate_path with resolved path in a temporary directory."""
    # Change to the temporary directory for this test
    original_dir = pathlib.Path.cwd()
    try:
        os.chdir(tmp_path)

        # Create a subdirectory in the temp directory
        test_dir = tmp_path / "test_dir"
        test_dir.mkdir()

        # Validate the path - should resolve relative to cwd (tmp_path)
        valid, msg = validator.validate_path("test_dir")
        assert valid
        assert msg is None

        # Test the entire validation flow with path resolution
        # RepositoryModel will resolve relative paths when used in the full flow
        config = {
            "section": {
                "repo": {
                    "vcs": "git",
                    "name": "test-repo",
                    "path": "test_dir",  # Relative path
                    "url": "https://example.com/repo.git",
                },
            },
        }

        # Check that the validation passes
        is_valid = validator.is_valid_config(config)
        assert is_valid
    finally:
        os.chdir(original_dir)


def test_validate_path_with_special_characters() -> None:
    """Test validate_path with special characters."""
    # Test with spaces
    path_with_spaces = "/tmp/path with spaces"
    valid, message = validator.validate_path(path_with_spaces)
    assert valid
    assert message is None

    # Test with unicode characters (ensure they don't cause validation errors)
    path_with_unicode = "/tmp/path/with/unicode/👍"
    valid, message = validator.validate_path(path_with_unicode)
    assert valid
    assert message is None

    # Test with percent encoding
    path_with_percent = "/tmp/path%20with%20encoding"
    valid, message = validator.validate_path(path_with_percent)
    assert valid
    assert message is None


def test_is_valid_config_with_edge_cases() -> None:
    """Test is_valid_config with edge cases."""
    # Empty config
    empty_config: dict[str, dict[str, t.Any]] = {}
    assert validator.is_valid_config(empty_config)

    # Empty section
    config_with_empty_section: dict[str, dict[str, t.Any]] = {"section1": {}}
    assert validator.is_valid_config(config_with_empty_section)

    # Config with multiple sections and repositories
    complex_config = {
        "section1": {
            "repo1": {
                "vcs": "git",
                "url": "https://example.com/repo1.git",
                "path": "/tmp/repo1",
                "name": "repo1",
            },
            "repo2": {
                "vcs": "hg",
                "url": "https://example.com/repo2",
                "path": "/tmp/repo2",
                "name": "repo2",
            },
        },
        "section2": {
            "repo3": {
                "vcs": "svn",
                "url": "https://example.com/repo3",
                "path": "/tmp/repo3",
                "name": "repo3",
            },
        },
    }
    assert validator.is_valid_config(complex_config)


def test_validate_repo_config_with_minimal_config() -> None:
    """Test validate_repo_config with minimal configuration."""
    minimal_repo = {
        "vcs": "git",
        "url": "https://example.com/repo.git",
        "path": "/tmp/repo",
        "name": "repo",
    }
    valid, message = validator.validate_repo_config(minimal_repo)
    assert valid
    assert message is None


def test_validate_repo_config_with_extra_fields() -> None:
    """Test validate_repo_config with extra fields."""
    repo_with_extra_fields = {
        "vcs": "git",
        "url": "https://example.com/repo.git",
        "path": "/tmp/repo",
        "name": "repo",
        "extra_field": "value",
        "another_field": 123,
    }
    valid, message = validator.validate_repo_config(repo_with_extra_fields)
    assert valid
    assert message is None


def test_format_pydantic_errors() -> None:
    """Test format_pydantic_errors utility function."""
    try:
        # Create an invalid model to trigger validation error
        RawRepositoryModel.model_validate(
            {
                # Omit required fields to trigger validation error
                "vcs": "invalid",
            },
        )
        pytest.fail("Should have raised ValidationError")
    except ValidationError as e:
        # Format the error
        formatted = validator.format_pydantic_errors(e)

        # Check that the error message contains relevant information
        assert "missing" in formatted.lower() or "required" in formatted.lower()
        assert "url" in formatted.lower()
        assert "path" in formatted.lower()
        assert "name" in formatted.lower()


def test_is_valid_repo_config() -> None:
    """Test the is_valid_repo_config function."""
    # Valid repository config
    valid_repo = {
        "vcs": "git",
        "url": "https://example.com/repo.git",
        "path": "/tmp/repo",
        "name": "test",
    }
    assert is_valid_repo_config(valid_repo)

    # Invalid repository config (missing fields)
    invalid_repo = {
        "vcs": "git",
        # Missing url, path, and name
    }
    assert not is_valid_repo_config(invalid_repo)

    # Invalid VCS type
    invalid_vcs_repo = {
        "vcs": "invalid",
        "url": "https://example.com/repo.git",
        "path": "/tmp/repo",
        "name": "test",
    }
    assert not is_valid_repo_config(invalid_vcs_repo)

    # Test with None
    assert not is_valid_repo_config(None)  # type: ignore


def test_validate_config_json() -> None:
    """Test validating config from JSON."""
    # Valid JSON
    valid_json = """
    {
        "section1": {
            "repo1": {
                "vcs": "git",
                "url": "https://example.com/repo.git",
                "path": "/tmp/repo",
                "name": "repo1"
            }
        }
    }
    """
    valid, message = validator.validate_config_json(valid_json)
    assert valid
    assert message is None

    # Invalid JSON syntax
    invalid_json = """
    {
        "section1": {
            "repo1": {
                "vcs": "git",
                "url": "https://example.com/repo.git",
                "path": "/tmp/repo",
                "name": "repo1"
            },
        }
    }
    """
    valid, message = validator.validate_config_json(invalid_json)
    assert not valid
    assert message is not None
    assert "json" in message.lower()

    # Invalid content (missing required fields)
    invalid_content_json = """
    {
        "section1": {
            "repo1": {
                "vcs": "git"
            }
        }
    }
    """
    valid, message = validator.validate_config_json(invalid_content_json)
    assert not valid
    assert message is not None

    # Empty JSON data
    valid, message = validator.validate_config_json("")
    assert not valid
    assert message is not None
