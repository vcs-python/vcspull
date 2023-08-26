import pathlib
import typing as t

from libvcs._internal.types import StrPath, VCSLiteral
from libvcs.sync.git import GitSyncRemoteDict
from typing_extensions import NotRequired, TypedDict


class RawConfigDict(t.TypedDict):
    vcs: VCSLiteral
    name: str
    dir: StrPath
    url: str
    remotes: GitSyncRemoteDict


RawConfigDir = dict[str, RawConfigDict]
RawConfig = dict[str, RawConfigDir]


class ConfigDict(TypedDict):
    vcs: t.Optional[VCSLiteral]
    name: str
    dir: pathlib.Path
    url: str
    remotes: NotRequired[t.Optional[GitSyncRemoteDict]]
    shell_command_after: NotRequired[t.Optional[list[str]]]


ConfigDir = dict[str, ConfigDict]
Config = dict[str, ConfigDir]
