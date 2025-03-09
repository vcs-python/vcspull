"""Tests for CLI commands in vcspull."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

from vcspull import cli
from vcspull.__about__ import __version__

if TYPE_CHECKING:
    import argparse


@pytest.fixture
def parser() -> argparse.ArgumentParser:
    """Return an ArgumentParser for testing."""
    return cli.create_parser(return_subparsers=False)


def test_help_command(parser: argparse.ArgumentParser) -> None:
    """Test that the help command displays help information."""
    with patch("sys.stdout") as mock_stdout:
        with pytest.raises(SystemExit):
            parser.parse_args(["--help"])

        # Check that help information was captured
        output = mock_stdout.write.call_args_list
        output_str = "".join(call[0][0] for call in output)

        # Check that help information is displayed
        assert "usage:" in output_str.lower()
        assert "sync" in output_str


def test_version_display(parser: argparse.ArgumentParser) -> None:
    """Test that the version command displays version information."""
    with patch("sys.stdout") as mock_stdout:
        with pytest.raises(SystemExit):
            parser.parse_args(["--version"])

        # Check that version information was captured
        output = mock_stdout.write.call_args_list
        output_str = "".join(call[0][0] for call in output)

        # Check that version information is displayed
        assert __version__ in output_str


def test_sync_help(parser: argparse.ArgumentParser) -> None:
    """Test that the sync --help command displays help information."""
    with patch("sys.stdout") as mock_stdout:
        with pytest.raises(SystemExit):
            parser.parse_args(["sync", "--help"])

        # Check that help information was captured
        output = mock_stdout.write.call_args_list
        output_str = "".join(call[0][0] for call in output)

        # Check that help information is displayed
        assert "usage:" in output_str.lower()
        assert "sync" in output_str


def test_cli_exit_on_error_flag() -> None:
    """Test the CLI --exit-on-error flag."""
    # Test that the --exit-on-error flag is passed to the sync function
    with (
        patch("vcspull.cli.sync") as mock_sync,
        patch("sys.argv", ["vcspull", "sync", "some_repo", "--exit-on-error"]),
        patch("sys.exit"),  # Prevent actual exit
    ):
        cli.cli()

    # Verify sync was called with exit_on_error=True
    mock_sync.assert_called_once()
    kwargs = mock_sync.call_args.kwargs
    assert kwargs.get("exit_on_error") is True


def test_cli_custom_working_directory(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test the CLI with a custom configuration file path."""
    # Test that the -c/--config option correctly passes the config path
    test_config_path = "/test/config.yaml"
    monkeypatch.setattr(os.path, "exists", lambda x: True)  # Make any path "exist"
    monkeypatch.setattr(os.path, "isdir", lambda x: True)  # And be a directory

    # Test both short and long forms
    for option in ["-c", "--config"]:
        with (
            patch("vcspull.cli.sync") as mock_sync,
            patch(
                "sys.argv", ["vcspull", "sync", "some_repo", option, test_config_path]
            ),
            patch("sys.exit"),  # Prevent actual exit
        ):
            cli.cli()

        # Verify config was passed correctly
        mock_sync.assert_called_once()
        kwargs = mock_sync.call_args.kwargs
        assert kwargs.get("config") == test_config_path


def test_cli_config_option() -> None:
    """Test CLI behavior with custom config option."""
    # Mock the sync function
    with patch("vcspull.cli.sync") as mock_sync:
        # Run with config option
        with (
            patch(
                "sys.argv",
                ["vcspull", "sync", "some_repo", "--config", "custom_config.yaml"],
            ),
            patch("sys.exit"),
        ):  # Prevent actual exit
            cli.cli()

        # Verify that sync was called with the config option
        mock_sync.assert_called_once()
        call_kwargs = mock_sync.call_args[1]
        assert call_kwargs.get("config") == "custom_config.yaml"


def test_unknown_command(parser: argparse.ArgumentParser) -> None:
    """Test behavior with non-existing commands."""
    with pytest.raises(SystemExit):
        parser.parse_args(["nonexistent"])

    # The test passes if we get here without an unexpected exception
