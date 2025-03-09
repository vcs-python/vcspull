"""Pydantic schemas for vcspull configuration."""

from __future__ import annotations

import enum
import os
import pathlib
import typing as t
from functools import lru_cache
from typing import Annotated, TypeVar

from typing_extensions import Doc, Literal, TypeGuard

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
T = TypeVar("T")

# Error message constants for consistency
EMPTY_VALUE_ERROR = "Value cannot be empty or whitespace only"
REMOTES_GIT_ONLY_ERROR = "Remotes are only supported for Git repositories"
INVALID_VCS_ERROR = "VCS type must be one of: 'git', 'hg', 'svn'"
URL_EMPTY_ERROR = "URL cannot be empty"
URL_WHITESPACE_ERROR = "URL cannot be empty or whitespace"
PATH_EMPTY_ERROR = "Path cannot be empty"
INVALID_REMOTE_ERROR = "Invalid remote configuration"


# Validation functions for Annotated types
def validate_not_empty(v: str) -> str:
    """Validate string is not empty after stripping.

    Parameters
    ----------
    v : str
        String to validate

    Returns
    -------
    str
        The input string if valid

    Raises
    ------
    ValueError
        If the string is empty or contains only whitespace
    """
    if v.strip() == "":
        raise ValueError(EMPTY_VALUE_ERROR)
    return v


def normalize_path(path: str | pathlib.Path) -> str:
    """Convert path to string form.

    Parameters
    ----------
    path : str | pathlib.Path
        Path to normalize

    Returns
    -------
    str
        String representation of the path
    """
    return str(path)


def expand_path(path: str) -> pathlib.Path:
    """Expand variables and user directory in path.

    Parameters
    ----------
    path : str
        Path string to expand

    Returns
    -------
    pathlib.Path
        Path object with expanded variables and user directory
    """
    return pathlib.Path(os.path.expandvars(path)).expanduser()


def expand_user(path: str) -> str:
    """Expand user directory in path string.

    Parameters
    ----------
    path : str
        Path string with potential user directory reference

    Returns
    -------
    str
        Path with expanded user directory
    """
    return pathlib.Path(path).expanduser().as_posix()


# Define reusable field types with Annotated
NonEmptyStr = Annotated[
    str,
    AfterValidator(validate_not_empty),
    WithJsonSchema({"type": "string", "minLength": 1}),
    Doc("A string that cannot be empty or contain only whitespace"),
]

# Path validation types
PathStr = Annotated[
    str,  # Base type
    BeforeValidator(normalize_path),
    AfterValidator(validate_not_empty),
    WithJsonSchema({"type": "string", "description": "File system path"}),
    Doc("A path string that will be validated as not empty"),
]

ExpandedPath = Annotated[
    str,  # Base type
    BeforeValidator(normalize_path),
    BeforeValidator(os.path.expandvars),
    BeforeValidator(expand_user),
    AfterValidator(expand_path),
    WithJsonSchema({"type": "string", "description": "Expanded file system path"}),
    Doc("A path with environment variables and user directory expanded"),
]


class VCSType(str, enum.Enum):
    """Supported version control systems."""

    GIT = "git"
    HG = "hg"
    SVN = "svn"


class GitRemote(BaseModel):
    """Git remote configuration.

    Represents a remote repository configuration for Git repositories.

    Attributes
    ----------
    name : str
        Remote name (e.g., 'origin', 'upstream')
    url : str
        Remote URL
    fetch : str | None
        Fetch specification (optional)
    push : str | None
        Push specification (optional)
    """

    name: NonEmptyStr = Field(description="Remote name")
    url: NonEmptyStr = Field(description="Remote URL")
    fetch: str | None = Field(default=None, description="Fetch specification")
    push: str | None = Field(default=None, description="Push specification")

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        frozen=False,
        json_schema_extra={
            "examples": [
                {
                    "name": "origin",
                    "url": "https://github.com/user/repo.git",
                    "fetch": "+refs/heads/*:refs/remotes/origin/*",
                    "push": "refs/heads/main:refs/heads/main",
                },
            ],
        },
    )


