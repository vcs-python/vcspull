"""Validation of vcspull configuration files and models."""

from __future__ import annotations

import pathlib
import typing as t
from pathlib import Path
from typing import Any, Dict, List, Optional, Union, cast

from pydantic import ValidationError

from . import exc
from .models import (
    ConfigModel,
    RawConfigModel,
    RawRepositoryModel,
    RepositoryModel,
)
from .types import (
    PathLike,
    RawConfig,
    ValidationResult,
)

if t.TYPE_CHECKING:
    from typing_extensions import TypeGuard


def is_valid_config(config: dict[str, Any]) -> TypeGuard[RawConfig]:
    """Return true and upcast if vcspull configuration file is valid.

    Parameters
    ----------
    config : Dict[str, Any]
        Configuration dictionary to validate

    Returns
    -------
    TypeGuard[RawConfig]
        True if config is valid, False otherwise
    """
    try:
        # Try to parse the config with Pydantic
        RawConfigModel.model_validate({"__root__": config})
        return True
    except ValidationError:
        return False


def validate_repo_config(repo_config: Dict[str, Any]) -> ValidationResult:
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
    try:
        # Validate using Pydantic
        RawRepositoryModel.model_validate(repo_config)
        return True, None
    except ValidationError as e:
        # Extract error details from Pydantic
        errors = e.errors()
        error_msgs = []
        for error in errors:
            field = ".".join(str(loc) for loc in error["loc"])
            msg = error["msg"]
            error_msgs.append(f"{field}: {msg}")
        
        return False, "; ".join(error_msgs)


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
    try:
        # Use the path validator from RepositoryModel
        RepositoryModel.validate_path(path)  # type: ignore
        return True, None
    except ValueError as e:
        return False, str(e)


def validate_config_structure(config: Any) -> ValidationResult:
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
    try:
        # Validate configuration structure using Pydantic
        RawConfigModel.model_validate({"__root__": config})
        return True, None
    except ValidationError as e:
        # Extract error details for better reporting
        errors = e.errors()
        error_msgs = []
        for error in errors:
            field = ".".join(str(loc) for loc in error["loc"])
            msg = error["msg"]
            error_msgs.append(f"{field}: {msg}")
        
        return False, "; ".join(error_msgs)


def validate_config(config: Any) -> None:
    """Validate a configuration and raise exceptions for invalid configs.

    Parameters
    ----------
    config : Any
        Configuration to validate

    Raises
    ------
    ConfigValidationError
        If configuration is invalid
    """
    try:
        # Try to validate with Pydantic
        raw_config_model = RawConfigModel.model_validate({"__root__": config})
        
        # Additional custom validations can be added here
        
    except ValidationError as e:
        # Convert Pydantic validation error to our exception
        error_details = []
        for error in e.errors():
            # Format location in a readable way
            loc = ".".join(str(part) for part in error["loc"])
            error_details.append(f"{loc}: {error['msg']}")
        
        # Create a well-formatted error message
        error_message = "Configuration validation failed:\n" + "\n".join(error_details)
        
        # Provide helpful suggestions based on error type
        suggestion = "Check your configuration format and required fields."
        
        # Add more specific suggestions based on error patterns
        if any("missing" in err["msg"].lower() for err in e.errors()):
            suggestion = "Ensure all required fields (vcs, url, path) are present for each repository."
        elif any("url" in str(err["loc"]).lower() for err in e.errors()):
            suggestion = "Check that all repository URLs are valid and properly formatted."
        elif any("path" in str(err["loc"]).lower() for err in e.errors()):
            suggestion = "Verify that all paths are valid and accessible."
        
        raise exc.ConfigValidationError(
            message=error_message,
            suggestion=suggestion,
        )


def format_pydantic_errors(validation_error: ValidationError) -> str:
    """Format Pydantic validation errors into a readable string.
    
    Parameters
    ----------
    validation_error : ValidationError
        Pydantic validation error
        
    Returns
    -------
    str
        Formatted error message
    """
    errors = validation_error.errors()
    messages = []
    
    for error in errors:
        # Format the location
        loc = " -> ".join(str(part) for part in error["loc"])
        # Get the error message
        msg = error["msg"]
        # Create a formatted message
        messages.append(f"{loc}: {msg}")
    
    return "\n".join(messages)
