"""Filesystem scanning functionality for vcspull."""

from __future__ import annotations

import logging
import os
import pathlib
import subprocess
import typing as t

import yaml
from colorama import Fore, Style

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


def create_add_from_fs_subparser(parser: argparse.ArgumentParser) -> None:
    """Create ``vcspull add-from-fs`` argument subparser."""
    parser.add_argument(
        "-c",
        "--config",
        dest="config",
        metavar="file",
        help="path to custom config file (default: .vcspull.yaml or ~/.vcspull.yaml)",
    )
    parser.add_argument(
        "scan_dir",
        nargs="?",
        default=".",
        help="Directory to scan for git repositories (default: current directory)",
    )
    parser.add_argument(
        "--recursive",
        "-r",
        action="store_true",
        help="Scan directories recursively.",
    )
    parser.add_argument(
        "--base-dir-key",
        help="Specify the top-level directory key from vcspull config "
        "(e.g., '~/study/python/') under which to add these repos. "
        "If not given, the normalized absolute path of scan_dir will be used as "
        "the key.",
    )
    parser.add_argument(
        "--yes",
        "-y",
        action="store_true",
        help="Automatically confirm additions without prompting.",
    )


def add_from_filesystem(
    scan_dir_str: str,
    config_file_path_str: str | None,
    recursive: bool,
    base_dir_key_arg: str | None,
    yes: bool,
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
    base_dir_key_arg : str | None
        Base directory key to use in config (overrides automatic detection)
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
                f"{Fore.CYAN}i{Style.RESET_ALL} No config specified and no default "
                f"home config, will use/create "
                f"{Fore.BLUE}{config_file_path}{Style.RESET_ALL}",
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
            with config_file_path.open(encoding="utf-8") as f:
                raw_config = yaml.safe_load(f) or {}
            if not isinstance(raw_config, dict):
                log.error(
                    "Config file %s is not a valid YAML dictionary. ",
                    config_file_path,
                )
                return
        except Exception:
            log.exception("Error loading YAML from %s. Aborting.", config_file_path)
            if log.isEnabledFor(logging.DEBUG):
                import traceback

                traceback.print_exc()
            return
    else:
        log.info(
            f"{Fore.CYAN}i{Style.RESET_ALL} Config file "
            f"{Fore.BLUE}{config_file_path}{Style.RESET_ALL} "
            f"not found. A new one will be created.",
        )

    found_repos: list[
        tuple[str, str, str]
    ] = []  # (repo_name, repo_url, determined_base_key)

    if recursive:
        for root, dirs, _ in os.walk(scan_dir):
            if ".git" in dirs:
                repo_path = pathlib.Path(root)
                repo_name = repo_path.name
                repo_url = get_git_origin_url(repo_path)

                if not repo_url:
                    log.warning(
                        "Could not determine remote URL for git repository at %s. Skipping.",
                        repo_path,
                    )
                    continue

                determined_base_key: str
                if base_dir_key_arg:
                    determined_base_key = (
                        base_dir_key_arg
                        if base_dir_key_arg.endswith("/")
                        else base_dir_key_arg + "/"
                    )
                else:
                    try:
                        determined_base_key = (
                            "~/" + str(scan_dir.relative_to(pathlib.Path.home())) + "/"
                        )
                    except ValueError:
                        determined_base_key = str(scan_dir.resolve()) + "/"

                if not determined_base_key.endswith("/"):
                    determined_base_key += "/"

                found_repos.append((repo_name, repo_url, determined_base_key))
    else:
        # Non-recursive: only check immediate subdirectories
        for item in scan_dir.iterdir():
            if item.is_dir() and (item / ".git").is_dir():
                repo_name = item.name
                repo_url = get_git_origin_url(item)

                if not repo_url:
                    log.warning(
                        "Could not determine remote URL for git repository at %s. Skipping.",
                        item,
                    )
                    continue

                if base_dir_key_arg:
                    determined_base_key = (
                        base_dir_key_arg
                        if base_dir_key_arg.endswith("/")
                        else base_dir_key_arg + "/"
                    )
                else:
                    try:
                        determined_base_key = (
                            "~/" + str(scan_dir.relative_to(pathlib.Path.home())) + "/"
                        )
                    except ValueError:
                        determined_base_key = str(scan_dir.resolve()) + "/"

                if not determined_base_key.endswith("/"):
                    determined_base_key += "/"

                found_repos.append((repo_name, repo_url, determined_base_key))

    if not found_repos:
        log.info(
            f"{Fore.YELLOW}!{Style.RESET_ALL} No git repositories found in "
            f"{Fore.BLUE}{scan_dir}{Style.RESET_ALL}. Nothing to add.",
        )
        return

    repos_to_add: list[tuple[str, str, str]] = []
    existing_repos: list[tuple[str, str, str]] = []  # (name, url, key)

    for name, url, key in found_repos:
        target_section = raw_config.get(key, {})
        if isinstance(target_section, dict) and name in target_section:
            existing_repos.append((name, url, key))
        else:
            repos_to_add.append((name, url, key))

    if existing_repos:
        # Show summary only when there are many existing repos
        if len(existing_repos) > 5:
            log.info(
                f"{Fore.YELLOW}!{Style.RESET_ALL} Found "
                f"{Fore.CYAN}{len(existing_repos)}{Style.RESET_ALL} "
                f"existing repositories already in configuration.",
            )
        else:
            # Show details only for small numbers
            log.info(
                f"{Fore.YELLOW}!{Style.RESET_ALL} Found "
                f"{Fore.CYAN}{len(existing_repos)}{Style.RESET_ALL} "
                f"existing repositories in configuration:",
            )
            for name, url, key in existing_repos:
                log.info(
                    f"  {Fore.BLUE}•{Style.RESET_ALL} "
                    f"{Fore.CYAN}{name}{Style.RESET_ALL} "
                    f"({Fore.YELLOW}{url}{Style.RESET_ALL}) at "
                    f"{Fore.MAGENTA}{key}{name}{Style.RESET_ALL} "
                    f"in {Fore.BLUE}{config_file_path}{Style.RESET_ALL}",
                )

    if not repos_to_add:
        if existing_repos:
            log.info(
                f"{Fore.GREEN}✓{Style.RESET_ALL} All found repositories already exist "
                f"in the configuration. {Fore.GREEN}Nothing to do.{Style.RESET_ALL}",
            )
        return

    # Show what will be added
    log.info(
        f"\n{Fore.GREEN}Found {len(repos_to_add)} new "
        f"{'repository' if len(repos_to_add) == 1 else 'repositories'} "
        f"to add:{Style.RESET_ALL}",
    )
    for repo_name, repo_url, _determined_base_key in repos_to_add:
        log.info(
            f"  {Fore.GREEN}+{Style.RESET_ALL} {Fore.CYAN}{repo_name}{Style.RESET_ALL} "
            f"({Fore.YELLOW}{repo_url}{Style.RESET_ALL})",
        )

    if not yes:
        confirm = input(
            f"\n{Fore.CYAN}Add these repositories? [y/N]: {Style.RESET_ALL}",
        ).lower()
        if confirm not in {"y", "yes"}:
            log.info(f"{Fore.RED}✗{Style.RESET_ALL} Aborted by user.")
            return

    changes_made = False
    for repo_name, repo_url, determined_base_key in repos_to_add:
        if determined_base_key not in raw_config:
            raw_config[determined_base_key] = {}
        elif not isinstance(raw_config[determined_base_key], dict):
            log.warning(
                "Section '%s' in config is not a dictionary. Skipping repo %s.",
                determined_base_key,
                repo_name,
            )
            continue

        if repo_name not in raw_config[determined_base_key]:
            raw_config[determined_base_key][repo_name] = {"repo": repo_url}
            log.info(
                f"{Fore.GREEN}+{Style.RESET_ALL} Adding "
                f"{Fore.CYAN}'{repo_name}'{Style.RESET_ALL} "
                f"({Fore.YELLOW}{repo_url}{Style.RESET_ALL}) under "
                f"'{Fore.MAGENTA}{determined_base_key}{Style.RESET_ALL}'.",
            )
            changes_made = True

    if changes_made:
        try:
            save_config_yaml(config_file_path, raw_config)
            log.info(
                f"{Fore.GREEN}✓{Style.RESET_ALL} Successfully updated "
                f"{Fore.BLUE}{config_file_path}{Style.RESET_ALL}.",
            )
        except Exception:
            log.exception("Error saving config to %s", config_file_path)
            if log.isEnabledFor(logging.DEBUG):
                import traceback

                traceback.print_exc()
            return
    else:
        log.info(
            f"{Fore.GREEN}✓{Style.RESET_ALL} No changes made to the configuration.",
        )
