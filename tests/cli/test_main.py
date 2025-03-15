"""Test the main CLI entry point."""

from __future__ import annotations

from typing import Callable


def test_cli_help(
    cli_runner: Callable[[list[str], int | None], tuple[str, str, int]],
) -> None:
    """Test the help output."""
    stdout, stderr, exit_code = cli_runner(["--help"], 0)  # Expected exit code 0
    assert exit_code == 0
    assert "usage: vcspull" in stdout
    assert "Manage multiple git, mercurial, svn repositories" in stdout


def test_cli_no_args(
    cli_runner: Callable[[list[str], int | None], tuple[str, str, int]],
) -> None:
    """Test running with no arguments."""
    stdout, stderr, exit_code = cli_runner([], 1)  # Expected exit code 1
    # The CLI returns exit code 1 when no arguments are provided
    assert exit_code == 1


def test_cli_unknown_command(
    cli_runner: Callable[[list[str], int | None], tuple[str, str, int]],
) -> None:
    """Test running with an unknown command."""
    stdout, stderr, exit_code = cli_runner(
        ["unknown_command"], 2
    )  # Expected exit code 2
    assert exit_code == 2
    assert "Unknown command: unknown_command" in stderr


def test_cli_version_option(
    cli_runner: Callable[[list[str], int | None], tuple[str, str, int]],
) -> None:
    """Test the version option."""
    stdout, stderr, exit_code = cli_runner(["--version"], 0)  # Expected exit code 0
    assert exit_code == 0
    assert "vcspull" in stdout
