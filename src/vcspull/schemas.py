"""Pydantic schemas for vcspull configuration."""

from __future__ import annotations

import enum
import os
import pathlib
import typing as t
from functools import lru_cache
from typing import Annotated

from typing_extensions import Literal, TypeGuard

from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    RootModel,
    TypeAdapter,
    ValidationInfo,
    WithJsonSchema,
    computed_field,
    field_validator,
    model_validator,
)

# Type aliases for better readability
PathLike = t.Union[str, pathlib.Path]
ConfigName = str
SectionName = str
ShellCommand = str


# Error message constants
EMPTY_VALUE_ERROR = "Value cannot be empty or whitespace only"
REMOTES_GIT_ONLY_ERROR = "Remotes are only supported for Git repositories"


# Validation functions for Annotated types
def validate_not_empty(v: str) -> str:
    """Validate string is not empty after stripping."""
    if v.strip() == "":
        raise ValueError(EMPTY_VALUE_ERROR)
    return v


def normalize_path(path: str | pathlib.Path) -> str:
    """Convert path to string form."""
    return str(path)


def expand_path(path: str) -> pathlib.Path:
    """Expand variables and user directory in path."""
    return pathlib.Path(os.path.expandvars(path)).expanduser()


# Define reusable field types with Annotated
NonEmptyStr = Annotated[
    str,
    AfterValidator(validate_not_empty),
    WithJsonSchema({"type": "string", "minLength": 1}),
]

# Path validation types
PathStr = Annotated[
    str | pathlib.Path,
    BeforeValidator(normalize_path),
    AfterValidator(validate_not_empty),
    WithJsonSchema({"type": "string", "description": "File system path"}),
]

ExpandedPath = Annotated[
    str | pathlib.Path,
    BeforeValidator(normalize_path),
    BeforeValidator(os.path.expandvars),
    AfterValidator(expand_path),
    WithJsonSchema({"type": "string", "description": "Expanded file system path"}),
]


class VCSType(str, enum.Enum):
    """Supported version control systems."""

    GIT = "git"
    HG = "hg"
    SVN = "svn"


