"""Tests for sync command."""

from __future__ import annotations

from unittest.mock import patch

import pytest


@pytest.mark.parametrize(
    "args",
    [
        ["sync", "--help"],
        ["sync", "-h"],
    ],
)
def test_sync_help(cli_runner, args):
    """Test sync command help output."""
    stdout, stderr, exit_code = cli_runner(args, expected_exit_code=0)

    # Check for help text
    assert "usage:" in stdout
    assert "sync" in stdout
    assert "Synchronize repositories" in stdout


@patch("vcspull.operations.sync_repositories")
def test_sync_command_basic(mock_sync, cli_runner, temp_config_file):
    """Test sync command with basic options."""
    # Mock the sync_repositories function to avoid actual filesystem operations
    mock_sync.return_value = []

    # Run the command
    stdout, stderr, exit_code = cli_runner(
        ["sync", "--config", str(temp_config_file)],
        expected_exit_code=0,
    )

    # Check mock was called properly
    mock_sync.assert_called_once()

    # Verify output
    assert "Syncing repositories" in stdout
    assert "Done" in stdout


@patch("vcspull.operations.sync_repositories")
def test_sync_command_with_repositories(
    mock_sync, cli_runner, temp_config_with_multiple_repos
):
    """Test sync command with multiple repositories."""
    # Mock the sync_repositories function
    mock_sync.return_value = []

    # Run the command with a specific repository filter
    stdout, stderr, exit_code = cli_runner(
        ["sync", "--config", str(temp_config_with_multiple_repos), "repo1"],
        expected_exit_code=0,
    )

    # Check mock was called
    mock_sync.assert_called_once()

    # Verify the repo filter was passed
    _, kwargs = mock_sync.call_args
    assert "repo_filter" in kwargs
    assert "repo1" in kwargs["repo_filter"]


@patch("vcspull.operations.sync_repositories")
def test_sync_command_with_type_filter(
    mock_sync, cli_runner, temp_config_with_multiple_repos
):
    """Test sync command with repository type filter."""
    # Mock the sync_repositories function
    mock_sync.return_value = []

    # Run the command with a specific type filter
    stdout, stderr, exit_code = cli_runner(
        ["sync", "--config", str(temp_config_with_multiple_repos), "--type", "git"],
        expected_exit_code=0,
    )

    # Check mock was called
    mock_sync.assert_called_once()

    # Verify the type filter was passed
    _, kwargs = mock_sync.call_args
    assert "vcs_types" in kwargs
    assert "git" in kwargs["vcs_types"]


@patch("vcspull.operations.sync_repositories")
def test_sync_command_parallel(mock_sync, cli_runner, temp_config_file):
    """Test sync command with parallel option."""
    # Mock the sync_repositories function
    mock_sync.return_value = []

    # Run the command with parallel flag
    stdout, stderr, exit_code = cli_runner(
        ["sync", "--config", str(temp_config_file), "--parallel"],
        expected_exit_code=0,
    )

    # Check mock was called
    mock_sync.assert_called_once()

    # Verify the parallel option was passed
    _, kwargs = mock_sync.call_args
    assert "parallel" in kwargs
    assert kwargs["parallel"] is True


@patch("vcspull.operations.sync_repositories")
def test_sync_command_json_output(mock_sync, cli_runner, temp_config_file):
    """Test sync command with JSON output."""
    # Mock the sync_repositories function
    mock_sync.return_value = []

    # Run the command with JSON output
    stdout, stderr, exit_code = cli_runner(
        ["sync", "--config", str(temp_config_file), "--output", "json"],
        expected_exit_code=0,
    )

    # Output should be valid JSON
    import json

    try:
        json_output = json.loads(stdout)
        assert isinstance(json_output, dict)
    except json.JSONDecodeError:
        pytest.fail("Output is not valid JSON")

    # Check mock was called
    mock_sync.assert_called_once()
