"""Example configuration fixtures for tests."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest
import yaml

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def simple_yaml_config(tmp_path: Path) -> Path:
    """Create a simple YAML configuration file.

    Parameters
    ----------
    tmp_path : Path
        Temporary directory path

    Returns
    -------
    Path
        Path to the created configuration file
    """
    config_data = {
        "settings": {
            "sync_remotes": True,
            "default_vcs": "git",
        },
        "repositories": [
            {
                "name": "example-repo",
                "url": "https://github.com/user/repo.git",
                "path": str(tmp_path / "repos" / "example-repo"),
                "vcs": "git",
            },
        ],
    }

    config_file = tmp_path / "config.yaml"
    with config_file.open("w", encoding="utf-8") as f:
        yaml.dump(config_data, f)

    return config_file


@pytest.fixture
def complex_yaml_config(tmp_path: Path) -> Path:
    """Create a complex YAML configuration file with multiple repositories.

    Parameters
    ----------
    tmp_path : Path
        Temporary directory path

    Returns
    -------
    Path
        Path to the created configuration file
    """
    config_data = {
        "settings": {
            "sync_remotes": True,
            "default_vcs": "git",
            "depth": 1,
        },
        "repositories": [
            {
                "name": "repo1",
                "url": "https://github.com/user/repo1.git",
                "path": str(tmp_path / "repos" / "repo1"),
                "vcs": "git",
                "rev": "main",
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
            {
                "name": "hg-repo",
                "url": "https://bitbucket.org/user/hg-repo",
                "path": str(tmp_path / "repos" / "hg-repo"),
                "vcs": "hg",
            },
        ],
    }

    config_file = tmp_path / "complex-config.yaml"
    with config_file.open("w", encoding="utf-8") as f:
        yaml.dump(config_data, f)

    return config_file


@pytest.fixture
def json_config(tmp_path: Path) -> Path:
    """Create a JSON configuration file.

    Parameters
    ----------
    tmp_path : Path
        Temporary directory path

    Returns
    -------
    Path
        Path to the created configuration file
    """
    config_data = {
        "settings": {
            "sync_remotes": True,
            "default_vcs": "git",
        },
        "repositories": [
            {
                "name": "json-repo",
                "url": "https://github.com/user/json-repo.git",
                "path": str(tmp_path / "repos" / "json-repo"),
                "vcs": "git",
            },
        ],
    }

    config_file = tmp_path / "config.json"
    with config_file.open("w", encoding="utf-8") as f:
        json.dump(config_data, f)

    return config_file


@pytest.fixture
def config_with_includes(tmp_path: Path) -> tuple[Path, Path]:
    """Create a configuration file with includes.

    Parameters
    ----------
    tmp_path : Path
        Temporary directory path

    Returns
    -------
    tuple[Path, Path]
        Paths to the main and included configuration files
    """
    # Create included config
    included_config_data = {
        "repositories": [
            {
                "name": "included-repo",
                "url": "https://github.com/user/included-repo.git",
                "path": str(tmp_path / "repos" / "included-repo"),
                "vcs": "git",
            },
        ],
    }

    included_file = tmp_path / "included.yaml"
    with included_file.open("w", encoding="utf-8") as f:
        yaml.dump(included_config_data, f)

    # Create main config with include
    main_config_data = {
        "settings": {
            "sync_remotes": True,
            "default_vcs": "git",
        },
        "repositories": [
            {
                "name": "main-repo",
                "url": "https://github.com/user/main-repo.git",
                "path": str(tmp_path / "repos" / "main-repo"),
                "vcs": "git",
            },
        ],
        "includes": [
            str(included_file),
        ],
    }

    main_file = tmp_path / "main-config.yaml"
    with main_file.open("w", encoding="utf-8") as f:
        yaml.dump(main_config_data, f)

    return main_file, included_file