class GitRemote(BaseModel):
    """Git remote configuration."""

    name: NonEmptyStr = Field(description="Remote name")
    url: NonEmptyStr = Field(description="Remote URL")
    fetch: str | None = Field(default=None, description="Fetch specification")
    push: str | None = Field(default=None, description="Push specification")

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )


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

    vcs: Literal["git", "hg", "svn"] = Field(description="Version control system type")
    name: NonEmptyStr = Field(description="Repository name")
    path: pathlib.Path = Field(description="Path to the repository")
    url: NonEmptyStr = Field(description="Repository URL")
    remotes: dict[str, GitRemote] | None = Field(
        default=None,
        description="Git remote configurations (name → config)",
    )
    shell_command_after: list[str] | None = Field(
        default=None,
        description="Commands to run after repository operations",
    )

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    @computed_field
    def is_git_repo(self) -> bool:
        """Determine if this is a Git repository."""
        return self.vcs == "git"

    @model_validator(mode="after")
    def validate_vcs_specific_fields(self) -> RepositoryModel:
        """Validate VCS-specific fields."""
        # Git remotes are only for Git repositories
        if self.remotes and self.vcs != "git":
            raise ValueError(REMOTES_GIT_ONLY_ERROR)

        # Additional VCS-specific validation could be added here
        return self

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str, info: ValidationInfo) -> str:
        """Validate repository URL.

        Parameters
        ----------
        v : str
            URL to validate
        info : ValidationInfo
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

        # Get VCS type from validation context
        vcs_type = info.data.get("vcs", "").lower() if info.data else ""

        # Basic validation for all URL types
        if v.strip() == "":
            msg = "URL cannot be empty or whitespace"
            raise ValueError(msg)

        # VCS-specific validation
        if vcs_type == "git" and "github.com" in v and not v.endswith(".git"):
            # Add .git suffix for GitHub URLs if missing
            return f"{v}.git"

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
    """Raw repository configuration model before validation and path resolution.

    This model validates the raw data from the configuration file before
    resolving paths and converting to the full RepositoryModel.

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
    remotes : dict[str, dict[str, Any]] | None, optional
        Dictionary of remote configurations (for Git only)
    shell_command_after : list[str] | None, optional
        Commands to run after repository operations
    """

    vcs: Literal["git", "hg", "svn"] = Field(
        description="Version control system type (git, hg, svn)",
    )
    name: NonEmptyStr = Field(description="Repository name")
    path: PathStr = Field(description="Path to the repository")
    url: NonEmptyStr = Field(description="Repository URL")
    remotes: dict[str, dict[str, t.Any]] | None = Field(
        default=None,
        description="Git remote configurations (name → config)",
    )
    shell_command_after: list[str] | None = Field(
        default=None,
        description="Commands to run after repository operations",
    )

    model_config = ConfigDict(
        extra="allow",  # Allow extra fields in raw config
        str_strip_whitespace=True,
    )

    @model_validator(mode="after")
    def validate_vcs_specific_fields(self) -> RawRepositoryModel:
        """Validate VCS-specific fields."""
        # Git remotes are only for Git repositories
        if self.remotes and self.vcs != "git":
            raise ValueError(REMOTES_GIT_ONLY_ERROR)

        # Additional VCS-specific validation could be added here
        return self

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str, info: ValidationInfo) -> str:
        """Validate repository URL based on VCS type.

        Parameters
        ----------
        v : str
            URL to validate
        info : ValidationInfo
            Validation information including access to other field values

        Returns
        -------
        str
            Validated URL
        """
        # Access other values using context
        vcs_type = info.data.get("vcs", "") if info.data else ""

        # Git-specific URL validation
        if vcs_type == "git" and "github.com" in v and not v.endswith(".git"):
            # Add .git suffix for GitHub URLs
            return f"{v}.git"

        return v

    @field_validator("remotes")
    @classmethod
    def validate_remotes(
        cls,
        v: dict[str, dict[str, t.Any]] | None,
        info: ValidationInfo,
    ) -> dict[str, dict[str, t.Any]] | None:
        """Validate Git remotes configuration.

        Parameters
        ----------
        v : dict[str, dict[str, Any]] | None
            Remotes configuration to validate
        info : ValidationInfo
            Validation information

        Returns
        -------
        dict[str, dict[str, Any]] | None
            Validated remotes configuration

        Raises
        ------
        TypeError
            If remotes configuration has incorrect type
        ValueError
            If remotes configuration has invalid values
        """
        if v is None:
            return None

        # Get VCS type from context
        vcs_type = info.data.get("vcs", "") if info.data else ""

        # Remotes are only relevant for Git repositories
        if vcs_type != "git":
            err_msg = f"Remotes are not supported for {vcs_type} repositories"
            raise ValueError(err_msg)

        for remote_name, remote_config in v.items():
            if not isinstance(remote_config, dict):
                msg = f"Invalid remote '{remote_name}': must be a dictionary"
                raise TypeError(msg)

            # Ensure required fields are present for each remote
            if isinstance(remote_config, dict) and "url" not in remote_config:
                msg = f"Missing required field 'url' in remote '{remote_name}'"
                raise ValueError(msg)

            # Check for empty URL in remote config
            if (
                isinstance(remote_config, dict)
                and "url" in remote_config
                and isinstance(remote_config["url"], str)
                and remote_config["url"].strip() == ""
            ):
                msg = f"Empty URL in remote '{remote_name}': URL cannot be empty"
                raise ValueError(msg)

        return v

    @field_validator("shell_command_after")
    @classmethod
    def validate_shell_commands(cls, v: list[str] | None) -> list[str] | None:
        """Validate shell commands.

        Parameters
        ----------
        v : list[str] | None
            Shell commands to validate

        Returns
        -------
        list[str] | None
            Validated shell commands

        Raises
        ------
        ValueError
            If shell commands are invalid
        """
        if v is None:
            return None

        if not all(isinstance(cmd, str) for cmd in v):
            msg = "All shell commands must be strings"
            raise ValueError(msg)

        return v


# Use a type alias for the complex type in RawConfigSectionDictModel
RawRepoDataType = t.Union[RawRepositoryModel, str, dict[str, t.Any]]


class RawConfigSectionDictModel(RootModel[dict[str, RawRepoDataType]]):
    """Raw configuration section model before validation."""

    model_config = ConfigDict(
        extra="allow",
        str_strip_whitespace=True,
    )


class RawConfigDictModel(RootModel[dict[str, RawConfigSectionDictModel]]):
    """Raw configuration model before validation and processing."""

    model_config = ConfigDict(
        extra="allow",
        str_strip_whitespace=True,
    )


# Create module-level TypeAdapters for improved performance
@lru_cache(maxsize=8)
def get_repo_validator() -> TypeAdapter[RawRepositoryModel]:
    """Get cached TypeAdapter for repository validation.

    Returns
    -------
    TypeAdapter[RawRepositoryModel]
        TypeAdapter for validating repositories
    """
    return TypeAdapter(
        RawRepositoryModel,
        config=ConfigDict(
            str_strip_whitespace=True,
            extra="allow",
            # Performance optimizations
            defer_build=True,
            validate_default=False,
        ),
    )


@lru_cache(maxsize=8)
def get_config_validator() -> TypeAdapter[RawConfigDictModel]:
    """Get cached TypeAdapter for config validation.

    Returns
    -------
    TypeAdapter[RawConfigDictModel]
        TypeAdapter for validating configs
    """
    return TypeAdapter(
        RawConfigDictModel,
        config=ConfigDict(
            extra="allow",
            str_strip_whitespace=True,
            # Performance optimizations
            defer_build=True,
            validate_default=False,
        ),
    )


# Initialize validators on module load
repo_validator = get_repo_validator()
config_validator = get_config_validator()

# Pre-build schemas for better performance
repo_validator.rebuild()
config_validator.rebuild()


def is_valid_repo_config(config: dict[str, t.Any]) -> TypeGuard[dict[str, t.Any]]:
    """Check if repository configuration is valid.

    Parameters
    ----------
    config : dict[str, Any]
        Repository configuration to validate

    Returns
    -------
    TypeGuard[dict[str, Any]]
        True if config is valid
    """
    if config is None:
        return False

    try:
        repo_validator.validate_python(config)
    except Exception:
        return False
    else:
        return True


def is_valid_config_dict(config: dict[str, t.Any]) -> TypeGuard[dict[str, t.Any]]:
    """Check if configuration dictionary is valid.

    Parameters
    ----------
    config : dict[str, Any]
        Configuration to validate

    Returns
    -------
    TypeGuard[dict[str, Any]]
        True if config is valid
    """
    if config is None:
        return False

    try:
        config_validator.validate_python({"root": config})
    except Exception:
        return False
    else:
        return True


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


def validate_config_from_json(
    json_data: str | bytes,
) -> tuple[bool, dict[str, t.Any] | str]:
    """Validate configuration directly from JSON.

    Parameters
    ----------
    json_data : str | bytes
        JSON data to validate

    Returns
    -------
    tuple[bool, dict[str, Any] | str]
        Tuple of (is_valid, validated_config_or_error_message)
    """
    try:
        # Direct JSON validation - more performant
        config = RawConfigDictModel.model_validate_json(
            json_data,
            context={"source": "json_data"},  # Add context for validators
        )
        return True, config.model_dump(
            exclude_unset=True,
            exclude_none=True,
        )
    except Exception as e:
        return False, str(e)
