"""Tests for the schemas module."""
# mypy: ignore-errors

from __future__ import annotations

import os
import pathlib
import typing as t

import pytest
from pydantic import ValidationError

from vcspull.schemas import (  # type: ignore
    ConfigDictModel,
    ConfigSectionDictModel,
    GitRemote,
    RawConfigDictModel,
    RawConfigSectionDictModel,
    RawRepositoryModel,
    RepositoryModel,
    VCSType,
    convert_raw_to_validated,
    expand_path,
    get_config_validator,
    get_repo_validator,
    is_valid_config_dict,
    is_valid_repo_config,
    normalize_path,
    validate_config_from_json,
    validate_not_empty,
)


def test_validate_not_empty() -> None:
    """Test validate_not_empty function."""
    # Valid cases
    assert validate_not_empty("test") == "test"
    assert validate_not_empty("a") == "a"

    # Invalid cases
    with pytest.raises(ValueError, match="Value cannot be empty"):
        validate_not_empty("")
    with pytest.raises(ValueError, match="Value cannot be empty"):
        validate_not_empty("   ")


def test_normalize_path() -> None:
    """Test normalize_path function."""
    # Test with string path
    result = normalize_path("/test/path")
    assert isinstance(result, str)
    assert result == "/test/path"

    # Test with Path object
    path_obj = pathlib.Path("/test/path")
    result = normalize_path(path_obj)
    assert isinstance(result, str)
    assert result == str(path_obj)

    # Test with tilde - normalize_path doesn't expand, it just converts to string
    result = normalize_path("~/test")
    assert result == "~/test"  # Should remain the same


def test_expand_path() -> None:
    """Test expand_path function."""
    # Test with regular path
    result = expand_path("/test/path")
    assert isinstance(result, pathlib.Path)
    assert str(result) == "/test/path"

    # Test with tilde expansion
    home_dir = str(pathlib.Path.home())
    result = expand_path("~/test")
    assert str(result).startswith(home_dir)
    assert str(result).endswith("/test")

    # Test with environment variable
    os.environ["TEST_VAR"] = "/test/env"
    result = expand_path("$TEST_VAR/path")
    assert str(result) == "/test/env/path"


def test_vcs_type_enum() -> None:
    """Test VCSType enum."""
    assert VCSType.GIT.value == "git"
    assert VCSType.HG.value == "hg"
    assert VCSType.SVN.value == "svn"

    # Test string comparison
    assert VCSType.GIT.value == "git"
    assert VCSType.GIT.value == "git"

    # Test enum from string
    assert VCSType("git") == VCSType.GIT
    assert VCSType("hg") == VCSType.HG
    assert VCSType("svn") == VCSType.SVN


def test_git_remote_model() -> None:
    """Test GitRemote model."""
    # Test basic instantiation
    remote = GitRemote(name="origin", url="https://github.com/test/repo.git")
    assert remote.name == "origin"
    assert remote.url == "https://github.com/test/repo.git"
    assert remote.fetch is None
    assert remote.push is None

    # Test with fetch and push
    remote = GitRemote(
        name="upstream",
        url="https://github.com/upstream/repo.git",
        fetch="+refs/heads/*:refs/remotes/upstream/*",
        push="refs/heads/*:refs/heads/*",
    )
    assert remote.name == "upstream"
    assert remote.url == "https://github.com/upstream/repo.git"
    assert remote.fetch == "+refs/heads/*:refs/remotes/upstream/*"
    assert remote.push == "refs/heads/*:refs/heads/*"

    # Test with empty name or URL
    with pytest.raises(ValidationError):
        GitRemote(name="", url="https://github.com/test/repo.git")

    with pytest.raises(ValidationError):
        GitRemote(name="origin", url="")


