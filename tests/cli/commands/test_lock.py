"""Tests for lock and apply-lock commands."""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest
import yaml


@pytest.mark.parametrize(
    "args",
    [
        ["lock", "--help"],
        ["lock", "-h"],
    ],
)
def test_lock_help(cli_runner, args):
    """Test lock command help output."""
    stdout, stderr, exit_code = cli_runner(args, expected_exit_code=0)

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
def test_apply_lock_help(cli_runner, args):
    """Test apply-lock command help output."""
    stdout, stderr, exit_code = cli_runner(args, expected_exit_code=0)

    # Check for help text
    assert "usage:" in stdout
    assert "apply-lock" in stdout
    assert "Apply lock" in stdout


@patch("vcspull.operations.lock_repositories")
def test_lock_command_basic(mock_lock, cli_runner, temp_config_file):
    """Test lock command with basic options."""
    # Example lock result
    mock_lock.return_value = {
        "repositories": [
            {
                "name": "repo1",
                "url": "https://github.com/user/repo1",
                "type": "git",
                "path": "~/repos/repo1",
                "revision": "abcdef123456",
                "tag": "v1.0.0",
            }
        ]
    }

    # Run the command
    stdout, stderr, exit_code = cli_runner(
        ["lock", "--config", str(temp_config_file)],
        expected_exit_code=0,
    )

    # Check mock was called
    mock_lock.assert_called_once()

    # Verify output
    assert "Locking repositories" in stdout
    assert "repo1" in stdout
    assert "abcdef123456" in stdout


@patch("vcspull.operations.lock_repositories")
def test_lock_command_output_file(mock_lock, cli_runner, temp_config_file, tmp_path):
    """Test lock command with output file."""
    # Output lock file
    lock_file = tmp_path / "lock.yaml"

    # Example lock result
    mock_lock.return_value = {
        "repositories": [
            {
                "name": "repo1",
                "url": "https://github.com/user/repo1",
                "type": "git",
                "path": "~/repos/repo1",
                "revision": "abcdef123456",
                "tag": "v1.0.0",
            }
        ]
    }

    # Run the command with output file
    stdout, stderr, exit_code = cli_runner(
        [
            "lock",
            "--config",
            str(temp_config_file),
            "--output-file",
            str(lock_file),
        ],
        expected_exit_code=0,
    )

    # Check mock was called
    mock_lock.assert_called_once()

    # Verify lock file was created
    assert lock_file.exists()

    # Verify lock file content
    lock_data = yaml.safe_load(lock_file.read_text())
    assert "repositories" in lock_data
    assert len(lock_data["repositories"]) == 1
    assert lock_data["repositories"][0]["name"] == "repo1"
    assert lock_data["repositories"][0]["revision"] == "abcdef123456"


@patch("vcspull.operations.lock_repositories")
def test_lock_command_json_output(mock_lock, cli_runner, temp_config_file):
    """Test lock command with JSON output."""
    # Example lock result
    mock_lock.return_value = {
        "repositories": [
            {
                "name": "repo1",
                "url": "https://github.com/user/repo1",
                "type": "git",
                "path": "~/repos/repo1",
                "revision": "abcdef123456",
                "tag": "v1.0.0",
            }
        ]
    }

    # Run the command with JSON output
    stdout, stderr, exit_code = cli_runner(
        ["lock", "--config", str(temp_config_file), "--output", "json"],
        expected_exit_code=0,
    )

    # Output should be valid JSON
    try:
        json_output = json.loads(stdout)
        assert isinstance(json_output, dict)
        assert "repositories" in json_output
        assert len(json_output["repositories"]) == 1
    except json.JSONDecodeError:
        pytest.fail("Output is not valid JSON")


@patch("vcspull.operations.apply_lock")
def test_apply_lock_command_basic(mock_apply, cli_runner, temp_config_file, tmp_path):
    """Test apply-lock command with basic options."""
    # Create a mock lock file
    lock_file = tmp_path / "lock.yaml"
    lock_content = {
        "repositories": [
            {
                "name": "repo1",
                "url": "https://github.com/user/repo1",
                "type": "git",
                "path": "~/repos/repo1",
                "revision": "abcdef123456",
                "tag": "v1.0.0",
            }
        ]
    }
    lock_file.write_text(yaml.dump(lock_content))

    # Mock apply_lock function
    mock_apply.return_value = lock_content["repositories"]

    # Run the command
    stdout, stderr, exit_code = cli_runner(
        [
            "apply-lock",
            "--config",
            str(temp_config_file),
            "--lock-file",
            str(lock_file),
        ],
        expected_exit_code=0,
    )

    # Check mock was called
    mock_apply.assert_called_once()

    # Verify output
    assert "Applying lock" in stdout
    assert "repo1" in stdout
    assert "abcdef123456" in stdout


@patch("vcspull.operations.apply_lock")
def test_apply_lock_command_with_filter(
    mock_apply, cli_runner, temp_config_file, tmp_path
):
    """Test apply-lock command with repository filter."""
    # Create a mock lock file
    lock_file = tmp_path / "lock.yaml"
    lock_content = {
        "repositories": [
            {
                "name": "repo1",
                "url": "https://github.com/user/repo1",
                "type": "git",
                "path": "~/repos/repo1",
                "revision": "abcdef123456",
                "tag": "v1.0.0",
            },
            {
                "name": "repo2",
                "url": "https://github.com/user/repo2",
                "type": "git",
                "path": "~/repos/repo2",
                "revision": "123456abcdef",
                "tag": "v2.0.0",
            },
        ]
    }
    lock_file.write_text(yaml.dump(lock_content))

    # Mock apply_lock function
    mock_apply.return_value = [lock_content["repositories"][0]]

    # Run the command with repository filter
    stdout, stderr, exit_code = cli_runner(
        [
            "apply-lock",
            "--config",
            str(temp_config_file),
            "--lock-file",
            str(lock_file),
            "repo1",
        ],
        expected_exit_code=0,
    )

    # Check mock was called with filter
    mock_apply.assert_called_once()
    _, kwargs = mock_apply.call_args
    assert "repo_filter" in kwargs
    assert "repo1" in kwargs["repo_filter"]

    # Verify output
    assert "Applying lock" in stdout
    assert "repo1" in stdout
    assert "abcdef123456" in stdout


@patch("vcspull.operations.apply_lock")
def test_apply_lock_command_json_output(
    mock_apply, cli_runner, temp_config_file, tmp_path
):
    """Test apply-lock command with JSON output."""
    # Create a mock lock file
    lock_file = tmp_path / "lock.yaml"
    lock_content = {
        "repositories": [
            {
                "name": "repo1",
                "url": "https://github.com/user/repo1",
                "type": "git",
                "path": "~/repos/repo1",
                "revision": "abcdef123456",
                "tag": "v1.0.0",
            }
        ]
    }
    lock_file.write_text(yaml.dump(lock_content))

    # Mock apply_lock function
    mock_apply.return_value = lock_content["repositories"]

    # Run the command with JSON output
    stdout, stderr, exit_code = cli_runner(
        [
            "apply-lock",
            "--config",
            str(temp_config_file),
            "--lock-file",
            str(lock_file),
            "--output",
            "json",
        ],
        expected_exit_code=0,
    )

    # Output should be valid JSON
    try:
        json_output = json.loads(stdout)
        assert isinstance(json_output, dict)
        assert "applied" in json_output
        assert len(json_output["applied"]) == 1
    except json.JSONDecodeError:
        pytest.fail("Output is not valid JSON")
