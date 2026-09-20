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
from typing import TypeAlias, TypedDict

if t.TYPE_CHECKING:
    from libvcs._internal.types import StrPath, VCSLiteral
    from libvcs.sync.git import GitSyncRemoteDict


class GitOptionsDict(TypedDict, total=False):
    """Git clone and transport options, matching ``libvcs.GitOptions``."""

    depth: int | None
    filter: str | dict[str, t.Any] | list[t.Any] | None
    tls_verify: bool


class HgOptionsDict(TypedDict, total=False):
    """Mercurial clone and transport options, matching ``libvcs.HgOptions``."""

    ssh: str | None
    remote_cmd: str | None
    pull: bool
    stream: bool
    tls_verify: bool


class SvnOptionsDict(TypedDict, total=False):
    """Subversion checkout and transport options, matching ``libvcs.SvnOptions``."""

    username: str | None
    password: str | None
    depth: t.Literal["empty", "files", "immediates", "infinity"] | None
    trust_server_cert: bool
    ignore_externals: bool


class SyncPolicyDict(TypedDict, total=False):
    """Policy for configured-target drift and uncommitted changes."""

    drift: t.Literal["keep", "follow", "warn"]
    """Keep the current ref, follow the configured target, or report drift."""

    dirty: t.Literal["abort", "preserve", "discard"]
    """Abort on local changes, preserve them, or discard with confirmation."""


class WorkingCopyConfigDict(TypedDict, total=False):
    """Exactly one native target, with an optional fetch remote and sync policy."""

    branch: str
    """Named branch to follow."""

    tag: str
    """Named tag to check out without following a branch."""

    commit: str
    """Commit or changeset to check out without following a branch."""

    rev: str | int
    """Native revision expression, including a numeric Subversion revision."""

    remote: str
    """Fetch source alias, independent of the configured push URL."""

    sync: SyncPolicyDict
    """Drift and dirty-state policy for this checkout."""


class _WorktreeConfigDictRequired(TypedDict):
    """Configuration for a single git worktree.

    Worktrees allow checking out multiple branches/tags/commits of a repository
    simultaneously in separate directories.

    Exactly one of ``tag``, ``branch``, ``commit``, or ``rev`` must be specified.

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


class _WorktreeConfigDictOptional(WorkingCopyConfigDict, total=False):
    """Optional configuration for a single git worktree."""

    detach: bool
    """Force detached HEAD. Default: True for tag/commit, False for branch."""

    lock: bool
    """Lock the worktree to prevent accidental removal."""

    lock_reason: str
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
    """Legacy tuning and entry policy accepted by the migration reader.

    Use ``working_copy``, the backend block, and entry-level pin fields in
    new configurations. ``vcspull migrate`` rewrites these legacy keys.
    """

    rev: str | int | None
    """Commit, tag, or branch to check out on sync (libvcs ``rev``).

    Distinct from ``pin``, which guards config mutation rather than pinning a
    git ref.
    """

    shallow: bool | None
    """If ``True``, clone with ``--depth 1`` on sync (``git.depth: 1``).

    Sugar for ``depth: 1``; ``depth`` wins when both are set.
    """

    depth: int | None
    """Clone with history truncated to ``depth`` commits (``git.depth``).

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


class RemoteURLsDict(TypedDict):
    """Separate fetch and push addresses for a configured remote."""

    fetch_url: str
    """Address used to fetch repository history."""
    push_url: str
    """Address used for pushes, independent of the fetch address."""


class RepoEntryDict(TypedDict, total=False):
    """Serialized repository entry; either ``repo`` or ``url`` is required.

    ``url`` takes precedence when both are present. Backend blocks match the
    inferred or declared VCS. Legacy keys remain available for migration.
    """

    repo: str
    """Repository URL; `url` wins when both aliases are supplied."""
    url: str
    """Alternate repository URL, taking precedence over `repo`."""
    name: str
    """Override the repository name taken from its workspace entry key."""
    path: str
    """Override the default checkout path computed from the workspace and name."""
    workspace_root: str
    """Override the workspace label attached to the resolved entry."""
    vcs: t.Literal["git", "hg", "svn"] | None
    """Declare a backend when the repository URL is ambiguous."""
    working_copy: WorkingCopyConfigDict
    """Target and drift/dirty policy for the main checkout."""
    worktrees: list[WorktreeConfigDict] | None
    """Additional Git checkouts with their own target and sync policy."""
    remotes: dict[str, str | RemoteURLsDict]
    """Named fetch and push URLs, separate from checkout targets."""
    shell_command_after: str | list[str] | None
    """Commands to run after synchronization; null disables the hook."""
    git: GitOptionsDict
    """Git clone and transport options."""
    hg: HgOptionsDict
    """Mercurial clone and transport options."""
    svn: SvnOptionsDict
    """Subversion checkout and transport options."""
    pin: bool | RepoPinDict
    """Prevent every config rewrite, or only the named operations."""
    pin_reason: str | None
    """Explanation displayed when a pinned entry is skipped."""
    allow_overwrite: bool
    """Set false to protect the entry from import URL replacement."""
    metadata: dict[str, t.Any]
    """JSON-compatible annotations, including import provenance."""
    rev: str | int | None
    """Legacy target; migrate to working_copy.rev."""
    shallow: bool | None
    """Legacy shallow clone request; migrate true to git.depth: 1."""
    depth: int | None
    """Legacy Git history depth; migrate to git.depth."""
    options: RepoOptionsDict
    """Legacy mixed tuning and entry policy; run vcspull migrate."""
    git_options: GitOptionsDict
    """Legacy alias for git; canonical git values take precedence."""
    hg_options: HgOptionsDict
    """Legacy alias for hg; canonical hg values take precedence."""
    svn_options: SvnOptionsDict
    """Legacy alias for svn; canonical svn values take precedence."""


class RawConfigDict(t.TypedDict):
    """Configuration dictionary without any type marshalling or variable resolution.

    Counterpart to :class:`ConfigDict` in the shape a config file supplies:
    paths stay as written and shorthand entries are not yet expanded.

    Attributes
    ----------
    vcs : VCSLiteral
        Version control system backing the repository — ``"git"``, ``"hg"``,
        or ``"svn"``.
    name : str
        Repository name, taken from the key it sits under within its
        workspace root.
    path : StrPath
        Checkout location as written, still a :class:`str` or
        :class:`os.PathLike` carrying any ``~`` or environment variable.
    url : str
        VCS URL in vcspull format, e.g. ``git+git@github.com:user/repo.git``.
    remotes : GitSyncRemoteDict
        Extra git remotes to keep in sync, keyed by remote name.
    """

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
    working_copy: WorkingCopyConfigDict
    git: GitOptionsDict
    hg: HgOptionsDict
    svn: SvnOptionsDict
    pin: bool | RepoPinDict
    pin_reason: str | None
    allow_overwrite: bool
    metadata: dict[str, t.Any]


class ConfigDict(_ConfigDictRequired, _ConfigDictOptional):
    """Configuration map for vcspull after shorthands and variables resolved."""


ConfigDir = dict[str, ConfigDict]
Config = dict[str, ConfigDir]

# ---------------------------------------------------------------------------
# Workspace root aliases
# ---------------------------------------------------------------------------

WorkspaceRoot = ConfigDir

WorkspaceRoots: TypeAlias = dict[pathlib.Path, WorkspaceRoot]
