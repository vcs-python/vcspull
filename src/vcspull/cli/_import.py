"""Import repository functionality for vcspull."""

from __future__ import annotations

import argparse
import logging
import os
import pathlib
import subprocess
import traceback
import typing as t

from colorama import Fore, Style

from vcspull._internal.config_reader import ConfigReader
from vcspull.config import expand_dir, find_home_config_files, save_config_yaml

if t.TYPE_CHECKING:
    import argparse

log = logging.getLogger(__name__)


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


def create_import_subparser(parser: argparse.ArgumentParser) -> None:
    """Create ``vcspull import`` argument subparser."""
    parser.add_argument(
        "-c",
        "--config",
        dest="config",
        metavar="file",
        help="path to custom config file (default: .vcspull.yaml or ~/.vcspull.yaml)",
    )

    # Positional arguments for single repo import
    parser.add_argument(
        "name",
        nargs="?",
        help="Name for the repository in the config",
    )
    parser.add_argument(
        "url",
        nargs="?",
        help="Repository URL (e.g., https://github.com/user/repo.git)",
    )

    # Options for single repo import
    parser.add_argument(
        "--path",
        dest="path",
        help="Local directory path where repo will be cloned "
        "(determines workspace root if not specified with --workspace-root)",
    )
    parser.add_argument(
        "--workspace-root",
        dest="workspace_root_path",
        metavar="DIR",
        help=(
            "Workspace root directory in config (e.g., '~/projects/'). "
            "If not specified, will be inferred from --path or use current directory. "
            "When used with --scan, applies the workspace root to all discovered repos."
        ),
    )

    # Filesystem scan mode
    parser.add_argument(
        "--scan",
        dest="scan_dir",
        metavar="DIR",
        help="Scan directory for git repositories and import them",
    )
    parser.add_argument(
        "--recursive",
        "-r",
        action="store_true",
        help="Scan directories recursively (use with --scan)",
    )
    parser.add_argument(
        "--yes",
        "-y",
        action="store_true",
        help="Skip confirmation prompt (use with --scan)",
    )


