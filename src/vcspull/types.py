"""Typings for vcspull."""

from __future__ import annotations

import typing as t

from typing_extensions import NotRequired, TypedDict

if t.TYPE_CHECKING:
    import pathlib

    from libvcs._internal.types import StrPath, VCSLiteral
    from libvcs.sync.git import GitSyncRemoteDict


class RawConfigDict(t.TypedDict):
    """Configuration dictionary without any type marshalling or variable resolution."""

    vcs: VCSLiteral
    name: str
    path: StrPath
    url: str
    remotes: GitSyncRemoteDict


RawConfigDir = dict[str, RawConfigDict]
RawConfig = dict[str, RawConfigDir]


class ConfigDict(TypedDict):
    """Configuration map for vcspull after shorthands and variables resolved."""

    vcs: VCSLiteral | None
    name: str
    path: pathlib.Path
    url: str
    remotes: NotRequired[GitSyncRemoteDict | None]
    shell_command_after: NotRequired[list[str] | None]


ConfigDir = dict[str, ConfigDict]
Config = dict[str, ConfigDir]
