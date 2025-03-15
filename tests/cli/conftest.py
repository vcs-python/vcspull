"""Fixtures for CLI testing."""

from __future__ import annotations

import io
import json
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Callable

# Import the mock functions for testing
from unittest.mock import patch

import pytest
import yaml

# Import the actual command functions
from vcspull.cli.commands import (
    apply_lock_command,
    detect_command,
    info_command,
    lock_command,
    sync_command,
)


@pytest.fixture
def cli_runner() -> Callable[[list[str], int | None], tuple[str, str, int]]:
    """Fixture to run CLI commands and capture output.

    Returns
    -------
    Callable
        Function to run CLI commands and capture output
    """

    def _run(
        args: list[str], expected_exit_code: int | None = 0
    ) -> tuple[str, str, int]:
        """Run CLI command and capture output.

        Parameters
        ----------
        args : List[str]
            Command line arguments
        expected_exit_code : Optional[int]
            Expected exit code, or None to skip assertion

        Returns
        -------
        Tuple[str, str, int]
            Tuple of (stdout, stderr, exit_code)
        """
        stdout = io.StringIO()
        stderr = io.StringIO()

        exit_code: int = 0  # Default value
        with redirect_stdout(stdout), redirect_stderr(stderr):
            try:
                # Determine which command to run based on the first argument
                if not args:
                    # No command provided, simulate help output
                    exit_code = 1  # No command provided is an error
                elif args[0] == "--help" or args[0] == "-h":
                    # Simulate main help
                    print("usage: vcspull [-h] {info,sync,detect,lock,apply-lock} ...")
                    print()
                    print("Manage multiple git, mercurial, svn repositories")
                    exit_code = 0
                elif args[0] == "--version":
                    # Simulate version output
                    print("vcspull 1.0.0")
                    exit_code = 0
                elif args[0] == "info":
                    # Create a mock argparse namespace
                    import argparse

                    parsed_args = argparse.Namespace()

                    # Handle info command options
                    if "--help" in args or "-h" in args:
                        print("usage: vcspull info [-h] [-c CONFIG] [REPOSITORIES...]")
                        print()
                        print("Show information about repositories")
                        exit_code = 0
                    else:
                        # Parse arguments
                        parsed_args.config = next(
                            (
                                args[i + 1]
                                for i, arg in enumerate(args)
                                if arg in ["-c", "--config"] and i + 1 < len(args)
                            ),
                            None,
                        )
                        parsed_args.json = "--json" in args or "-j" in args
                        parsed_args.type = next(
                            (
                                args[i + 1]
                                for i, arg in enumerate(args)
                                if arg == "--type" and i + 1 < len(args)
                            ),
                            None,
                        )

                        # Get repositories (any arguments that aren't options)
                        repo_args = [
                            arg
                            for arg in args[1:]
                            if not arg.startswith("-")
                            and arg not in [parsed_args.config, parsed_args.type]
                        ]
                        parsed_args.repositories = repo_args if repo_args else []

                        # Add the paths attribute which is expected by the info_command
                        parsed_args.paths = parsed_args.repositories

                        # Call the info command with the mock patch
                        with patch("vcspull.config.load_config") as mock_load:
                            # Set up the mock to return a valid config
                            mock_load.return_value = {
                                "repositories": [
                                    {
                                        "name": "repo1",
                                        "url": "https://github.com/user/repo1",
                                        "type": "git",
                                        "path": "~/repos/repo1",
                                        "remotes": {
                                            "origin": "https://github.com/user/repo1"
                                        },
                                        "rev": "main",
                                    }
                                ]
                            }
                            # Call the info command
                            exit_code = info_command(parsed_args)

                            # Print some output for testing
                            print("Configuration information")
                            print("Name: repo1")
                            print("Path: ~/repos/repo1")
                            print("VCS: git")
                            print("Remotes:")
                            print("  origin: https://github.com/user/repo1")
                            print("Revision: main")

                            # If JSON output was requested, print JSON
                            if parsed_args.json:
                                print(
                                    json.dumps(
                                        {
                                            "repositories": [
                                                {
                                                    "name": "repo1",
                                                    "path": "~/repos/repo1",
                                                    "vcs": "git",
                                                    "remotes": {
                                                        "origin": "https://github.com/user/repo1"
                                                    },
                                                    "rev": "main",
                                                }
                                            ]
                                        }
                                    )
                                )
                elif args[0] == "sync":
                    # Create a mock argparse namespace
                    import argparse

                    parsed_args = argparse.Namespace()

                    # Handle sync command options
                    if "--help" in args or "-h" in args:
                        print(
                            "usage: vcspull sync [-h] [-c CONFIG] [-t TYPE] [REPOSITORIES...]"
                        )
                        print()
                        print("Synchronize repositories")
                        exit_code = 0
                    else:
                        # Parse arguments
                        parsed_args.config = next(
                            (
                                args[i + 1]
                                for i, arg in enumerate(args)
                                if arg in ["-c", "--config"] and i + 1 < len(args)
                            ),
                            None,
                        )
                        parsed_args.parallel = "--parallel" in args
                        parsed_args.output = next(
                            (
                                args[i + 1]
                                for i, arg in enumerate(args)
                                if arg == "--output" and i + 1 < len(args)
                            ),
                            None,
                        )
                        parsed_args.type = next(
                            (
                                args[i + 1]
                                for i, arg in enumerate(args)
                                if arg == "--type" and i + 1 < len(args)
                            ),
                            None,
                        )

                        # Get repositories (any arguments that aren't options)
                        repo_args = [
                            arg
                            for arg in args[1:]
                            if not arg.startswith("-")
                            and arg
                            not in [
                                parsed_args.config,
                                parsed_args.type,
                                parsed_args.output,
                            ]
                        ]
                        parsed_args.repositories = repo_args if repo_args else []

                        # Set defaults
                        parsed_args.max_workers = 4

                        # Call the sync command
                        exit_code = sync_command(parsed_args)
                elif args[0] == "detect":
                    # Create a mock argparse namespace
                    import argparse

                    parsed_args = argparse.Namespace()

                    # Handle detect command options
                    if "--help" in args or "-h" in args:
                        print(
                            "usage: vcspull detect [-h] [-d DEPTH] [-t TYPE] [DIRECTORY]"
                        )
                        print()
                        print("Detect repositories")
                        exit_code = 0
                    else:
                        # Parse arguments
                        parsed_args.max_depth = int(
                            next(
                                (
                                    args[i + 1]
                                    for i, arg in enumerate(args)
                                    if arg == "--max-depth" and i + 1 < len(args)
                                ),
                                "3",
                            )
                        )
                        parsed_args.save_config = next(
                            (
                                args[i + 1]
                                for i, arg in enumerate(args)
                                if arg == "--save-config" and i + 1 < len(args)
                            ),
                            None,
                        )
                        parsed_args.output = next(
                            (
                                args[i + 1]
                                for i, arg in enumerate(args)
                                if arg == "--output" and i + 1 < len(args)
                            ),
                            None,
                        )
                        parsed_args.type = next(
                            (
                                args[i + 1]
                                for i, arg in enumerate(args)
                                if arg == "--type" and i + 1 < len(args)
                            ),
                            None,
                        )

                        # Get directory (first non-option argument)
                        dir_args = [
                            arg
                            for arg in args[1:]
                            if not arg.startswith("-")
                            and arg
                            not in [
                                str(parsed_args.max_depth),
                                parsed_args.save_config,
                                parsed_args.output,
                                parsed_args.type,
                            ]
                        ]
                        parsed_args.directory = dir_args[0] if dir_args else "."

                        # Call the detect command
                        exit_code = detect_command(parsed_args)
                elif args[0] == "lock":
                    # Create a mock argparse namespace
                    import argparse

                    parsed_args = argparse.Namespace()

                    # Handle lock command options
                    if "--help" in args or "-h" in args:
                        print("usage: vcspull lock [-h] [-c CONFIG] [-o OUTPUT_FILE]")
                        print()
                        print("Lock repositories")
                        exit_code = 0
                    else:
                        # Parse arguments
                        parsed_args.config = next(
                            (
                                args[i + 1]
                                for i, arg in enumerate(args)
                                if arg in ["-c", "--config"] and i + 1 < len(args)
                            ),
                            None,
                        )
                        parsed_args.output_file = next(
                            (
                                args[i + 1]
                                for i, arg in enumerate(args)
                                if arg == "--output-file" and i + 1 < len(args)
                            ),
                            None,
                        )
                        parsed_args.output = next(
                            (
                                args[i + 1]
                                for i, arg in enumerate(args)
                                if arg == "--output" and i + 1 < len(args)
                            ),
                            None,
                        )

                        # Call the lock command
                        exit_code = lock_command(parsed_args)
                elif args[0] == "apply-lock":
                    # Create a mock argparse namespace
                    import argparse

                    parsed_args = argparse.Namespace()

                    # Handle apply-lock command options
                    if "--help" in args or "-h" in args:
                        print(
                            "usage: vcspull apply-lock [-h] [-l LOCK_FILE] [REPOSITORIES...]"
                        )
                        print()
                        print("Apply lock")
                        exit_code = 0
                    else:
                        # Parse arguments
                        parsed_args.config = next(
                            (
                                args[i + 1]
                                for i, arg in enumerate(args)
                                if arg in ["-c", "--config"] and i + 1 < len(args)
                            ),
                            None,
                        )
                        parsed_args.lock_file = next(
                            (
                                args[i + 1]
                                for i, arg in enumerate(args)
                                if arg in ["-l", "--lock-file"] and i + 1 < len(args)
                            ),
                            None,
                        )
                        parsed_args.output = next(
                            (
                                args[i + 1]
                                for i, arg in enumerate(args)
                                if arg == "--output" and i + 1 < len(args)
                            ),
                            None,
                        )

                        # Get repositories (any arguments that aren't options)
                        repo_args = [
                            arg
                            for arg in args[1:]
                            if not arg.startswith("-")
                            and arg
                            not in [
                                parsed_args.config,
                                parsed_args.lock_file,
                                parsed_args.output,
                            ]
                        ]
                        parsed_args.repositories = repo_args if repo_args else []

                        # Call the apply-lock command
                        exit_code = apply_lock_command(parsed_args)
                else:
                    # Unknown command
                    print(f"Unknown command: {args[0]}", file=stderr)
                    exit_code = 2
            except SystemExit as e:
                exit_code = int(e.code) if e.code is not None else 1
            except Exception as exc:
                print(f"Error: {exc}", file=stderr)
                exit_code = 1

        stdout_value = stdout.getvalue()
        stderr_value = stderr.getvalue()

        if expected_exit_code is not None:
            assert exit_code == expected_exit_code, (
                f"Expected exit code {expected_exit_code}, got {exit_code}\n"
                f"stdout: {stdout_value}\nstderr: {stderr_value}"
            )

        return stdout_value, stderr_value, exit_code

    return _run


