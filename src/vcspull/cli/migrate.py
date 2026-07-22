"""Migrate vcspull configuration files to the ``options:`` form."""

from __future__ import annotations

import argparse
import copy
import logging
import pathlib
import traceback
import typing as t

from colorama import Fore, Style

from vcspull._internal import scopes
from vcspull._internal.config_reader import DuplicateAwareConfigReader
from vcspull._internal.private_path import PrivatePath
from vcspull.config import (
    LEGACY_REPO_OPTION_KEYS,
    ensure_config_trusted,
    find_home_config_files,
    migrate_repo_entry,
    normalize_config_file_path,
    save_config,
)

log = logging.getLogger(__name__)


def create_migrate_subparser(parser: argparse.ArgumentParser) -> None:
    """Create ``vcspull migrate`` argument subparser."""
    parser.add_argument(
        "-f",
        "--file",
        dest="config",
        metavar="FILE",
        help="path to config file (default: ~/.vcspull.yaml, else ./.vcspull.yaml)",
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
    """Relocate legacy top-level sync keys under ``options:`` for every entry.

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
    ({'~/code/': {'flask': {'repo': 'git+x', 'options': {'shallow': True}}}}, 1)

    An already-migrated config is returned unchanged:

    >>> migrate_config(
    ...     {"~/code/": {"flask": {"repo": "git+x", "options": {"shallow": True}}}}
    ... )
    ({'~/code/': {'flask': {'repo': 'git+x', 'options': {'shallow': True}}}}, 0)
    """
    migrated: dict[str, t.Any] = copy.deepcopy(config_data)
    change_count = 0

    for repos in migrated.values():
        if not isinstance(repos, dict):
            continue
        for repo_name, entry in repos.items():
            changed, new_entry = migrate_repo_entry(entry)
            if changed:
                repos[repo_name] = new_entry
                change_count += 1

    return migrated, change_count


def migrate_single_config(
    config_file_path: pathlib.Path,
    write: bool,
    *,
    trust_project: bool = False,
    explicit: bool = False,
) -> bool:
    """Migrate a single vcspull configuration file.

    Parameters
    ----------
    config_file_path : pathlib.Path
        Path to config file.
    write : bool
        Whether to write changes back to file.
    trust_project : bool
        Trust an escaping project config without prompting.
    explicit : bool
        The caller named this file with ``--file``.

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

    if not ensure_config_trusted(
        config_file_path,
        trust_project=trust_project,
        explicit=explicit,
    ):
        return False

    try:
        raw_config, _duplicate_root_occurrences, _top_level_items = (
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

    migrated_config, change_count = migrate_config(raw_config)

    if change_count == 0:
        log.info(
            "%s✓%s %s%s%s already nests rev/shallow/depth under options:.",
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

    moved = "/".join(LEGACY_REPO_OPTION_KEYS)
    for workspace_label, repos in migrated_config.items():
        if not isinstance(repos, dict):
            continue
        original = raw_config.get(workspace_label)
        for repo_name, entry in repos.items():
            previous = original.get(repo_name) if isinstance(original, dict) else None
            if entry != previous:
                log.info(
                    "  %s•%s %s%s%s: moved %s under options:",
                    Fore.BLUE,
                    Style.RESET_ALL,
                    Fore.CYAN,
                    repo_name,
                    Style.RESET_ALL,
                    moved,
                )

    if write:
        try:
            save_config(config_file_path, migrated_config)
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
    *,
    trust_project: bool = False,
) -> None:
    """Migrate vcspull configuration file(s) to the ``options:`` form.

    Parameters
    ----------
    config_file_path_str : str | None
        Path to config file, or None to use the default.
    write : bool
        Whether to write changes back to file.
    migrate_all : bool
        If True, migrate all discovered config files.
    trust_project : bool
        Trust escaping project configs without prompting.
    """
    if migrate_all:
        cwd = pathlib.Path.cwd()
        config_files = [source.path for source in scopes.resolve_sources(cwd=cwd)]

        if not config_files:
            log.error(
                "%s✗%s No configuration files found.",
                Fore.RED,
                Style.RESET_ALL,
            )
            return

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
            if migrate_single_config(
                config_file,
                write,
                trust_project=trust_project,
            ):
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
        return

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
                return
        elif len(home_configs) > 1:
            log.error(
                "Multiple home config files found, please specify one with -f/--file",
            )
            return
        else:
            config_file_path = home_configs[0]

    migrate_single_config(
        config_file_path,
        write,
        trust_project=trust_project,
        explicit=bool(config_file_path_str),
    )
