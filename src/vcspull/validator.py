"""Validation of vcspull configuration files and schemas."""

from __future__ import annotations

import json
import typing as t

from typing_extensions import TypeGuard

from pydantic import ValidationError

from . import exc
from .schemas import (
    PATH_EMPTY_ERROR,
    config_validator,
    is_valid_config_dict,
    repo_validator,
)

if t.TYPE_CHECKING:
    from .types import (
        PathLike,
        RawConfig,
        ValidationResult,
    )


def is_valid_config(config: dict[str, t.Any]) -> TypeGuard[RawConfig]:
    """Return true and upcast if vcspull configuration file is valid.

    Parameters
    ----------
    config : Dict[str, Any]
        Configuration dictionary to validate

    Returns
    -------
    TypeGuard[RawConfig]
        True if config is a valid RawConfig
    """
    # Handle null case
    if config is None:
        return False

    # Basic type check
    if not isinstance(config, dict):
        return False

    # Check that all keys are strings
    if not all(isinstance(k, str) for k in config):
        return False

    # Check that all values are dictionaries
    if not all(isinstance(v, dict) for v in config.values()):
        return False

    # Check repositories in each section
    for _section, repos in config.values():
        for _repo_name, repo in repos.values():
            # String URLs are valid repository configs
            if isinstance(repo, str):
                continue

            # Repository must be a dict
            if not isinstance(repo, dict):
                return False

            # Must have required fields
            if not all(field in repo for field in ["vcs", "url", "path"]):
                return False

    # If basic structure is valid, delegate to the type-based validator
    try:
        # Fast validation using the cached type adapter
        return is_valid_config_dict(config)
    except Exception:
        return False


def validate_repo_config(repo_config: dict[str, t.Any]) -> ValidationResult:
    """Validate a repository configuration using Pydantic.

    Parameters
    ----------
    repo_config : Dict[str, Any]
        Repository configuration to validate

    Returns
    -------
    ValidationResult
        Tuple of (is_valid, error_message)
    """
    # Basic type check
    if repo_config is None:
        return False, "Repository configuration cannot be None"

    if not isinstance(repo_config, dict):
        type_name = type(repo_config).__name__
        error_msg = f"Repository configuration must be a dictionary, got {type_name}"
        return False, error_msg

    try:
        # Use TypeAdapter for validation - more efficient
        repo_validator.validate_python(repo_config)
        return True, None
    except ValidationError as e:
        # Format validation errors with improved formatting
        return False, format_pydantic_errors(e)
    except Exception as e:
        # Handle other exceptions
        return False, f"Validation error: {e}"


def validate_path(path: PathLike) -> ValidationResult:
    """Validate a path.

    Parameters
    ----------
    path : PathLike
        Path to validate

    Returns
    -------
    ValidationResult
        Tuple of (is_valid, error_message)
    """
    # Handle None specially for test cases
    if path is None:
        return False, "Path cannot be None"

    # Empty string check - done here for clear error message
    if isinstance(path, str) and not path.strip():
        return False, PATH_EMPTY_ERROR

    # Check for invalid path characters
    if isinstance(path, str) and "\0" in path:
        return False, "Invalid path: contains null character"

    try:
        # Create a minimal repo config to validate the path through the model
        test_repo = {
            "vcs": "git",
            "name": "test",
            "url": "https://example.com/repo.git",
            "path": path,
        }

        # Use the repository validator
        repo_validator.validate_python(test_repo)
        return True, None
    except ValidationError as e:
        # Extract path-specific errors using improved error extraction
        errors = e.errors(include_context=True, include_input=True)
        path_errors = [err for err in errors if "path" in str(err.get("loc", ""))]

        if path_errors:
            formatted_errors = ", ".join(str(err.get("msg", "")) for err in path_errors)
            return False, f"Invalid path: {formatted_errors}"
        return False, "Invalid path"
    except Exception as e:
        # Catch any other exceptions
        return False, f"Invalid path: {e}"