def import_repo(
    name: str,
    url: str,
    config_file_path_str: str | None,
    path: str | None,
    workspace_root_path: str | None,
) -> None:
    """Import a repository to the vcspull configuration.

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
                "Multiple home config files found, please specify one with -c/--config",
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

    # Determine workspace root key
    if workspace_root_path:
        workspace_root_key = (
            workspace_root_path
            if workspace_root_path.endswith("/")
            else workspace_root_path + "/"
        )
    elif path:
        # Infer from provided path
        repo_path = pathlib.Path(path).expanduser().resolve()
        try:
            # Try to make it relative to home
            workspace_root_key = (
                "~/" + str(repo_path.relative_to(pathlib.Path.home())) + "/"
            )
        except ValueError:
            # Use absolute path
            workspace_root_key = str(repo_path) + "/"
    else:
        # Default to current directory
        workspace_root_key = "./"

    # Ensure workspace root key exists in config
    if workspace_root_key not in raw_config:
        raw_config[workspace_root_key] = {}
    elif not isinstance(raw_config[workspace_root_key], dict):
        log.error(
            "Workspace root '%s' in configuration is not a dictionary. Aborting.",
            workspace_root_key,
        )
        return

    # Check if repo already exists
    if name in raw_config[workspace_root_key]:
        existing_config = raw_config[workspace_root_key][name]
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
            workspace_root_key,
            current_url,
        )
        return

    # Add the repository in verbose format
    raw_config[workspace_root_key][name] = {"repo": url}

    # Save config
    try:
        save_config_yaml(config_file_path, raw_config)
        log.info(
            "%s✓%s Successfully imported %s'%s'%s (%s%s%s) to %s%s%s under '%s%s%s'.",
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
            workspace_root_key,
            Style.RESET_ALL,
        )
    except Exception:
        log.exception("Error saving config to %s", config_file_path)
        if log.isEnabledFor(logging.DEBUG):
            traceback.print_exc()
        return


def import_from_filesystem(
    scan_dir_str: str,
    config_file_path_str: str | None,
    recursive: bool,
    workspace_root_override: str | None,
    yes: bool,
) -> None:
    """Scan filesystem for git repositories and import to vcspull config.

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
                config_file_path,
                Style.RESET_ALL,
            )
        elif len(home_configs) > 1:
            log.error(
                "Multiple home_config files found, please specify one with -c/--config",
            )
            return
        else:
            config_file_path = home_configs[0]

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
            "%si%s Config file %s%s%s not found. A new one will be created.",
            Fore.CYAN,
            Style.RESET_ALL,
            Fore.BLUE,
            config_file_path,
            Style.RESET_ALL,
        )

    # Each entry stores (repo_name, repo_url, workspace_root_key)
    found_repos: list[tuple[str, str, str]] = []

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
                        repo_path,
                    )
                    continue

                workspace_root_key: str
                if workspace_root_override:
                    workspace_root_key = (
                        workspace_root_override
                        if workspace_root_override.endswith("/")
                        else workspace_root_override + "/"
                    )
                else:
                    try:
                        workspace_root_key = (
                            "~/" + str(scan_dir.relative_to(pathlib.Path.home())) + "/"
                        )
                    except ValueError:
                        workspace_root_key = str(scan_dir.resolve()) + "/"

                if not workspace_root_key.endswith("/"):
                    workspace_root_key += "/"

                found_repos.append((repo_name, repo_url, workspace_root_key))
    else:
        # Non-recursive: only check immediate subdirectories
        for item in scan_dir.iterdir():
            if item.is_dir() and (item / ".git").is_dir():
                repo_name = item.name
                repo_url = get_git_origin_url(item)

                if not repo_url:
                    log.warning(
                        "Could not determine remote URL for git repository "
                        "at %s. Skipping.",
                        item,
                    )
                    continue

                if workspace_root_override:
                    workspace_root_key = (
                        workspace_root_override
                        if workspace_root_override.endswith("/")
                        else workspace_root_override + "/"
                    )
                else:
                    try:
                        workspace_root_key = (
                            "~/" + str(scan_dir.relative_to(pathlib.Path.home())) + "/"
                        )
                    except ValueError:
                        workspace_root_key = str(scan_dir.resolve()) + "/"

                if not workspace_root_key.endswith("/"):
                    workspace_root_key += "/"

                found_repos.append((repo_name, repo_url, workspace_root_key))

    if not found_repos:
        log.info(
            "%s!%s No git repositories found in %s%s%s. Nothing to import.",
            Fore.YELLOW,
            Style.RESET_ALL,
            Fore.BLUE,
            scan_dir,
            Style.RESET_ALL,
        )
        return

    repos_to_add: list[tuple[str, str, str]] = []
    existing_repos: list[tuple[str, str, str]] = []  # (name, url, workspace_root_key)

    for name, url, workspace_root_key in found_repos:
        target_section = raw_config.get(workspace_root_key, {})
        if isinstance(target_section, dict) and name in target_section:
            existing_repos.append((name, url, workspace_root_key))
        else:
            repos_to_add.append((name, url, workspace_root_key))

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
            for name, url, workspace_root_key in existing_repos:
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
                    workspace_root_key,
                    name,
                    Style.RESET_ALL,
                    Fore.BLUE,
                    config_file_path,
                    Style.RESET_ALL,
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
        return

    # Show what will be added
    log.info(
        "\n%sFound %d new %s to import:%s",
        Fore.GREEN,
        len(repos_to_add),
        "repository" if len(repos_to_add) == 1 else "repositories",
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

    if not yes:
        confirm = input(
            f"\n{Fore.CYAN}Import these repositories? [y/N]: {Style.RESET_ALL}",
        ).lower()
        if confirm not in {"y", "yes"}:
            log.info("%s✗%s Aborted by user.", Fore.RED, Style.RESET_ALL)
            return

    changes_made = False
    for repo_name, repo_url, workspace_root_key in repos_to_add:
        if workspace_root_key not in raw_config:
            raw_config[workspace_root_key] = {}
        elif not isinstance(raw_config[workspace_root_key], dict):
            log.warning(
                "Workspace root '%s' in config is not a dictionary. Skipping repo %s.",
                workspace_root_key,
                repo_name,
            )
            continue

        if repo_name not in raw_config[workspace_root_key]:
            raw_config[workspace_root_key][repo_name] = {"repo": repo_url}
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
                workspace_root_key,
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
                config_file_path,
                Style.RESET_ALL,
            )
        except Exception:
            log.exception("Error saving config to %s", config_file_path)
            if log.isEnabledFor(logging.DEBUG):
                traceback.print_exc()
            return
    else:
        log.info(
            "%s✓%s No changes made to the configuration.",
            Fore.GREEN,
            Style.RESET_ALL,
        )
