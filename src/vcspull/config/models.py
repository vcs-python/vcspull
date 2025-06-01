"""Configuration models for VCSPull.

This module defines Pydantic models for the VCSPull configuration format.
"""

from __future__ import annotations

import datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Repository(BaseModel):
    """Repository configuration model."""

    name: str | None = None
    url: str
    path: str
    vcs: str | None = None
    remotes: dict[str, str] = Field(default_factory=dict)
    rev: str | None = None
    web_url: str | None = None

    @field_validator("path")
    @classmethod
    def validate_path(cls, v: str) -> str:
        """Normalize repository path.

        Parameters
        ----------
        v : str
            The path to normalize

        Returns
        -------
        str
            The normalized path
        """
        path_obj = Path(v).expanduser().resolve()
        return str(path_obj)


class Settings(BaseModel):
    """Global settings model."""

    sync_remotes: bool = True
    default_vcs: str | None = None
    depth: int | None = None


class VCSPullConfig(BaseModel):
    """Root configuration model."""

    settings: Settings = Field(default_factory=Settings)
    repositories: list[Repository] = Field(default_factory=list)
    includes: list[str] = Field(default_factory=list)

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "settings": {
                        "sync_remotes": True,
                        "default_vcs": "git",
                    },
                    "repositories": [
                        {
                            "name": "example-repo",
                            "url": "https://github.com/user/repo.git",
                            "path": "~/code/repo",
                            "vcs": "git",
                        },
                    ],
                    "includes": [
                        "~/other-config.yaml",
                    ],
                },
            ],
        },
    )


class LockedRepository(BaseModel):
    """Locked repository information.

    This model represents a repository with its revision locked to a specific version.
    """

    name: str | None = None
    path: str
    vcs: str
    url: str
    rev: str
    locked_at: datetime.datetime = Field(default_factory=datetime.datetime.now)

    @field_validator("path")
    @classmethod
    def validate_path(cls, v: str) -> str:
        """Normalize repository path.

        Parameters
        ----------
        v : str
            The path to normalize

        Returns
        -------
        str
            The normalized path
        """
        path_obj = Path(v).expanduser().resolve()
        return str(path_obj)


class LockFile(BaseModel):
    """Lock file model.

    This model represents the lock file format for VCSPull, which contains
    locked revisions for repositories to ensure consistent states across environments.
    """

    version: str = "1.0.0"
    created_at: datetime.datetime = Field(default_factory=datetime.datetime.now)
    repositories: list[LockedRepository] = Field(default_factory=list)

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "version": "1.0.0",
                    "created_at": "2023-03-09T12:00:00",
                    "repositories": [
                        {
                            "name": "example-repo",
                            "path": "~/code/repo",
                            "vcs": "git",
                            "url": "https://github.com/user/repo.git",
                            "rev": "a1b2c3d4e5f6",
                            "locked_at": "2023-03-09T12:00:00",
                        },
                    ],
                },
            ],
        },
    )
