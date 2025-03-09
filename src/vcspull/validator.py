"""Validation of vcspull configuration files and schemas."""

from __future__ import annotations

import json
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
        # Format validation errors with improved formatting
        return False, format_pydantic_errors(e)
    except Exception as e:
        # Handle other exceptions
        return False, f"Validation error: {e}"
    else:
        # Return success when no exceptions occur
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

    # Empty string check - done here for clear error message
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

    # Use Pydantic validation through TypeAdapter for complete validation
    try:
        # Use type adapter for validation
        config_validator.validate_python({"root": config})
    except ValidationError as e:
        # Format the Pydantic errors with the improved formatter
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

    # Type check - important for test_validate_config_raises_exceptions
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

    # Check that all keys are strings
    for key in config:
        if not isinstance(key, str):
            raise exc.ConfigValidationError(
                message=f"Invalid section name: {key} (type: {type(key).__name__})",
                suggestion="Section names must be strings.",
            )

    # Check that all values are dictionaries
    for section, section_value in config.items():
        if not isinstance(section_value, dict):
            raise exc.ConfigValidationError(
                message=f"Invalid section value for '{section}': {section_value} (type: {type(section_value).__name__})",
                suggestion="Section values must be dictionaries containing repositories.",
            )

        # Check repository configurations
        for repo_name, repo_config in section_value.items():
            # Skip string shorthand URLs
            if isinstance(repo_config, str):
                continue

            # Check that repo config is a dictionary
            if not isinstance(repo_config, dict):
                raise exc.ConfigValidationError(
                    message=f"Invalid repository configuration for '{section}.{repo_name}': {repo_config} (type: {type(repo_config).__name__})",
                    suggestion="Repository configurations must be dictionaries or URL strings.",
                )

            # Check for required fields
            if "vcs" not in repo_config:
                raise exc.ConfigValidationError(
                    message=f"Missing required field 'vcs' in repository '{section}.{repo_name}'",
                    suggestion="Each repository configuration must include a 'vcs' field.",
                )

            # Check VCS value
            if "vcs" in repo_config and repo_config["vcs"] not in {"git", "hg", "svn"}:
                raise exc.ConfigValidationError(
                    message=f"Invalid VCS type '{repo_config['vcs']}' in repository '{section}.{repo_name}'",
                    suggestion="VCS type must be one of: 'git', 'hg', 'svn'.",
                )

    # Use Pydantic validation for complete validation
    try:
        config_validator.validate_python({"root": config})
    except ValidationError as e:
        # Create a more user-friendly error message with structure
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
    # Get structured error representation with enhanced information
    errors = validation_error.errors(
        include_url=True,  # Include documentation URLs
        include_context=True,  # Include validation context
        include_input=True,  # Include input values
    )

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
        url = error.get("url", "")
        ctx = error.get("ctx", {})
        input_value = error.get("input", "")

        # Create a detailed error message
        formatted_error = f"{location}: {message}"

        # Add input value if available (for more context)
        if input_value != "" and input_value is not None:
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

        # Add documentation URL if available
        if url:
            formatted_error += f" (docs: {url})"

        # Add context information if available
        if ctx:
            context_info = ", ".join(f"{k}={v!r}" for k, v in ctx.items())
            formatted_error += f" [Context: {context_info}]"

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


def get_structured_errors(validation_error: ValidationError) -> dict[str, t.Any]:
    """Get structured error representation suitable for API responses.

    Parameters
    ----------
    validation_error : ValidationError
        The validation error to format

    Returns
    -------
    dict[str, t.Any]
        Structured error format with categorized errors
    """
    # Get structured representation from errors method
    errors = validation_error.errors(
        include_url=True,
        include_context=True,
        include_input=True,
    )

    # Group by error type
    categorized = {}
    for error in errors:
        location = ".".join(str(loc) for loc in error.get("loc", []))
        error_type = error.get("type", "unknown")

        if error_type not in categorized:
            categorized[error_type] = []

        categorized[error_type].append(
            {
                "location": location,
                "message": error.get("msg", ""),
                "context": error.get("ctx", {}),
                "url": error.get("url", ""),
                "input": error.get("input", ""),
            },
        )

    return {
        "error": "ValidationError",
        "detail": categorized,
        "error_count": validation_error.error_count(),
        "summary": str(validation_error),
    }


def validate_config_json(json_data: str | bytes) -> ValidationResult:
    """Validate configuration from JSON string or bytes.

    Parameters
    ----------
    json_data : str | bytes
        JSON data to validate

    Returns
    -------
    ValidationResult
        Tuple of (is_valid, result_or_error_message)
    """
    if not json_data:
        return False, "JSON data cannot be empty"

    try:
        # First parse the JSON
        config_dict = json.loads(json_data)

        # Then validate the parsed config
        try:
            # Validate the structure first
            valid, message = validate_config_structure(config_dict)
            if not valid:
                return False, message

            # Check for invalid VCS values
            for section_name, section in config_dict.items():
                if not isinstance(section, dict):
                    continue

                for repo_name, repo in section.items():
                    if not isinstance(repo, dict):
                        continue

                    if "vcs" in repo and repo["vcs"] not in {"git", "hg", "svn"}:
                        return (
                            False,
                            f"Invalid VCS type: {repo['vcs']} in {section_name}.{repo_name}",
                        )

            # Use Pydantic validation as a final check
            RawConfigDictModel.model_validate(
                config_dict,
                context={"source": "json_input"},  # Add context for validators
            )
        except ValidationError as e:
            return False, format_pydantic_errors(e)
        except Exception as e:
            return False, f"Invalid configuration: {e!s}"

    except json.JSONDecodeError as e:
        return False, f"Invalid JSON syntax: {e}"
    except Exception as e:
        return False, f"Invalid JSON: {e!s}"
    else:
        # Return success with no error message
        return True, None