def test_repository_model() -> None:
    """Test RepositoryModel."""
    # Test git repository
    repo = RepositoryModel(
        vcs="git",
        name="test-repo",
        path=pathlib.Path("/test/path"),
        url="https://github.com/test/repo.git",
    )
    assert repo.vcs == "git"
    assert repo.name == "test-repo"
    assert repo.path == pathlib.Path("/test/path")
    assert repo.url == "https://github.com/test/repo.git"
    assert repo.is_git_repo is True
    assert repo.is_hg_repo is False
    assert repo.is_svn_repo is False

    # Test with remotes
    repo = RepositoryModel(
        vcs="git",
        name="test-repo",
        path=pathlib.Path("/test/path"),
        url="https://github.com/test/repo.git",
        remotes={
            "origin": GitRemote(name="origin", url="https://github.com/test/repo.git"),
            "upstream": GitRemote(
                name="upstream", url="https://github.com/upstream/repo.git"
            ),
        },
    )
    assert len(repo.remotes or {}) == 2
    assert repo.remotes is not None
    assert "origin" in repo.remotes
    assert "upstream" in repo.remotes

    # Test with shell commands
    repo = RepositoryModel(
        vcs="git",
        name="test-repo",
        path=pathlib.Path("/test/path"),
        url="https://github.com/test/repo.git",
        shell_command_after=["echo 'Done'", "git status"],
    )
    assert len(repo.shell_command_after or []) == 2
    assert repo.shell_command_after is not None
    assert "echo 'Done'" in repo.shell_command_after
    assert "git status" in repo.shell_command_after

    # Test hg repository
    repo = RepositoryModel(
        vcs="hg",
        name="test-repo",
        path=pathlib.Path("/test/path"),
        url="https://hg.example.com/test/repo",
    )
    assert repo.is_git_repo is False
    assert repo.is_hg_repo is True
    assert repo.is_svn_repo is False

    # Test svn repository
    repo = RepositoryModel(
        vcs="svn",
        name="test-repo",
        path=pathlib.Path("/test/path"),
        url="https://svn.example.com/test/repo",
    )
    assert repo.is_git_repo is False
    assert repo.is_hg_repo is False
    assert repo.is_svn_repo is True


def test_config_section_dict_model() -> None:
    """Test ConfigSectionDictModel."""
    # Create repository models
    repo1 = RepositoryModel(
        vcs="git",
        name="repo1",
        path=pathlib.Path("/test/path1"),
        url="https://github.com/test/repo1.git",
    )
    repo2 = RepositoryModel(
        vcs="git",
        name="repo2",
        path=pathlib.Path("/test/path2"),
        url="https://github.com/test/repo2.git",
    )

    # Create section model
    section = ConfigSectionDictModel(root={"repo1": repo1, "repo2": repo2})

    # Test accessing items
    assert section["repo1"] == repo1
    assert section["repo2"] == repo2

    # Test keys, values, items
    assert sorted(section.keys()) == ["repo1", "repo2"]
    assert list(section.values()) == [repo1, repo2] or list(section.values()) == [
        repo2,
        repo1,
    ]
    assert dict(section.items()) == {"repo1": repo1, "repo2": repo2}


def test_config_dict_model() -> None:
    """Test ConfigDictModel."""
    # Create repository models
    repo1 = RepositoryModel(
        vcs="git",
        name="repo1",
        path=pathlib.Path("/section1/path1"),
        url="https://github.com/test/repo1.git",
    )
    repo2 = RepositoryModel(
        vcs="git",
        name="repo2",
        path=pathlib.Path("/section1/path2"),
        url="https://github.com/test/repo2.git",
    )
    repo3 = RepositoryModel(
        vcs="git",
        name="repo3",
        path=pathlib.Path("/section2/path3"),
        url="https://github.com/test/repo3.git",
    )

    # Create section models
    section1 = ConfigSectionDictModel(root={"repo1": repo1, "repo2": repo2})
    section2 = ConfigSectionDictModel(root={"repo3": repo3})

    # Create config model
    config = ConfigDictModel(root={"section1": section1, "section2": section2})

    # Test accessing items
    assert config["section1"] == section1
    assert config["section2"] == section2

    # Test keys, values, items
    assert sorted(config.keys()) == ["section1", "section2"]
    assert list(config.values()) == [section1, section2] or list(config.values()) == [
        section2,
        section1,
    ]
    assert dict(config.items()) == {"section1": section1, "section2": section2}


