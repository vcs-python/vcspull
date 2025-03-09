"""Validation of vcspull configuration files and schemas."""

from __future__ import annotations

import typing as t

from typing_extensions import TypeGuard

from pydantic import ValidationError

from . import exc
from .schemas import (
    RawConfigDictModel,
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
    if repo_config is None or not isinstance(repo_config, dict):
        return False, "Repository configuration must be a dictionary"

    try:
        # Use TypeAdapter for validation - more efficient
        repo_validator.validate_python(repo_config)
    except ValidationError as e:
        # Format validation errors
        return False, format_pydantic_errors(e)
    except Exception as e:
        # Handle other exceptions
        return False, f"Validation error: {e}"
    else:
        return True, None


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

    # Empty string check
    if isinstance(path, str) and not path.strip():
        return False, "Path cannot be empty"

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
    except ValidationError as e:
        # Extract path-specific errors with simpler error formatting
        errors = e.errors()
        path_errors = [err for err in errors if "path" in str(err.get("loc", ""))]
        if path_errors:
            formatted_errors = ", ".join(str(err.get("msg", "")) for err in path_errors)
            return False, f"Invalid path: {formatted_errors}"
        return False, "Invalid path"
    except Exception as e:
        # Catch any other exceptions
        return False, f"Invalid path: {e}"
    else:
        return True, None


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
        return False, "Configuration must be a dictionary"

    # Basic structure checks for better error messages
    # This provides more specific error messages than Pydantic
    for section_name in config:
        if not isinstance(section_name, str):
            return (
                False,
                f"Section name must be a string, got {type(section_name).__name__}",
            )

        section = config[section_name]
        if not isinstance(section, dict):
            return False, f"Section '{section_name}' must be a dictionary"

        for repo_name in section:
            if not isinstance(repo_name, str):
                return (
                    False,
                    f"Repository name must be a string, got {type(repo_name).__name__}",
                )

    # Now validate the entire config with Pydantic for deeper validation
    try:
        # Use type adapter for validation - more efficient
        config_validator.validate_python({"root": config})
    except ValidationError as e:
        # Format the Pydantic errors in a more user-friendly way
        error_message = format_pydantic_errors(e)

        # Add custom suggestion based on error type if needed
        if "missing" in error_message:
            message = (
                error_message
                + "\nMake sure all sections and repositories have the required fields."
            )
            return False, message

        return False, error_message
    else:
        return True, None


def validate_config(config: t.Any) -> None:
    """Validate a configuration and raise exceptions for invalid configs.

    Parameters
    ----------
    config : Any
        Configuration to validate

    Raises
    ------
    ConfigValidationError
        If the configuration is invalid
    """
    # Check for basic structure issues first
    if config is None:
        raise exc.ConfigValidationError(
            message="Invalid configuration: Configuration cannot be None",
            suggestion="Provide a valid configuration dictionary.",
        )

    # Important for test_validate_config_raises_exceptions
    if not isinstance(config, dict):
        raise exc.ConfigValidationError(
            message=(
                f"Invalid configuration structure: Configuration must be a dictionary, "
                f"got {type(config).__name__}"
            ),
            suggestion=(
                "Check that your configuration is properly formatted "
                "as a dictionary of sections containing repositories."
            ),
        )

    # Validate basic structure
    is_valid, error = validate_config_structure(config)
    if not is_valid:
        raise exc.ConfigValidationError(
            message=f"Invalid configuration structure: {error}",
            suggestion="Ensure your configuration follows the required format.",
        )

    # Use model validation for the whole configuration
    try:
        config_validator.validate_python({"root": config})
    except ValidationError as e:
        # Create a more user-friendly error message
        error_message = format_pydantic_errors(e)
        raise exc.ConfigValidationError(
            message=f"Invalid configuration: {error_message}",
            suggestion="Please correct the configuration errors and try again.",
        ) from e


def format_pydantic_errors(validation_error: ValidationError) -> str:
    """Format Pydantic validation errors into a user-friendly message.

    Parameters
    ----------
    validation_error : ValidationError
        Pydantic ValidationError

    Returns
    -------
    str
        Formatted error message
    """
    # Get structured error representation
    errors = validation_error.errors()

    # Group errors by type for better organization
    error_categories: dict[str, list[str]] = {
        "missing_required": [],
        "type_error": [],
        "value_error": [],
        "url_error": [],
        "path_error": [],
        "other": [],
    }

    for error in errors:
        # Format location as dot-notation path
        location = ".".join(str(loc) for loc in error.get("loc", []))
        message = error.get("msg", "Unknown error")
        error_type = error.get("type", "")
        input_value = error.get("input", "")

        # Create a detailed error message
        formatted_error = f"{location}: {message}"

        # Add input value if available (for more context)
        if input_value not in {"", None}:
            try:
                # Format input value concisely
                if isinstance(input_value, (dict, list)):
                    # For complex values, summarize
                    type_name = type(input_value).__name__
                    items_count = len(input_value)
                    value_repr = f"{type_name} with {items_count} items"
                else:
                    value_repr = repr(input_value)
                formatted_error += f" (input: {value_repr})"
            except Exception:
                # Skip if there's an issue with the input value
                pass

        # Categorize error by type
        if "missing" in error_type or "required" in error_type:
            error_categories["missing_required"].append(formatted_error)
        elif "type" in error_type:
            error_categories["type_error"].append(formatted_error)
        elif "value" in error_type:
            if "url" in location.lower():
                error_categories["url_error"].append(formatted_error)
            elif "path" in location.lower():
                error_categories["path_error"].append(formatted_error)
            else:
                error_categories["value_error"].append(formatted_error)
        else:
            error_categories["other"].append(formatted_error)

    # Build user-friendly message
    result = ["Validation error:"]

    if error_categories["missing_required"]:
        result.append("\nMissing required fields:")
        result.extend(f"  • {err}" for err in error_categories["missing_required"])

    if error_categories["type_error"]:
        result.append("\nType errors:")
        result.extend(f"  • {err}" for err in error_categories["type_error"])

    if error_categories["value_error"]:
        result.append("\nValue errors:")
        result.extend(f"  • {err}" for err in error_categories["value_error"])

    if error_categories["url_error"]:
        result.append("\nURL errors:")
        result.extend(f"  • {err}" for err in error_categories["url_error"])

    if error_categories["path_error"]:
        result.append("\nPath errors:")
        result.extend(f"  • {err}" for err in error_categories["path_error"])

    if error_categories["other"]:
        result.append("\nOther errors:")
        result.extend(f"  • {err}" for err in error_categories["other"])

    # Add suggestions based on error types
    if error_categories["missing_required"]:
        result.append("\nSuggestion: Ensure all required fields are provided.")
    elif error_categories["type_error"]:
        result.append("\nSuggestion: Check that field values have the correct types.")
    elif error_categories["value_error"]:
        suggestion = (
            "\nSuggestion: Verify that values meet constraints (length, format, etc.)."
        )
        result.append(suggestion)
    elif error_categories["url_error"]:
        suggestion = "\nSuggestion: Ensure URLs are properly formatted and accessible."
        result.append(suggestion)
    elif error_categories["path_error"]:
        result.append("\nSuggestion: Verify that file paths exist and are accessible.")

    return "\n".join(result)


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
        # Validate directly from JSON for better performance
        RawConfigDictModel.model_validate_json(json_data)
    except ValidationError as e:
        return False, format_pydantic_errors(e)
    except Exception as e:
        return False, f"Invalid JSON: {e!s}"
    else:
        return True, None
