"""Discover repositories from filesystem for vcspull."""

from __future__ import annotations

import argparse
import logging
import os
import pathlib
import subprocess
import traceback
import typing as t

from colorama import Fore, Style

from vcspull._internal.config_reader import DuplicateAwareConfigReader
from vcspull._internal.private_path import PrivatePath
from vcspull.config import (
    canonicalize_workspace_path,
    expand_dir,
    find_home_config_files,
    merge_duplicate_workspace_roots,
    normalize_workspace_roots,
    save_config_yaml,
    workspace_root_label,
)

log = logging.getLogger(__name__)

ConfigScope = t.Literal["system", "user", "project", "external"]


def _classify_config_scope(
    config_path: pathlib.Path,
    *,
    cwd: pathlib.Path,
    home: pathlib.Path,
) -> ConfigScope:
    """Determine whether a config lives in user, system, project, or external scope."""
    resolved = config_path.expanduser().resolve()
    home = home.expanduser().resolve()
    cwd = cwd.expanduser().resolve()

    default_user_configs = {
        (home / ".vcspull.yaml").resolve(),
        (home / ".vcspull.json").resolve(),
    }
    if resolved in default_user_configs:
        return "user"

    xdg_config_home = (
        pathlib.Path(os.environ.get("XDG_CONFIG_HOME", home / ".config"))
        .expanduser()
        .resolve()
    )
    user_config_root = (xdg_config_home / "vcspull").resolve()
    try:
        resolved.relative_to(user_config_root)
    except ValueError:
        pass
    else:
        return "user"

    xdg_config_dirs_value = os.environ.get("XDG_CONFIG_DIRS")
    if xdg_config_dirs_value:
        config_dir_bases = [
            pathlib.Path(entry).expanduser().resolve()
            for entry in xdg_config_dirs_value.split(os.pathsep)
            if entry
        ]
    else:
        config_dir_bases = [pathlib.Path("/etc/xdg").resolve()]

    for base in config_dir_bases:
        candidate = (base / "vcspull").resolve()
        try:
            resolved.relative_to(candidate)
        except ValueError:
            continue
        else:
            return "system"

    try:
        resolved.relative_to(cwd)
    except ValueError:
        return "external"
    return "project"


