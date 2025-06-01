"""Tests for info command."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Callable
from unittest.mock import MagicMock, patch

import pytest


@pytest.mark.parametrize(
    "args",
    [
        ["info", "--help"],
        ["info", "-h"],
    ],
)
def test_info_help(
    cli_runner: Callable[[list[str], int | None], tuple[str, str, int]], args: list[str]
) -> None:
    """Test info command help output."""
    stdout, stderr, exit_code = cli_runner(args, 0)  # Expected exit code 0

    # Check for help text
    assert "usage:" in stdout
    assert "info" in stdout
    assert "Show information" in stdout


@patch("vcspull.config.load_config")
def test_info_command_basic(
    mock_load: MagicMock,
    cli_runner: Callable[[list[str], int | None], tuple[str, str, int]],
    temp_config_file: Path,
) -> None:
    """Test info command with basic options."""
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
        ["info", "--config", str(temp_config_file)],
        0,  # Expected exit code 0
    )

    # Check mock was called
    mock_load.assert_called_once()

    # Verify output
    assert "Configuration information" in stdout
    assert "repo1" in stdout
    assert "https://github.com/user/repo1" in stdout


@patch("vcspull.config.load_config")
def test_info_command_with_filter(
    mock_load: MagicMock,
    cli_runner: Callable[[list[str], int | None], tuple[str, str, int]],
    temp_config_with_multiple_repos: Path,
) -> None:
    """Test info command with repository filter."""
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
        ["info", "--config", str(temp_config_with_multiple_repos), "repo1"],
        0,  # Expected exit code 0
    )

    # Check mock was called
    mock_load.assert_called_once()

    # Verify output contains only the filtered repository
    assert "repo1" in stdout
    assert "https://github.com/user/repo1" in stdout
    assert "repo2" not in stdout


@patch("vcspull.config.load_config")
def test_info_command_with_type_filter(
    mock_load: MagicMock,
    cli_runner: Callable[[list[str], int | None], tuple[str, str, int]],
    temp_config_with_multiple_repos: Path,
) -> None:
    """Test info command with repository type filter."""
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
        ["info", "--config", str(temp_config_with_multiple_repos), "--type", "git"],
        0,  # Expected exit code 0
    )

    # Check mock was called
    mock_load.assert_called_once()

    # Verify output contains only git repositories
    assert "repo1" in stdout
    assert "repo2" in stdout
    assert "repo3" not in stdout


@patch("vcspull.config.load_config")
def test_info_command_json_output(
    mock_load: MagicMock,
    cli_runner: Callable[[list[str], int | None], tuple[str, str, int]],
    temp_config_file: Path,
) -> None:
    """Test info command with JSON output."""
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
        ["info", "--config", str(temp_config_file), "--output", "json"],
        0,  # Expected exit code 0
    )

    # Output should be valid JSON
    try:
        json_output = json.loads(stdout)
        assert isinstance(json_output, dict)
        assert "repositories" in json_output
        assert len(json_output["repositories"]) == 1
    except json.JSONDecodeError:
        pytest.fail("Output is not valid JSON")


@patch("vcspull.config.load_config")
def test_info_command_with_includes(
    mock_load: MagicMock,
    cli_runner: Callable[[list[str], int | None], tuple[str, str, int]],
    temp_config_with_includes: tuple[Path, Path],
) -> None:
    """Test info command with included configs."""
    main_config_file, _ = temp_config_with_includes

    # Example config content with includes
    config_content = {
        "includes": ["included_config.yaml"],
        "repositories": [
            {
                "name": "main_repo",
                "url": "https://github.com/user/main_repo",
                "type": "git",
                "path": "~/repos/main_repo",
            },
            {
                "name": "included_repo",
                "url": "https://github.com/user/included_repo",
                "type": "git",
                "path": "~/repos/included_repo",
            },
        ],
    }

    # Mock the load_config function
    mock_load.return_value = config_content

    # Run the command
    stdout, stderr, exit_code = cli_runner(
        ["info", "--config", str(main_config_file)],
        0,  # Expected exit code 0
    )

    # Check mock was called
    mock_load.assert_called_once()

    # Verify output contains repositories from main and included config
    assert "main_repo" in stdout
    assert "included_repo" in stdout

    # Check that includes are shown
    assert "Includes" in stdout
    assert "included_config.yaml" in stdout
