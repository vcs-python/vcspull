"""Format vcspull configuration files."""

from __future__ import annotations

import logging
import pathlib
import traceback
import typing as t

from colorama import Fore, Style

from vcspull._internal.config_reader import ConfigReader
from vcspull.config import (
    find_config_files,
    find_home_config_files,
    normalize_workspace_roots,
    save_config_yaml,
)

if t.TYPE_CHECKING:
    import argparse

log = logging.getLogger(__name__)


def create_fmt_subparser(parser: argparse.ArgumentParser) -> None:
    """Create ``vcspull fmt`` argument subparser."""
    parser.add_argument(
        "-c",
        "--config",
        dest="config",
        metavar="file",
        help="path to custom config file (default: .vcspull.yaml or ~/.vcspull.yaml)",
    )
    parser.add_argument(
        "--write",
        "-w",
        action="store_true",
        help="Write formatted configuration back to file",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Format all discovered config files (home, config dir, and current dir)",
    )


def normalize_repo_config(repo_data: t.Any) -> dict[str, t.Any]:
    """Normalize repository configuration to verbose format.

    Parameters
    ----------
    repo_data : Any
        Repository configuration (string URL or dict)

    Returns
    -------
    dict
        Normalized repository configuration with 'repo' key
    """
    if isinstance(repo_data, str):
        # Convert compact format to verbose format
        return {"repo": repo_data}
    if isinstance(repo_data, dict):
        # If it has 'url' key but not 'repo', convert to use 'repo'
        if "url" in repo_data and "repo" not in repo_data:
            normalized = repo_data.copy()
            normalized["repo"] = normalized.pop("url")
            return normalized
        # Already in correct format or has other fields
        return repo_data
    # Return as-is for other types
    return t.cast("dict[str, t.Any]", repo_data)


def format_config(config_data: dict[str, t.Any]) -> tuple[dict[str, t.Any], int]:
    """Format vcspull configuration for consistency.

    Parameters
    ----------
    config_data : dict
        Raw configuration data

    Returns
    -------
    tuple[dict, int]
        Formatted configuration and count of changes made
    """
    changes = 0
    formatted: dict[str, t.Any] = {}

    # Sort directories
    sorted_dirs = sorted(config_data.keys())

    for directory in sorted_dirs:
        repos = config_data[directory]

        if not isinstance(repos, dict):
            # Not a repository section, keep as-is
            formatted[directory] = repos
            continue

        # Sort repositories within each directory
        sorted_repos = sorted(repos.keys())
        formatted_dir: dict[str, t.Any] = {}

        for repo_name in sorted_repos:
            repo_data = repos[repo_name]
            normalized = normalize_repo_config(repo_data)

            # Check if normalization changed anything
            if normalized != repo_data:
                changes += 1

            formatted_dir[repo_name] = normalized

        # Check if sorting changed the order
        if list(repos.keys()) != sorted_repos:
            changes += 1

        formatted[directory] = formatted_dir

    # Check if directory sorting changed the order
    if list(config_data.keys()) != sorted_dirs:
        changes += 1

    return formatted, changes


