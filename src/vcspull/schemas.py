"""Pydantic schemas for vcspull configuration."""

from __future__ import annotations

import enum
import os
import pathlib
import typing as t

from pydantic import (
    BaseModel,
    ConfigDict,
    RootModel,
    field_validator,
)

# Type aliases for better readability
PathLike = t.Union[str, pathlib.Path]
ConfigName = str
SectionName = str
ShellCommand = str


class VCSType(str, enum.Enum):
    """Supported version control systems."""

    GIT = "git"
    HG = "hg"
    SVN = "svn"


class GitRemote(BaseModel):
    """Git remote configuration."""

    name: str
    url: str
    fetch: str | None = None
    push: str | None = None


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
    path: str | pathlib.Path
    url: str
    remotes: dict[str, GitRemote] | None = None
    shell_command_after: list[str] | None = None

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
        if v.lower() not in {"git", "hg", "svn"}:
            msg = f"Invalid VCS type: {v}. Supported types are: git, hg, svn"
            raise ValueError(msg)
        return v.lower()

    @field_validator("path")
    @classmethod
    def validate_path(cls, v: str | pathlib.Path) -> pathlib.Path:
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
            path_obj = pathlib.Path(path_str)
            # Use Path methods instead of os.path
            expanded_path = pathlib.Path(os.path.expandvars(str(path_obj)))
            return expanded_path.expanduser()
        except Exception as e:
            msg = f"Invalid path: {v}. Error: {e!s}"
            raise ValueError(msg) from e

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
            msg = "URL cannot be empty"
            raise ValueError(msg)

        # Different validation based on VCS type
        # Keeping this but not using yet - can be expanded later
        # vcs_type = values.get("vcs", "").lower()

        # Basic validation for all URL types
        if v.strip() == "":
            msg = "URL cannot be empty or whitespace"
            raise ValueError(msg)

        # VCS-specific validation could be added here
        # For now, just return the URL as is
        return v


class ConfigSectionDictModel(RootModel[dict[str, RepositoryModel]]):
    """Configuration section model containing repositories.

    A section is a logical grouping of repositories, typically by project or
    organization.
    """

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
        return self.root[key]

    def keys(self) -> t.KeysView[str]:
        """Get repository names.

        Returns
        -------
        KeysView[str]
            View of repository names
        """
        return self.root.keys()

    def items(self) -> t.ItemsView[str, RepositoryModel]:
        """Get items as name-repository pairs.

        Returns
        -------
        ItemsView[str, RepositoryModel]
            View of name-repository pairs
        """
        return self.root.items()

    def values(self) -> t.ValuesView[RepositoryModel]:
        """Get repository configurations.

        Returns
        -------
        ValuesView[RepositoryModel]
            View of repository configurations
        """
        return self.root.values()


class ConfigDictModel(RootModel[dict[str, ConfigSectionDictModel]]):
    """Complete configuration model containing sections.

    A configuration is a collection of sections, where each section contains
    repositories.
    """

    def __getitem__(self, key: str) -> ConfigSectionDictModel:
        """Get section by name.

        Parameters
        ----------
        key : str
            Section name

        Returns
        -------
        ConfigSectionDictModel
            Section configuration
        """
        return self.root[key]

    def keys(self) -> t.KeysView[str]:
        """Get section names.

        Returns
        -------
        KeysView[str]
            View of section names
        """
        return self.root.keys()

    def items(self) -> t.ItemsView[str, ConfigSectionDictModel]:
        """Get items as section-repositories pairs.

        Returns
        -------
        ItemsView[str, ConfigSectionDictModel]
            View of section-repositories pairs
        """
        return self.root.items()

    def values(self) -> t.ValuesView[ConfigSectionDictModel]:
        """Get section configurations.

        Returns
        -------
        ValuesView[ConfigSectionDictModel]
            View of section configurations
        """
        return self.root.values()


# Raw configuration models for initial parsing without validation
class RawRepositoryModel(BaseModel):
    """Raw repository configuration model before validation and path resolution."""

    vcs: str
    name: str
    path: str | pathlib.Path
    url: str
    remotes: dict[str, dict[str, t.Any]] | None = None
    shell_command_after: list[str] | None = None

    model_config = ConfigDict(
        extra="allow",  # Allow extra fields in raw config
        str_strip_whitespace=True,
    )


# Use a type alias for the complex type in RawConfigSectionDictModel
RawRepoDataType = t.Union[RawRepositoryModel, str, dict[str, t.Any]]


class RawConfigSectionDictModel(RootModel[dict[str, RawRepoDataType]]):
    """Raw configuration section model before validation."""


class RawConfigDictModel(RootModel[dict[str, RawConfigSectionDictModel]]):
    """Raw configuration model before validation and processing."""


# Functions to convert between raw and validated models
def convert_raw_to_validated(
    raw_config: RawConfigDictModel,
    cwd: t.Callable[[], pathlib.Path] = pathlib.Path.cwd,
) -> ConfigDictModel:
    """Convert raw configuration to validated configuration.

    Parameters
    ----------
    raw_config : RawConfigDictModel
        Raw configuration
    cwd : Callable[[], Path], optional
        Function to get current working directory, by default Path.cwd

    Returns
    -------
    ConfigDictModel
        Validated configuration
    """
    # Create a new ConfigDictModel
    config = ConfigDictModel(root={})

    # Process each section in the raw config
    for section_name, raw_section in raw_config.root.items():
        # Create a new section in the validated config
        config.root[section_name] = ConfigSectionDictModel(root={})

        # Process each repository in the section
        for repo_name, raw_repo_data in raw_section.root.items():
            # Handle string shortcuts (URL strings)
            if isinstance(raw_repo_data, str):
                # Convert string URL to a repository model
                repo_model = RepositoryModel(
                    vcs="git",  # Default to git for string URLs
                    name=repo_name,
                    path=cwd() / repo_name,  # Default path is repo name in current dir
                    url=raw_repo_data,
                )
            # Handle direct dictionary data
            elif isinstance(raw_repo_data, dict):
                # Ensure name is set
                if "name" not in raw_repo_data:
                    raw_repo_data["name"] = repo_name

                # Validate and convert path
                if "path" in raw_repo_data:
                    path = raw_repo_data["path"]
                    # Convert relative paths to absolute using cwd
                    path_obj = pathlib.Path(os.path.expandvars(str(path))).expanduser()
                    if not path_obj.is_absolute():
                        path_obj = cwd() / path_obj
                    raw_repo_data["path"] = path_obj

                # Create repository model
                repo_model = RepositoryModel.model_validate(raw_repo_data)
            else:
                # Skip invalid repository data
                continue

            # Add repository to the section
            config.root[section_name].root[repo_name] = repo_model

    return config