class RepositoryModel(BaseModel):
    """Repository configuration model.

    Parameters
    ----------
    vcs : Literal["git", "hg", "svn"]
        Version control system type (e.g., 'git', 'hg', 'svn')
    name : str
        Name of the repository
    path : pathlib.Path
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
        validate_assignment=True,
        json_schema_extra={
            "examples": [
                {
                    "vcs": "git",
                    "name": "example",
                    "path": "~/repos/example",
                    "url": "https://github.com/user/example.git",
                    "remotes": {
                        "origin": {
                            "name": "origin",
                            "url": "https://github.com/user/example.git",
                        },
                    },
                    "shell_command_after": ["echo 'Repository updated'"],
                },
            ],
        },
    )

    @computed_field
    def is_git_repo(self) -> bool:
        """Determine if this is a Git repository."""
        return self.vcs == VCSType.GIT.value

    @computed_field
    def is_hg_repo(self) -> bool:
        """Determine if this is a Mercurial repository."""
        return self.vcs == VCSType.HG.value

    @computed_field
    def is_svn_repo(self) -> bool:
        """Determine if this is a Subversion repository."""
        return self.vcs == VCSType.SVN.value

    @model_validator(mode="after")
    def validate_vcs_specific_fields(self) -> RepositoryModel:
        """Validate VCS-specific fields.

        Ensures that certain fields only appear with the appropriate VCS type.
        For example, remotes are only valid for Git repositories.

        Returns
        -------
        RepositoryModel
            The validated repository model

        Raises
        ------
        ValueError
            If remotes are provided for non-Git repositories
        """
        is_git = self.vcs == VCSType.GIT.value
        if not is_git and self.remotes:
            raise ValueError(REMOTES_GIT_ONLY_ERROR)
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
            Validation context information

        Returns
        -------
        str
            Validated URL

        Raises
        ------
        ValueError
            If URL is empty or contains only whitespace
        """
        if not v:
            raise ValueError(URL_EMPTY_ERROR)
        if v.strip() == "":
            raise ValueError(URL_WHITESPACE_ERROR)
        return v.strip()

    def model_dump_config(
        self,
        include_shell_commands: bool = False,
    ) -> dict[str, t.Any]:
        """Dump the model as a configuration dictionary.

        Parameters
        ----------
        include_shell_commands : bool, optional
            Whether to include shell_command_after in the output, by default False

        Returns
        -------
        dict[str, t.Any]
            Configuration dictionary
        """
        exclude_fields = set()
        if not include_shell_commands and self.shell_command_after is None:
            exclude_fields.add("shell_command_after")

        data = self.model_dump(exclude=exclude_fields, exclude_none=True)

        # Convert pathlib.Path to string for serialization
        if "path" in data and isinstance(data["path"], pathlib.Path):
            data["path"] = str(data["path"])

        return data


class ConfigSectionDictModel(RootModel[dict[str, RepositoryModel]]):
    """Configuration section model (dictionary of repositories).

    A ConfigSectionDictModel represents a section of the configuration file,
    containing a dictionary of repository configurations keyed by repository name.
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
            Repository model
        """
        return self.root[key]

    def keys(self) -> t.KeysView[str]:
        """Get repository names.

        Returns
        -------
        t.KeysView[str]
            Repository names
        """
        return self.root.keys()

    def items(self) -> t.ItemsView[str, RepositoryModel]:
        """Get repository items.

        Returns
        -------
        t.ItemsView[str, RepositoryModel]
            Repository items (name, model)
        """
        return self.root.items()

    def values(self) -> t.ValuesView[RepositoryModel]:
        """Get repository models.

        Returns
        -------
        t.ValuesView[RepositoryModel]
            Repository models
        """
        return self.root.values()


class ConfigDictModel(RootModel[dict[str, ConfigSectionDictModel]]):
    """Configuration model (dictionary of sections).

    A ConfigDictModel represents the entire configuration file,
    containing a dictionary of sections keyed by section name.
    Each section contains a dictionary of repository configurations.
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
            Section model
        """
        return self.root[key]

    def keys(self) -> t.KeysView[str]:
        """Get section names.

        Returns
        -------
        t.KeysView[str]
            Section names
        """
        return self.root.keys()

    def items(self) -> t.ItemsView[str, ConfigSectionDictModel]:
        """Get section items.

        Returns
        -------
        t.ItemsView[str, ConfigSectionDictModel]
            Section items (name, model)
        """
        return self.root.items()

    def values(self) -> t.ValuesView[ConfigSectionDictModel]:
        """Get section models.

        Returns
        -------
        t.ValuesView[ConfigSectionDictModel]
            Section models
        """
        return self.root.values()


# Type alias for raw repository data
RawRepoDataType = t.Union[str, dict[str, t.Any]]


