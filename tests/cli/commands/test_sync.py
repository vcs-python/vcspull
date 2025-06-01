"""Tests for sync command."""

from __future__ import annotations

from pathlib import Path
from typing import Callable
from unittest.mock import MagicMock, patch

import pytest


@pytest.mark.parametrize(
    "args",
    [
        ["sync", "--help"],
        ["sync", "-h"],
    ],
)
def test_sync_help(
    cli_runner: Callable[[list[str], int | None], tuple[str, str, int]],
    args: list[str],
) -> None:
    """Test sync command help output."""
    stdout, stderr, exit_code = cli_runner(args, 0)

    # Check for help text
    assert "usage:" in stdout
    assert "sync" in stdout
    assert "Synchronize repositories" in stdout


@patch("vcspull.config.load_config")
def test_sync_command_basic(
    mock_load: MagicMock,
    cli_runner: Callable[[list[str], int | None], tuple[str, str, int]],
    temp_config_file: Path,
) -> None:
    """Test sync command with basic options."""
    # Example config content
    config_content = {
        "repositories": [
            {
                "name": "repo1",
                "url": "https://github.com/user/repo1",
                "type": "git",
                "path": "~/repos/repo1",
            }
        ]
    }

    # Mock the load_config function
    mock_load.return_value = config_content

    # Run the command
    stdout, stderr, exit_code = cli_runner(
        ["sync", "--config", str(temp_config_file)], 0
    )

    # Check mock was called
    mock_load.assert_called_once()


@patch("vcspull.config.load_config")
def test_sync_command_with_repositories(
    mock_load: MagicMock,
    cli_runner: Callable[[list[str], int | None], tuple[str, str, int]],
    temp_config_with_multiple_repos: Path,
) -> None:
    """Test sync command with repository filter."""
    # Example config content
    config_content = {
        "repositories": [
            {
                "name": "repo1",
                "url": "https://github.com/user/repo1",
                "type": "git",
                "path": "~/repos/repo1",
            },
            {
                "name": "repo2",
                "url": "https://github.com/user/repo2",
                "type": "git",
                "path": "~/repos/repo2",
            },
        ]
    }

    # Mock the load_config function
    mock_load.return_value = config_content

    # Run the command with repository filter
    stdout, stderr, exit_code = cli_runner(
        ["sync", "--config", str(temp_config_with_multiple_repos), "repo1"], 0
    )

    # Check mock was called
    mock_load.assert_called_once()


@patch("vcspull.config.load_config")
def test_sync_command_with_type_filter(
    mock_load: MagicMock,
    cli_runner: Callable[[list[str], int | None], tuple[str, str, int]],
    temp_config_with_multiple_repos: Path,
) -> None:
    """Test sync command with repository type filter."""
    # Example config content
    config_content = {
        "repositories": [
            {
                "name": "repo1",
                "url": "https://github.com/user/repo1",
                "type": "git",
                "path": "~/repos/repo1",
            },
            {
                "name": "repo2",
                "url": "https://github.com/user/repo2",
                "type": "git",
                "path": "~/repos/repo2",
            },
            {
                "name": "repo3",
                "url": "https://github.com/user/repo3",
                "type": "hg",
                "path": "~/repos/repo3",
            },
        ]
    }

    # Mock the load_config function
    mock_load.return_value = config_content

    # Run the command with type filter
    stdout, stderr, exit_code = cli_runner(
        ["sync", "--config", str(temp_config_with_multiple_repos), "--type", "git"], 0
    )

    # Check mock was called
    mock_load.assert_called_once()


@patch("vcspull.config.load_config")
def test_sync_command_parallel(
    mock_load: MagicMock,
    cli_runner: Callable[[list[str], int | None], tuple[str, str, int]],
    temp_config_file: Path,
) -> None:
    """Test sync command with parallel option."""
    # Example config content
    config_content = {
        "repositories": [
            {
                "name": "repo1",
                "url": "https://github.com/user/repo1",
                "type": "git",
                "path": "~/repos/repo1",
            }
        ]
    }

    # Mock the load_config function
    mock_load.return_value = config_content

    # Run the command with parallel option
    stdout, stderr, exit_code = cli_runner(
        ["sync", "--config", str(temp_config_file), "--sequential"], 0
    )

    # Check mock was called
    mock_load.assert_called_once()


@patch("vcspull.config.load_config")
def test_sync_command_json_output(
    mock_load: MagicMock,
    cli_runner: Callable[[list[str], int | None], tuple[str, str, int]],
    temp_config_file: Path,
) -> None:
    """Test sync command with JSON output."""
    # Example config content
    config_content = {
        "repositories": [
            {
                "name": "repo1",
                "url": "https://github.com/user/repo1",
                "type": "git",
                "path": "~/repos/repo1",
            }
        ]
    }

    # Mock the load_config function
    mock_load.return_value = config_content

    # Run the command with JSON output
    stdout, stderr, exit_code = cli_runner(
        ["sync", "--config", str(temp_config_file), "--json"], 0
    )

    # Check mock was called
    mock_load.assert_called_once()
