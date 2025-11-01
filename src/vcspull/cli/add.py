"""Add single repository functionality for vcspull."""

from __future__ import annotations

import logging
import pathlib
import traceback
import typing as t

from colorama import Fore, Style

from vcspull._internal.config_reader import ConfigReader
from vcspull.config import (
    canonicalize_workspace_path,
    expand_dir,
    find_home_config_files,
    normalize_workspace_roots,
    save_config_yaml,
    workspace_root_label,
)

if t.TYPE_CHECKING:
    import argparse

log = logging.getLogger(__name__)


def create_add_subparser(parser: argparse.ArgumentParser) -> None:
    """Create ``vcspull add`` argument subparser.

    Parameters
    ----------
    parser : argparse.ArgumentParser
        The parser to configure
    """
    parser.add_argument(
        "name",
        help="Name for the repository in the config",
    )
    parser.add_argument(
        "url",
        help="Repository URL (e.g., https://github.com/user/repo.git)",
    )
    parser.add_argument(
        "-f",
        "--file",
        dest="config",
        metavar="FILE",
        help="path to config file (default: ~/.vcspull.yaml or ./.vcspull.yaml)",
    )
    parser.add_argument(
        "--path",
        dest="path",
        help="Local directory path where repo will be cloned "
        "(determines workspace root if not specified with --workspace)",
    )
    parser.add_argument(
        "-w",
        "--workspace",
        "--workspace-root",
        dest="workspace_root_path",
        metavar="DIR",
        help=(
            "Workspace root directory in config (e.g., '~/projects/'). "
            "If not specified, will be inferred from --path or use current directory."
        ),
    )
    parser.add_argument(
        "--dry-run",
        "-n",
        action="store_true",
        help="Preview changes without writing to config file",
    )


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


def add_repo(
    name: str,
    url: str,
    config_file_path_str: str | None,
    path: str | None,
    workspace_root_path: str | None,
    dry_run: bool,
) -> None:
    """Add a repository to the vcspull configuration.

    Parameters
    ----------
    name : str
        Repository name for the config
    url : str
        Repository URL
    config_file_path_str : str | None
        Path to config file, or None to use default
    path : str | None
        Local path where repo will be cloned
    workspace_root_path : str | None
        Workspace root to use in config
    dry_run : bool
        If True, preview changes without writing
    """
    # Determine config file
    config_file_path: pathlib.Path
    if config_file_path_str:
        config_file_path = pathlib.Path(config_file_path_str).expanduser().resolve()
    else:
        home_configs = find_home_config_files(filetype=["yaml"])
        if not home_configs:
            config_file_path = pathlib.Path.cwd() / ".vcspull.yaml"
            log.info(
                "No config specified and no default found, will create at %s",
                config_file_path,
            )
        elif len(home_configs) > 1:
            log.error(
                "Multiple home config files found, please specify one with -f/--file",
            )
            return
        else:
            config_file_path = home_configs[0]

    # Load existing config
    raw_config: dict[str, t.Any] = {}
    if config_file_path.exists() and config_file_path.is_file():
        try:
            loaded_config = ConfigReader._from_file(config_file_path)
        except Exception:
            log.exception("Error loading YAML from %s. Aborting.", config_file_path)
            if log.isEnabledFor(logging.DEBUG):
                traceback.print_exc()
            return

        if loaded_config is None:
            raw_config = {}
        elif isinstance(loaded_config, dict):
            raw_config = loaded_config
        else:
            log.error(
                "Config file %s is not a valid YAML dictionary.",
                config_file_path,
            )
            return
    else:
        log.info(
            "Config file %s not found. A new one will be created.",
            config_file_path,
        )

    cwd = pathlib.Path.cwd()
    home = pathlib.Path.home()

    normalization_result = normalize_workspace_roots(
        raw_config,
        cwd=cwd,
        home=home,
    )
    raw_config, workspace_map, merge_conflicts, merge_changes = normalization_result
    config_was_normalized = merge_changes > 0

    for message in merge_conflicts:
        log.warning(message)

    workspace_path = _resolve_workspace_path(
        workspace_root_path,
        path,
        cwd=cwd,
    )
    workspace_label = workspace_map.get(workspace_path)
    if workspace_label is None:
        workspace_label = workspace_root_label(
            workspace_path,
            cwd=cwd,
            home=home,
        )
        workspace_map[workspace_path] = workspace_label
        raw_config.setdefault(workspace_label, {})

    if workspace_label not in raw_config:
        raw_config[workspace_label] = {}
    elif not isinstance(raw_config[workspace_label], dict):
        log.error(
            "Workspace root '%s' in configuration is not a dictionary. Aborting.",
            workspace_label,
        )
        return

    # Check if repo already exists
    if name in raw_config[workspace_label]:
        existing_config = raw_config[workspace_label][name]
        # Handle both string and dict formats
        current_url: str
        if isinstance(existing_config, str):
            current_url = existing_config
        elif isinstance(existing_config, dict):
            repo_value = existing_config.get("repo")
            url_value = existing_config.get("url")
            current_url = repo_value or url_value or "unknown"
        else:
            current_url = str(existing_config)

        log.warning(
            "Repository '%s' already exists under '%s'. Current URL: %s. "
            "To update, remove and re-add, or edit the YAML file manually.",
            name,
            workspace_label,
            current_url,
        )
        if config_was_normalized:
            if dry_run:
                log.info(
                    "%s→%s Would save normalized workspace roots to %s%s%s.",
                    Fore.YELLOW,
                    Style.RESET_ALL,
                    Fore.BLUE,
                    config_file_path,
                    Style.RESET_ALL,
                )
            else:
                try:
                    save_config_yaml(config_file_path, raw_config)
                    log.info(
                        "%s✓%s Normalized workspace roots saved to %s%s%s.",
                        Fore.GREEN,
                        Style.RESET_ALL,
                        Fore.BLUE,
                        config_file_path,
                        Style.RESET_ALL,
                    )
                except Exception:
                    log.exception("Error saving config to %s", config_file_path)
                    if log.isEnabledFor(logging.DEBUG):
                        traceback.print_exc()
        return

    # Add the repository in verbose format
    raw_config[workspace_label][name] = {"repo": url}

    # Save or preview config
    if dry_run:
        log.info(
            "%s→%s Would add %s'%s'%s (%s%s%s) to %s%s%s under '%s%s%s'.",
            Fore.YELLOW,
            Style.RESET_ALL,
            Fore.CYAN,
            name,
            Style.RESET_ALL,
            Fore.YELLOW,
            url,
            Style.RESET_ALL,
            Fore.BLUE,
            config_file_path,
            Style.RESET_ALL,
            Fore.MAGENTA,
            workspace_label,
            Style.RESET_ALL,
        )
    else:
        try:
            save_config_yaml(config_file_path, raw_config)
            log.info(
                "%s✓%s Successfully added %s'%s'%s (%s%s%s) to %s%s%s under '%s%s%s'.",
                Fore.GREEN,
                Style.RESET_ALL,
                Fore.CYAN,
                name,
                Style.RESET_ALL,
                Fore.YELLOW,
                url,
                Style.RESET_ALL,
                Fore.BLUE,
                config_file_path,
                Style.RESET_ALL,
                Fore.MAGENTA,
                workspace_label,
                Style.RESET_ALL,
            )
        except Exception:
            log.exception("Error saving config to %s", config_file_path)
            if log.isEnabledFor(logging.DEBUG):
                traceback.print_exc()
            return