class RawRepositoryModel(BaseModel):
    """Raw repository configuration model before validation and path resolution.

    This model validates the raw data from the configuration file before
    resolving paths and converting to the full RepositoryModel.

    Parameters
    ----------
    vcs : Literal["git", "hg", "svn"]
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
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    @model_validator(mode="after")
    def validate_vcs_specific_fields(self) -> RawRepositoryModel:
        """Validate VCS-specific fields.

        Ensures that certain fields only appear with the appropriate VCS type.
        For example, remotes are only valid for Git repositories.

        Returns
        -------
        RawRepositoryModel
            The validated repository model

        Raises
        ------
        ValueError
            If remotes are provided for non-Git repositories
        """
        if self.vcs != VCSType.GIT.value and self.remotes:
            raise ValueError(REMOTES_GIT_ONLY_ERROR)
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
            Validation context information

        Returns
        -------
        str
            Validated URL

        Raises
        ------
        ValueError
            If URL is empty or contains only whitespace
        """
        if not v:
            raise ValueError(URL_EMPTY_ERROR)
        if v.strip() == "":
            raise ValueError(URL_WHITESPACE_ERROR)
        return v.strip()

    @field_validator("remotes")
    @classmethod
    def validate_remotes(
        cls,
        v: dict[str, dict[str, t.Any]] | None,
        info: ValidationInfo,
    ) -> dict[str, dict[str, t.Any]] | None:
        """Validate remotes configuration.

        Parameters
        ----------
        v : dict[str, dict[str, t.Any]] | None
            Remotes configuration to validate
        info : ValidationInfo
            Validation context information

        Returns
        -------
        dict[str, dict[str, t.Any]] | None
            Validated remotes configuration or None

        Raises
        ------
        ValueError
            If remotes are provided for non-Git repositories or
            if remote configuration is invalid
        """
        if v is None:
            return None

        # Check that remotes are only used with Git repositories
        values = info.data
        if "vcs" in values and values["vcs"] != VCSType.GIT.value:
            raise ValueError(REMOTES_GIT_ONLY_ERROR)

        # Validate each remote
        for remote_name, remote_config in v.items():
            if not isinstance(remote_config, dict):
                error_msg = f"Remote {remote_name}: {INVALID_REMOTE_ERROR}"
                raise TypeError(error_msg)

            # Required fields
            if "url" not in remote_config:
                error_msg = f"Remote {remote_name}: Missing required field 'url'"
                raise ValueError(error_msg)

            # URL must not be empty
            if not remote_config.get("url", "").strip():
                error_msg = f"Remote {remote_name}: {URL_EMPTY_ERROR}"
                raise ValueError(error_msg)

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
            Validated shell commands or None

        Raises
        ------
        ValueError
            If shell commands are invalid
        """
        if v is None:
            return None

        shell_cmd_error = "Shell commands must be strings"
        if not all(isinstance(cmd, str) for cmd in v):
            raise ValueError(shell_cmd_error)

        # Remove empty commands and strip whitespace
        return [cmd.strip() for cmd in v if cmd.strip()]


# Create pre-instantiated TypeAdapters for better performance
class RawConfigSectionDictModel(RootModel[dict[str, RawRepoDataType]]):
    """Raw configuration section model before validation.

    Represents a section of the raw configuration file before validation.
    """


class RawConfigDictModel(RootModel[dict[str, RawConfigSectionDictModel]]):
    """Raw configuration model before validation and processing.

    Represents the entire raw configuration file before validation.
    """


# Cache the type adapters for better performance
@lru_cache(maxsize=8)
def get_repo_validator() -> TypeAdapter[RawRepositoryModel]:
    """Get or create a TypeAdapter for RawRepositoryModel.

    Returns
    -------
    TypeAdapter[RawRepositoryModel]
        Type adapter for repository validation
    """
    return TypeAdapter(RawRepositoryModel)


# Cache the type adapter for better performance
@lru_cache(maxsize=8)
def get_config_validator() -> TypeAdapter[RawConfigDictModel]:
    """Get or create a TypeAdapter for RawConfigDictModel.

    Returns
    -------
    TypeAdapter[RawConfigDictModel]
        Type adapter for configuration validation
    """
    return TypeAdapter(RawConfigDictModel)


# Pre-instantiate frequently used TypeAdapters for better performance
repo_validator = get_repo_validator()
config_validator = get_config_validator()


def is_valid_repo_config(config: dict[str, t.Any]) -> TypeGuard[dict[str, t.Any]]:
    """Check if a repository configuration is valid.

    Parameters
    ----------
    config : dict[str, t.Any]
        Repository configuration to validate

    Returns
    -------
    TypeGuard[dict[str, t.Any]]
        True if the configuration is valid
    """
    try:
        # Use the pre-instantiated TypeAdapter
        repo_validator.validate_python(config)
    except Exception:
        return False
    else:
        return True


def is_valid_config_dict(config: dict[str, t.Any]) -> TypeGuard[dict[str, t.Any]]:
    """Check if a configuration dictionary is valid.

    Parameters
    ----------
    config : dict[str, t.Any]
        Configuration dictionary to validate

    Returns
    -------
    TypeGuard[dict[str, t.Any]]
        True if the configuration is valid
    """
    try:
        sections = {}
        for section_name, section_repos in config.items():
            section_dict = {}
            for repo_name, repo_config in section_repos.items():
                # Handle string URLs (convert to dict)
                if isinstance(repo_config, str):
                    repo_config = {
                        "url": repo_config,
                        "vcs": VCSType.GIT.value,  # Default to git
                        "name": repo_name,
                        "path": repo_name,  # Use name as default path
                    }
                # Add name if missing
                if isinstance(repo_config, dict) and "name" not in repo_config:
                    repo_config = {**repo_config, "name": repo_name}
                section_dict[repo_name] = repo_config
            sections[section_name] = section_dict

        # Use the pre-instantiated TypeAdapter for validation
        config_validator.validate_python(sections)
    except Exception:
        return False
    else:
        return True


def convert_raw_to_validated(
    raw_config: RawConfigDictModel,
    cwd: t.Callable[[], pathlib.Path] = pathlib.Path.cwd,
) -> ConfigDictModel:
    """Convert raw configuration to validated configuration.

    Parameters
    ----------
    raw_config : RawConfigDictModel
        Raw configuration from file
    cwd : t.Callable[[], pathlib.Path], optional
        Function to get current working directory, by default pathlib.Path.cwd

    Returns
    -------
    ConfigDictModel
        Validated configuration
    """
    validated_sections = {}

    for section_name, section in raw_config.root.items():
        validated_repos = {}

        for repo_name, repo_config in section.root.items():
            # Convert string URLs to full config
            if isinstance(repo_config, str):
                url = repo_config
                repo_config = {
                    "vcs": VCSType.GIT.value,  # Default to git
                    "url": url,
                    "name": repo_name,
                    "path": repo_name,  # Default path is repo name
                }

            # Ensure name is set from the config key if not provided
            if isinstance(repo_config, dict) and "name" not in repo_config:
                repo_config = {**repo_config, "name": repo_name}

            # Validate raw repository config
            raw_repo = RawRepositoryModel.model_validate(repo_config)

            # Resolve path: if relative, base on CWD
            path_str = raw_repo.path
            path = pathlib.Path(os.path.expandvars(path_str))
            if not path.is_absolute():
                path = cwd() / path

            # Handle remotes if present
            remotes = None
            if raw_repo.remotes:
                validated_remotes = {}
                for remote_name, remote_config in raw_repo.remotes.items():
                    remote_model = GitRemote.model_validate(remote_config)
                    validated_remotes[remote_name] = remote_model
                remotes = validated_remotes

            # Create validated repository model
            repo = RepositoryModel(
                vcs=raw_repo.vcs,
                name=raw_repo.name,
                path=path,
                url=raw_repo.url,
                remotes=remotes,
                shell_command_after=raw_repo.shell_command_after,
            )

            validated_repos[repo_name] = repo

        validated_sections[section_name] = ConfigSectionDictModel(root=validated_repos)

    return ConfigDictModel(root=validated_sections)


def validate_config_from_json(
    json_data: str | bytes,
) -> tuple[bool, dict[str, t.Any] | str]:
    """Validate configuration from JSON string or bytes.

    Parameters
    ----------
    json_data : str | bytes
        JSON data to validate

    Returns
    -------
    tuple[bool, dict[str, t.Any] | str]
        Tuple of (is_valid, data_or_error_message)
    """
    try:
        import json

        # Parse JSON
        if isinstance(json_data, bytes):
            config_dict = json.loads(json_data.decode("utf-8"))
        else:
            config_dict = json.loads(json_data)

        # Basic type checking
        if not isinstance(config_dict, dict):
            return False, "Configuration must be a dictionary"

        # Validate using Pydantic
        raw_config = RawConfigDictModel.model_validate(config_dict)
        validated_config = convert_raw_to_validated(raw_config)

        # If validation succeeded, return the validated config
        return True, validated_config.model_dump()
    except Exception as e:
        # Return error message on failure
        return False, str(e)
