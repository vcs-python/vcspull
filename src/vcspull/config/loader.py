"""Configuration loading and handling for VCSPull."""

from __future__ import annotations

import json
from pathlib import Path

import yaml
from pydantic import TypeAdapter

from .models import VCSPullConfig

# Define type adapters for optimized validation
CONFIG_ADAPTER = TypeAdapter(VCSPullConfig)


def normalize_path(path: str | Path) -> Path:
    """Normalize a path by expanding user directory and resolving it.

    Parameters
    ----------
    path : str | Path
        The path to normalize

    Returns
    -------
    Path
        The normalized path
    """
    return Path(path).expanduser().resolve()


def load_config(config_path: str | Path) -> VCSPullConfig:
    """Load and validate configuration from a file.

    Parameters
    ----------
    config_path : str | Path
        Path to the configuration file

    Returns
    -------
    VCSPullConfig
        Validated configuration model

    Raises
    ------
    FileNotFoundError
        If the configuration file doesn't exist
    ValueError
        If the configuration is invalid or the file format is unsupported
    """
    config_path = normalize_path(config_path)

    if not config_path.exists():
        error_msg = f"Configuration file not found: {config_path}"
        raise FileNotFoundError(error_msg)

    # Load raw configuration
    with config_path.open(encoding="utf-8") as f:
        if config_path.suffix.lower() in {".yaml", ".yml"}:
            raw_config = yaml.safe_load(f)
        elif config_path.suffix.lower() == ".json":
            raw_config = json.load(f)
        else:
            error_msg = f"Unsupported file format: {config_path.suffix}"
            raise ValueError(error_msg)

    # Handle empty files
    if raw_config is None:
        raw_config = {}

    # Validate with type adapter
    return CONFIG_ADAPTER.validate_python(raw_config)


def find_config_files(search_paths: list[str | Path]) -> list[Path]:
    """Find configuration files in the specified search paths.

    Parameters
    ----------
    search_paths : list[str | Path]
        List of paths to search for configuration files

    Returns
    -------
    list[Path]
        List of found configuration files
    """
    config_files = []
    for path in search_paths:
        path = normalize_path(path)

        if path.is_file() and path.suffix.lower() in {".yaml", ".yml", ".json"}:
            config_files.append(path)
        elif path.is_dir():
            for suffix in (".yaml", ".yml", ".json"):
                files = list(path.glob(f"*{suffix}"))
                config_files.extend(files)

    return config_files


def resolve_includes(
    config: VCSPullConfig,
    base_path: str | Path,
) -> VCSPullConfig:
    """Resolve included configuration files.

    Parameters
    ----------
    config : VCSPullConfig
        The base configuration
    base_path : str | Path
        The base path for resolving relative include paths

    Returns
    -------
    VCSPullConfig
        Configuration with includes resolved and merged
    """
    base_path = normalize_path(base_path)

    if not config.includes:
        return config

    merged_config = config.model_copy(deep=True)

    # Process include files
    for include_path_str in config.includes:
        include_path = Path(include_path_str)

        # If path is relative, make it relative to base_path
        if not include_path.is_absolute():
            include_path = base_path / include_path

        include_path = include_path.expanduser().resolve()

        if not include_path.exists():
            continue

        # Load included config
        included_config = load_config(include_path)

        # Recursively resolve nested includes
        included_config = resolve_includes(included_config, include_path.parent)

        # Merge configs
        merged_config.repositories.extend(included_config.repositories)

        # Merge settings (only override non-default values)
        for field_name, field_value in included_config.settings.model_dump().items():
            if field_name not in merged_config.settings.model_fields_set:
                setattr(merged_config.settings, field_name, field_value)

    # Clear includes to prevent circular references
    merged_config.includes = []

    return merged_config
