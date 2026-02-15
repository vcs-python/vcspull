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

import enum
import pathlib
import typing as t
from typing import TypeAlias, TypedDict

if t.TYPE_CHECKING:
    from libvcs._internal.types import StrPath, VCSLiteral
    from libvcs.sync.git import GitSyncRemoteDict


class ConfigStyle(enum.Enum):
    """Output style for repository entries in vcspull configuration files.

    Examples
    --------
    >>> from vcspull.types import ConfigStyle
    >>> ConfigStyle("concise")
    <ConfigStyle.CONCISE: 'concise'>
    >>> ConfigStyle.STANDARD.value
    'standard'
    """

    CONCISE = "concise"
    STANDARD = "standard"
    VERBOSE = "verbose"


RawRepoEntry: TypeAlias = "str | dict[str, t.Any]"


class _WorktreeConfigDictRequired(TypedDict):
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


class _WorktreeConfigDictOptional(TypedDict, total=False):
    """Optional configuration for a single git worktree."""

    tag: str | None
    """Tag to checkout (creates detached HEAD)."""

    branch: str | None
    """Branch to checkout (can be updated/pulled)."""

    commit: str | None
    """Commit SHA to checkout (creates detached HEAD)."""

    detach: bool | None
    """Force detached HEAD. Default: True for tag/commit, False for branch."""

    lock: bool | None
    """Lock the worktree to prevent accidental removal."""

    lock_reason: str | None
    """Reason for locking. If provided, implies lock=True."""


class WorktreeConfigDict(
    _WorktreeConfigDictRequired,
    _WorktreeConfigDictOptional,
):
    """Configuration for a single git worktree."""


RepoPinDict = TypedDict(
    "RepoPinDict",
    {
        "add": bool,
        "discover": bool,
        "fmt": bool,
        "import": bool,
        "merge": bool,
    },
    total=False,
)
"""Per-operation pin flags for a repository entry.

Unspecified keys default to ``False`` (not pinned).

Note: Distinct from ``WorktreeConfigDict.lock`` which prevents git worktree
removal at the filesystem level. ``RepoPinDict`` controls vcspull config
mutation policy only.

Examples
--------
Pin only import::

    options:
      pin:
        import: true

Pin import and fmt::

    options:
      pin:
        import: true
        fmt: true
"""


class RepoOptionsDict(TypedDict, total=False):
    """Per-repository options stored under the ``options:`` key in a repo entry.

    Two groups of keys live here:

    - **Sync tuning** (``rev``, ``shallow``, ``depth``) — forwarded to libvcs to
      shape how the checkout is cloned/updated.
    - **Mutation policy** (``pin``, ``allow_overwrite``, ``pin_reason``) — guards
      whether vcspull's commands may rewrite this config entry.

    Note: ``pin`` here controls vcspull config mutation. It is distinct from
    ``WorktreeConfigDict.lock`` which prevents git worktree removal.

    Examples
    --------
    Pin to a ref and clone with a small history window::

        options:
          rev: v1.2.3
          depth: 50

    Pin all operations::

        options:
          pin: true
          pin_reason: "pinned to upstream"

    Pin only import (prevent ``--sync`` from replacing URL)::

        options:
          pin:
            import: true

    Shorthand form — equivalent to ``pin: {import: true}``::

        options:
          allow_overwrite: false
    """

    rev: str
    """Commit, tag, or branch to check out on sync (libvcs ``rev``).

    Distinct from ``pin``, which guards config mutation rather than pinning a
    git ref.
    """

    shallow: bool
    """If ``True``, clone with ``--depth 1`` on sync (libvcs ``git_shallow``).

    Sugar for ``depth: 1``; ``depth`` wins when both are set.
    """

    depth: int
    """Clone with history truncated to ``depth`` commits (libvcs ``depth``).

    Takes precedence over ``shallow``.
    """

    pin: bool | RepoPinDict
    """``True`` pins all ops; a mapping pins specific ops only.

    Unspecified keys in the mapping default to ``False`` (not pinned).
    """

    allow_overwrite: bool
    """If ``False``, shorthand for ``pin: {import: true}``.

    Pins only the import operation.
    """

    pin_reason: str | None
    """Human-readable reason shown in log output when an op is skipped due to pin."""


class _RepoEntryDictRequired(TypedDict):
    """Raw per-repository entry as written to .vcspull.yaml.

    Examples
    --------
    Minimal entry::

        repo: git+git@github.com:user/myrepo.git

    Pinned to a ref and shallow-cloned::

        repo: git+git@github.com:user/myrepo.git
        options:
          rev: v1.2.3
          depth: 50

    With pin options::

        repo: git+git@github.com:user/myrepo.git
        options:
          pin:
            import: true
          pin_reason: "pinned to company fork"
    """

    repo: str
    """VCS URL in vcspull format, e.g. ``git+git@github.com:user/repo.git``."""


class _RepoEntryDictOptional(TypedDict, total=False):
    """Optional raw per-repository entry fields."""

    rev: str
    """Deprecated top-level form of ``options.rev``; still read, with a warning.

    Run ``vcspull migrate`` to relocate it under ``options:``.
    """

    shallow: bool
    """Deprecated top-level form of ``options.shallow``; still read, with a warning.

    Run ``vcspull migrate`` to relocate it under ``options:``.
    """

    options: RepoOptionsDict
    """Sync tuning (``rev``/``shallow``/``depth``) plus mutation policy."""


class RepoEntryDict(_RepoEntryDictRequired, _RepoEntryDictOptional):
    """Raw per-repository entry as written to .vcspull.yaml."""


class RawConfigDict(t.TypedDict):
    """Configuration dictionary without any type marshalling or variable resolution."""

    vcs: VCSLiteral
    name: str
    path: StrPath
    url: str
    remotes: GitSyncRemoteDict


RawConfigDir = dict[str, RawConfigDict]
RawConfig = dict[str, RawConfigDir]


class _ConfigDictRequired(TypedDict):
    """Required fields for resolved vcspull configuration entries."""

    vcs: VCSLiteral | None
    name: str
    path: pathlib.Path
    url: str
    workspace_root: str


class _ConfigDictOptional(TypedDict, total=False):
    """Optional fields for resolved vcspull configuration entries."""

    rev: str | None
    shallow: bool | None
    depth: int | None
    remotes: GitSyncRemoteDict | None
    shell_command_after: list[str] | None
    worktrees: list[WorktreeConfigDict] | None
    options: RepoOptionsDict


class ConfigDict(_ConfigDictRequired, _ConfigDictOptional):
    """Configuration map for vcspull after shorthands and variables resolved."""


ConfigDir = dict[str, ConfigDict]
Config = dict[str, ConfigDir]

# ---------------------------------------------------------------------------
# Workspace root aliases
# ---------------------------------------------------------------------------

WorkspaceRoot = ConfigDir

WorkspaceRoots: TypeAlias = dict[pathlib.Path, WorkspaceRoot]
