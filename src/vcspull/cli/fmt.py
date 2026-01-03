"""Format vcspull configuration files."""

from __future__ import annotations

import argparse
import copy
import logging
import pathlib
import traceback
import typing as t

from colorama import Fore, Style

from vcspull._internal.config_reader import DuplicateAwareConfigReader
from vcspull._internal.private_path import PrivatePath
from vcspull.config import (
    find_config_files,
    find_home_config_files,
    merge_duplicate_workspace_roots,
    normalize_workspace_roots,
    save_config_yaml,
)

log = logging.getLogger(__name__)

RepoConfigData: t.TypeAlias = str | pathlib.Path | t.Mapping[str, object]


def create_fmt_subparser(parser: argparse.ArgumentParser) -> None:
    """Create ``vcspull fmt`` argument subparser."""
    parser.add_argument(
        "-f",
        "--file",
        dest="config",
        metavar="FILE",
        help="path to config file (default: .vcspull.yaml or ~/.vcspull.yaml)",
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
    parser.add_argument(
        "--no-merge",
        dest="merge_roots",
        action="store_false",
        help="Do not merge duplicate workspace roots when formatting",
    )
    parser.set_defaults(merge_roots=True)


def normalize_repo_config(repo_data: RepoConfigData) -> dict[str, object]:
    """Normalize repository configuration to verbose format.

    Parameters
    ----------
    repo_data : str | pathlib.Path | Mapping[str, object]
        Repository configuration (string URL or dict)

    Returns
    -------
    dict
        Normalized repository configuration with 'repo' key
    """
    if isinstance(repo_data, str):
        # Convert compact format to verbose format
        return {"repo": repo_data}
    if isinstance(repo_data, pathlib.Path):
        return {"repo": str(repo_data)}
    repo_map = dict(repo_data)
    # If it has 'url' key but not 'repo', convert to use 'repo'
    if "url" in repo_map and "repo" not in repo_map:
        normalized = repo_map.copy()
        normalized["repo"] = normalized.pop("url")
        return normalized
    # Already in correct format or has other fields
    return repo_map


def format_config(
    config_data: t.Mapping[str, object],
) -> tuple[dict[str, object], int]:
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
    formatted: dict[str, object] = {}

    # Sort directories
    sorted_dirs = sorted(config_data.keys())

    for directory in sorted_dirs:
        repos = config_data[directory]

        if not isinstance(repos, dict):
            # Not a repository section, keep as-is
            formatted[directory] = repos
            continue

        # Sort repositories within each directory
        repos_map = t.cast("dict[str, object]", repos)
        sorted_repos = sorted(repos_map.keys())
        formatted_dir: dict[str, object] = {}

        for repo_name in sorted_repos:
            repo_data = t.cast("RepoConfigData", repos_map[repo_name])
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
    *,
    merge_roots: bool,
) -> bool:
    """Format a single vcspull configuration file.

    Parameters
    ----------
    config_file_path : pathlib.Path
        Path to config file
    write : bool
        Whether to write changes back to file
    merge_roots : bool
        Merge duplicate workspace roots when True (default behavior)

    Returns
    -------
    bool
        True if formatting was successful, False otherwise
    """
    # Precompute redacted path for CLI output.
    display_config_path = str(PrivatePath(config_file_path))

    # Check if file exists
    if not config_file_path.exists():
        log.error(
            "%s✗%s Config file %s%s%s not found.",
            Fore.RED,
            Style.RESET_ALL,
            Fore.BLUE,
            display_config_path,
            Style.RESET_ALL,
        )
        return False

    # Load existing config
    try:
        raw_config, duplicate_root_occurrences, _top_level_items = (
            DuplicateAwareConfigReader.load_with_duplicates(config_file_path)
        )
    except TypeError:
        log.exception(
            "Config file %s is not a mapping",
            PrivatePath(config_file_path),
        )
        return False
    except Exception:
        log.exception(
            "Error loading config from %s",
            PrivatePath(config_file_path),
        )
        if log.isEnabledFor(logging.DEBUG):
            traceback.print_exc()
        return False

    # Format the configuration
    cwd = pathlib.Path.cwd()
    home = pathlib.Path.home()

    duplicate_merge_conflicts: list[str] = []
    duplicate_merge_changes = 0
    duplicate_merge_details: list[tuple[str, int]] = []

    working_config = copy.deepcopy(raw_config)

    if merge_roots:
        (
            working_config,
            duplicate_merge_conflicts,
            duplicate_merge_changes,
            duplicate_merge_details,
        ) = merge_duplicate_workspace_roots(working_config, duplicate_root_occurrences)
    elif duplicate_root_occurrences:
        duplicate_merge_details = [
            (label, len(values)) for label, values in duplicate_root_occurrences.items()
        ]
        for label, occurrence_count in duplicate_merge_details:
            log.warning(
                "%s•%s Duplicate workspace root %s%s%s appears %s%d%s time%s; "
                "skipping merge because --no-merge was provided.",
                Fore.BLUE,
                Style.RESET_ALL,
                Fore.MAGENTA,
                label,
                Style.RESET_ALL,
                Fore.YELLOW,
                occurrence_count,
                Style.RESET_ALL,
                "" if occurrence_count == 1 else "s",
            )

    if merge_roots:
        normalization_result = normalize_workspace_roots(
            working_config,
            cwd=cwd,
            home=home,
        )
        (
            normalized_config,
            _workspace_map,
            merge_conflicts,
            normalization_changes,
        ) = normalization_result
    else:
        normalized_config = working_config
        merge_conflicts = []
        normalization_changes = 0

    for message in merge_conflicts:
        log.warning(message)
    for message in duplicate_merge_conflicts:
        log.warning(message)

    formatted_config, change_count = format_config(normalized_config)
    change_count += normalization_changes + duplicate_merge_changes

    if change_count == 0:
        log.info(
            "%s✓%s %s%s%s is already formatted correctly.",
            Fore.GREEN,
            Style.RESET_ALL,
            Fore.BLUE,
            display_config_path,
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
        display_config_path,
        Style.RESET_ALL,
    )

    # Analyze and report specific changes
    if merge_roots and normalization_changes > 0:
        log.info(
            "  %s•%s Normalized workspace root labels",
            Fore.BLUE,
            Style.RESET_ALL,
        )

    if merge_roots and duplicate_merge_details:
        for label, occurrence_count in duplicate_merge_details:
            log.info(
                "  %s•%s Merged %s%d%s duplicate entr%s for workspace root %s%s%s",
                Fore.BLUE,
                Style.RESET_ALL,
                Fore.YELLOW,
                occurrence_count,
                Style.RESET_ALL,
                "y" if occurrence_count == 1 else "ies",
                Fore.MAGENTA,
                label,
                Style.RESET_ALL,
            )

    compact_to_verbose = 0
    url_to_repo = 0

    for repos in normalized_config.values():
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

    if list(normalized_config.keys()) != sorted(normalized_config.keys()):
        log.info(
            "  %s•%s Directories will be sorted alphabetically",
            Fore.BLUE,
            Style.RESET_ALL,
        )

    # Check if any repos need sorting
    for directory, repos in normalized_config.items():
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
                display_config_path,
                Style.RESET_ALL,
            )
        except Exception:
            log.exception(
                "Error saving formatted config to %s",
                PrivatePath(config_file_path),
            )
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
    *,
    merge_roots: bool = True,
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
    merge_roots : bool
        Merge duplicate workspace roots when True (default)
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
            display_config_file = str(PrivatePath(config_file))
            log.info(
                "  %s•%s %s%s%s",
                Fore.BLUE,
                Style.RESET_ALL,
                Fore.CYAN,
                display_config_file,
                Style.RESET_ALL,
            )

        log.info("")  # Empty line for readability

        success_count = 0
        for config_file in config_files:
            if format_single_config(
                config_file,
                write,
                merge_roots=merge_roots,
            ):
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
                    "please specify one with -f/--file",
                )
                return
            else:
                config_file_path = home_configs[0]

        format_single_config(
            config_file_path,
            write,
            merge_roots=merge_roots,
        )