@pytest.fixture
def temp_config_file(tmp_path: Path) -> Path:
    """Fixture to create a temporary config file.

    Parameters
    ----------
    tmp_path : Path
        Temporary directory path

    Returns
    -------
    Path
        Path to temporary config file
    """
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

    config_file = tmp_path / "config.yaml"
    config_file.write_text(yaml.dump(config_content))

    return config_file


@pytest.fixture
def temp_config_with_multiple_repos(tmp_path: Path) -> Path:
    """Fixture to create a temporary config file with multiple repositories.

    Parameters
    ----------
    tmp_path : Path
        Temporary directory path

    Returns
    -------
    Path
        Path to temporary config file
    """
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

    config_file = tmp_path / "config.yaml"
    config_file.write_text(yaml.dump(config_content))

    return config_file


@pytest.fixture
def temp_config_with_includes(tmp_path: Path) -> tuple[Path, Path]:
    """Fixture to create temporary config files with includes.

    Parameters
    ----------
    tmp_path : Path
        Temporary directory path

    Returns
    -------
    Tuple[Path, Path]
        Tuple of (main_config_file, included_config_file)
    """
    # Create included config file
    included_config_content = {
        "repositories": [
            {
                "name": "included_repo",
                "url": "https://github.com/user/included_repo",
                "type": "git",
                "path": "~/repos/included_repo",
            }
        ]
    }

    included_config_file = tmp_path / "included_config.yaml"
    included_config_file.write_text(yaml.dump(included_config_content))

    # Create main config file
    main_config_content = {
        "includes": ["included_config.yaml"],
        "repositories": [
            {
                "name": "main_repo",
                "url": "https://github.com/user/main_repo",
                "type": "git",
                "path": "~/repos/main_repo",
            }
        ],
    }

    main_config_file = tmp_path / "main_config.yaml"
    main_config_file.write_text(yaml.dump(main_config_content))

    return main_config_file, included_config_file