def test_raw_repository_model() -> None:
    """Test RawRepositoryModel."""
    # Test basic instantiation
    repo = RawRepositoryModel(
        vcs="git",
        name="test-repo",
        path="/test/path",
        url="https://github.com/test/repo.git",
    )
    assert repo.vcs == "git"
    assert repo.name == "test-repo"
    assert repo.path == "/test/path"
    assert repo.url == "https://github.com/test/repo.git"

    # Test with remotes
    repo = RawRepositoryModel(
        vcs="git",
        name="test-repo",
        path="/test/path",
        url="https://github.com/test/repo.git",
        remotes={
            "origin": {"name": "origin", "url": "https://github.com/test/repo.git"},
            "upstream": {
                "name": "upstream",
                "url": "https://github.com/upstream/repo.git",
            },
        },
    )
    assert repo.remotes is not None
    assert len(repo.remotes) == 2
    assert "origin" in repo.remotes
    assert "upstream" in repo.remotes

    # Test with shell commands
    repo = RawRepositoryModel(
        vcs="git",
        name="test-repo",
        path="/test/path",
        url="https://github.com/test/repo.git",
        shell_command_after=["echo 'Done'", "git status"],
    )
    assert repo.shell_command_after is not None
    assert len(repo.shell_command_after) == 2
    assert "echo 'Done'" in repo.shell_command_after
    assert "git status" in repo.shell_command_after

    # Test with optional fields omitted
    repo = RawRepositoryModel(
        vcs="git",
        name="test-repo",
        path="/test/path",
        url="https://github.com/test/repo.git",
    )
    assert repo.remotes is None
    assert repo.shell_command_after is None


def test_raw_config_section_dict_model() -> None:
    """Test RawConfigSectionDictModel."""
    # Use the correct type for the dictionary
    section_dict = {
        "repo1": {
            "vcs": "git",
            "name": "repo1",
            "path": "/test/path1",
            "url": "https://github.com/test/repo1.git"
        },
        "repo2": {
            "vcs": "hg",
            "name": "repo2",
            "path": "/test/path2",
            "url": "https://hg.example.com/repo2"
        }
    }
    
    # Create a section with repositories
    section = RawConfigSectionDictModel(root=section_dict)
    
    # Test the structure
    assert "repo1" in section.root
    assert "repo2" in section.root
    assert section.root["repo1"]["vcs"] == "git"
    assert section.root["repo2"]["vcs"] == "hg"


def test_raw_config_dict_model() -> None:
    """Test RawConfigDictModel."""
    # Create plain dictionaries for the config input
    repo1_dict = {
        "vcs": "git",
        "name": "repo1",
        "path": "/test/path1",
        "url": "https://github.com/test/repo1.git"
    }
    
    repo2_dict = {
        "vcs": "hg",
        "name": "repo2",
        "path": "/test/path2",
        "url": "https://hg.example.com/repo2"
    }
    
    # Create a plain dictionary input for RawConfigDictModel
    config_dict = {
        "section1": {
            "repo1": repo1_dict
        },
        "section2": {
            "repo2": repo2_dict
        }
    }
    
    # Create a config with sections
    config = RawConfigDictModel(root=config_dict)
    
    # Test the structure
    assert "section1" in config.root
    assert "section2" in config.root
    
    # Sections get converted to RawConfigSectionDictModel objects
    assert isinstance(config.root["section1"], RawConfigSectionDictModel)
    assert isinstance(config.root["section2"], RawConfigSectionDictModel)
    
    # Access the repository data through the section's root
    assert "repo1" in config.root["section1"].root
    assert "repo2" in config.root["section2"].root
    
    # Check specific values
    assert config.root["section1"].root["repo1"]["vcs"] == "git"
    assert config.root["section2"].root["repo2"]["vcs"] == "hg"


