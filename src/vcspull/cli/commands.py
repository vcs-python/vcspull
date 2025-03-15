"""CLI command implementations."""

from __future__ import annotations

import argparse
import contextlib
import json
import sys
import typing as t
from pathlib import Path
from typing import Union

from colorama import init

from vcspull._internal import logger
from vcspull.config import load_config
from vcspull.config.migration import migrate_all_configs, migrate_config_file
from vcspull.config.models import VCSPullConfig
from vcspull.operations import (
    apply_lock,
    detect_repositories,
    lock_repositories,
    sync_repositories,
)

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
    add_lock_command(subparsers)
    add_apply_lock_command(subparsers)
    add_migrate_command(subparsers)

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
    if args.command == "lock":
        return lock_command(args)
    if args.command == "apply-lock":
        return apply_lock_command(args)
    if args.command == "migrate":
        return migrate_command(args)

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


def add_lock_command(subparsers: argparse._SubParsersAction[t.Any]) -> None:
    """Add the lock command to the parser.

    Parameters
    ----------
    subparsers : argparse._SubParsersAction
        Subparsers action to add the command to
    """
    parser = subparsers.add_parser(
        "lock",
        help="Lock repositories to their current revisions",
    )
    parser.add_argument(
        "-c",
        "--config",
        help="Path to configuration file",
        default="~/.config/vcspull/vcspull.yaml",
    )
    parser.add_argument(
        "-o",
        "--output",
        help="Path to save the lock file",
        default="~/.config/vcspull/vcspull.lock.json",
    )
    parser.add_argument(
        "-p",
        "--path",
        action="append",
        dest="paths",
        help="Specific repository paths to lock (can be used multiple times)",
    )
    parser.add_argument(
        "--no-parallel",
        action="store_true",
        help="Disable parallel processing",
    )


def add_apply_lock_command(subparsers: argparse._SubParsersAction[t.Any]) -> None:
    """Add the apply-lock command to the parser.

    Parameters
    ----------
    subparsers : argparse._SubParsersAction
        Subparsers action to add the command to
    """
    parser = subparsers.add_parser(
        "apply-lock",
        help="Apply a lock file to set repositories to specific revisions",
    )
    parser.add_argument(
        "-l",
        "--lock-file",
        help="Path to the lock file",
        default="~/.config/vcspull/vcspull.lock.json",
    )
    parser.add_argument(
        "-p",
        "--path",
        action="append",
        dest="paths",
        help="Specific repository paths to apply lock to (can be used multiple times)",
    )
    parser.add_argument(
        "--no-parallel",
        action="store_true",
        help="Disable parallel processing",
    )
    parser.add_argument(
        "-j",
        "--json",
        action="store_true",
        help="Output results in JSON format",
    )


