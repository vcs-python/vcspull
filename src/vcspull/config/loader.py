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
    processed_paths: set[Path] | None = None,
) -> VCSPullConfig:
    """Resolve included configuration files.

    Parameters
    ----------
    config : VCSPullConfig
        The base configuration
    base_path : str | Path
        The base path for resolving relative include paths
    processed_paths : set[Path] | None, optional
        Set of paths that have already been processed
        (for circular reference detection), by default None

    Returns
    -------
    VCSPullConfig
        Configuration with includes resolved and merged
    """
    base_path = normalize_path(base_path)

    # Initialize processed paths to track circular references
    if processed_paths is None:
        processed_paths = set()

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

        # Skip processing if the file doesn't exist or has already been processed
        if not include_path.exists() or include_path in processed_paths:
            continue

        # Add to processed paths to prevent circular references
        processed_paths.add(include_path)

        # Load included config
        included_config = load_config(include_path)

        # Recursively resolve nested includes
        included_config = resolve_includes(
            included_config,
            include_path.parent,
            processed_paths,
        )

        # Merge configs
        merged_config.repositories.extend(included_config.repositories)

        # Merge settings (only override non-default values)
        for field_name, field_value in included_config.settings.model_dump().items():
            if field_name not in merged_config.settings.model_fields_set:
                setattr(merged_config.settings, field_name, field_value)

    # Clear includes to prevent circular references
    merged_config.includes = []

    return merged_config


def save_config(
    config: VCSPullConfig,
    config_path: str | Path,
    format_type: str | None = None,
) -> Path:
    """Save configuration to a file.

    Parameters
    ----------
    config : VCSPullConfig
        Configuration to save
    config_path : str | Path
        Path to save the configuration file
    format_type : str | None, optional
        Force a specific format type ('yaml', 'json'), by default None
        (inferred from file extension)

    Returns
    -------
    Path
        Path to the saved configuration file

    Raises
    ------
    ValueError
        If the format type is not supported
    """
    config_path = normalize_path(config_path)

    # Create parent directories if they don't exist
    config_path.parent.mkdir(parents=True, exist_ok=True)

    # Convert config to dict
    config_dict = config.model_dump()

    # Determine format type
    if format_type is None:
        if config_path.suffix.lower() in {".yaml", ".yml"}:
            format_type = "yaml"
        elif config_path.suffix.lower() == ".json":
            format_type = "json"
        else:
            format_type = "yaml"  # Default to YAML
            config_path = config_path.with_suffix(".yaml")

    # Write to file in the appropriate format
    with config_path.open("w", encoding="utf-8") as f:
        if format_type.lower() == "yaml":
            yaml.dump(config_dict, f, default_flow_style=False, sort_keys=False)
        elif format_type.lower() == "json":
            json.dump(config_dict, f, indent=2)
        else:
            error_msg = f"Unsupported format type: {format_type}"
            raise ValueError(error_msg)

    return config_path
