"""CLI command implementations."""

from __future__ import annotations

import argparse
import sys
import typing as t

from vcspull._internal import logger
from vcspull.config import load_config, resolve_includes


def cli(argv: list[str] | None = None) -> int:
    """CLI entrypoint.

    Parameters
    ----------
    argv : list[str] | None
        Command line arguments, defaults to sys.argv[1:] if not provided

    Returns
    -------
    int
        Exit code
    """
    parser = argparse.ArgumentParser(
        description="Manage multiple git, mercurial, svn repositories",
    )
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Add subparsers for each command
    add_info_command(subparsers)
    add_sync_command(subparsers)

    args = parser.parse_args(argv if argv is not None else sys.argv[1:])

    if not args.command:
        parser.print_help()
        return 1

    # Dispatch to the appropriate command handler
    if args.command == "info":
        return info_command(args)
    if args.command == "sync":
        return sync_command(args)

    return 0


def add_info_command(subparsers: argparse._SubParsersAction[t.Any]) -> None:
    """Add the info command to the parser.

    Parameters
    ----------
    subparsers : argparse._SubParsersAction
        Subparsers action to add the command to
    """
    parser = subparsers.add_parser("info", help="Show information about repositories")
    parser.add_argument(
        "-c",
        "--config",
        help="Path to configuration file",
        default="~/.config/vcspull/vcspull.yaml",
    )


def add_sync_command(subparsers: argparse._SubParsersAction[t.Any]) -> None:
    """Add the sync command to the parser.

    Parameters
    ----------
    subparsers : argparse._SubParsersAction
        Subparsers action to add the command to
    """
    parser = subparsers.add_parser("sync", help="Synchronize repositories")
    parser.add_argument(
        "-c",
        "--config",
        help="Path to configuration file",
        default="~/.config/vcspull/vcspull.yaml",
    )


def info_command(args: argparse.Namespace) -> int:
    """Handle the info command.

    Parameters
    ----------
    args : argparse.Namespace
        Command line arguments

    Returns
    -------
    int
        Exit code
    """
    try:
        config = load_config(args.config)
        config = resolve_includes(config, args.config)

        for _repo in config.repositories:
            pass
    except Exception as e:
        logger.error(f"Error: {e}")
        return 1
    else:
        return 0


def sync_command(args: argparse.Namespace) -> int:
    """Handle the sync command.

    Parameters
    ----------
    args : argparse.Namespace
        Command line arguments

    Returns
    -------
    int
        Exit code
    """
    try:
        config = load_config(args.config)
        config = resolve_includes(config, args.config)

        # TODO: Implement actual sync logic
    except Exception as e:
        logger.error(f"Error: {e}")
        return 1
    else:
        return 0