def add_migrate_command(subparsers: argparse._SubParsersAction[t.Any]) -> None:
    """Add the migrate command to the parser.

    Parameters
    ----------
    subparsers : argparse._SubParsersAction
        Subparsers action to add the command to
    """
    parser = subparsers.add_parser(
        "migrate",
        help="Migrate configuration files to the latest format",
        description=(
            "Migrate VCSPull configuration files from old format to new "
            "Pydantic-based format"
        ),
    )
    parser.add_argument(
        "config_paths",
        nargs="*",
        help=(
            "Paths to configuration files to migrate (defaults to standard "
            "paths if not provided)"
        ),
    )
    parser.add_argument(
        "-o",
        "--output",
        help=(
            "Path to save the migrated configuration (if not specified, "
            "overwrites the original)"
        ),
    )
    parser.add_argument(
        "-n",
        "--no-backup",
        action="store_true",
        help="Don't create backup files of original configurations",
    )
    parser.add_argument(
        "-f",
        "--force",
        action="store_true",
        help="Force migration even if files are already in the latest format",
    )
    parser.add_argument(
        "-d",
        "--dry-run",
        action="store_true",
        help="Show what would be migrated without making changes",
    )
    parser.add_argument(
        "-c",
        "--color",
        action="store_true",
        help="Colorize output",
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
        # Load config
        config = load_config(args.config)
        if not config:
            logger.error("No configuration found")
            return 1

        # Check specified paths
        if args.paths:
            config = filter_repositories_by_paths(config, args.paths)

        # Extract essential information from repositories
        repo_info = []
        for repo in config.repositories:
            # Use a typed dictionary to avoid type errors
            repo_data: dict[str, t.Any] = {
                "name": Path(repo.path).name,  # Use Path.name
                "path": repo.path,
                "vcs": repo.vcs,
            }
            # remotes is a dict[str, str], not Optional[str]
            if repo.remotes:
                repo_data["remotes"] = repo.remotes
            if repo.rev:
                repo_data["rev"] = repo.rev
            repo_info.append(repo_data)

        # Log repository information
        config_path = getattr(config, "_config_path", "Unknown")
        logger.info(f"Configuration: {config_path}")
        logger.info(f"Number of repositories: {len(repo_info)}")

        # Log individual repository details
        for info in repo_info:
            logger.info(f"Name: {info['name']}")
            logger.info(f"Path: {info['path']}")
            logger.info(f"VCS: {info['vcs']}")

            if "remotes" in info:
                logger.info("Remotes:")
                remotes = info["remotes"]
                for remote_name, remote_url in remotes.items():
                    logger.info(f"  {remote_name}: {remote_url}")

            if "rev" in info:
                logger.info(f"Revision: {info['rev']}")

            logger.info("")  # Empty line between repositories
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
        # Load config
        config = load_config(args.config)
        if not config:
            logger.error("No configuration found")
            return 1

        # Check specified paths
        if args.paths:
            config = filter_repositories_by_paths(config, args.paths)

        # Sync repositories
        results = sync_repositories(
            config,
            paths=args.paths,
            parallel=not args.sequential,
            max_workers=args.max_workers,
        )

        # Report results
        successful_count = sum(1 for success in results.values() if success)
        failure_count = sum(1 for success in results.values() if not success)

        # Log summary
        logger.info(
            f"Sync summary: {successful_count} successful, {failure_count} failed",
        )
    except Exception as e:
        logger.error(f"Error: {e}")
        return 1
    else:
        # Return non-zero if any sync failed - in else block to fix TRY300
        if failure_count == 0:
            return 0
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
            json_output = json.dumps([repo.model_dump() for repo in repos], indent=2)
            logger.info(json_output)
        else:
            # Human-readable output
            logger.info(f"Detected {len(repos)} repositories:")
            for repo in repos:
                repo_name = repo.name or Path(repo.path).name
                vcs_type = repo.vcs or "unknown"
                logger.info(f"- {repo_name} ({vcs_type})")
                logger.info(f"  Path: {repo.path}")
                logger.info(f"  URL: {repo.url}")
                if repo.remotes:
                    logger.info("  Remotes:")
                    for remote_name, remote_url in repo.remotes.items():
                        logger.info(f"    {remote_name}: {remote_url}")
                if repo.rev:
                    logger.info(f"  Revision: {repo.rev}")
                logger.info("")  # Empty line between repositories

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
                    logger.info(f"Configuration written to YAML file: {output_path}")
                elif output_path.suffix.lower() == ".json":
                    json.dump(config.model_dump(), f, indent=2)
                    logger.info(f"Configuration written to JSON file: {output_path}")
                else:
                    # Handle unsupported format without raising directly
                    # This avoids the TRY301 linting error
                    suffix = output_path.suffix
                    logger.error(f"Unsupported file format: {suffix}")
                    return 1

            # Log summary
            repo_count = len(repos)
            logger.info(f"Wrote configuration with {repo_count} repositories")
            logger.info(f"Output file: {output_path}")
            return 0
    except Exception as e:
        logger.error(f"Error: {e}")
        return 1
    return 0


def lock_command(args: argparse.Namespace) -> int:
    """Handle the lock command.

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
        # Load configuration
        config_path = Path(args.config).expanduser().resolve()
        logger.info(f"Loading configuration from {config_path}")
        config = load_config(config_path)

        if not config:
            logger.error("No configuration found")
            return 1

        # Get the output path
        output_path = Path(args.output).expanduser().resolve()
        logger.info(f"Output lock file will be written to {output_path}")

        # Filter repositories if paths specified
        if args.paths:
            original_count = len(config.repositories)
            config = filter_repositories_by_paths(config, args.paths)
            filtered_count = len(config.repositories)
            logger.info(f"Filtered repositories: {filtered_count} of {original_count}")

        # Lock repositories
        parallel = not args.no_parallel
        mode = "parallel" if parallel else "sequential"
        logger.info(f"Locking repositories in {mode} mode")
        lock_file = lock_repositories(
            config=config,
            output_path=args.output,
            paths=args.paths,
            parallel=parallel,
        )

        # Log summary
        repo_count = len(lock_file.repositories)
        logger.info(f"Lock file created with {repo_count} locked repositories")
        logger.info(f"Lock file written to {output_path}")

    except Exception as e:
        logger.error(f"Error: {e}")
        return 1
    return 0


def apply_lock_command(args: argparse.Namespace) -> int:
    """Handle the apply-lock command.

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
        # Log operation start
        lock_file_path = Path(args.lock_file).expanduser().resolve()
        logger.info(f"Applying lock file: {lock_file_path}")

        # Apply lock
        parallel = not args.no_parallel
        logger.info(f"Processing in {'parallel' if parallel else 'sequential'} mode")

        if args.paths:
            logger.info(f"Filtering to paths: {', '.join(args.paths)}")

        results = apply_lock(
            lock_file_path=args.lock_file,
            paths=args.paths,
            parallel=parallel,
        )

        # Calculate success/failure counts
        success_count = sum(1 for success in results.values() if success)
        failure_count = sum(1 for success in results.values() if not success)

        # Log summary
        logger.info(
            f"Apply lock summary: {success_count} successful, {failure_count} failed",
        )

        # Output detailed results
        if args.json:
            # Create JSON output
            json_output = {
                "results": dict(results),
                "summary": {
                    "total": len(results),
                    "success": success_count,
                    "failure": failure_count,
                },
            }
            logger.info(json.dumps(json_output, indent=2))
        else:
            # Log individual repository results
            logger.info("Detailed results:")
            for path, success in results.items():
                status = "SUCCESS" if success else "FAILED"
                logger.info(f"{path}: {status}")
    except Exception as e:
        logger.error(f"Error: {e}")
        return 1
    # Return non-zero exit code if any repositories failed
    return 0 if failure_count == 0 else 1


# Add a new helper function to filter repositories by paths


def filter_repositories_by_paths(
    config: VCSPullConfig,
    paths: list[str],
) -> VCSPullConfig:
    """Filter repositories by paths.

    Parameters
    ----------
    config : VCSPullConfig
        Config to filter
    paths : list[str]
        Paths to filter by

    Returns
    -------
    VCSPullConfig
        Filtered config
    """
    # Create paths as Path objects for comparison
    path_objects = [Path(p).expanduser().resolve() for p in paths]

    # Filter repositories by path
    filtered_repos = [
        repo
        for repo in config.repositories
        if any(
            Path(repo.path).expanduser().resolve().is_relative_to(path)
            for path in path_objects
        )
    ]

    # Create a new config with filtered repositories
    filtered_config = VCSPullConfig(
        repositories=filtered_repos,
        settings=config.settings,
    )

    # We can't directly access _config_path as it's not part of the model
    # Instead, use a more generic approach to preserve custom attributes
    for attr_name in dir(config):
        # Skip standard attributes and methods
        # Only process non-dunder private attributes that exist
        is_private = attr_name.startswith("_") and not attr_name.startswith("__")
        if is_private and hasattr(config, attr_name):
            with contextlib.suppress(AttributeError, TypeError):
                setattr(filtered_config, attr_name, getattr(config, attr_name))

    return filtered_config


def migrate_command(args: argparse.Namespace) -> int:
    """Migrate configuration files to the latest format.

    Parameters
    ----------
    args : argparse.Namespace
        Parsed command line arguments

    Returns
    -------
    int
        Exit code
    """
    from colorama import Fore, Style

    use_color = args.color

    def format_status(success: bool) -> str:
        """Format success status with color if enabled."""
        if not use_color:
            return "Success" if success else "Failed"

        if success:
            return f"{Fore.GREEN}Success{Style.RESET_ALL}"
        return f"{Fore.RED}Failed{Style.RESET_ALL}"

    # Determine paths to process
    if args.config_paths:
        # Convert to strings to satisfy Union[str, Path] typing requirement
        paths_to_process: list[str | Path] = list(args.config_paths)
    else:
        # Use default paths if none provided
        default_paths = [
            Path("~/.config/vcspull").expanduser(),
            Path("~/.vcspull").expanduser(),
            Path.cwd(),
        ]
        paths_to_process = [str(p) for p in default_paths if p.exists()]

    # Show header
    if args.dry_run:
        print("Dry run: No files will be modified")
        print()

    create_backups = not args.no_backup

    # Process single file if output specified
    if args.output and len(paths_to_process) == 1:
        path_obj = Path(paths_to_process[0])
        if path_obj.is_file():
            source_path = path_obj
            output_path = Path(args.output)

            try:
                if args.dry_run:
                    from vcspull.config.migration import detect_config_version

                    version = detect_config_version(source_path)
                    needs_migration = version == "v1" or args.force
                    print(f"Would migrate: {source_path}")
                    print(f"  - Format: {version}")
                    print(f"  - Output: {output_path}")
                    print(f"  - Needs migration: {'Yes' if needs_migration else 'No'}")
                else:
                    success, message = migrate_config_file(
                        source_path,
                        output_path,
                        create_backup=create_backups,
                        force=args.force,
                    )
                    status = format_status(success)
                    print(f"{status}: {message}")

                return 0
            except Exception as e:
                logger.exception(f"Error migrating {source_path}")
                print(f"Error: {e}")
                return 1

    # Process multiple files or directories
    try:
        if args.dry_run:
            from vcspull.config.loader import find_config_files
            from vcspull.config.migration import detect_config_version

            config_files = find_config_files(paths_to_process)
            if not config_files:
                print("No configuration files found")
                return 0

            print(f"Found {len(config_files)} configuration file(s):")

            # Process files outside the loop to avoid try-except inside loop
            configs_to_process = []
            for file_path in config_files:
                try:
                    version = detect_config_version(file_path)
                    needs_migration = version == "v1" or args.force
                    configs_to_process.append((file_path, version, needs_migration))
                except Exception as e:
                    if use_color:
                        print(f"{Fore.RED}Error{Style.RESET_ALL}: {file_path} - {e}")
                    else:
                        print(f"Error: {file_path} - {e}")

            # Display results
            for file_path, version, needs_migration in configs_to_process:
                status = "Would migrate" if needs_migration else "Already migrated"

                if use_color:
                    status_color = Fore.YELLOW if needs_migration else Fore.GREEN
                    print(
                        f"{status_color}{status}{Style.RESET_ALL}: {file_path} ({version})"
                    )
                else:
                    print(f"{status}: {file_path} ({version})")
        else:
            results = migrate_all_configs(
                paths_to_process,
                create_backups=create_backups,
                force=args.force,
            )

            if not results:
                print("No configuration files found")
                return 0

            # Print results
            print(f"Processed {len(results)} configuration file(s):")
            for file_path, success, message in results:
                status = format_status(success)
                print(f"{status}: {file_path} - {message}")

        return 0
    except Exception as e:
        logger.exception(f"Error processing configuration files")
        print(f"Error: {e}")
        return 1
