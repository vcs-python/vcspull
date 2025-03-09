"""CLI command implementations."""

from __future__ import annotations

import argparse
import json
import sys
import typing as t
from pathlib import Path

from colorama import init

from vcspull._internal import logger
from vcspull.config import load_config, resolve_includes
from vcspull.operations import detect_repositories, sync_repositories

# Initialize colorama
init(autoreset=True)


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
    add_detect_command(subparsers)

    args = parser.parse_args(argv if argv is not None else sys.argv[1:])

    if not args.command:
        parser.print_help()
        return 1

    # Dispatch to the appropriate command handler
    if args.command == "info":
        return info_command(args)
    if args.command == "sync":
        return sync_command(args)
    if args.command == "detect":
        return detect_command(args)

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
    parser.add_argument(
        "-j",
        "--json",
        action="store_true",
        help="Output in JSON format",
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
    parser.add_argument(
        "-p",
        "--path",
        action="append",
        help="Sync only repositories at the specified path(s)",
        dest="paths",
    )
    parser.add_argument(
        "-s",
        "--sequential",
        action="store_true",
        help="Sync repositories sequentially instead of in parallel",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose output",
    )


def add_detect_command(subparsers: argparse._SubParsersAction[t.Any]) -> None:
    """Add the detect command to the parser.

    Parameters
    ----------
    subparsers : argparse._SubParsersAction
        Subparsers action to add the command to
    """
    parser = subparsers.add_parser("detect", help="Detect repositories in directories")
    parser.add_argument(
        "directories",
        nargs="*",
        help="Directories to search for repositories",
        default=["."],
    )
    parser.add_argument(
        "-r",
        "--recursive",
        action="store_true",
        help="Search directories recursively",
    )
    parser.add_argument(
        "-d",
        "--depth",
        type=int,
        default=2,
        help="Maximum directory depth when searching recursively",
    )
    parser.add_argument(
        "-j",
        "--json",
        action="store_true",
        help="Output in JSON format",
    )
    parser.add_argument(
        "-o",
        "--output",
        help="Write detected repositories to config file",
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

        if args.json:
            # JSON output
            config.model_dump()
        else:
            # Human-readable output

            # Show settings
            for _key, _value in config.settings.model_dump().items():
                pass

            # Show repositories
            for repo in config.repositories:
                if repo.remotes:
                    for _remote_name, _remote_url in repo.remotes.items():
                        pass

                if repo.rev:
                    pass

        return 0
    except Exception as e:
        logger.error(f"Error: {e}")
        return 1


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

        # Set up some progress reporting
        len(config.repositories)
        if args.paths:
            filtered_repos = [
                repo
                for repo in config.repositories
                if any(
                    Path(repo.path)
                    .expanduser()
                    .resolve()
                    .as_posix()
                    .startswith(Path(p).expanduser().resolve().as_posix())
                    for p in args.paths
                )
            ]
            len(filtered_repos)

        # Run the sync operation
        results = sync_repositories(
            config,
            paths=args.paths,
            parallel=not args.sequential,
        )

        # Report results
        sum(1 for success in results.values() if success)
        failure_count = sum(1 for success in results.values() if not success)

        # Use a shorter line to address E501

        # Return non-zero if any sync failed
        if failure_count == 0:
            return 0
        return 1
    except Exception as e:
        logger.error(f"Error: {e}")
        return 1


def detect_command(args: argparse.Namespace) -> int:
    """Handle the detect command.

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
        # Detect repositories
        repos = detect_repositories(
            args.directories,
            recursive=args.recursive,
            depth=args.depth,
        )

        if not repos:
            return 0

        # Output results
        if args.json:
            # JSON output
            [repo.model_dump() for repo in repos]
        else:
            # Human-readable output
            for _repo in repos:
                pass

        # Optionally write to configuration file
        if args.output:
            from vcspull.config.models import Settings, VCSPullConfig

            output_path = Path(args.output).expanduser().resolve()
            output_dir = output_path.parent

            # Create directory if it doesn't exist
            if not output_dir.exists():
                output_dir.mkdir(parents=True)

            # Create config with detected repositories
            config = VCSPullConfig(
                settings=Settings(),
                repositories=repos,
            )

            # Write config to file
            with output_path.open("w", encoding="utf-8") as f:
                if output_path.suffix.lower() in {".yaml", ".yml"}:
                    import yaml

                    yaml.dump(config.model_dump(), f, default_flow_style=False)
                elif output_path.suffix.lower() == ".json":
                    json.dump(config.model_dump(), f, indent=2)
                else:
                    error_msg = f"Unsupported file format: {output_path.suffix}"
                    raise ValueError(error_msg)

            # Split the line to avoid E501

            return 0
        return 0
    except Exception as e:
        logger.error(f"Error: {e}")
        return 1
