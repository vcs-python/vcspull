"""Migrate configuration to checkout targets and backend option blocks."""

from __future__ import annotations

import argparse
import copy
import logging
import pathlib
import traceback
import typing as t

from colorama import Fore, Style

from vcspull._internal.config_reader import (
    DuplicateAwareConfigReader,
    config_format_from_path,
)
from vcspull._internal.private_path import PrivatePath
from vcspull.config import (
    find_config_files,
    find_home_config_files,
    migrate_repo_entry,
    normalize_config_file_path,
    save_config,
    save_config_yaml_with_items,
)

log = logging.getLogger(__name__)


def create_migrate_subparser(parser: argparse.ArgumentParser) -> None:
    """Create ``vcspull migrate`` argument subparser."""
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
        help="Write migrated configuration back to file",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Migrate all discovered config files (home, config dir, current dir)",
    )


def migrate_config(config_data: dict[str, t.Any]) -> tuple[dict[str, t.Any], int]:
    """Separate legacy checkout, backend, and policy settings in every entry.

    Parameters
    ----------
    config_data : dict
        Raw configuration data (workspace root → repo name → entry).

    Returns
    -------
    tuple[dict, int]
        The migrated configuration and the number of entries rewritten.

    Examples
    --------
    >>> migrate_config(
    ...     {"~/code/": {"flask": {"repo": "git+x", "shallow": True}}}
    ... )
    ({'~/code/': {'flask': {'repo': 'git+x', 'git': {'depth': 1}}}}, 1)

    An already-migrated config is returned unchanged:

    >>> migrate_config(
    ...     {"~/code/": {"flask": {"repo": "git+x", "git": {"depth": 1}}}}
    ... )
    ({'~/code/': {'flask': {'repo': 'git+x', 'git': {'depth': 1}}}}, 0)
    """
    migrated: dict[str, t.Any] = copy.deepcopy(config_data)
    change_count = 0

    for workspace, repos in migrated.items():
        if not isinstance(repos, dict):
            continue
        for repo_name, entry in repos.items():
            try:
                changed, new_entry = migrate_repo_entry(entry)
            except (TypeError, ValueError) as error:
                msg = f"workspace {workspace!r}, repository {repo_name!r}: {error}"
                raise ValueError(msg) from error
            if changed:
                repos[repo_name] = new_entry
                change_count += 1

    return migrated, change_count


def migrate_single_config(config_file_path: pathlib.Path, write: bool) -> bool:
    """Migrate a single vcspull configuration file.

    Parameters
    ----------
    config_file_path : pathlib.Path
        Path to config file.
    write : bool
        Whether to write changes back to file.

    Returns
    -------
    bool
        ``True`` if the file was processed successfully, ``False`` otherwise.
    """
    display_config_path = str(PrivatePath(config_file_path))

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

    try:
        raw_config, _duplicate_root_occurrences, top_level_items = (
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

    items = top_level_items or list(raw_config.items())
    migrated_items: list[tuple[str, t.Any]] = []
    changed_entries: list[str] = []
    change_count = 0
    try:
        for workspace, repos in items:
            migrated, changes = migrate_config({workspace: repos})
            migrated_repos = migrated[workspace]
            migrated_items.append((workspace, migrated_repos))
            change_count += changes
            if isinstance(repos, dict):
                changed_entries.extend(
                    str(name)
                    for name, entry in migrated_repos.items()
                    if entry != repos[name]
                )
    except ValueError as error:
        # Invalid user input needs its location and message, not a traceback.
        log.error(  # noqa: TRY400
            "migration failed for %s: %s",
            display_config_path,
            error,
        )
        return False

    if change_count == 0:
        log.info(
            "%s%s %s%s%s already uses checkout targets and backend options",
            Fore.GREEN,
            Style.RESET_ALL,
            Fore.BLUE,
            display_config_path,
            Style.RESET_ALL,
        )
        return True

    log.info(
        "%si%s Migrating %s%d%s %s in %s%s%s",
        Fore.CYAN,
        Style.RESET_ALL,
        Fore.YELLOW,
        change_count,
        Style.RESET_ALL,
        "entry" if change_count == 1 else "entries",
        Fore.BLUE,
        display_config_path,
        Style.RESET_ALL,
    )

    for repo_name in changed_entries:
        log.info(
            "  %s%s %s%s%s: separated checkout, backend, and policy settings",
            Fore.BLUE,
            Style.RESET_ALL,
            Fore.CYAN,
            repo_name,
            Style.RESET_ALL,
        )

    if write:
        try:
            if config_format_from_path(config_file_path) == "json":
                save_config(config_file_path, dict(migrated_items))
            else:
                save_config_yaml_with_items(config_file_path, migrated_items)
            log.info(
                "%s✓%s Successfully migrated %s%s%s",
                Fore.GREEN,
                Style.RESET_ALL,
                Fore.BLUE,
                display_config_path,
                Style.RESET_ALL,
            )
        except Exception:
            log.exception(
                "Error saving migrated config to %s",
                PrivatePath(config_file_path),
            )
            if log.isEnabledFor(logging.DEBUG):
                traceback.print_exc()
            return False
    else:
        log.info(
            "\n%s→%s Run with %s--write%s to apply these changes.",
            Fore.YELLOW,
            Style.RESET_ALL,
            Fore.CYAN,
            Style.RESET_ALL,
        )

    return True


def migrate_config_file(
    config_file_path_str: str | None,
    write: bool,
    migrate_all: bool = False,
) -> int:
    """Migrate configuration files and return zero when every file succeeds.

    Parameters
    ----------
    config_file_path_str : str | None
        Path to config file, or None to use the default.
    write : bool
        Whether to write changes back to file.
    migrate_all : bool
        If True, migrate all discovered config files.

    Returns
    -------
    int
        Zero on success, one when discovery or any migration fails.
    """
    if migrate_all:
        config_files = find_config_files(include_home=True)

        local_yaml = pathlib.Path.cwd() / ".vcspull.yaml"
        if local_yaml.exists() and local_yaml not in config_files:
            config_files.append(local_yaml)

        local_json = pathlib.Path.cwd() / ".vcspull.json"
        if local_json.exists() and local_json not in config_files:
            config_files.append(local_json)

        if not config_files:
            log.error(
                "%s✗%s No configuration files found.",
                Fore.RED,
                Style.RESET_ALL,
            )
            return 1

        log.info(
            "%si%s Found %s%d%s configuration %s to check:",
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
                str(PrivatePath(config_file)),
                Style.RESET_ALL,
            )
        log.info("")

        success_count = 0
        for config_file in config_files:
            if migrate_single_config(config_file, write):
                success_count += 1

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
        return int(success_count != len(config_files))

    if config_file_path_str:
        config_file_path = normalize_config_file_path(
            pathlib.Path(config_file_path_str)
        )
    else:
        home_configs = find_home_config_files(filetype=["yaml"])
        if not home_configs:
            local_config = pathlib.Path.cwd() / ".vcspull.yaml"
            if local_config.exists():
                config_file_path = local_config
            else:
                log.error(
                    "%s✗%s No configuration file found. Create .vcspull.yaml first.",
                    Fore.RED,
                    Style.RESET_ALL,
                )
                return 1
        elif len(home_configs) > 1:
            log.error(
                "Multiple home config files found, please specify one with -f/--file",
            )
            return 1
        else:
            config_file_path = home_configs[0]

    return int(not migrate_single_config(config_file_path, write))