def validate_config_structure(config: t.Any) -> ValidationResult:
    """Validate the overall structure of a configuration using Pydantic.

    Parameters
    ----------
    config : Any
        Configuration to validate

    Returns
    -------
    ValidationResult
        Tuple of (is_valid, error_message)
    """
    # Handle None specially
    if config is None:
        return False, "Configuration cannot be None"

    # Handle non-dict config
    if not isinstance(config, dict):
        return False, f"Configuration must be a dictionary, got {type(config).__name__}"

    # Basic structure validation
    for section_name, section in config.items():
        # Validate section
        if not isinstance(section_name, str):
            return (
                False,
                f"Section name must be a string, got {type(section_name).__name__}",
            )

        if not isinstance(section, dict):
            type_name = type(section).__name__
            error_msg = (
                f"Section '{section_name}' must be a dictionary, got {type_name}"
            )
            return False, error_msg

        # Validate repositories in section
        for repo_name, repo in section.items():
            if not isinstance(repo_name, str):
                type_name = type(repo_name).__name__
                err_msg = (
                    f"Repository name in section '{section_name}' must be a string, "
                    f"got {type_name}"
                )
                return False, err_msg

            # If repo is a string, it's a URL shorthand
            if isinstance(repo, str):
                if not repo.strip():
                    return (
                        False,
                        f"Empty URL for repository '{section_name}.{repo_name}'",
                    )
                continue

            # If repo is not a dict, it's an invalid type
            if not isinstance(repo, dict):
                type_name = type(repo).__name__
                err_msg = (
                    f"Repository '{section_name}.{repo_name}' must be a dictionary "
                    f"or string URL, got {type_name}"
                )
                return False, err_msg

            # Check for required fields in repository
            if isinstance(repo, dict):
                for field in ["vcs", "url", "path"]:
                    if field not in repo:
                        err_msg = (
                            f"Missing required field '{field}' in repository "
                            f"'{section_name}.{repo_name}'"
                        )
                        return False, err_msg

    # Use Pydantic validation through TypeAdapter for complete validation
    try:
        # Convert string URLs to full repo configurations for validation
        converted_config = {}
        for section_name, section in config.items():
            converted_section = {}
            for repo_name, repo in section.items():
                # String URLs are shorthand for git repositories
                if isinstance(repo, str):
                    repo = {
                        "vcs": "git",
                        "url": repo,
                        "name": repo_name,
                        "path": repo_name,
                    }
                # Ensure name field is set
                elif isinstance(repo, dict) and "name" not in repo:
                    repo = {**repo, "name": repo_name}

                converted_section[repo_name] = repo
            converted_config[section_name] = converted_section

        # Validate with the TypeAdapter
        config_validator.validate_python(converted_config)
        return True, None
    except ValidationError as e:
        # Format the Pydantic errors with the improved formatter
        error_message = format_pydantic_errors(e)

        # Add custom suggestion based on error type if needed
        if "missing" in error_message:
            suffix = "Make sure all required fields are present in your configuration."
            message = f"{error_message}\n{suffix}"
            return False, message

        return False, error_message
    except Exception as e:
        # Catch any other exceptions
        return False, f"Validation error: {e}"


def validate_config(config: t.Any) -> None:
    """Validate a complete configuration and raise exceptions for any issues.

    Parameters
    ----------
    config : Any
        Configuration to validate

    Returns
    -------
    None

    Raises
    ------
    exc.ConfigError
        If the configuration is invalid
    """
    # Strategy: validate in stages, raising specific exceptions for each type of error

    # Stage 1: Validate basic types and structure
    is_valid, error_message = validate_config_structure(config)
    if not is_valid:
        error_msg = f"Configuration structure error: {error_message}"
        raise exc.ConfigValidationError(error_msg)

    # Stage 2: Validate each section and repository
    validation_errors = {}

    for section_name, section in config.items():
        section_errors = {}

        for repo_name, repo in section.items():
            # Skip string URLs - they're already validated in structure check
            if isinstance(repo, str):
                continue

            # Validate repository configuration
            if isinstance(repo, dict):
                # Add name if missing
                if "name" not in repo:
                    repo = {**repo, "name": repo_name}

                is_valid, error = validate_repo_config(repo)
                if not is_valid:
                    section_errors[repo_name] = error

        # Add section errors if any were found
        if section_errors:
            validation_errors[section_name] = section_errors

    # If validation_errors has entries, raise detailed exception
    if validation_errors:
        error_message = "Configuration validation failed:\n"
        for section, section_errors in validation_errors.items():
            error_message += f"  Section '{section}':\n"
            for repo, repo_error in section_errors.items():
                error_message += f"    Repository '{repo}': {repo_error}\n"

        raise exc.ConfigValidationError(error_message)

    # If we get here, configuration is valid


