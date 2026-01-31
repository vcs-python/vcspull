"""Typings for vcspull.

Configuration Object Graph
--------------------------

The user-facing ``.vcspull.yaml`` maps *workspace roots* (parent directories)
to named repositories.  For example::

    ~/study/c:
      cpython:
        repo: git+https://github.com/python/cpython.git
      tmux:
        repo: git+https://github.com/tmux/tmux.git

    ~/work/js:
      react:
        repo: https://github.com/facebook/react.git
      vite:
        repo: https://github.com/vitejs/vite.git

In Python we model this as:

``WorkspaceRoot`` - Mapping of repository name to its configuration
``WorkspaceRoots`` - Mapping of workspace root path to ``WorkspaceRoot``

When the configuration is parsed we preserve the original key string, but
``WorkspaceRoot`` terminology is used consistently across the codebase.
"""

from __future__ import annotations

import pathlib
import typing as t
from typing import TypeAlias

from typing_extensions import NotRequired, TypedDict

if t.TYPE_CHECKING:
    from libvcs._internal.types import StrPath, VCSLiteral
    from libvcs.sync.git import GitSyncRemoteDict


class WorktreeConfigDict(TypedDict):
    """Configuration for a single git worktree.

    Worktrees allow checking out multiple branches/tags/commits of a repository
    simultaneously in separate directories.

    Exactly one of ``tag``, ``branch``, or ``commit`` must be specified.

    Examples
    --------
    Tag worktree (immutable, detached HEAD)::

        {"dir": "../myproject-v1.0", "tag": "v1.0.0"}

    Branch worktree (updatable)::

        {"dir": "../myproject-dev", "branch": "develop"}

    Commit worktree (immutable, detached HEAD)::

        {"dir": "../myproject-abc", "commit": "abc123"}
    """

    dir: str
    """Path for the worktree (relative to workspace root or absolute)."""

    tag: NotRequired[str | None]
    """Tag to checkout (creates detached HEAD)."""

    branch: NotRequired[str | None]
    """Branch to checkout (can be updated/pulled)."""

    commit: NotRequired[str | None]
    """Commit SHA to checkout (creates detached HEAD)."""

    detach: NotRequired[bool | None]
    """Force detached HEAD. Default: True for tag/commit, False for branch."""

    lock: NotRequired[bool | None]
    """Lock the worktree to prevent accidental removal."""

    lock_reason: NotRequired[str | None]
    """Reason for locking (requires lock=True)."""


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
    workspace_root: str
    remotes: NotRequired[GitSyncRemoteDict | None]
    shell_command_after: NotRequired[list[str] | None]
    worktrees: NotRequired[list[WorktreeConfigDict] | None]


ConfigDir = dict[str, ConfigDict]
Config = dict[str, ConfigDir]

# ---------------------------------------------------------------------------
# Workspace root aliases
# ---------------------------------------------------------------------------

WorkspaceRoot = ConfigDir

WorkspaceRoots: TypeAlias = dict[pathlib.Path, WorkspaceRoot]
