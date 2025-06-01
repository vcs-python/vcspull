"""Configuration migration tools for VCSPull.

This module provides functions to detect and migrate old VCSPull configuration
formats to the new Pydantic v2-based format.
"""

from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path
from typing import Any, Optional

import yaml

from ..config.models import Repository, Settings, VCSPullConfig
from .loader import load_config, normalize_path, save_config

logger = logging.getLogger(__name__)


def detect_config_version(config_path: str | Path) -> str:
    """Detect the version of a configuration file.

    Parameters
    ----------
    config_path : str | Path
        Path to the configuration file

    Returns
    -------
    str
        Version identifier: 'v1' for old format, 'v2' for new Pydantic format

    Raises
    ------
    FileNotFoundError
        If the configuration file doesn't exist
    ValueError
        If the configuration format cannot be determined
    """
    config_path = normalize_path(config_path)

    if not config_path.exists():
        error_msg = f"Configuration file not found: {config_path}"
        raise FileNotFoundError(error_msg)

    # Try to load as new format first
    try:
        with config_path.open(encoding="utf-8") as f:
            if config_path.suffix.lower() in {".yaml", ".yml"}:
                config_data = yaml.safe_load(f)
            elif config_path.suffix.lower() == ".json":
                config_data = json.load(f)
            else:
                error_msg = f"Unsupported file format: {config_path.suffix}"
                raise ValueError(error_msg)

            if config_data is None:
                # Empty file, consider it new format
                return "v2"

            # Check for new format indicators
            if isinstance(config_data, dict) and (
                "repositories" in config_data
                or "settings" in config_data
                or "includes" in config_data
            ):
                return "v2"

            # Check for old format indicators (nested dictionaries with path keys)
            if isinstance(config_data, dict) and all(
                isinstance(k, str) and isinstance(v, dict)
                for k, v in config_data.items()
            ):
                return "v1"

            # If no clear indicators, but it's a dictionary, assume v1
            if isinstance(config_data, dict):
                return "v1"

            error_msg = "Unable to determine configuration version"
            raise ValueError(error_msg)

    except Exception as e:
        logger.exception("Error detecting configuration version")
        error_msg = f"Unable to determine configuration version: {e}"
        raise ValueError(error_msg) from e


def migrate_v1_to_v2(
    config_path: str | Path,
    output_path: str | Path | None = None,
    default_settings: dict[str, Any] | None = None,
) -> VCSPullConfig:
    """Migrate a v1 configuration file to v2 format.

    Parameters
    ----------
    config_path : str | Path
        Path to the v1 configuration file
    output_path : str | Path | None, optional
        Path to save the migrated configuration, by default None
        (saves to the same path if not specified)
    default_settings : dict[str, Any] | None, optional
        Default settings to use in the migrated configuration, by default None

    Returns
    -------
    VCSPullConfig
        The migrated configuration model

    Raises
    ------
    FileNotFoundError
        If the configuration file doesn't exist
    ValueError
        If the configuration can't be loaded or migrated
    """
    config_path = normalize_path(config_path)

    if not config_path.exists():
        error_msg = f"Configuration file not found: {config_path}"
        raise FileNotFoundError(error_msg)

    # Load the old format configuration
    try:
        with config_path.open(encoding="utf-8") as f:
            if config_path.suffix.lower() in {".yaml", ".yml"}:
                old_config = yaml.safe_load(f)
            elif config_path.suffix.lower() == ".json":
                old_config = json.load(f)
            else:
                error_msg = f"Unsupported file format: {config_path.suffix}"
                raise ValueError(error_msg)

        if old_config is None:
            old_config = {}

        if not isinstance(old_config, dict):
            type_msg = type(old_config)
            error_msg = (
                f"Invalid configuration format: expected dictionary, got {type_msg}"
            )
            raise TypeError(error_msg)

    except Exception as e:
        logger.exception("Error loading configuration")
        error_msg = f"Unable to load configuration: {e}"
        raise ValueError(error_msg) from e

    # Create settings
    settings = Settings(**(default_settings or {}))

    # Convert repositories
    repositories: list[Repository] = []

    for path_or_group, repos_or_subgroups in old_config.items():
        # Skip non-dict items or empty dicts
        if not isinstance(repos_or_subgroups, dict) or not repos_or_subgroups:
            continue

        for repo_name, repo_config in repos_or_subgroups.items():
            repo_data: dict[str, Any] = {"name": repo_name}

            # Handle path - use parent path from key plus repo name
            repo_path = Path(path_or_group) / repo_name
            repo_data["path"] = str(repo_path)

            # Handle string shorthand format: "vcs+url"
            if isinstance(repo_config, str):
                parts = repo_config.split("+", 1)
                if len(parts) == 2:
                    repo_data["vcs"] = parts[0]
                    repo_data["url"] = parts[1]
                else:
                    # Assume it's just a URL with implicit git
                    repo_data["url"] = repo_config
                    repo_data["vcs"] = "git"
            # Handle dictionary format
            elif isinstance(repo_config, dict):
                # Copy URL
                if "url" in repo_config:
                    url = repo_config["url"]
                    # Handle "vcs+url" format within dictionary
                    if isinstance(url, str) and "+" in url:
                        parts = url.split("+", 1)
                        if len(parts) == 2:
                            repo_data["vcs"] = parts[0]
                            repo_data["url"] = parts[1]
                        else:
                            repo_data["url"] = url
                    else:
                        repo_data["url"] = url

                # Copy other fields
                if "remotes" in repo_config and isinstance(
                    repo_config["remotes"], dict
                ):
                    # Convert old remotes format to new
                    new_remotes = {}
                    for remote_name, remote_url in repo_config["remotes"].items():
                        # Handle "vcs+url" format for remotes
                        if isinstance(remote_url, str) and "+" in remote_url:
                            parts = remote_url.split("+", 1)
                            if len(parts) == 2:
                                new_remotes[remote_name] = parts[1]
                            else:
                                new_remotes[remote_name] = remote_url
                        else:
                            new_remotes[remote_name] = remote_url
                    repo_data["remotes"] = new_remotes

                # Copy other fields directly
                for field in ["rev", "web_url"]:
                    if field in repo_config:
                        repo_data[field] = repo_config[field]

                # Infer VCS from URL if not already set
                if "vcs" not in repo_data and "url" in repo_data:
                    url = repo_data["url"]
                    if "github.com" in url or url.endswith(".git"):
                        repo_data["vcs"] = "git"
                    elif "bitbucket.org" in url and not url.endswith(".git"):
                        repo_data["vcs"] = "hg"
                    else:
                        # Default to git
                        repo_data["vcs"] = "git"

            # Try to create Repository model (will validate)
            try:
                repository = Repository(**repo_data)
                repositories.append(repository)
            except Exception as e:
                logger.warning(f"Skipping invalid repository '{repo_name}': {e}")

    # Create the new configuration
    new_config = VCSPullConfig(settings=settings, repositories=repositories)

    # Save the configuration if output path provided
    if output_path is not None:
        save_path = normalize_path(output_path)
        save_config(new_config, save_path)

    return new_config