def get_git_origin_url(repo_path: pathlib.Path) -> str | None:
    """Get the origin URL from a git repository.

    Parameters
    ----------
    repo_path : pathlib.Path
        Path to the git repository

    Returns
    -------
    str | None
        The origin URL if found, None otherwise
    """
    try:
        result = subprocess.run(
            ["git", "config", "--get", "remote.origin.url"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        log.debug("Could not get origin URL for %s: %s", repo_path, e)
        return None


def create_discover_subparser(parser: argparse.ArgumentParser) -> None:
    """Create ``vcspull discover`` argument subparser.

    Parameters
    ----------
    parser : argparse.ArgumentParser
        The parser to configure
    """
    parser.add_argument(
        "scan_dir",
        metavar="PATH",
        help="Directory to scan for git repositories",
    )
    parser.add_argument(
        "-f",
        "--file",
        dest="config",
        metavar="FILE",
        help="path to config file (default: ~/.vcspull.yaml or ./.vcspull.yaml)",
    )
    parser.add_argument(
        "-w",
        "--workspace",
        "--workspace-root",
        dest="workspace_root_path",
        metavar="DIR",
        help=(
            "Workspace root directory in config (e.g., '~/projects/'). "
            "If not specified, uses the scan directory. "
            "Applies the workspace root to all discovered repos."
        ),
    )
    parser.add_argument(
        "--recursive",
        "-r",
        action="store_true",
        help="Scan directories recursively",
    )
    parser.add_argument(
        "--yes",
        "-y",
        action="store_true",
        help="Skip confirmation prompt",
    )
    parser.add_argument(
        "--dry-run",
        "-n",
        action="store_true",
        help="Preview changes without writing to config file",
    )
    parser.add_argument(
        "--no-merge",
        dest="merge_duplicates",
        action="store_false",
        help="Skip merging duplicate workspace roots before writing",
    )
    parser.set_defaults(merge_duplicates=True)


def _resolve_workspace_path(
    workspace_root: str | None,
    repo_path_str: str | None,
    *,
    cwd: pathlib.Path,
) -> pathlib.Path:
    """Resolve workspace path from arguments.

    Parameters
    ----------
    workspace_root : str | None
        Workspace root path from user
    repo_path_str : str | None
        Repo path from user
    cwd : pathlib.Path
        Current working directory

    Returns
    -------
    pathlib.Path
        Resolved workspace path
    """
    if workspace_root:
        return canonicalize_workspace_path(workspace_root, cwd=cwd)
    if repo_path_str:
        return expand_dir(pathlib.Path(repo_path_str), cwd)
    return cwd


def discover_repos(
    scan_dir_str: str,
    config_file_path_str: str | None,
    recursive: bool,
    workspace_root_override: str | None,
    yes: bool,
    dry_run: bool,
    *,
    merge_duplicates: bool = True,
) -> None:
    """Scan filesystem for git repositories and add to vcspull config.

    Parameters
    ----------
    scan_dir_str : str
        Directory to scan for git repositories
    config_file_path_str : str | None
        Path to config file, or None to use default
    recursive : bool
        Whether to scan subdirectories recursively
    workspace_root_override : str | None
        Workspace root to use in config (overrides automatic detection)
    yes : bool
        Whether to skip confirmation prompt
    dry_run : bool
        If True, preview changes without writing
    """
    scan_dir = expand_dir(pathlib.Path(scan_dir_str))

    config_file_path: pathlib.Path
    if config_file_path_str:
        config_file_path = pathlib.Path(config_file_path_str).expanduser().resolve()
    else:
        home_configs = find_home_config_files(filetype=["yaml"])
        if not home_configs:
            config_file_path = pathlib.Path.cwd() / ".vcspull.yaml"
            log.info(
                "%si%s No config specified and no default "
                "home config, will use/create %s%s%s",
                Fore.CYAN,
                Style.RESET_ALL,
                Fore.BLUE,
                PrivatePath(config_file_path),
                Style.RESET_ALL,
            )
        elif len(home_configs) > 1:
            log.error(
                "Multiple home_config files found, please specify one with -f/--file",
            )
            return
        else:
            config_file_path = home_configs[0]

    display_config_path = str(PrivatePath(config_file_path))

    cwd = pathlib.Path.cwd()
    home = pathlib.Path.home()
    config_scope = _classify_config_scope(config_file_path, cwd=cwd, home=home)
    allow_relative_workspace = config_scope == "project"

    raw_config: dict[str, t.Any]
    duplicate_root_occurrences: dict[str, list[t.Any]]
    if config_file_path.exists() and config_file_path.is_file():
        try:
            (
                raw_config,
                duplicate_root_occurrences,
                _top_level_items,
            ) = DuplicateAwareConfigReader.load_with_duplicates(config_file_path)
        except TypeError:
            log.exception(
                "Config file %s is not a valid YAML dictionary.",
                display_config_path,
            )
            return
        except Exception:
            log.exception(
                "Error loading YAML from %s. Aborting.",
                PrivatePath(config_file_path),
            )
            if log.isEnabledFor(logging.DEBUG):
                traceback.print_exc()
            return
        if raw_config is None:
            raw_config = {}
        elif not isinstance(raw_config, dict):
            log.error(
                "Config file %s is not a valid YAML dictionary.",
                display_config_path,
            )
            return
    else:
        raw_config = {}
        duplicate_root_occurrences = {}
        log.info(
            "%si%s Config file %s%s%s not found. A new one will be created.",
            Fore.CYAN,
            Style.RESET_ALL,
            Fore.BLUE,
            display_config_path,
            Style.RESET_ALL,
        )

    duplicate_merge_conflicts: list[str] = []
    duplicate_merge_changes = 0
    duplicate_merge_details: list[tuple[str, int]] = []

    if merge_duplicates:
        (
            raw_config,
            duplicate_merge_conflicts,
            duplicate_merge_changes,
            duplicate_merge_details,
        ) = merge_duplicate_workspace_roots(raw_config, duplicate_root_occurrences)
        for message in duplicate_merge_conflicts:
            log.warning(message)
        if duplicate_merge_changes and duplicate_merge_details:
            for label, occurrence_count in duplicate_merge_details:
                log.info(
                    "%s•%s Merged %s%d%s duplicate entr%s for workspace root %s%s%s",
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

    explicit_relative_override = workspace_root_override in {".", "./"}
    preserve_cwd_label = explicit_relative_override or allow_relative_workspace

    if merge_duplicates:
        (
            raw_config,
            workspace_map,
            merge_conflicts,
            merge_changes,
        ) = normalize_workspace_roots(
            raw_config,
            cwd=cwd,
            home=home,
            preserve_cwd_label=preserve_cwd_label,
        )
    else:
        (
            _,
            workspace_map,
            merge_conflicts,
            merge_changes,
        ) = normalize_workspace_roots(
            raw_config,
            cwd=cwd,
            home=home,
            preserve_cwd_label=preserve_cwd_label,
        )

    for message in merge_conflicts:
        log.warning(message)

    found_repos: list[tuple[str, str, pathlib.Path]] = []

    override_workspace_path: pathlib.Path | None = None
    if workspace_root_override:
        override_workspace_path = _resolve_workspace_path(
            workspace_root_override,
            None,
            cwd=cwd,
        )

    if recursive:
        for root, dirs, _ in os.walk(scan_dir):
            if ".git" in dirs:
                repo_path = pathlib.Path(root)
                repo_name = repo_path.name
                repo_url = get_git_origin_url(repo_path)

                if not repo_url:
                    log.warning(
                        "Could not determine remote URL for git repository "
                        "at %s. Skipping.",
                        PrivatePath(repo_path),
                    )
                    continue

                workspace_path = override_workspace_path or scan_dir
                found_repos.append((repo_name, repo_url, workspace_path))
    else:
        for item in scan_dir.iterdir():
            if item.is_dir() and (item / ".git").is_dir():
                repo_name = item.name
                repo_url = get_git_origin_url(item)

                if not repo_url:
                    log.warning(
                        "Could not determine remote URL for git repository "
                        "at %s. Skipping.",
                        PrivatePath(item),
                    )
                    continue

                workspace_path = override_workspace_path or scan_dir
                found_repos.append((repo_name, repo_url, workspace_path))

    if not found_repos:
        log.info(
            "%s!%s No git repositories found in %s%s%s. Nothing to import.",
            Fore.YELLOW,
            Style.RESET_ALL,
            Fore.BLUE,
            PrivatePath(scan_dir),
            Style.RESET_ALL,
        )
        return

    repos_to_add: list[tuple[str, str, pathlib.Path]] = []
    existing_repos: list[tuple[str, str, pathlib.Path]] = []

    for name, url, workspace_path in found_repos:
        workspace_label = workspace_map.get(workspace_path)
        if workspace_label is None:
            workspace_label = workspace_root_label(
                workspace_path,
                cwd=cwd,
                home=home,
                preserve_cwd_label=preserve_cwd_label,
            )
            workspace_map[workspace_path] = workspace_label
            raw_config.setdefault(workspace_label, {})

        target_section = raw_config.get(workspace_label, {})
        if isinstance(target_section, dict) and name in target_section:
            existing_repos.append((name, url, workspace_path))
        else:
            repos_to_add.append((name, url, workspace_path))

    if existing_repos:
        # Show summary only when there are many existing repos
        if len(existing_repos) > 5:
            log.info(
                "%s!%s Found %s%d%s existing repositories already in configuration.",
                Fore.YELLOW,
                Style.RESET_ALL,
                Fore.CYAN,
                len(existing_repos),
                Style.RESET_ALL,
            )
        else:
            # Show details only for small numbers
            log.info(
                "%s!%s Found %s%d%s existing repositories in configuration:",
                Fore.YELLOW,
                Style.RESET_ALL,
                Fore.CYAN,
                len(existing_repos),
                Style.RESET_ALL,
            )
            for name, url, workspace_path in existing_repos:
                workspace_label = workspace_map.get(workspace_path)
                if workspace_label is None:
                    workspace_label = workspace_root_label(
                        workspace_path,
                        cwd=cwd,
                        home=home,
                        preserve_cwd_label=preserve_cwd_label,
                    )
                    workspace_map[workspace_path] = workspace_label
                    raw_config.setdefault(workspace_label, {})
                log.info(
                    "  %s•%s %s%s%s (%s%s%s) at %s%s%s%s in %s%s%s",
                    Fore.BLUE,
                    Style.RESET_ALL,
                    Fore.CYAN,
                    name,
                    Style.RESET_ALL,
                    Fore.YELLOW,
                    url,
                    Style.RESET_ALL,
                    Fore.MAGENTA,
                    workspace_label,
                    name,
                    Style.RESET_ALL,
                    Fore.BLUE,
                    display_config_path,
                    Style.RESET_ALL,
                )

    changes_made = merge_duplicates and (
        merge_changes > 0 or duplicate_merge_changes > 0
    )

    if not repos_to_add:
        if existing_repos:
            log.info(
                "%s✓%s All found repositories already exist in the configuration. "
                "%sNothing to do.%s",
                Fore.GREEN,
                Style.RESET_ALL,
                Fore.GREEN,
                Style.RESET_ALL,
            )
        if changes_made and not dry_run:
            try:
                save_config_yaml(config_file_path, raw_config)
                log.info(
                    "%s✓%s Successfully updated %s%s%s.",
                    Fore.GREEN,
                    Style.RESET_ALL,
                    Fore.BLUE,
                    display_config_path,
                    Style.RESET_ALL,
                )
            except Exception:
                log.exception(
                    "Error saving config to %s",
                    PrivatePath(config_file_path),
                )
                if log.isEnabledFor(logging.DEBUG):
                    traceback.print_exc()
            return
        return

    # Show what will be added
    log.info(
        "\n%sFound %d new %s to %s:%s",
        Fore.GREEN,
        len(repos_to_add),
        "repository" if len(repos_to_add) == 1 else "repositories",
        "preview" if dry_run else "import",
        Style.RESET_ALL,
    )
    for repo_name, repo_url, _determined_base_key in repos_to_add:
        log.info(
            "  %s+%s %s%s%s (%s%s%s)",
            Fore.GREEN,
            Style.RESET_ALL,
            Fore.CYAN,
            repo_name,
            Style.RESET_ALL,
            Fore.YELLOW,
            repo_url,
            Style.RESET_ALL,
        )

    if dry_run:
        log.info(
            "\n%s→%s Dry run complete. No changes made to %s%s%s.",
            Fore.YELLOW,
            Style.RESET_ALL,
            Fore.BLUE,
            display_config_path,
            Style.RESET_ALL,
        )
        return

    if not yes:
        confirm = input(
            f"\n{Fore.CYAN}Import these repositories? [y/N]: {Style.RESET_ALL}",
        ).lower()
        if confirm not in {"y", "yes"}:
            log.info("%s✗%s Aborted by user.", Fore.RED, Style.RESET_ALL)
            return

    for repo_name, repo_url, workspace_path in repos_to_add:
        workspace_label = workspace_map.get(workspace_path)
        if workspace_label is None:
            workspace_label = workspace_root_label(
                workspace_path,
                cwd=cwd,
                home=home,
                preserve_cwd_label=preserve_cwd_label,
            )
            workspace_map[workspace_path] = workspace_label

        if workspace_label not in raw_config:
            raw_config[workspace_label] = {}
        elif not isinstance(raw_config[workspace_label], dict):
            log.warning(
                "Workspace root '%s' in config is not a dictionary. Skipping repo %s.",
                workspace_label,
                repo_name,
            )
            continue

        if repo_name not in raw_config[workspace_label]:
            raw_config[workspace_label][repo_name] = {"repo": repo_url}
            log.info(
                "%s+%s Importing %s'%s'%s (%s%s%s) under '%s%s%s'.",
                Fore.GREEN,
                Style.RESET_ALL,
                Fore.CYAN,
                repo_name,
                Style.RESET_ALL,
                Fore.YELLOW,
                repo_url,
                Style.RESET_ALL,
                Fore.MAGENTA,
                workspace_label,
                Style.RESET_ALL,
            )
            changes_made = True

    if changes_made:
        try:
            save_config_yaml(config_file_path, raw_config)
            log.info(
                "%s✓%s Successfully updated %s%s%s.",
                Fore.GREEN,
                Style.RESET_ALL,
                Fore.BLUE,
                display_config_path,
                Style.RESET_ALL,
            )
        except Exception:
            log.exception(
                "Error saving config to %s",
                PrivatePath(config_file_path),
            )
            if log.isEnabledFor(logging.DEBUG):
                traceback.print_exc()
            return
    else:
        log.info(
            "%s✓%s No changes made to the configuration.",
            Fore.GREEN,
            Style.RESET_ALL,
        )
