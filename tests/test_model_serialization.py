"""Tests for Pydantic model serialization and type coercion in vcspull."""

from __future__ import annotations

import pathlib

import pytest
from pydantic import BaseModel, ValidationError

from vcspull.schemas import (
    RawConfigDictModel,
    RawRepositoryModel,
)


def test_model_serialization() -> None:
    """Test serialization of models to dictionaries."""
    # Create a repository model
    repo_model = RawRepositoryModel.model_validate(
        {
            "vcs": "git",
            "url": "git+https://github.com/user/repo.git",
            "path": "/tmp/repo",
            "name": "repo",
        },
    )

    # Convert model to dictionary
    repo_dict = repo_model.model_dump()

    # Check that the dictionary has all expected fields
    assert repo_dict["vcs"] == "git"
    assert repo_dict["url"] == "git+https://github.com/user/repo.git"
    assert repo_dict["path"] == "/tmp/repo"
    assert repo_dict["name"] == "repo"


def test_model_serialization_with_nested_models() -> None:
    """Test serialization of models with nested structures."""
    # Create a config with multiple repositories
    config_dict = {
        "/tmp/repos": {
            "repo1": {
                "vcs": "git",
                "url": "git+https://github.com/user/repo1.git",
            },
            "repo2": {
                "vcs": "git",
                "url": "git+https://github.com/user/repo2.git",
            },
        },
    }
    config_model = RawConfigDictModel.model_validate(config_dict)

    # Convert model to dictionary
    config_dict_out = config_model.model_dump()

    # Check that nested structure is preserved
    assert "/tmp/repos" in config_dict_out
    assert "repo1" in config_dict_out["/tmp/repos"]
    assert "repo2" in config_dict_out["/tmp/repos"]
    assert config_dict_out["/tmp/repos"]["repo1"]["vcs"] == "git"
    assert (
        config_dict_out["/tmp/repos"]["repo1"]["url"]
        == "git+https://github.com/user/repo1.git"
    )


def test_field_type_coercion() -> None:
    """Test automatic type conversion for fields."""

    # Create a model with a path field that should be converted to Path
    class TestModel(BaseModel):
        path: pathlib.Path

    # Test conversion of string path to Path object
    model = TestModel(path="/tmp/repo")

    # Check that path was converted to Path object
    assert isinstance(model.path, pathlib.Path)
    assert model.path == pathlib.Path("/tmp/repo")


def test_field_type_coercion_from_dict() -> None:
    """Test type coercion when loading from dictionary."""

    # Create a model with a path field that should be converted to Path
    class TestModel(BaseModel):
        path: pathlib.Path

    # Create a dictionary with string path
    data = {"path": "/tmp/repo"}

    # Convert to model
    model = TestModel.model_validate(data)

    # Check that path was converted to Path object
    assert isinstance(model.path, pathlib.Path)
    assert model.path == pathlib.Path("/tmp/repo")


def test_coercion_of_boolean_fields() -> None:
    """Test coercion of boolean fields."""

    # Create a model with a boolean field
    class TestModel(BaseModel):
        test_bool: bool

    # Create models with various boolean-like values
    boolean_values = [
        (True, True),  # True stays True
        (False, False),  # False stays False
        ("true", True),  # String "true" becomes True
        ("false", False),  # String "false" becomes False
        ("yes", True),  # String "yes" becomes True
        ("no", False),  # String "no" becomes False
        (1, True),  # 1 becomes True
        (0, False),  # 0 becomes False
    ]

    for input_value, expected_value in boolean_values:
        # Create the model and check coercion
        model = TestModel(test_bool=input_value)
        assert model.test_bool == expected_value


def test_coercion_failures() -> None:
    """Test behavior when type coercion fails."""
    # Try to use an invalid value for VCS field
    repo_dict = {
        "vcs": 123,  # Should be a string, not int
        "url": "git+https://github.com/user/repo.git",
        "path": "/tmp/repo",
        "name": "repo",
    }

    # Should raise a validation error
    with pytest.raises(ValidationError) as excinfo:
        RawRepositoryModel.model_validate(repo_dict)

    # Check that the error message mentions the type issue
    assert "string_type" in str(excinfo.value)


def test_roundtrip_conversion() -> None:
    """Test that converting model to dict and back preserves data."""
    # Original model
    original_data = {
        "vcs": "git",
        "url": "git+https://github.com/user/repo.git",
        "path": "/tmp/repo",
        "name": "repo",
        "remotes": {"origin": {"url": "git+https://github.com/user/repo.git"}},
        "shell_command_after": ["echo 'Done'"],
    }

    original_model = RawRepositoryModel.model_validate(original_data)

    # Convert to dict
    model_dict = original_model.model_dump()

    # Convert back to model
    new_model = RawRepositoryModel.model_validate(model_dict)

    # Check that all fields match
    assert new_model.vcs == original_model.vcs
    assert new_model.url == original_model.url
    assert new_model.path == original_model.path
    assert new_model.name == original_model.name
    assert new_model.remotes == original_model.remotes
    assert new_model.shell_command_after == original_model.shell_command_after
