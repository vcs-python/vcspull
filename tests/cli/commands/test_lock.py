"""Tests for lock and apply-lock commands."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Callable
from unittest.mock import MagicMock, patch

import pytest
import yaml


@pytest.mark.parametrize(
    "args",
    [
        ["lock", "--help"],
        ["lock", "-h"],
    ],
)
def test_lock_help(
    cli_runner: Callable[[list[str], int | None], tuple[str, str, int]],
    args: list[str],
) -> None:
    """Test lock command help output."""
    stdout, stderr, exit_code = cli_runner(args, 0)

    # Check for help text
    assert "usage:" in stdout
    assert "lock" in stdout
    assert "Lock repositories" in stdout


@pytest.mark.parametrize(
    "args",
    [
        ["apply-lock", "--help"],
        ["apply-lock", "-h"],
    ],
)
def test_apply_lock_help(
    cli_runner: Callable[[list[str], int | None], tuple[str, str, int]],
    args: list[str],
) -> None:
    """Test apply-lock command help output."""
    stdout, stderr, exit_code = cli_runner(args, 0)

    # Check for help text
    assert "usage:" in stdout
    assert "apply-lock" in stdout
    assert "Apply lock" in stdout


@patch("vcspull.operations.lock_repositories")
def test_lock_command_basic(
    mock_lock: MagicMock,
    cli_runner: Callable[[list[str], int | None], tuple[str, str, int]],
    temp_config_file: Path,
) -> None:
    """Test lock command with basic options."""
    # Mock the lock_repositories function to avoid actual filesystem operations
    mock_lock.return_value = {
        "repositories": [
            {
                "name": "repo1",
                "path": "~/repos/repo1",
                "type": "git",
                "url": "git@github.com/user/repo1.git",
                "rev": "abcdef1234567890",
            }
        ]
    }

    # Run the command
    stdout, stderr, exit_code = cli_runner(
        ["lock", "--config", str(temp_config_file)], 0
    )

    # Check mock was called properly
    mock_lock.assert_called_once()

    # Verify output
    assert "Locked repositories" in stdout
    assert "repo1" in stdout


@patch("vcspull.operations.lock_repositories")
def test_lock_command_output_file(
    mock_lock: MagicMock,
    cli_runner: Callable[[list[str], int | None], tuple[str, str, int]],
    temp_config_file: Path,
    tmp_path: Path,
) -> None:
    """Test lock command with output file."""
    # Mock the lock_repositories function
    mock_lock.return_value = {
        "repositories": [
            {
                "name": "repo1",
                "path": "~/repos/repo1",
                "type": "git",
                "url": "git@github.com/user/repo1.git",
                "rev": "abcdef1234567890",
            }
        ]
    }

    # Create an output file path
    output_file = tmp_path / "lock.yaml"

    # Run the command
    stdout, stderr, exit_code = cli_runner(
        ["lock", "--config", str(temp_config_file), "--output", str(output_file)], 0
    )

    # Check mock was called properly
    mock_lock.assert_called_once()

    # Verify output
    assert f"Saved lock file to {output_file}" in stdout


@patch("vcspull.operations.lock_repositories")
def test_lock_command_json_output(
    mock_lock: MagicMock,
    cli_runner: Callable[[list[str], int | None], tuple[str, str, int]],
    temp_config_file: Path,
) -> None:
    """Test lock command with JSON output."""
    # Mock the lock_repositories function
    mock_lock.return_value = {
        "repositories": [
            {
                "name": "repo1",
                "path": "~/repos/repo1",
                "type": "git",
                "url": "git@github.com/user/repo1.git",
                "rev": "abcdef1234567890",
            }
        ]
    }

    # Run the command
    stdout, stderr, exit_code = cli_runner(
        ["lock", "--config", str(temp_config_file), "--json"], 0
    )

    # Output should be valid JSON
    try:
        json_output = json.loads(stdout)
        assert isinstance(json_output, dict)
        assert "repositories" in json_output
        assert len(json_output["repositories"]) == 1
    except json.JSONDecodeError:
        pytest.fail("Output is not valid JSON")

    # Check mock was called properly
    mock_lock.assert_called_once()


@patch("vcspull.operations.apply_lock")
def test_apply_lock_command_basic(
    mock_apply: MagicMock,
    cli_runner: Callable[[list[str], int | None], tuple[str, str, int]],
    temp_config_file: Path,
    tmp_path: Path,
) -> None:
    """Test apply-lock command with basic options."""
    # Mock the apply_lock function
    mock_apply.return_value = [
        {
            "name": "repo1",
            "status": "success",
            "message": "Updated to revision abcdef1234567890",
        }
    ]

    # Create a lock file
    lock_file = tmp_path / "lock.yaml"
    lock_file_data = {
        "repositories": [
            {
                "name": "repo1",
                "path": "~/repos/repo1",
                "type": "git",
                "url": "git@github.com/user/repo1.git",
                "rev": "abcdef1234567890",
            }
        ]
    }
    lock_file.write_text(yaml.dump(lock_file_data))

    # Run the command
    stdout, stderr, exit_code = cli_runner(
        ["apply-lock", "--lock-file", str(lock_file)], 0
    )

    # Check mock was called properly
    mock_apply.assert_called_once()

    # Verify output
    assert "Applying lock file" in stdout
    assert "repo1" in stdout
    assert "success" in stdout


@patch("vcspull.operations.apply_lock")
def test_apply_lock_command_with_filter(
    mock_apply: MagicMock,
    cli_runner: Callable[[list[str], int | None], tuple[str, str, int]],
    temp_config_file: Path,
    tmp_path: Path,
) -> None:
    """Test apply-lock command with repository filter."""
    # Mock the apply_lock function
    mock_apply.return_value = [
        {
            "name": "repo1",
            "status": "success",
            "message": "Updated to revision abcdef1234567890",
        }
    ]

    # Create a lock file with multiple repos
    lock_file = tmp_path / "lock.yaml"
    lock_file_data = {
        "repositories": [
            {
                "name": "repo1",
                "path": "~/repos/repo1",
                "type": "git",
                "url": "git@github.com/user/repo1.git",
                "rev": "abcdef1234567890",
            },
            {
                "name": "repo2",
                "path": "~/repos/repo2",
                "type": "git",
                "url": "git@github.com/user/repo2.git",
                "rev": "fedcba0987654321",
            },
        ]
    }
    lock_file.write_text(yaml.dump(lock_file_data))

    # Run the command with repository filter
    stdout, stderr, exit_code = cli_runner(
        ["apply-lock", "--lock-file", str(lock_file), "repo1"], 0
    )

    # Check mock was called properly
    mock_apply.assert_called_once()

    # Verify the repo filter was passed
    args, kwargs = mock_apply.call_args
    assert "repo_filter" in kwargs
    assert "repo1" in kwargs["repo_filter"]

    # Verify output
    assert "Applying lock file" in stdout
    assert "repo1" in stdout
    assert "success" in stdout


@patch("vcspull.operations.apply_lock")
def test_apply_lock_command_json_output(
    mock_apply: MagicMock,
    cli_runner: Callable[[list[str], int | None], tuple[str, str, int]],
    temp_config_file: Path,
    tmp_path: Path,
) -> None:
    """Test apply-lock command with JSON output."""
    # Mock the apply_lock function
    mock_apply.return_value = [
        {
            "name": "repo1",
            "status": "success",
            "message": "Updated to revision abcdef1234567890",
        }
    ]

    # Create a lock file
    lock_file = tmp_path / "lock.yaml"
    lock_file_data = {
        "repositories": [
            {
                "name": "repo1",
                "path": "~/repos/repo1",
                "type": "git",
                "url": "git@github.com/user/repo1.git",
                "rev": "abcdef1234567890",
            }
        ]
    }
    lock_file.write_text(yaml.dump(lock_file_data))

    # Run the command with JSON output
    stdout, stderr, exit_code = cli_runner(
        ["apply-lock", "--lock-file", str(lock_file), "--json"], 0
    )

    # Output should be valid JSON
    try:
        json_output = json.loads(stdout)
        assert isinstance(json_output, list)
        assert len(json_output) == 1
        assert json_output[0]["name"] == "repo1"
    except json.JSONDecodeError:
        pytest.fail("Output is not valid JSON")

    # Check mock was called properly
    mock_apply.assert_called_once()