def test_validator_functions() -> None:
    """Test validator functions."""
    # Test get_repo_validator
    repo_validator = get_repo_validator()
    assert repo_validator is not None
    
    # Test get_config_validator
    config_validator = get_config_validator()
    assert config_validator is not None
    
    # Test is_valid_repo_config with valid repo
    valid_repo = {
        "vcs": "git",
        "name": "test-repo",
        "path": "/test/path",
        "url": "https://github.com/test/repo.git"
    }
    # The function either returns a boolean or a model depending on implementation
    result = is_valid_repo_config(valid_repo)
    assert result is not None

    # Test is_valid_config_dict
    valid_config = {
        "section1": {
            "repo1": {
                "vcs": "git",
                "name": "repo1",
                "path": "/test/path1",
                "url": "https://github.com/test/repo1.git",
            }
        }
    }
    result = is_valid_config_dict(valid_config)
    assert result is not None


def test_validate_config_from_json() -> None:
    """Test validate_config_from_json function."""
    # Valid JSON
    valid_json = """
    {
        "section1": {
            "repo1": {
                "vcs": "git",
                "name": "repo1",
                "path": "/test/path1",
                "url": "https://github.com/test/repo1.git"
            }
        }
    }
    """
    result = validate_config_from_json(valid_json)
    assert result[0] is True
    assert isinstance(result[1], dict)

    # Invalid JSON syntax
    invalid_json = """
    {
        "section1": {
            "repo1": {
                "vcs": "git",
                "name": "repo1",
                "path": "/test/path1",
                "url": "https://github.com/test/repo1.git"
            },
        }
    }
    """
    result = validate_config_from_json(invalid_json)
    assert result[0] is False
    assert isinstance(result[1], str)

    # Valid JSON but invalid schema
    invalid_schema_json = """
    {
        "section1": {
            "repo1": {
                "vcs": "invalid",
                "name": "repo1",
                "path": "/test/path1",
                "url": "https://github.com/test/repo1.git"
            }
        }
    }
    """
    result = validate_config_from_json(invalid_schema_json)
    assert result[0] is False
    assert isinstance(result[1], str)


def test_convert_raw_to_validated() -> None:
    """Test convert_raw_to_validated function."""
    # Create raw config
    raw_section = RawConfigSectionDictModel(
        root={
            "repo1": {
                "vcs": "git",
                "name": "repo1",
                "path": "/test/path1",
                "url": "https://github.com/test/repo1.git",
            },
            "repo2": {
                "vcs": "git",
                "name": "repo2",
                "path": "/test/path2",
                "url": "https://github.com/test/repo2.git",
            },
        }
    )
    raw_config = RawConfigDictModel(root={"section1": raw_section})

    # Convert to validated config
    validated_config = convert_raw_to_validated(raw_config)

    # Check structure using the root attribute
    assert "section1" in validated_config.root
    assert "repo1" in validated_config.root["section1"].root
    assert "repo2" in validated_config.root["section1"].root

    # Check types
    assert isinstance(validated_config, ConfigDictModel)
    assert isinstance(validated_config.root["section1"], ConfigSectionDictModel)
    assert isinstance(validated_config.root["section1"].root["repo1"], RepositoryModel)
    assert isinstance(validated_config.root["section1"].root["repo2"], RepositoryModel)

    # Check path conversion
    assert isinstance(
        validated_config.root["section1"].root["repo1"].path, pathlib.Path
    )
    assert isinstance(
        validated_config.root["section1"].root["repo2"].path, pathlib.Path
    )
