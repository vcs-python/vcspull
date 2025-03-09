"""Tests for vcspull validation functionality."""

from __future__ import annotations

import os
import typing as t

import pytest

from pydantic import ValidationError
from vcspull import exc, validator
from vcspull.schemas import (
    RawRepositoryModel,
    is_valid_repo_config,
)

if t.TYPE_CHECKING:
    import pathlib


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
    assert not validator.is_valid_config(None)

    # None key
    invalid_config1: dict[t.Any, t.Any] = {None: {}}
    assert not validator.is_valid_config(invalid_config1)

    # None value
    invalid_config2: dict[str, t.Any] = {"section1": None}
    assert not validator.is_valid_config(invalid_config2)

    # Non-string key
    invalid_config3: dict[t.Any, t.Any] = {123: {}}
    assert not validator.is_valid_config(invalid_config3)

    # Non-dict value
    invalid_config4: dict[str, t.Any] = {"section1": "not-a-dict"}
    assert not validator.is_valid_config(invalid_config4)

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
    """Test repository configuration validation with missing keys."""
    # Missing vcs
    repo_missing_vcs = {
        "url": "https://example.com/repo.git",
        "path": "/tmp/repo",
        "name": "repo1",
    }
    valid, message = validator.validate_repo_config(repo_missing_vcs)
    assert not valid
    assert message is not None
    assert "missing" in message.lower()
    assert "vcs" in message

    # Missing url
    repo_missing_url = {
        "vcs": "git",
        "path": "/tmp/repo",
        "name": "repo1",
    }
    valid, message = validator.validate_repo_config(repo_missing_url)
    assert not valid
    assert message is not None
    assert "missing" in message.lower() or "url" in message.lower()

    # Missing path
    repo_missing_path = {
        "vcs": "git",
        "url": "https://example.com/repo.git",
        "name": "repo1",
    }
    valid, message = validator.validate_repo_config(repo_missing_path)
    assert not valid
    assert message is not None
    assert "missing" in message.lower() or "path" in message.lower()

    # Missing name
    repo_missing_name = {
        "vcs": "git",
        "url": "https://example.com/repo.git",
        "path": "/tmp/repo",
    }
    valid, message = validator.validate_repo_config(repo_missing_name)
    assert not valid
    assert message is not None
    assert "missing" in message.lower() or "name" in message.lower()

    # Missing all required fields
    repo_missing_all = {}
    valid, message = validator.validate_repo_config(repo_missing_all)
    assert not valid
    assert message is not None
    assert "missing" in message.lower()