def format_pydantic_errors(validation_error: ValidationError) -> str:
    """Format Pydantic validation errors into a human-readable string.

    Parameters
    ----------
    validation_error : ValidationError
        Pydantic validation error

    Returns
    -------
    str
        Formatted error message
    """
    # Get errors with context
    errors = validation_error.errors(include_context=True, include_input=True)

    if not errors:
        return "Validation error"

    # Single-error case - simplified message
    if len(errors) == 1:
        error = errors[0]
        loc = ".".join(str(loc_part) for loc_part in error.get("loc", []))
        msg = error.get("msg", "Unknown error")

        if loc:
            return f"Error at {loc}: {msg}"
        return msg

    # Multi-error case - detailed message
    formatted_lines = []
    for error in errors:
        # Format location
        loc = ".".join(str(loc_part) for loc_part in error.get("loc", []))
        msg = error.get("msg", "Unknown error")

        # Add the input if available (limited to avoid overwhelming output)
        input_value = error.get("input")
        if input_value is not None:
            # Truncate long inputs
            input_str = str(input_value)
            if len(input_str) > 50:
                input_str = input_str[:47] + "..."
            error_line = f"- {loc}: {msg} (input: {input_str})"
        else:
            error_line = f"- {loc}: {msg}"

        formatted_lines.append(error_line)

    return "\n".join(formatted_lines)


def get_structured_errors(validation_error: ValidationError) -> dict[str, t.Any]:
    """Convert Pydantic validation errors to a structured dictionary.

    Parameters
    ----------
    validation_error : ValidationError
        Pydantic validation error

    Returns
    -------
    dict[str, Any]
        Structured error information
    """
    # Get raw errors with context
    raw_errors = validation_error.errors(include_context=True, include_input=True)

    # Group errors by location
    structured_errors = {}

    for error in raw_errors:
        # Get location path as string
        loc_parts = error.get("loc", [])
        current_node = structured_errors

        # Build a nested structure based on the location
        for i, loc_part in enumerate(loc_parts):
            # Convert location part to string for keys
            loc_key = str(loc_part)

            # Last element - store the error
            if i == len(loc_parts) - 1:
                if loc_key not in current_node:
                    current_node[loc_key] = []

                # Add error info
                error_info = {
                    "msg": error.get("msg", "Unknown error"),
                    "type": error.get("type", "unknown_error"),
                }

                # Include input value if available
                if "input" in error:
                    error_info["input"] = error.get("input")

                current_node[loc_key].append(error_info)
            else:
                # Navigate to or create nested level
                if loc_key not in current_node:
                    current_node[loc_key] = {}
                current_node = current_node[loc_key]

    return structured_errors


def validate_config_json(json_data: str | bytes) -> ValidationResult:
    """Validate configuration from JSON string or bytes.

    Parameters
    ----------
    json_data : str | bytes
        JSON data to validate

    Returns
    -------
    ValidationResult
        Tuple of (is_valid, error_message)
    """
    if not json_data:
        return False, "JSON data cannot be empty"

    try:
        # Parse JSON
        if isinstance(json_data, bytes):
            config_dict = json.loads(json_data.decode("utf-8"))
        else:
            config_dict = json.loads(json_data)

        # Validate the parsed dictionary
        is_valid, message = validate_config_structure(config_dict)
        return is_valid, message
    except json.JSONDecodeError as e:
        # Handle JSON parsing errors
        return False, f"Invalid JSON: {e}"
    except ValidationError as e:
        # Handle Pydantic validation errors
        return False, format_pydantic_errors(e)
    except Exception as e:
        # Handle any other exceptions
        return False, f"Validation error: {e}"
