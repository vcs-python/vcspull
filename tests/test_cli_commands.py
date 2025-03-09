"""Tests for CLI commands in vcspull."""

from __future__ import annotations

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
    return cli.create_parser()


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
    """Test CLI behavior with exit-on-error flag."""
    # Mock the sync function
    with patch("vcspull.cli.sync") as mock_sync:
        # Run the CLI command with --exit-on-error flag
        with patch("sys.argv", ["vcspull", "sync", "some_repo", "--exit-on-error"]):
            with patch("sys.exit"):  # Prevent actual exit
                cli.cli()

        # Verify that sync was called with exit_on_error=True
        mock_sync.assert_called_once()
        call_kwargs = mock_sync.call_args[1]
        assert call_kwargs.get("exit_on_error", False) is True


def test_cli_custom_working_directory(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test CLI behavior with custom working directory."""
    # Mock os.getcwd to return a custom directory
    with patch("os.getcwd") as mock_getcwd:
        mock_getcwd.return_value = "/custom/working/directory"

        # Mock the sync function
        with patch("vcspull.cli.sync") as mock_sync:
            # Run the CLI command
            with patch("sys.argv", ["vcspull", "sync", "some_repo"]):
                with patch("sys.exit"):  # Prevent actual exit
                    cli.cli()

            # Verify that sync was called
            mock_sync.assert_called_once()


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
