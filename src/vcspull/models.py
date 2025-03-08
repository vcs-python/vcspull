"""Pydantic models for vcspull configuration."""

from __future__ import annotations

import os
import pathlib
import typing as t
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    field_validator,
    model_validator,
)

if t.TYPE_CHECKING:
    from libvcs._internal.types import VCSLiteral
    from libvcs.sync.git import GitSyncRemoteDict

# Type aliases for better readability
PathLike = Union[str, Path]
ConfigName = str
SectionName = str
ShellCommand = str


class VCSType(str, Enum):
    """Supported version control systems."""

    GIT = "git"
    HG = "hg"
    SVN = "svn"


class GitRemote(BaseModel):
    """Git remote configuration."""

    name: str
    url: str
    fetch: Optional[str] = None
    push: Optional[str] = None


class RepositoryModel(BaseModel):
    """Repository configuration model.

    Parameters
    ----------
    vcs : str
        Version control system type (e.g., 'git', 'hg', 'svn')
    name : str
        Name of the repository
    path : str | Path
        Path to the repository
    url : str
        URL of the repository
    remotes : dict[str, GitRemote] | None, optional
        Dictionary of remote configurations (for Git only)
    shell_command_after : list[str] | None, optional
        Commands to run after repository operations
    """

    vcs: str
    name: str
    path: Union[str, Path]
    url: str
    remotes: Optional[Dict[str, GitRemote]] = None
    shell_command_after: Optional[List[str]] = None

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    @field_validator("vcs")
    @classmethod
    def validate_vcs(cls, v: str) -> str:
        """Validate VCS type.

        Parameters
        ----------
        v : str
            VCS type to validate

        Returns
        -------
        str
            Validated VCS type

        Raises
        ------
        ValueError
            If VCS type is invalid
        """
        if v.lower() not in ("git", "hg", "svn"):
            raise ValueError(
                f"Invalid VCS type: {v}. Supported types are: git, hg, svn"
            )
        return v.lower()

    @field_validator("path")
    @classmethod
    def validate_path(cls, v: Union[str, Path]) -> Path:
        """Validate and convert path to Path object.

        Parameters
        ----------
        v : str | Path
            Path to validate

        Returns
        -------
        Path
            Validated path as Path object

        Raises
        ------
        ValueError
            If path is invalid
        """
        try:
            # Convert to string first to handle Path objects
            path_str = str(v)
            # Expand environment variables and user directory
            expanded_path = os.path.expandvars(path_str)
            expanded_path = os.path.expanduser(expanded_path)
            # Convert to Path object
            return Path(expanded_path)
        except Exception as e:
            raise ValueError(f"Invalid path: {v}. Error: {str(e)}")

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str, info: t.Any) -> str:
        """Validate repository URL.

        Parameters
        ----------
        v : str
            URL to validate
        info : Any
            Validation context

        Returns
        -------
        str
            Validated URL

        Raises
        ------
        ValueError
            If URL is invalid
        """
        if not v:
            raise ValueError("URL cannot be empty")

        # Different validation based on VCS type
        values = info.data
        vcs_type = values.get("vcs", "").lower()

        # Basic validation for all URL types
        if v.strip() == "":
            raise ValueError("URL cannot be empty or whitespace")

        # VCS-specific validation could be added here
        # For now, just return the URL as is
        return v


class ConfigSectionModel(BaseModel):
    """Configuration section model containing repositories.

    A section is a logical grouping of repositories, typically by project or organization.
    """

    __root__: Dict[str, RepositoryModel] = Field(default_factory=dict)

    def __getitem__(self, key: str) -> RepositoryModel:
        """Get repository by name.

        Parameters
        ----------
        key : str
            Repository name

        Returns
        -------
        RepositoryModel
            Repository configuration
        """
        return self.__root__[key]

    def __iter__(self) -> t.Iterator[str]:
        """Iterate over repository names.

        Returns
        -------
        Iterator[str]
            Iterator of repository names
        """
        return iter(self.__root__)

    def items(self) -> t.ItemsView[str, RepositoryModel]:
        """Get items as name-repository pairs.

        Returns
        -------
        ItemsView[str, RepositoryModel]
            View of name-repository pairs
        """
        return self.__root__.items()

    def values(self) -> t.ValuesView[RepositoryModel]:
        """Get repository configurations.

        Returns
        -------
        ValuesView[RepositoryModel]
            View of repository configurations
        """
        return self.__root__.values()


class ConfigModel(BaseModel):
    """Complete configuration model containing sections.

    A configuration is a collection of sections, where each section contains repositories.
    """

    __root__: Dict[str, ConfigSectionModel] = Field(default_factory=dict)

    def __getitem__(self, key: str) -> ConfigSectionModel:
        """Get section by name.

        Parameters
        ----------
        key : str
            Section name

        Returns
        -------
        ConfigSectionModel
            Section configuration
        """
        return self.__root__[key]

    def __iter__(self) -> t.Iterator[str]:
        """Iterate over section names.

        Returns
        -------
        Iterator[str]
            Iterator of section names
        """
        return iter(self.__root__)

    def items(self) -> t.ItemsView[str, ConfigSectionModel]:
        """Get items as section-repositories pairs.

        Returns
        -------
        ItemsView[str, ConfigSectionModel]
            View of section-repositories pairs
        """
        return self.__root__.items()

    def values(self) -> t.ValuesView[ConfigSectionModel]:
        """Get section configurations.

        Returns
        -------
        ValuesView[ConfigSectionModel]
            View of section configurations
        """
        return self.__root__.values()


# Raw configuration models for initial parsing without validation
class RawRepositoryModel(BaseModel):
    """Raw repository configuration model before validation and path resolution."""

    vcs: str
    name: str
    path: Union[str, Path]
    url: str
    remotes: Optional[Dict[str, Dict[str, Any]]] = None
    shell_command_after: Optional[List[str]] = None

    model_config = ConfigDict(
        extra="allow",  # Allow extra fields in raw config
        str_strip_whitespace=True,
    )


class RawConfigSectionModel(BaseModel):
    """Raw configuration section model before validation."""

    __root__: Dict[str, Union[RawRepositoryModel, str, Dict[str, Any]]] = Field(
        default_factory=dict
    )


class RawConfigModel(BaseModel):
    """Raw configuration model before validation and processing."""

    __root__: Dict[str, RawConfigSectionModel] = Field(default_factory=dict)


# Functions to convert between raw and validated models
def convert_raw_to_validated(
    raw_config: RawConfigModel,
    cwd: t.Callable[[], Path] = Path.cwd,
) -> ConfigModel:
    """Convert raw configuration to validated configuration.

    Parameters
    ----------
    raw_config : RawConfigModel
        Raw configuration
    cwd : Callable[[], Path], optional
        Function to get current working directory, by default Path.cwd

    Returns
    -------
    ConfigModel
        Validated configuration
    """
    # Implementation will go here
    # This will handle shorthand syntax, variable resolution, etc.
    pass 