def test_validate_repo_config_empty_values() -> None:
    """Test repository configuration validation with empty values."""
    # Empty vcs
    repo_empty_vcs: _TestRawConfigDict = {
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
    repo_empty_url: _TestRawConfigDict = {
        "vcs": "git",
        "url": "",
        "path": "/tmp/repo",
        "name": "repo1",
    }
    valid, message = validator.validate_repo_config(repo_empty_url)
    assert not valid
    assert message is not None
    assert "url" in message.lower() or "empty" in message.lower()

    # Empty path
    repo_empty_path: _TestRawConfigDict = {
        "vcs": "git",
        "url": "https://example.com/repo.git",
        "path": "",
        "name": "repo1",
    }
    valid, message = validator.validate_repo_config(repo_empty_path)
    assert not valid
    assert message is not None
    assert "path" in message.lower() or "empty" in message.lower()

    # Empty name
    repo_empty_name: _TestRawConfigDict = {
        "vcs": "git",
        "url": "https://example.com/repo.git",
        "path": "/tmp/repo",
        "name": "",
    }
    valid, message = validator.validate_repo_config(repo_empty_name)
    assert not valid
    assert message is not None
    assert "name" in message.lower() or "empty" in message.lower()

    # Whitespace in values
    repo_whitespace: _TestRawConfigDict = {
        "vcs": "git",
        "url": "https://example.com/repo.git",
        "path": "  ",
        "name": "repo1",
    }
    valid, message = validator.validate_repo_config(repo_whitespace)
    assert not valid
    assert message is not None
    assert (
        "path" in message.lower()
        or "empty" in message.lower()
        or "whitespace" in message.lower()
    )


def test_validate_path_valid(tmp_path: pathlib.Path) -> None:
    """Test path validation with valid paths."""
    # Valid absolute path
    abs_path = tmp_path / "repo"
    # Make sure the directory exists
    abs_path.mkdir(exist_ok=True)
    valid, message = validator.validate_path(abs_path)
    assert valid
    assert message is None

    # Valid relative path
    rel_path = "repo"
    valid, message = validator.validate_path(rel_path)
    assert valid
    assert message is None


def test_validate_path_invalid() -> None:
    """Test path validation with invalid paths."""
    # None path
    valid, message = validator.validate_path(None)
    assert not valid
    assert message is not None
    assert "none" in message.lower()

    # Empty path
    valid, message = validator.validate_path("")
    assert not valid
    assert message is not None
    assert "empty" in message.lower()

    # Path with null character
    valid, message = validator.validate_path("repo\0name")
    assert not valid
    assert message is not None
    assert "null" in message.lower() or "invalid" in message.lower()


def test_validate_config_structure_valid() -> None:
    """Test configuration structure validation with valid configs."""
    # Valid minimal config
    config = {
        "section1": {
            "repo1": {
                "vcs": "git",
                "url": "https://example.com/repo.git",
                "path": "/tmp/repo",
                "name": "repo1",
            },
        },
    }
    valid, message = validator.validate_config_structure(config)
    assert valid
    assert message is None

    # Valid config with multiple sections and repos
    config_multi = {
        "section1": {
            "repo1": {
                "vcs": "git",
                "url": "https://example.com/repo1.git",
                "path": "/tmp/repo1",
                "name": "repo1",
            },
            "repo2": {
                "vcs": "git",
                "url": "https://example.com/repo2.git",
                "path": "/tmp/repo2",
                "name": "repo2",
            },
        },
        "section2": {
            "repo3": {
                "vcs": "hg",
                "url": "https://example.com/repo3",
                "path": "/tmp/repo3",
                "name": "repo3",
            },
        },
    }
    valid, message = validator.validate_config_structure(config_multi)
    assert valid
    assert message is None


def test_validate_config_structure_invalid() -> None:
    """Test configuration structure validation with invalid configs."""
    # None config
    valid, message = validator.validate_config_structure(None)
    assert not valid
    assert message is not None
    assert "none" in message.lower()

    # Non-dict config
    valid, message = validator.validate_config_structure("not-a-dict")
    assert not valid
    assert message is not None
    assert "dictionary" in message.lower()

    # Invalid section value (None)
    config_invalid_section: dict[str, t.Any] = {
        "section1": None,
    }
    valid, message = validator.validate_config_structure(config_invalid_section)
    assert not valid
    assert message is not None

    # Invalid section value (string)
    config_invalid_section2: dict[str, t.Any] = {
        "section1": "not-a-dict",
    }
    valid, message = validator.validate_config_structure(config_invalid_section2)
    assert not valid
    assert message is not None

    # Invalid repo value (None)
    config_invalid_repo: dict[str, dict[str, t.Any]] = {
        "section1": {
            "repo1": None,
        },
    }
    valid, message = validator.validate_config_structure(config_invalid_repo)
    assert not valid
    assert message is not None

    # Invalid repo value (int)
    config_invalid_repo2: dict[str, dict[str, t.Any]] = {
        "section1": {
            "repo1": 123,
        },
    }
    valid, message = validator.validate_config_structure(config_invalid_repo2)
    assert not valid
    assert message is not None

    # Missing required fields in repo
    config_missing_fields: dict[str, dict[str, dict[str, t.Any]]] = {
        "section1": {
            "repo1": {
                # Missing vcs, url, path, name
            },
        },
    }
    valid, message = validator.validate_config_structure(config_missing_fields)
    assert not valid
    assert message is not None
    assert "missing" in message.lower()


def test_validate_config_raises_exceptions() -> None:
    """Test validate_config function raising exceptions."""
    # None config
    with pytest.raises(exc.ConfigValidationError) as excinfo:
        validator.validate_config(None)
    assert "none" in str(excinfo.value).lower()

    # Non-dict config
    with pytest.raises(exc.ConfigValidationError) as excinfo:
        validator.validate_config("not-a-dict")
    assert "dictionary" in str(excinfo.value).lower()

    # Invalid configuration
    invalid_config: dict[str, t.Any] = {"section1": None}
    with pytest.raises(exc.ConfigValidationError) as excinfo:
        validator.validate_config(invalid_config)
    assert "invalid" in str(excinfo.value).lower()

    # Invalid repository
    invalid_repo_config: dict[str, dict[str, t.Any]] = {
        "section1": {
            "repo1": {"invalid": "config"},
        },
    }
    with pytest.raises(exc.ConfigValidationError) as excinfo:
        validator.validate_config(invalid_repo_config)
    assert "invalid" in str(excinfo.value).lower()


def test_validate_config_with_valid_config() -> None:
    """Test validate_config function with valid config."""
    # Valid config
    valid_config = {
        "section1": {
            "repo1": {
                "vcs": "git",
                "url": "https://example.com/repo.git",
                "path": "/tmp/repo",
                "name": "repo1",
            },
        },
    }
    # Should not raise exception
    validator.validate_config(valid_config)


def test_validate_config_with_complex_config() -> None:
    """Test validate_config with a more complex configuration."""
    # Complex valid config
    complex_config = {
        "projects": {
            "repo1": {
                "vcs": "git",
                "url": "https://github.com/user/repo1.git",
                "path": "/home/user/projects/repo1",
                "name": "repo1",
                "remotes": {
                    "origin": {
                        "url": "https://github.com/user/repo1.git",
                    },
                    "upstream": {
                        "url": "https://github.com/upstream/repo1.git",
                    },
                },
                "shell_command_after": [
                    "git fetch --all",
                    "git status",
                ],
            },
            "repo2": "https://github.com/user/repo2.git",  # URL shorthand
        },
        "tools": {
            "tool1": {
                "vcs": "hg",
                "url": "https://hg.example.com/tool1",
                "path": "/home/user/tools/tool1",
                "name": "tool1",
            },
        },
    }
    # Should not raise exception
    validator.validate_config(complex_config)


def test_validate_config_nested_validation_errors() -> None:
    """Test validate_config with nested validation errors."""
    # Config with nested error (invalid remotes for non-git repo)
    invalid_nested_config = {
        "section1": {
            "repo1": {
                "vcs": "hg",  # Not git
                "url": "https://example.com/repo",
                "path": "/tmp/repo",
                "name": "repo1",
                "remotes": {  # Remotes only valid for git
                    "origin": {
                        "url": "https://example.com/repo",
                    },
                },
            },
        },
    }
    with pytest.raises(exc.ConfigValidationError) as excinfo:
        validator.validate_config(invalid_nested_config)
    error_message = str(excinfo.value)
    assert "remotes" in error_message.lower()
    assert "git" in error_message.lower()


def test_validate_path_with_resolved_path(tmp_path: pathlib.Path) -> None:
    """Test path validation with environment variables and user directory."""
    # Set up a temporary environment variable
    env_var_name = "TEST_REPO_PATH"
    old_env = os.environ.get(env_var_name)
    try:
        os.environ[env_var_name] = str(tmp_path)

        # Path with environment variable
        path_with_env = f"${env_var_name}/repo"
        valid, message = validator.validate_path(path_with_env)
        assert valid, f"Path with environment variable should be valid: {message}"
        assert message is None

        # User home directory
        path_with_home = "~/repo"
        valid, message = validator.validate_path(path_with_home)
        assert valid, f"Path with home directory should be valid: {message}"
        assert message is None

    finally:
        # Restore environment
        if old_env is not None:
            os.environ[env_var_name] = old_env
        else:
            os.environ.pop(env_var_name, None)


def test_validate_path_with_special_characters() -> None:
    """Test path validation with special characters."""
    # Path with spaces
    path_with_spaces = "/tmp/path with spaces"
    valid, message = validator.validate_path(path_with_spaces)
    assert valid
    assert message is None

    # Path with unicode characters
    path_with_unicode = "/tmp/üñîçõdê_pàth"
    valid, message = validator.validate_path(path_with_unicode)
    assert valid
    assert message is None

    # Path with other special characters
    path_with_special = "/tmp/path-with_special.chars"
    valid, message = validator.validate_path(path_with_special)
    assert valid
    assert message is None


def test_is_valid_config_with_edge_cases() -> None:
    """Test is_valid_config with edge cases."""
    # Empty config
    empty_config: dict[str, t.Any] = {}
    assert validator.is_valid_config(empty_config)

    # Empty section
    empty_section_config = {
        "section1": {},
    }
    assert validator.is_valid_config(empty_section_config)

    # URL string shorthand
    url_string_config = {
        "section1": {
            "repo1": "https://github.com/user/repo.git",
        },
    }
    assert validator.is_valid_config(url_string_config)

    # Mixed URL string and repo dict
    mixed_config = {
        "section1": {
            "repo1": "https://github.com/user/repo1.git",
            "repo2": {
                "vcs": "git",
                "url": "https://github.com/user/repo2.git",
                "path": "/tmp/repo2",
                "name": "repo2",
            },
        },
    }
    assert validator.is_valid_config(mixed_config)

    # Extra fields in repo
    extra_fields_config = {
        "section1": {
            "repo1": {
                "vcs": "git",
                "url": "https://github.com/user/repo.git",
                "path": "/tmp/repo",
                "name": "repo1",
                "extra_field": "value",
                "another_field": 123,
            },
        },
    }
    assert validator.is_valid_config(extra_fields_config)


def test_validate_repo_config_with_minimal_config() -> None:
    """Test validate_repo_config with minimal config."""
    # Minimal config with URL string
    minimal_config = {
        "vcs": "git",
        "url": "https://example.com/repo.git",
        "path": "/tmp/repo",
        "name": "repo1",
    }
    valid, message = validator.validate_repo_config(minimal_config)
    assert valid
    assert message is None


def test_validate_repo_config_with_extra_fields() -> None:
    """Test validate_repo_config with extra fields."""
    # Config with extra fields
    config_with_extra: _TestRawConfigDict = {
        "vcs": "git",
        "url": "https://example.com/repo.git",
        "path": "/tmp/repo",
        "name": "repo1",
        "custom_field": "value",
    }
    valid, message = validator.validate_repo_config(config_with_extra)
    assert valid
    assert message is None


def test_format_pydantic_errors() -> None:
    """Test format_pydantic_errors function."""
    # Create a ValidationError
    try:
        RawRepositoryModel.model_validate(
            {
                # Missing required fields
            },
        )
        pytest.fail("Should have raised ValidationError")
    except ValidationError as e:
        # Format the error
        formatted = validator.format_pydantic_errors(e)

        # Check common elements
        assert "Validation error:" in formatted
        assert "Missing required fields:" in formatted

        # Make sure it includes the missing fields
        assert "vcs" in formatted
        assert "name" in formatted
        assert "url" in formatted
        assert "path" in formatted

        # Should include suggestion
        assert "Suggestion:" in formatted


def test_is_valid_repo_config() -> None:
    """Test is_valid_repo_config."""
    # Valid repo config
    valid_repo = {
        "vcs": "git",
        "url": "https://example.com/repo.git",
        "path": "/tmp/repo",
        "name": "repo1",
    }
    assert is_valid_repo_config(valid_repo)

    # Invalid repo config (missing fields)
    invalid_repo = {
        "vcs": "git",
        # Missing other required fields
    }
    assert not is_valid_repo_config(invalid_repo)

    # None instead of dict
    assert not is_valid_repo_config(None)

    # String instead of dict
    string_repo = "https://example.com/repo.git"
    assert not is_valid_repo_config(string_repo)


def test_validate_config_json() -> None:
    """Test validate_config_json function."""
    # Valid JSON config
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
            },  // Extra comma
        }
    }
    """
    valid, message = validator.validate_config_json(invalid_json)
    assert not valid
    assert message is not None
    assert "JSON" in message

    # Valid JSON but invalid config
    invalid_config_json = """
    {
        "section1": {
            "repo1": {
                "vcs": "invalid",
                "url": "https://example.com/repo.git",
                "path": "/tmp/repo",
                "name": "repo1"
            }
        }
    }
    """
    valid, message = validator.validate_config_json(invalid_config_json)
    assert not valid
    assert message is not None


def test_get_structured_errors() -> None:
    """Test get_structured_errors function."""
    # Create a ValidationError
    try:
        RawRepositoryModel.model_validate(
            {
                # Missing required fields
            },
        )
        pytest.fail("Should have raised ValidationError")
    except ValidationError as e:
        # Get structured errors
        structured = validator.get_structured_errors(e)

        # Check structure
        assert "error" in structured
        assert "detail" in structured
        assert "error_count" in structured
        assert "summary" in structured

        # Check error details
        assert structured["error"] == "ValidationError"
        assert isinstance(structured["error_count"], int)
        assert structured["error_count"] > 0
        assert isinstance(structured["detail"], dict)

        # At least one error category should exist
        assert len(structured["detail"]) > 0

        # Check error details for missing fields
        for errors in structured["detail"].values():
            for error in errors:
                assert "location" in error
                assert "message" in error
                # Other fields may be present (context, url, input)
