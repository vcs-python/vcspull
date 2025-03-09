"""Tests for vcspull validation functionality."""

from __future__ import annotations

import os
import typing as t
from pathlib import Path

import pytest

from pydantic import ValidationError
from vcspull import exc, validator
from vcspull.schemas import (
    EMPTY_VALUE_ERROR,
    PATH_EMPTY_ERROR,
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

    # Non-dict repo - note this can be a valid URL string, so we need to use an invalid
    # value
    config_with_non_dict_repo: dict[str, dict[str, t.Any]] = {
        "section1": {
            "repo1": 123,  # This is not a valid repository config
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
    assert "vcs" in message.lower() or EMPTY_VALUE_ERROR in message

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
    assert "url" in message.lower() or EMPTY_VALUE_ERROR in message

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
    assert "path" in message.lower() or PATH_EMPTY_ERROR in message

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
    assert "name" in message.lower() or EMPTY_VALUE_ERROR in message

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
    assert "path" in message.lower() or EMPTY_VALUE_ERROR in message


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
    assert PATH_EMPTY_ERROR in message

    # Path with null character
    valid, message = validator.validate_path("invalid\0path")
    assert not valid
    assert message is not None
    assert "invalid path" in message.lower()


def test_validate_config_structure_valid() -> None:
    """Test validation of valid configuration structures."""
    # Valid configuration with standard repository
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
    valid, message = validator.validate_config_structure(valid_config)
    assert valid
    assert message is None

    # Valid configuration with string URL shorthand
    valid_url_shorthand = {
        "section1": {
            "repo1": "https://example.com/repo.git",
        },
    }
    valid, message = validator.validate_config_structure(valid_url_shorthand)
    assert valid
    assert message is None

    # Valid configuration with multiple sections
    valid_multi_section = {
        "section1": {
            "repo1": {
                "vcs": "git",
                "url": "https://example.com/repo1.git",
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
    valid, message = validator.validate_config_structure(valid_multi_section)
    assert valid
    assert message is None


def test_validate_config_structure_invalid() -> None:
    """Test validation of invalid configuration structures."""
    # None configuration
    valid, message = validator.validate_config_structure(None)
    assert not valid
    assert message is not None
    assert "none" in message.lower()

    # Non-dict configuration
    valid, message = validator.validate_config_structure("not-a-dict")
    assert not valid
    assert message is not None
    assert "dict" in message.lower()

    # Non-string section name
    invalid_section_name = {
        123: {  # Non-string section name
            "repo1": {
                "vcs": "git",
                "url": "https://example.com/repo.git",
                "path": "/tmp/repo",
                "name": "repo1",
            },
        },
    }
    valid, message = validator.validate_config_structure(invalid_section_name)
    assert not valid
    assert message is not None
    assert "section name" in message.lower()

    # Non-dict section
    invalid_section_type = {
        "section1": "not-a-dict",  # Non-dict section
    }
    valid, message = validator.validate_config_structure(invalid_section_type)
    assert not valid
    assert message is not None
    assert "section" in message.lower()

    # Non-string repository name
    invalid_repo_name = {
        "section1": {
            123: {  # Non-string repository name
                "vcs": "git",
                "url": "https://example.com/repo.git",
                "path": "/tmp/repo",
                "name": "repo1",
            },
        },
    }
    valid, message = validator.validate_config_structure(invalid_repo_name)
    assert not valid
    assert message is not None
    assert "repository name" in message.lower()

    # Invalid repository type (not dict or string)
    invalid_repo_type = {
        "section1": {
            "repo1": 123,  # Not a dict or string
        },
    }
    valid, message = validator.validate_config_structure(invalid_repo_type)
    assert not valid
    assert message is not None
    assert "repository" in message.lower()

    # Empty URL string
    empty_url = {
        "section1": {
            "repo1": "",  # Empty URL
        },
    }
    valid, message = validator.validate_config_structure(empty_url)
    assert not valid
    assert message is not None
    assert "empty url" in message.lower()

    # Missing required fields in repository configuration
    missing_fields = {
        "section1": {
            "repo1": {
                # Missing vcs, url, path
                "name": "repo1",
            },
        },
    }
    valid, message = validator.validate_config_structure(missing_fields)
    assert not valid
    assert message is not None
    assert "missing required field" in message.lower()


def test_validate_config_raises_exceptions() -> None:
    """Test that validate_config raises appropriate exceptions."""
    # None configuration
    with pytest.raises(exc.ConfigValidationError) as excinfo:
        validator.validate_config(None)
    assert "none" in str(excinfo.value).lower()

    # Non-dict configuration
    with pytest.raises(exc.ConfigValidationError) as excinfo:
        validator.validate_config("not-a-dict")
    assert "dict" in str(excinfo.value).lower()

    # Invalid section
    with pytest.raises(exc.ConfigValidationError) as excinfo:
        validator.validate_config({"section1": "not-a-dict"})
    assert "section" in str(excinfo.value).lower()

    # Invalid repository
    with pytest.raises(exc.ConfigValidationError) as excinfo:
        validator.validate_config({"section1": {"repo1": 123}})
    error_msg = str(excinfo.value).lower()
    assert "repository" in error_msg or "repo" in error_msg


def test_validate_config_with_valid_config() -> None:
    """Test validate_config with a valid configuration."""
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

    # Should not raise an exception
    validator.validate_config(valid_config)


def test_validate_config_with_complex_config() -> None:
    """Test validate_config with a complex but valid configuration."""
    # Complex config with multiple sections and repo types
    complex_config = {
        "projects": {
            "project1": {
                "vcs": "git",
                "url": "https://github.com/org/project1.git",
                "path": "/projects/project1",
                "name": "project1",
                "remotes": {
                    "upstream": {
                        "url": "https://github.com/upstream/project1.git",
                        "name": "upstream",
                    },
                },
                "shell_command_after": ["echo 'Synced project1'"],
            },
            "project2": "https://github.com/org/project2.git",  # URL shorthand
        },
        "libraries": {
            "lib1": {
                "vcs": "hg",
                "url": "https://hg.example.com/lib1",
                "path": "/libs/lib1",
                "name": "lib1",
            },
            "lib2": {
                "vcs": "svn",
                "url": "https://svn.example.com/lib2",
                "path": "/libs/lib2",
                "name": "lib2",
            },
        },
    }

    # Should not raise an exception
    validator.validate_config(complex_config)


def test_validate_config_nested_validation_errors() -> None:
    """Test that validate_config captures nested validation errors."""
    # Config with multiple validation errors
    invalid_config = {
        "section1": {
            "repo1": {
                "vcs": "git",
                "url": "",  # Empty URL
                "path": "/tmp/repo1",
                "name": "repo1",
            },
            "repo2": {
                "vcs": "invalid",  # Invalid VCS
                "url": "https://example.com/repo2.git",
                "path": "/tmp/repo2",
                "name": "repo2",
            },
        },
        "section2": {
            "repo3": {
                "vcs": "hg",
                "url": "https://example.com/repo3",
                "path": "",  # Empty path
                "name": "repo3",
            },
        },
    }

    with pytest.raises(exc.ConfigValidationError) as excinfo:
        validator.validate_config(invalid_config)

    error_message = str(excinfo.value)

    # Check that the error message includes all the errors
    assert "repo1" in error_message
    assert "repo2" in error_message
    assert "repo3" in error_message
    assert "empty" in error_message.lower()
    assert "invalid" in error_message.lower()


def test_validate_path_with_resolved_path(tmp_path: pathlib.Path) -> None:
    """Test path validation with paths that need resolution."""
    # Create a temporary directory and file for testing
    test_dir = tmp_path / "test_dir"
    test_dir.mkdir()
    test_file = test_dir / "test_file.txt"
    test_file.write_text("test content")

    # Test with relative path
    rel_path = Path("test_dir") / "test_file.txt"

    # Change to the temporary directory
    cwd = Path.cwd()
    try:
        os.chdir(tmp_path)

        # Now the relative path should be valid
        valid, message = validator.validate_path(rel_path)
        assert valid, f"Path validation failed: {message}"
        assert message is None
    finally:
        # Restore original directory
        os.chdir(cwd)

    # Test with path containing environment variables
    if os.name == "posix":
        # Create a test environment variable
        os.environ["TEST_PATH"] = str(tmp_path)

        # Test with path containing environment variable
        env_path = Path("$TEST_PATH") / "test_dir"
        valid, message = validator.validate_path(env_path)
        assert valid, f"Path validation failed: {message}"
        assert message is None


def test_validate_path_with_special_characters() -> None:
    """Test path validation with special characters."""
    # Path with spaces
    valid, message = validator.validate_path("/path/with spaces/file.txt")
    assert valid
    assert message is None

    # Path with unicode characters
    valid, message = validator.validate_path("/path/with/unicode/😀/file.txt")
    assert valid
    assert message is None

    # Path with special characters
    special_path = "/path/with/special/chars/$!@#%^&*()_+-={}[]|;'.,.txt"
    valid, message = validator.validate_path(special_path)
    assert valid
    assert message is None


def test_is_valid_config_with_edge_cases() -> None:
    """Test is_valid_config with edge cases."""
    # Config with extra fields in repository
    config_with_extra_fields = {
        "section1": {
            "repo1": {
                "vcs": "git",
                "url": "https://example.com/repo.git",
                "path": "/tmp/repo",
                "name": "repo1",
                "extra_field": "extra value",  # Extra field
            },
        },
    }
    # Should be valid with extra fields
    assert not validator.is_valid_config(config_with_extra_fields)

    # Config with multiple repositories including a URL shorthand
    mixed_config = {
        "section1": {
            "repo1": {
                "vcs": "git",
                "url": "https://example.com/repo1.git",
                "path": "/tmp/repo1",
                "name": "repo1",
            },
            "repo2": "https://example.com/repo2.git",  # URL shorthand
        },
    }
    assert validator.is_valid_config(mixed_config)

    # Config with nested dictionaries (invalid)
    nested_dict_config = {
        "section1": {
            "repo1": {
                "vcs": "git",
                "url": "https://example.com/repo.git",
                "path": "/tmp/repo",
                "name": "repo1",
                "nested": {  # Nested dictionary
                    "key": "value",
                },
            },
        },
    }
    assert not validator.is_valid_config(nested_dict_config)

    # Config with lists in unexpected places (invalid)
    list_config = {
        "section1": {
            "repo1": {
                "vcs": "git",
                "url": ["https://example.com/repo.git"],  # List instead of string
                "path": "/tmp/repo",
                "name": "repo1",
            },
        },
    }
    assert not validator.is_valid_config(list_config)

    # Config with empty section (valid)
    empty_section_config = {
        "section1": {},
    }
    assert validator.is_valid_config(empty_section_config)


def test_validate_repo_config_with_minimal_config() -> None:
    """Test repository validation with minimal valid config."""
    # Minimal valid repository config with just required fields
    minimal_config = {
        "vcs": "git",
        "url": "https://example.com/repo.git",
        "path": "/tmp/repo",
        "name": "repo1",
    }
    valid, message = validator.validate_repo_config(minimal_config)
    assert valid, f"Validation failed: {message}"
    assert message is None


def test_validate_repo_config_with_extra_fields() -> None:
    """Test repository validation with extra fields."""
    # Repository config with extra fields (should be rejected)
    config_with_extra_fields = {
        "vcs": "git",
        "url": "https://example.com/repo.git",
        "path": "/tmp/repo",
        "name": "repo1",
        "extra_field": "extra value",  # Extra field
    }
    valid, message = validator.validate_repo_config(config_with_extra_fields)
    assert not valid
    assert message is not None
    assert "extra_field" in message.lower() or "extra" in message.lower()


def test_format_pydantic_errors() -> None:
    """Test formatting of Pydantic validation errors."""
    # Create a validation error for testing
    try:
        RawRepositoryModel.model_validate(
            {
                # Missing required fields
                "extra_field": "value",
            },
        )
    except ValidationError as e:
        formatted = validator.format_pydantic_errors(e)

        # Check that the formatted error includes key details
        assert "missing" in formatted.lower()
        assert "required" in formatted.lower()
        assert "vcs" in formatted
        assert "url" in formatted
        assert "path" in formatted
        assert "name" in formatted

    # Test with multiple errors
    try:
        RawRepositoryModel.model_validate(
            {
                "vcs": "invalid",  # Invalid VCS
                "url": "",  # Empty URL
                "path": 123,  # Wrong type for path
                "name": "",  # Empty name
            },
        )
    except ValidationError as e:
        formatted = validator.format_pydantic_errors(e)

        # Check that the formatted error includes all errors
        assert "vcs" in formatted
        assert "url" in formatted
        assert "path" in formatted
        assert "name" in formatted
        assert "empty" in formatted.lower() or "invalid" in formatted.lower()
        assert "type" in formatted.lower()


def test_is_valid_repo_config() -> None:
    """Test is_valid_repo_config function."""
    # Valid config
    valid_config = {
        "vcs": "git",
        "url": "https://example.com/repo.git",
        "path": "/tmp/repo",
        "name": "repo1",
    }
    assert is_valid_repo_config(valid_config)

    # Invalid configs
    # Missing required field
    missing_path = {
        "vcs": "git",
        "url": "https://example.com/repo.git",
        "name": "repo1",
    }
    assert not is_valid_repo_config(missing_path)

    # Invalid VCS
    invalid_vcs = {
        "vcs": "invalid",
        "url": "https://example.com/repo.git",
        "path": "/tmp/repo",
        "name": "repo1",
    }
    assert not is_valid_repo_config(invalid_vcs)

    # Empty URL
    empty_url = {"vcs": "git", "url": "", "path": "/tmp/repo", "name": "repo1"}
    assert not is_valid_repo_config(empty_url)

    # None config
    assert not is_valid_repo_config(None)


def test_validate_config_json() -> None:
    """Test validation of JSON configuration data."""
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
    assert valid, f"JSON validation failed: {message}"
    assert message is None

    # Valid JSON as bytes
    valid, message = validator.validate_config_json(valid_json.encode("utf-8"))
    assert valid, f"JSON bytes validation failed: {message}"
    assert message is None

    # Invalid JSON syntax
    invalid_json_syntax = """
    {
        "section1": {
            "repo1": {
                "vcs": "git",
                "url": "https://example.com/repo.git",
                "path": "/tmp/repo",
                "name": "repo1",
            }  // Extra comma
        }
    }
    """
    valid, message = validator.validate_config_json(invalid_json_syntax)
    assert not valid
    assert message is not None
    assert "json" in message.lower()

    # Valid JSON syntax but invalid config
    invalid_config_json = """
    {
        "section1": {
            "repo1": {
                "vcs": "invalid",
                "url": "",
                "path": "/tmp/repo",
                "name": "repo1"
            }
        }
    }
    """
    valid, message = validator.validate_config_json(invalid_config_json)
    assert not valid
    assert message is not None
    assert "vcs" in message.lower() or "url" in message.lower()

    # Empty JSON
    valid, message = validator.validate_config_json("")
    assert not valid
    assert message is not None
    assert "empty" in message.lower()


def test_get_structured_errors() -> None:
    """Test extraction of structured error information from ValidationError."""
    try:
        # Create a validation error with multiple issues
        RawRepositoryModel.model_validate(
            {
                "vcs": "invalid",  # Invalid VCS
                "url": "",  # Empty URL
                "path": 123,  # Wrong type for path
                "name": "",  # Empty name
                "remotes": {
                    "origin": {
                        # Missing URL in remote
                    },
                },
            },
        )
    except ValidationError as e:
        # Get structured errors
        structured = validator.get_structured_errors(e)

        # Check that all error locations are present
        assert "vcs" in structured
        assert "url" in structured
        assert "path" in structured
        assert "name" in structured
        assert "remotes" in structured

        # Check that each error has the required fields
        for error_list in structured.values():
            for error in error_list:
                assert "msg" in error
                assert "type" in error
