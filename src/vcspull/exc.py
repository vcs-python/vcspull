"""Exceptions for vcspull."""

from __future__ import annotations

import typing as t
from pathlib import Path


class VCSPullException(Exception):
    """Standard exception raised by vcspull.

    Parameters
    ----------
    message : str
        The error message describing what went wrong.
    path : Optional[Path | str]
        The file path related to this exception, if any.
    url : Optional[str]
        The URL related to this exception, if any.
    suggestion : Optional[str]
        A suggestion on how to fix the error, if applicable.
    risk_level : Optional[str]
        Severity level of the exception ('low', 'medium', 'high', 'critical').
    """

    def __init__(
        self,
        message: str,
        path: Path | str | None = None,
        url: str | None = None,
        suggestion: str | None = None,
        risk_level: str | None = None,
    ) -> None:
        """Initialize exception with metadata."""
        self.message = message
        self.path = Path(path) if isinstance(path, str) else path
        self.url = url
        self.suggestion = suggestion
        self.risk_level = risk_level
        super().__init__(message)

    def __str__(self) -> str:
        """Return formatted string representation of exception."""
        result = self.message
        if self.path:
            result += f" (path: {self.path})"
        if self.url:
            result += f" (url: {self.url})"
        if self.suggestion:
            result += f"\nSuggestion: {self.suggestion}"
        return result


# Configuration related exceptions
class ConfigException(VCSPullException):
    """Base exception for configuration related errors."""


class MultipleConfigWarning(ConfigException):
    """Multiple eligible config files found at the same time."""

    def __init__(
        self,
        message: str | None = None,
        path: Path | str | None = None,
        **kwargs: t.Any,
    ) -> None:
        """Initialize with default message if none provided."""
        if message is None:
            message = (
                "Multiple configs found in home directory. Use only one: .yaml, .json."
            )
        super().__init__(message=message, path=path, risk_level="low", **kwargs)


class ConfigLoadError(ConfigException):
    """Error loading a configuration file."""


class ConfigParseError(ConfigException):
    """Error parsing a configuration file."""


class ConfigValidationError(ConfigException):
    """Configuration validation error."""


# VCS related exceptions
class VCSException(VCSPullException):
    """Base exception for VCS related errors."""


class VCSNotFound(VCSException):
    """VCS binary not found or not installed."""


class VCSOperationError(VCSException):
    """Error during VCS operation."""


class RepoNotFound(VCSException):
    """Repository not found at the specified path."""


class RemoteNotFound(VCSException):
    """Remote repository not found."""


class RemoteAccessError(VCSException):
    """Error accessing remote repository."""


# Path related exceptions
class PathException(VCSPullException):
    """Base exception for path related errors."""


class PathPermissionError(PathException):
    """Permission error when accessing a path."""


class PathAlreadyExists(PathException):
    """Path already exists and cannot be overwritten."""


class PathNotFound(PathException):
    """Path not found."""
