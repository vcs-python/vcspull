"""Typings for vcspull."""

from __future__ import annotations

import pathlib
import typing as t
from pathlib import Path
from typing import (
    Any,
    Callable,
    Optional,
    Protocol,
    TypeVar,
    Union,
)

from typing_extensions import NotRequired, TypedDict

if t.TYPE_CHECKING:
    from libvcs._internal.types import StrPath, VCSLiteral
    from libvcs.sync.git import GitSyncRemoteDict

# Type aliases for better readability
PathLike = Union[str, Path]
ConfigName = str
SectionName = str
ShellCommand = str


class RawConfigDict(TypedDict):
    """Configuration dictionary without any type marshalling or variable resolution.

    Parameters
    ----------
    vcs : VCSLiteral
        Version control system type (e.g., 'git', 'hg', 'svn')
    name : str
        Name of the repository
    path : StrPath
        Path to the repository
    url : str
        URL of the repository
    remotes : GitSyncRemoteDict
        Dictionary of remote configurations (for Git only)
    """

    vcs: VCSLiteral
    name: str
    path: StrPath
    url: str
    remotes: NotRequired[GitSyncRemoteDict]


# More specific type aliases instead of simple Dict
RawConfigDir = dict[SectionName, RawConfigDict]
RawConfig = dict[ConfigName, RawConfigDir]


class ConfigDict(TypedDict):
    """Configuration map for vcspull after shorthands and variables resolved.

    Parameters
    ----------
    vcs : VCSLiteral | None
        Version control system type (e.g., 'git', 'hg', 'svn')
    name : str
        Name of the repository
    path : pathlib.Path
        Path to the repository (resolved to a Path object)
    url : str
        URL of the repository
    remotes : GitSyncRemoteDict | None, optional
        Dictionary of remote configurations (for Git only)
    shell_command_after : list[str] | None, optional
        Commands to run after repository operations
    """

    vcs: VCSLiteral | None
    name: str
    path: pathlib.Path
    url: str
    remotes: NotRequired[GitSyncRemoteDict | None]
    shell_command_after: NotRequired[list[ShellCommand] | None]


# More specific type aliases
ConfigDir = dict[SectionName, ConfigDict]
Config = dict[ConfigName, ConfigDir]

# Tuple type for duplicate repository detection
ConfigDictTuple = tuple[ConfigDict, ConfigDict]

# Path resolver type
PathResolver = Callable[[], Path]


# Structural typing with Protocol
class ConfigLoader(Protocol):
    """Protocol for config loader objects."""

    def load(self, path: PathLike) -> RawConfig:
        """Load configuration from a path.

        Parameters
        ----------
        path : PathLike
            Path to configuration file

        Returns
        -------
        RawConfig
            Loaded configuration
        """
        ...


class ConfigValidator(Protocol):
    """Protocol for config validator objects."""

    def validate(self, config: RawConfig) -> bool:
        """Validate configuration.

        Parameters
        ----------
        config : RawConfig
            Configuration to validate

        Returns
        -------
        bool
            True if valid, False otherwise
        """
        ...


# Generic type for filtering operations
T = TypeVar("T")
FilterPredicate = Callable[[T], bool]

# Result types
ValidationResult = tuple[bool, Optional[str]]
SyncResult = dict[str, Any]
