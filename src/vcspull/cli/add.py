"""Add repository functionality for vcspull."""

from __future__ import annotations

import logging
import pathlib
import traceback
import typing as t

from colorama import Fore, Style

from vcspull._internal.config_reader import ConfigReader
from vcspull.config import find_home_config_files, save_config_yaml

if t.TYPE_CHECKING:
    import argparse

log = logging.getLogger(__name__)


def create_add_subparser(parser: argparse.ArgumentParser) -> None:
    """Create ``vcspull add`` argument subparser."""
    parser.add_argument(
        "-c",
        "--config",
        dest="config",
        metavar="file",
        help="path to custom config file (default: .vcspull.yaml or ~/.vcspull.yaml)",
    )
    parser.add_argument(
        "name",
        help="Name for the repository in the config",
    )
    parser.add_argument(
        "url",
        help="Repository URL (e.g., https://github.com/user/repo.git)",
    )
    parser.add_argument(
        "--path",
        dest="path",
        help="Local directory path where repo will be cloned "
        "(determines base directory key if not specified with --dir)",
    )
    parser.add_argument(
        "--dir",
        dest="base_dir",
        help="Base directory key in config (e.g., '~/projects/'). "
        "If not specified, will be inferred from --path or use current directory.",
    )


def add_repo(
    name: str,
    url: str,
    config_file_path_str: str | None,
    path: str | None,
    base_dir: str | None,
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
    base_dir : str | None
        Base directory key to use in config
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

    # Determine base directory key
    if base_dir:
        # Use explicit base directory
        base_dir_key = base_dir if base_dir.endswith("/") else base_dir + "/"
    elif path:
        # Infer from provided path
        repo_path = pathlib.Path(path).expanduser().resolve()
        try:
            # Try to make it relative to home
            base_dir_key = "~/" + str(repo_path.relative_to(pathlib.Path.home())) + "/"
        except ValueError:
            # Use absolute path
            base_dir_key = str(repo_path) + "/"
    else:
        # Default to current directory
        base_dir_key = "./"

    # Ensure base directory key exists in config
    if base_dir_key not in raw_config:
        raw_config[base_dir_key] = {}
    elif not isinstance(raw_config[base_dir_key], dict):
        log.error(
            "Configuration section '%s' is not a dictionary. Aborting.",
            base_dir_key,
        )
        return

    # Check if repo already exists
    if name in raw_config[base_dir_key]:
        existing_config = raw_config[base_dir_key][name]
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
            base_dir_key,
            current_url,
        )
        return

    # Add the repository in verbose format
    raw_config[base_dir_key][name] = {"repo": url}

    # Save config
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
            base_dir_key,
            Style.RESET_ALL,
        )
    except Exception:
        log.exception("Error saving config to %s", config_file_path)
        if log.isEnabledFor(logging.DEBUG):
            traceback.print_exc()
        return