def migrate_config_file(
    config_path: str | Path,
    output_path: str | Path | None = None,
    create_backup: bool = True,
    force: bool = False,
) -> tuple[bool, str]:
    """Migrate a configuration file to the latest format.

    Parameters
    ----------
    config_path : str | Path
        Path to the configuration file to migrate
    output_path : str | Path | None, optional
        Path to save the migrated configuration, by default None
        (saves to the same path if not specified)
    create_backup : bool, optional
        Whether to create a backup of the original file, by default True
    force : bool, optional
        Force migration even if the file is already in the latest format,
        by default False

    Returns
    -------
    tuple[bool, str]
        A tuple of (success, message) indicating whether the migration was
        successful and a descriptive message

    Raises
    ------
    FileNotFoundError
        If the configuration file doesn't exist
    """
    config_path = normalize_path(config_path)

    if not config_path.exists():
        error_msg = f"Configuration file not found: {config_path}"
        raise FileNotFoundError(error_msg)

    # Determine output path
    if output_path is None:
        output_path = config_path

    output_path = normalize_path(output_path)

    # Create directory if it doesn't exist
    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        # Detect version
        version = detect_config_version(config_path)

        if version == "v2" and not force:
            return True, f"Configuration already in latest format: {config_path}"

        # Create backup if needed
        if create_backup and config_path.exists():
            backup_path = config_path.with_suffix(f"{config_path.suffix}.bak")
            shutil.copy2(config_path, backup_path)
            logger.info(f"Created backup at {backup_path}")

        # Migrate based on version
        if version == "v1":
            migrate_v1_to_v2(config_path, output_path)
            return True, f"Successfully migrated {config_path} from v1 to v2 format"
        else:
            # Load and save to ensure format compliance
            config = load_config(config_path)
            save_config(config, output_path)
            return True, f"Configuration verified and saved at {output_path}"

    except Exception as e:
        logger.exception("Error migrating configuration")
        return False, f"Failed to migrate {config_path}: {e}"


def migrate_all_configs(
    search_paths: list[str | Path],
    create_backups: bool = True,
    force: bool = False,
) -> list[tuple[Path, bool, str]]:
    """Migrate all configuration files in the specified paths.

    Parameters
    ----------
    search_paths : list[str | Path]
        List of paths to search for configuration files
    create_backups : bool, optional
        Whether to create backups of original files, by default True
    force : bool, optional
        Force migration even if files are already in the latest format,
        by default False

    Returns
    -------
    list[tuple[Path, bool, str]]
        List of tuples containing (file_path, success, message) for each file
    """
    from .loader import find_config_files

    # Find all configuration files, with proper recursive search
    normalized_paths = [normalize_path(p) for p in search_paths]
    config_files = []

    # Custom implementation to find all config files recursively
    for path in normalized_paths:
        if path.is_file() and path.suffix.lower() in {".yaml", ".yml", ".json"}:
            config_files.append(path)
        elif path.is_dir():
            # Find all .yaml, .yml, and .json files recursively
            config_files.extend(path.glob("**/*.yaml"))
            config_files.extend(path.glob("**/*.yml"))
            config_files.extend(path.glob("**/*.json"))

    # Make sure paths are unique
    config_files = list(set(config_files))

    # Process all files
    results = []
    for config_path in config_files:
        try:
            success, message = migrate_config_file(
                config_path,
                create_backup=create_backups,
                force=force,
            )
            results.append((config_path, success, message))
        except Exception as e:
            logger.exception(f"Error processing {config_path}")
            results.append((config_path, False, f"Error: {e}"))

    return results
