"""Tests for detect command."""

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
        ["detect", "--help"],
        ["detect", "-h"],
    ],
)
def test_detect_help(
    cli_runner: Callable[[list[str], int | None], tuple[str, str, int]],
    args: list[str],
) -> None:
    """Test detect command help output."""
    stdout, stderr, exit_code = cli_runner(args, 0)

    # Check for help text
    assert "usage:" in stdout
    assert "detect" in stdout
    assert "Detect repositories" in stdout


@patch("vcspull.operations.detect_repositories")
def test_detect_command_basic(
    mock_detect: MagicMock,
    cli_runner: Callable[[list[str], int | None], tuple[str, str, int]],
    tmp_path: Path,
) -> None:
    """Test detect command with basic options."""
    # Create a dummy directory to scan
    target_dir = tmp_path / "repos"
    target_dir.mkdir()

    # Mock the detect_repositories function
    mock_detect.return_value = [
        {
            "name": "repo1",
            "path": str(target_dir / "repo1"),
            "type": "git",
            "url": "https://github.com/user/repo1",
        }
    ]

    # Run the command
    stdout, stderr, exit_code = cli_runner(["detect", str(target_dir)], 0)

    # Check mock was called with correct path
    mock_detect.assert_called_once()
    args, _ = mock_detect.call_args
    assert str(target_dir) in str(args[0])

    # Verify output
    assert "Detected repositories" in stdout
    assert "repo1" in stdout


@patch("vcspull.operations.detect_repositories")
@patch("vcspull.config.save_config")
def test_detect_command_save_config(
    mock_save: MagicMock,
    mock_detect: MagicMock,
    cli_runner: Callable[[list[str], int | None], tuple[str, str, int]],
    tmp_path: Path,
) -> None:
    """Test detect command with save-config option."""
    # Create a dummy directory to scan
    target_dir = tmp_path / "repos"
    target_dir.mkdir()

    # Output config file
    output_file = tmp_path / "detected_config.yaml"

    # Mock the detect_repositories function
    mock_detect.return_value = [
        {
            "name": "repo1",
            "path": str(target_dir / "repo1"),
            "type": "git",
            "url": "https://github.com/user/repo1",
        }
    ]

    # Run the command with save-config option
    stdout, stderr, exit_code = cli_runner(
        [
            "detect",
            str(target_dir),
            "--save-config",
            str(output_file),
        ],
        0,
    )

    # Verify config file was created
    assert output_file.exists()

    # Verify config content
    config = yaml.safe_load(output_file.read_text())
    assert "repositories" in config
    assert len(config["repositories"]) == 1
    assert config["repositories"][0]["name"] == "repo1"

    # Verify mocks were called properly
    mock_detect.assert_called_once()
    mock_save.assert_called_once()


@patch("vcspull.operations.detect_repositories")
def test_detect_command_json_output(
    mock_detect: MagicMock,
    cli_runner: Callable[[list[str], int | None], tuple[str, str, int]],
    tmp_path: Path,
) -> None:
    """Test detect command with JSON output."""
    # Create a dummy directory to scan
    target_dir = tmp_path / "repos"
    target_dir.mkdir()

    # Mock the detect_repositories function
    mock_detect.return_value = [
        {
            "name": "repo1",
            "path": str(target_dir / "repo1"),
            "type": "git",
            "url": "https://github.com/user/repo1",
        }
    ]

    # Run the command with JSON output
    stdout, stderr, exit_code = cli_runner(
        ["detect", str(target_dir), "--output", "json"], 0
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
    mock_detect.assert_called_once()


@patch("vcspull.operations.detect_repositories")
def test_detect_command_filter_type(
    mock_detect: MagicMock,
    cli_runner: Callable[[list[str], int | None], tuple[str, str, int]],
    tmp_path: Path,
) -> None:
    """Test detect command with type filter."""
    # Create a dummy directory to scan
    target_dir = tmp_path / "repos"
    target_dir.mkdir()

    # Mock the detect_repositories function
    mock_detect.return_value = [
        {
            "name": "repo1",
            "path": str(target_dir / "repo1"),
            "type": "git",
            "url": "https://github.com/user/repo1",
        }
    ]

    # Run the command with type filter
    stdout, stderr, exit_code = cli_runner(
        ["detect", str(target_dir), "--type", "git"], 0
    )

    # Check mock was called with type filter
    mock_detect.assert_called_once()
    _, kwargs = mock_detect.call_args
    assert "vcs_types" in kwargs
    assert "git" in kwargs["vcs_types"]

    # Verify output
    assert "Detected repositories" in stdout
    assert "repo1" in stdout


@patch("vcspull.operations.detect_repositories")
def test_detect_command_max_depth(
    mock_detect: MagicMock,
    cli_runner: Callable[[list[str], int | None], tuple[str, str, int]],
    tmp_path: Path,
) -> None:
    """Test detect command with max-depth option."""
    # Create a dummy directory to scan
    target_dir = tmp_path / "repos"
    target_dir.mkdir()

    # Mock the detect_repositories function
    mock_detect.return_value = []

    # Run the command with max-depth option
    stdout, stderr, exit_code = cli_runner(
        ["detect", str(target_dir), "--max-depth", "3"], 0
    )

    # Check mock was called with max_depth parameter
    mock_detect.assert_called_once()
    _, kwargs = mock_detect.call_args
    assert "max_depth" in kwargs
    assert kwargs["max_depth"] == 3

    # Verify output
    assert "Detected repositories" in stdout
    assert "repo1" in stdout