def format_single_config(
    config_file_path: pathlib.Path,
    write: bool,
) -> bool:
    """Format a single vcspull configuration file.

    Parameters
    ----------
    config_file_path : pathlib.Path
        Path to config file
    write : bool
        Whether to write changes back to file

    Returns
    -------
    bool
        True if formatting was successful, False otherwise
    """
    # Check if file exists
    if not config_file_path.exists():
        log.error(
            "%s✗%s Config file %s%s%s not found.",
            Fore.RED,
            Style.RESET_ALL,
            Fore.BLUE,
            config_file_path,
            Style.RESET_ALL,
        )
        return False

    # Load existing config
    try:
        raw_config = ConfigReader._from_file(config_file_path)
        if not isinstance(raw_config, dict):
            log.error(
                "Config file %s is not a valid YAML dictionary.",
                config_file_path,
            )
            return False
    except Exception:
        log.exception("Error loading config from %s", config_file_path)
        if log.isEnabledFor(logging.DEBUG):
            traceback.print_exc()
        return False

    # Format the configuration
    cwd = pathlib.Path.cwd()
    home = pathlib.Path.home()

    normalization_result = normalize_workspace_roots(
        raw_config,
        cwd=cwd,
        home=home,
    )
    raw_config, _workspace_map, merge_conflicts, merge_changes = normalization_result

    for message in merge_conflicts:
        log.warning(message)

    formatted_config, change_count = format_config(raw_config)
    change_count += merge_changes

    if change_count == 0:
        log.info(
            "%s✓%s %s%s%s is already formatted correctly.",
            Fore.GREEN,
            Style.RESET_ALL,
            Fore.BLUE,
            config_file_path,
            Style.RESET_ALL,
        )
        return True

    # Show what would be changed
    log.info(
        "%si%s Found %s%d%s formatting %s in %s%s%s",
        Fore.CYAN,
        Style.RESET_ALL,
        Fore.YELLOW,
        change_count,
        Style.RESET_ALL,
        "issue" if change_count == 1 else "issues",
        Fore.BLUE,
        config_file_path,
        Style.RESET_ALL,
    )

    # Analyze and report specific changes
    if merge_changes > 0:
        log.info(
            "  %s•%s Normalized workspace root labels",
            Fore.BLUE,
            Style.RESET_ALL,
        )

    compact_to_verbose = 0
    url_to_repo = 0

    for repos in raw_config.values():
        if isinstance(repos, dict):
            for repo_data in repos.values():
                if isinstance(repo_data, str):
                    compact_to_verbose += 1
                elif (
                    isinstance(repo_data, dict)
                    and "url" in repo_data
                    and "repo" not in repo_data
                ):
                    url_to_repo += 1

    if compact_to_verbose > 0:
        log.info(
            "  %s•%s %d %s from compact to verbose format",
            Fore.BLUE,
            Style.RESET_ALL,
            compact_to_verbose,
            "repository" if compact_to_verbose == 1 else "repositories",
        )

    if url_to_repo > 0:
        log.info(
            "  %s•%s %d %s from 'url' to 'repo' key",
            Fore.BLUE,
            Style.RESET_ALL,
            url_to_repo,
            "repository" if url_to_repo == 1 else "repositories",
        )

    if list(raw_config.keys()) != sorted(raw_config.keys()):
        log.info(
            "  %s•%s Directories will be sorted alphabetically",
            Fore.BLUE,
            Style.RESET_ALL,
        )

    # Check if any repos need sorting
    for directory, repos in raw_config.items():
        if isinstance(repos, dict) and list(repos.keys()) != sorted(repos.keys()):
            log.info(
                "  %s•%s Repositories in %s%s%s will be sorted alphabetically",
                Fore.BLUE,
                Style.RESET_ALL,
                Fore.MAGENTA,
                directory,
                Style.RESET_ALL,
            )
            break

    if write:
        # Save formatted config
        try:
            save_config_yaml(config_file_path, formatted_config)
            log.info(
                "%s✓%s Successfully formatted %s%s%s",
                Fore.GREEN,
                Style.RESET_ALL,
                Fore.BLUE,
                config_file_path,
                Style.RESET_ALL,
            )
        except Exception:
            log.exception("Error saving formatted config to %s", config_file_path)
            if log.isEnabledFor(logging.DEBUG):
                traceback.print_exc()
            return False
    else:
        log.info(
            "\n%s→%s Run with %s--write%s to apply these formatting changes.",
            Fore.YELLOW,
            Style.RESET_ALL,
            Fore.CYAN,
            Style.RESET_ALL,
        )

    return True


def format_config_file(
    config_file_path_str: str | None,
    write: bool,
    format_all: bool = False,
) -> None:
    """Format vcspull configuration file(s).

    Parameters
    ----------
    config_file_path_str : str | None
        Path to config file, or None to use default
    write : bool
        Whether to write changes back to file
    format_all : bool
        If True, format all discovered config files
    """
    if format_all:
        # Format all discovered config files
        config_files = find_config_files(include_home=True)

        # Also check for local .vcspull.yaml
        local_yaml = pathlib.Path.cwd() / ".vcspull.yaml"
        if local_yaml.exists() and local_yaml not in config_files:
            config_files.append(local_yaml)

        # Also check for local .vcspull.json
        local_json = pathlib.Path.cwd() / ".vcspull.json"
        if local_json.exists() and local_json not in config_files:
            config_files.append(local_json)

        if not config_files:
            log.error(
                "%s✗%s No configuration files found.",
                Fore.RED,
                Style.RESET_ALL,
            )
            return

        log.info(
            "%si%s Found %s%d%s configuration %s to format:",
            Fore.CYAN,
            Style.RESET_ALL,
            Fore.YELLOW,
            len(config_files),
            Style.RESET_ALL,
            "file" if len(config_files) == 1 else "files",
        )

        for config_file in config_files:
            log.info(
                "  %s•%s %s%s%s",
                Fore.BLUE,
                Style.RESET_ALL,
                Fore.CYAN,
                config_file,
                Style.RESET_ALL,
            )

        log.info("")  # Empty line for readability

        success_count = 0
        for config_file in config_files:
            if format_single_config(config_file, write):
                success_count += 1

        # Summary
        if success_count == len(config_files):
            log.info(
                "\n%s✓%s All %d configuration files processed successfully.",
                Fore.GREEN,
                Style.RESET_ALL,
                len(config_files),
            )
        else:
            log.info(
                "\n%si%s Processed %d/%d configuration files successfully.",
                Fore.CYAN,
                Style.RESET_ALL,
                success_count,
                len(config_files),
            )
    else:
        # Format single config file
        if config_file_path_str:
            config_file_path = pathlib.Path(config_file_path_str).expanduser().resolve()
        else:
            home_configs = find_home_config_files(filetype=["yaml"])
            if not home_configs:
                # Try local .vcspull.yaml
                local_config = pathlib.Path.cwd() / ".vcspull.yaml"
                if local_config.exists():
                    config_file_path = local_config
                else:
                    log.error(
                        "%s✗%s No configuration file found. "
                        "Create .vcspull.yaml first.",
                        Fore.RED,
                        Style.RESET_ALL,
                    )
                    return
            elif len(home_configs) > 1:
                log.error(
                    "Multiple home config files found, "
                    "please specify one with -c/--config",
                )
                return
            else:
                config_file_path = home_configs[0]

        format_single_config(config_file_path, write)
