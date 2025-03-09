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

    # Test with None path
    none_path: t.Any = None
    valid, message = validator.validate_path(none_path)
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
    # Test with a non-dict
    non_dict_config: t.Any = "not-a-dict"
    valid, message = validator.validate_config_structure(non_dict_config)
    assert not valid
    assert message is not None

    # None config
    none_config: t.Any = None
    valid, message = validator.validate_config_structure(none_config)
    assert not valid
    assert message is not None

    # Section not string
    config_with_non_string_section: dict[t.Any, t.Any] = {
        123: {
            "repo1": {
                "vcs": "git",
                "url": "https://example.com/repo.git",
                "path": "/tmp/repo",
                "name": "repo1",
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
    config_with_non_string_repo: dict[str, dict[t.Any, t.Any]] = {
        "section1": {
            123: {
                "vcs": "git",
                "url": "https://example.com/repo.git",
                "path": "/tmp/repo",
                "name": "repo1",
            },
        },
    }
    valid, message = validator.validate_config_structure(config_with_non_string_repo)
    assert not valid
    assert message is not None

    # Invalid repo config inside valid structure
    config_with_invalid_repo: dict[str, dict[str, dict[str, t.Any]]] = {
        "section1": {
            "repo1": {
                # Missing required fields
            },
        },
    }
    valid, message = validator.validate_config_structure(config_with_invalid_repo)
    assert not valid
    assert message is not None


def test_validate_config_raises_exceptions() -> None:
    """Test validate_config raises appropriate exceptions."""
    # Test with None
    with pytest.raises(exc.ConfigValidationError) as excinfo:
        validator.validate_config(None)
    assert "None" in str(excinfo.value)

    # Test with non-dict
    not_a_dict: t.Any = "not-a-dict"
    with pytest.raises(exc.ConfigValidationError) as excinfo:
        validator.validate_config(not_a_dict)
    assert "dictionary" in str(excinfo.value)

    # Test with invalid section name
    config_with_non_string_section: dict[t.Any, t.Any] = {
        123: {
            "repo1": {
                "vcs": "git",
                "url": "https://example.com/repo.git",
                "path": "/tmp/repo",
                "name": "repo1",
            },
        },
    }
    with pytest.raises(exc.ConfigValidationError) as excinfo:
        validator.validate_config(config_with_non_string_section)
    assert "Section name" in str(excinfo.value) or "section name" in str(excinfo.value)

    # Test with invalid repo config
    config_with_invalid_repo: dict[str, dict[str, dict[str, t.Any]]] = {
        "section1": {
            "repo1": {
                # Missing required fields
            },
        },
    }
    with pytest.raises(exc.ConfigValidationError) as excinfo:
        validator.validate_config(config_with_invalid_repo)
    assert "required" in str(excinfo.value) or "missing" in str(excinfo.value)


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
    }
    # Should not raise any exceptions
    validator.validate_config(valid_config)

    # Test with more complex config
    complex_config = {
        "my_projects": {
            "project1": {
                "vcs": "git",
                "url": "https://github.com/user/project1.git",
                "path": "/projects/project1",
                "name": "project1",
                "remotes": {
                    "origin": {
                        "url": "https://github.com/user/project1.git",
                    },
                    "upstream": {
                        "url": "https://github.com/upstream/project1.git",
                    },
                },
            },
            "project2": {
                "vcs": "hg",
                "url": "https://example.com/project2",
                "path": "/projects/project2",
                "name": "project2",
            },
        },
        "external": {
            "external1": {
                "vcs": "git",
                "url": "https://github.com/external/external1.git",
                "path": "/external/external1",
                "name": "external1",
                "shell_command_after": [
                    "echo 'Pulled external1'",
                    "make install",
                ],
            },
        },
    }
    # Should not raise any exceptions
    validator.validate_config(complex_config)


def test_validate_config_with_complex_config() -> None:
    """Test validate_config with a complex configuration."""
    # Config with remotes and shell commands
    complex_config = {
        "projects": {
            "myapp": {
                "vcs": "git",
                "url": "https://github.com/user/myapp.git",
                "path": "/home/user/code/myapp",
                "name": "myapp",
                "remotes": {
                    "origin": {
                        "url": "https://github.com/user/myapp.git",
                    },
                    "upstream": {
                        "url": "https://github.com/upstream/myapp.git",
                    },
                },
                "shell_command_after": [
                    "npm install",
                    "npm run build",
                ],
            },
        },
    }
    # Should not raise any exceptions
    validator.validate_config(complex_config)


def test_validate_config_nested_validation_errors() -> None:
    """Test validate_config with nested validation errors."""
    # Config with invalid remotes for a non-git repo
    invalid_config = {
        "projects": {
            "myapp": {
                "vcs": "hg",  # hg doesn't support remotes
                "url": "https://example.com/myapp",
                "path": "/home/user/code/myapp",
                "name": "myapp",
                # This should cause an error since hg doesn't support remotes
                "remotes": {
                    "origin": {
                        "url": "https://example.com/myapp",
                    },
                },
            },
        },
    }
    # Should raise ConfigValidationError with a meaningful message
    with pytest.raises(exc.ConfigValidationError) as excinfo:
        validator.validate_config(invalid_config)
    assert "remotes" in str(excinfo.value).lower()
    assert "git" in str(excinfo.value).lower()


def test_validate_path_with_resolved_path(tmp_path: pathlib.Path) -> None:
    """Test validate_path with a path that needs resolving."""
    # Create a temporary directory and file
    test_file = tmp_path / "test_file.txt"
    test_file.touch()

    # Test with absolute path
    valid, message = validator.validate_path(str(test_file))
    assert valid, f"Expected valid path, got error: {message}"
    assert message is None

    # Test with relative path (should work)
    cwd = pathlib.Path.cwd()
    try:
        os.chdir(str(tmp_path))
        valid, message = validator.validate_path("test_file.txt")
        assert valid, f"Expected valid relative path, got error: {message}"
        assert message is None
    finally:
        os.chdir(str(cwd))

    # Test with home directory expansion (using ~ prefix)
    home_path_str = "~/some_dir"
    # This should be valid even if the path doesn't actually exist
    # because we're just validating the format of the path, not existence
    valid, message = validator.validate_path(home_path_str)
    assert valid, f"Expected valid path with tilde, got error: {message}"
    assert message is None


def test_validate_path_with_special_characters() -> None:
    """Test validate_path with special characters."""
    # Test with spaces in path
    space_path = "/path with spaces/file.txt"
    valid, message = validator.validate_path(space_path)
    assert valid, f"Expected valid path with spaces, got error: {message}"
    assert message is None

    # Test with environment variables
    env_var_path = "$HOME/file.txt"
    valid, message = validator.validate_path(env_var_path)
    assert valid, f"Expected valid path with env var, got error: {message}"
    assert message is None

    # Test with unicode characters if not on Windows
    if os.name != "nt":  # Skip on Windows
        unicode_path = "/path/with/unicode/⌘/file.txt"
        valid, message = validator.validate_path(unicode_path)
        assert valid, f"Expected valid path with unicode, got error: {message}"
        assert message is None


def test_is_valid_config_with_edge_cases() -> None:
    """Test is_valid_config with edge cases."""
    # Empty config with valid structure
    empty_config: dict[str, dict[str, t.Any]] = {
        "section1": {},
    }
    assert validator.is_valid_config(empty_config)

    # Config with empty string section
    empty_section_name_config: dict[str, dict[str, t.Any]] = {
        "": {},
    }
    assert validator.is_valid_config(empty_section_name_config)

    # Config with empty string repo name but valid repo
    empty_repo_name_config = {
        "section1": {
            "": {
                "vcs": "git",
                "url": "https://example.com/repo.git",
                "path": "/tmp/repo",
                "name": "repo_name",  # Still need a valid name field
            },
        },
    }
    assert validator.is_valid_config(empty_repo_name_config)

    # Config with extra fields in repos
    extra_fields_config = {
        "section1": {
            "repo1": {
                "vcs": "git",
                "url": "https://example.com/repo.git",
                "path": "/tmp/repo",
                "name": "repo1",
                "extra_field": "value",  # Extra field, should be allowed in raw config
            },
        },
    }
    assert validator.is_valid_config(extra_fields_config)


def test_validate_repo_config_with_minimal_config() -> None:
    """Test validate_repo_config with minimal configuration."""
    # Minimal valid repo config
    minimal_repo = {
        "vcs": "git",
        "url": "https://example.com/repo.git",
        "path": "/tmp/repo",
        "name": "repo1",
    }
    valid, message = validator.validate_repo_config(minimal_repo)
    assert valid
    assert message is None


def test_validate_repo_config_with_extra_fields() -> None:
    """Test validate_repo_config with extra fields."""
    # Repo config with extra fields
    repo_with_extra = {
        "vcs": "git",
        "url": "https://example.com/repo.git",
        "path": "/tmp/repo",
        "name": "repo1",
        "extra_field": "value",  # Extra field
        "another_extra": 123,  # Another extra field
    }
    valid, message = validator.validate_repo_config(repo_with_extra)
    assert valid
    assert message is None


def test_format_pydantic_errors() -> None:
    """Test format_pydantic_errors function."""
    # Create a ValidationError to format
    try:
        RawRepositoryModel.model_validate({})
    except ValidationError as e:
        formatted = validator.format_pydantic_errors(e)
        # Check for expected sections in the formatted error
        assert "Validation error:" in formatted
        assert "Missing required fields:" in formatted
        assert "vcs" in formatted
        assert "url" in formatted
        assert "path" in formatted
        assert "name" in formatted
        assert "Suggestion:" in formatted


def test_is_valid_repo_config() -> None:
    """Test is_valid_repo_config function."""
    # Valid repo config
    valid_repo = {
        "vcs": "git",
        "url": "https://example.com/repo.git",
        "path": "/tmp/repo",
        "name": "repo1",
    }
    assert is_valid_repo_config(valid_repo)

    # Missing required field
    missing_field_repo = {
        "vcs": "git",
        "url": "https://example.com/repo.git",
        # Missing path
        "name": "repo1",
    }
    assert not is_valid_repo_config(missing_field_repo)

    # Invalid field value
    invalid_value_repo = {
        "vcs": "invalid",  # Invalid VCS type
        "url": "https://example.com/repo.git",
        "path": "/tmp/repo",
        "name": "repo1",
    }
    assert not is_valid_repo_config(invalid_value_repo)

    # None instead of dict
    none_repo: t.Any = None
    assert not is_valid_repo_config(none_repo)

    # String instead of dict
    string_repo: t.Any = "not-a-dict"
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
