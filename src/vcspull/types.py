"""Type definitions for VCSPull."""

from __future__ import annotations

import typing as t


class ConfigDict(t.TypedDict, total=False):
    """TypedDict for repository configuration dictionary.

    This is used primarily in test fixtures and legacy code paths.
    """

    vcs: str
    name: str
    path: t.Any  # Can be str or Path
    url: str
    remotes: dict[str, t.Any]  # Can contain various remote types
    rev: str
    shell_command_after: str | list[str]


class Config(t.TypedDict):
    """TypedDict for config dictionary.

    Used for untyped access to config data before parsing.
    """

    settings: dict[str, t.Any] | None
    repositories: list[dict[str, t.Any]] | None
    includes: list[str] | None
