"""Core worktree synchronization logic for vcspull."""

from __future__ import annotations

import enum
import logging
import pathlib
import subprocess
from dataclasses import dataclass, field

from vcspull import exc
from vcspull.types import WorktreeConfigDict

log = logging.getLogger(__name__)


class WorktreeAction(enum.Enum):
    """Actions that can be taken on a worktree during sync."""

    CREATE = "create"
    """Worktree doesn't exist, will be created."""

    UPDATE = "update"
    """Branch worktree exists, will pull latest."""

    UNCHANGED = "unchanged"
    """Tag/commit worktree exists, already at target."""

    BLOCKED = "blocked"
    """Worktree has uncommitted changes (safety)."""

    ERROR = "error"
    """Operation failed (ref not found, permission, etc.)."""


@dataclass
class WorktreePlanEntry:
    """Planning information for a single worktree operation."""

    worktree_path: pathlib.Path
    """Absolute path where the worktree will be/is located."""

    ref_type: str
    """Type of reference: 'tag', 'branch', or 'commit'."""

    ref_value: str
    """The actual tag name, branch name, or commit SHA."""

    action: WorktreeAction
    """What action will be/was taken."""

    detail: str | None = None
    """Human-readable explanation of the action."""

    error: str | None = None
    """Error message if action is ERROR."""

    exists: bool = False
    """Whether the worktree currently exists."""

    is_dirty: bool = False
    """Whether the worktree has uncommitted changes."""

    current_ref: str | None = None
    """Current HEAD reference if worktree exists."""


@dataclass
class WorktreeSyncResult:
    """Result of a worktree sync operation."""

    entries: list[WorktreePlanEntry] = field(default_factory=list)
    """List of worktree plan entries."""

    created: int = 0
    """Number of worktrees created."""

    updated: int = 0
    """Number of worktrees updated."""

    unchanged: int = 0
    """Number of worktrees left unchanged."""

    blocked: int = 0
    """Number of worktrees blocked due to dirty state."""

    errors: int = 0
    """Number of worktrees that encountered errors."""


def _get_ref_type_and_value(
    wt_config: WorktreeConfigDict,
) -> tuple[str, str] | None:
    """Extract the reference type and value from worktree config.

    Returns
    -------
    tuple[str, str] | None
        Tuple of (ref_type, ref_value) or None if invalid config.
    """
    tag = wt_config.get("tag")
    branch = wt_config.get("branch")
    commit = wt_config.get("commit")

    refs_specified = sum(1 for ref in [tag, branch, commit] if ref is not None)

    if refs_specified == 0:
        return None
    if refs_specified > 1:
        return None

    if tag:
        return ("tag", tag)
    if branch:
        return ("branch", branch)
    if commit:
        return ("commit", commit)

    return None


def validate_worktree_config(wt_config: WorktreeConfigDict) -> None:
    """Validate a worktree configuration dictionary.

    Parameters
    ----------
    wt_config : WorktreeConfigDict
        The worktree configuration to validate.

    Raises
    ------
    WorktreeConfigError
        If the configuration is invalid.
    """
    if "dir" not in wt_config or not wt_config["dir"]:
        msg = "Worktree config missing required 'dir' field"
        raise exc.WorktreeConfigError(msg)

    ref_info = _get_ref_type_and_value(wt_config)
    if ref_info is None:
        tag = wt_config.get("tag")
        branch = wt_config.get("branch")
        commit = wt_config.get("commit")
        refs_specified = sum(1 for ref in [tag, branch, commit] if ref is not None)

        if refs_specified == 0:
            msg = "Worktree config must specify one of: tag, branch, or commit"
            raise exc.WorktreeConfigError(msg)
        msg = "Worktree config cannot specify multiple refs (tag, branch, commit)"
        raise exc.WorktreeConfigError(msg)


def _is_worktree_dirty(worktree_path: pathlib.Path) -> bool:
    """Check if a worktree has uncommitted changes.

    Parameters
    ----------
    worktree_path : pathlib.Path
        Path to the worktree directory.

    Returns
    -------
    bool
        True if the worktree has uncommitted changes.
    """
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=worktree_path,
            capture_output=True,
            text=True,
            check=False,
        )
        # If there's any output, the worktree is dirty
        return bool(result.stdout.strip())
    except (FileNotFoundError, OSError):
        # If we can't check, assume clean to avoid blocking unnecessarily
        return False


def _ref_exists(repo_path: pathlib.Path, ref: str, ref_type: str) -> bool:
    """Check if a reference exists in the repository.

    Parameters
    ----------
    repo_path : pathlib.Path
        Path to the main repository.
    ref : str
        The reference to check.
    ref_type : str
        Type of reference: 'tag', 'branch', or 'commit'.

    Returns
    -------
    bool
        True if the reference exists.
    """
    try:
        if ref_type == "tag":
            result = subprocess.run(
                ["git", "rev-parse", f"refs/tags/{ref}"],
                cwd=repo_path,
                capture_output=True,
                check=False,
            )
        elif ref_type == "branch":
            # Check both local and remote branches
            result = subprocess.run(
                ["git", "rev-parse", "--verify", ref],
                cwd=repo_path,
                capture_output=True,
                check=False,
            )
            if result.returncode != 0:
                # Try remote
                result = subprocess.run(
                    ["git", "rev-parse", "--verify", f"origin/{ref}"],
                    cwd=repo_path,
                    capture_output=True,
                    check=False,
                )
        else:  # commit
            result = subprocess.run(
                ["git", "rev-parse", "--verify", f"{ref}^{{commit}}"],
                cwd=repo_path,
                capture_output=True,
                check=False,
            )
    except (FileNotFoundError, OSError):
        return False
    else:
        return result.returncode == 0


def _get_worktree_head(worktree_path: pathlib.Path) -> str | None:
    """Get the current HEAD reference of a worktree.

    Parameters
    ----------
    worktree_path : pathlib.Path
        Path to the worktree.

    Returns
    -------
    str | None
        The HEAD reference or None if unable to determine.
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=worktree_path,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (FileNotFoundError, OSError):
        pass
    return None


def _worktree_exists(repo_path: pathlib.Path, worktree_path: pathlib.Path) -> bool:
    """Check if a worktree is registered in the repository.

    Parameters
    ----------
    repo_path : pathlib.Path
        Path to the main repository.
    worktree_path : pathlib.Path
        Path to check for worktree.

    Returns
    -------
    bool
        True if the worktree exists and is registered.
    """
    if not worktree_path.exists():
        return False

    # Check if it's a valid git worktree
    git_file = worktree_path / ".git"
    if git_file.is_file():
        return True
    if git_file.is_dir():
        # This is a regular repository, not a worktree
        return False

    return False


def _resolve_worktree_path(
    wt_config: WorktreeConfigDict,
    workspace_root: pathlib.Path,
) -> pathlib.Path:
    """Resolve the worktree path from config.

    Parameters
    ----------
    wt_config : WorktreeConfigDict
        Worktree configuration.
    workspace_root : pathlib.Path
        The workspace root directory.

    Returns
    -------
    pathlib.Path
        Absolute path for the worktree.
    """
    dir_path = pathlib.Path(wt_config["dir"])

    if dir_path.is_absolute():
        return dir_path.resolve()

    # Relative paths are resolved relative to workspace root
    return (workspace_root / dir_path).resolve()


def plan_worktree_sync(
    repo_path: pathlib.Path,
    worktrees_config: list[WorktreeConfigDict],
    workspace_root: pathlib.Path,
) -> list[WorktreePlanEntry]:
    """Plan worktree sync operations without executing them.

    Parameters
    ----------
    repo_path : pathlib.Path
        Path to the main repository.
    worktrees_config : list[WorktreeConfigDict]
        List of worktree configurations.
    workspace_root : pathlib.Path
        The workspace root directory for resolving relative paths.

    Returns
    -------
    list[WorktreePlanEntry]
        List of planned operations.
    """
    entries: list[WorktreePlanEntry] = []

    for wt_config in worktrees_config:
        try:
            validate_worktree_config(wt_config)
        except exc.WorktreeConfigError as e:
            entries.append(
                WorktreePlanEntry(
                    worktree_path=pathlib.Path(wt_config.get("dir", "unknown")),
                    ref_type="unknown",
                    ref_value="unknown",
                    action=WorktreeAction.ERROR,
                    error=str(e),
                )
            )
            continue

        ref_info = _get_ref_type_and_value(wt_config)
        assert ref_info is not None  # Validated above
        ref_type, ref_value = ref_info

        worktree_path = _resolve_worktree_path(wt_config, workspace_root)
        exists = _worktree_exists(repo_path, worktree_path)

        entry = WorktreePlanEntry(
            worktree_path=worktree_path,
            ref_type=ref_type,
            ref_value=ref_value,
            action=WorktreeAction.CREATE,
            exists=exists,
        )

        # Check if ref exists
        if not _ref_exists(repo_path, ref_value, ref_type):
            entry.action = WorktreeAction.ERROR
            entry.error = f"{ref_type.capitalize()} '{ref_value}' not found"
            entries.append(entry)
            continue

        if not exists:
            # Worktree doesn't exist, create it
            entry.action = WorktreeAction.CREATE
            entry.detail = f"will create {ref_type} worktree"
        else:
            # Worktree exists
            entry.current_ref = _get_worktree_head(worktree_path)
            entry.is_dirty = _is_worktree_dirty(worktree_path)

            if entry.is_dirty:
                entry.action = WorktreeAction.BLOCKED
                entry.detail = "worktree has uncommitted changes"
            elif ref_type == "branch":
                entry.action = WorktreeAction.UPDATE
                entry.detail = "branch worktree may be updated"
            else:
                # Tags and commits are immutable
                entry.action = WorktreeAction.UNCHANGED
                entry.detail = f"{ref_type} worktree already exists"

        entries.append(entry)

    return entries


def sync_worktree(
    repo_path: pathlib.Path,
    wt_config: WorktreeConfigDict,
    workspace_root: pathlib.Path,
    *,
    dry_run: bool = False,
) -> WorktreePlanEntry:
    """Synchronize a single worktree.

    Parameters
    ----------
    repo_path : pathlib.Path
        Path to the main repository.
    wt_config : WorktreeConfigDict
        Worktree configuration.
    workspace_root : pathlib.Path
        The workspace root directory.
    dry_run : bool
        If True, only plan without executing.

    Returns
    -------
    WorktreePlanEntry
        Result of the sync operation.
    """
    # Plan the operation
    entries = plan_worktree_sync(repo_path, [wt_config], workspace_root)
    entry = entries[0]

    if dry_run or entry.action in (WorktreeAction.ERROR, WorktreeAction.BLOCKED):
        return entry

    ref_info = _get_ref_type_and_value(wt_config)
    if ref_info is None:
        return entry
    ref_type, ref_value = ref_info

    worktree_path = entry.worktree_path

    try:
        if entry.action == WorktreeAction.CREATE:
            _create_worktree(
                repo_path,
                worktree_path,
                ref_type,
                ref_value,
                wt_config,
            )
            entry.detail = f"created {ref_type} worktree"

        elif entry.action == WorktreeAction.UPDATE:
            _update_worktree(worktree_path, ref_value)
            entry.detail = "branch worktree updated"

        elif entry.action == WorktreeAction.UNCHANGED:
            entry.detail = f"{ref_type} worktree already exists"

    except subprocess.CalledProcessError as e:
        entry.action = WorktreeAction.ERROR
        entry.error = e.stderr.strip() if e.stderr else str(e)
    except OSError as e:
        entry.action = WorktreeAction.ERROR
        entry.error = str(e)

    return entry


def _create_worktree(
    repo_path: pathlib.Path,
    worktree_path: pathlib.Path,
    ref_type: str,
    ref_value: str,
    wt_config: WorktreeConfigDict,
) -> None:
    """Create a new worktree.

    Parameters
    ----------
    repo_path : pathlib.Path
        Path to the main repository.
    worktree_path : pathlib.Path
        Path for the new worktree.
    ref_type : str
        Type of reference: 'tag', 'branch', or 'commit'.
    ref_value : str
        The reference value.
    wt_config : WorktreeConfigDict
        Full worktree configuration.
    """
    cmd = ["git", "worktree", "add"]

    # Determine if we should detach
    detach = wt_config.get("detach")
    if detach is None:
        # Default: detach for tags and commits, not for branches
        detach = ref_type in ("tag", "commit")

    if detach:
        cmd.append("--detach")

    # Handle locking
    if wt_config.get("lock"):
        cmd.append("--lock")
        lock_reason = wt_config.get("lock_reason")
        if lock_reason:
            cmd.extend(["--reason", lock_reason])

    cmd.append(str(worktree_path))
    cmd.append(ref_value)

    subprocess.run(
        cmd,
        cwd=repo_path,
        check=True,
        capture_output=True,
        text=True,
    )


def _update_worktree(worktree_path: pathlib.Path, branch: str) -> None:
    """Update a branch worktree by pulling latest changes.

    Parameters
    ----------
    worktree_path : pathlib.Path
        Path to the worktree.
    branch : str
        The branch name.
    """
    subprocess.run(
        ["git", "pull", "--ff-only"],
        cwd=worktree_path,
        check=True,
        capture_output=True,
        text=True,
    )


def sync_all_worktrees(
    repo_path: pathlib.Path,
    worktrees_config: list[WorktreeConfigDict],
    workspace_root: pathlib.Path,
    *,
    dry_run: bool = False,
) -> WorktreeSyncResult:
    """Synchronize all worktrees for a repository.

    Parameters
    ----------
    repo_path : pathlib.Path
        Path to the main repository.
    worktrees_config : list[WorktreeConfigDict]
        List of worktree configurations.
    workspace_root : pathlib.Path
        The workspace root directory.
    dry_run : bool
        If True, only plan without executing.

    Returns
    -------
    WorktreeSyncResult
        Summary of all sync operations.
    """
    result = WorktreeSyncResult()

    for wt_config in worktrees_config:
        entry = sync_worktree(
            repo_path,
            wt_config,
            workspace_root,
            dry_run=dry_run,
        )
        result.entries.append(entry)

        if entry.action == WorktreeAction.CREATE:
            result.created += 1
        elif entry.action == WorktreeAction.UPDATE:
            result.updated += 1
        elif entry.action == WorktreeAction.UNCHANGED:
            result.unchanged += 1
        elif entry.action == WorktreeAction.BLOCKED:
            result.blocked += 1
        elif entry.action == WorktreeAction.ERROR:
            result.errors += 1

    return result


def list_existing_worktrees(repo_path: pathlib.Path) -> list[pathlib.Path]:
    """List all existing worktrees for a repository.

    Parameters
    ----------
    repo_path : pathlib.Path
        Path to the main repository.

    Returns
    -------
    list[pathlib.Path]
        List of worktree paths.
    """
    try:
        result = subprocess.run(
            ["git", "worktree", "list", "--porcelain"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        return []

    paths: list[pathlib.Path] = []
    for line in result.stdout.strip().split("\n"):
        if line.startswith("worktree "):
            path_str = line[9:]  # Remove "worktree " prefix
            path = pathlib.Path(path_str)
            # Skip the main worktree (the repo itself)
            if path.resolve() != repo_path.resolve():
                paths.append(path)

    return paths


def prune_worktrees(
    repo_path: pathlib.Path,
    config_worktrees: list[WorktreeConfigDict],
    workspace_root: pathlib.Path,
    *,
    dry_run: bool = False,
) -> list[pathlib.Path]:
    """Remove worktrees that are not in the configuration.

    Parameters
    ----------
    repo_path : pathlib.Path
        Path to the main repository.
    config_worktrees : list[WorktreeConfigDict]
        List of configured worktrees.
    workspace_root : pathlib.Path
        The workspace root directory.
    dry_run : bool
        If True, only report what would be pruned.

    Returns
    -------
    list[pathlib.Path]
        List of worktree paths that were (or would be) pruned.
    """
    existing = set(list_existing_worktrees(repo_path))
    configured = {_resolve_worktree_path(wt, workspace_root) for wt in config_worktrees}

    orphaned = existing - configured
    pruned: list[pathlib.Path] = []

    for wt_path in orphaned:
        if dry_run:
            log.info("Would prune worktree: %s", wt_path)
        else:
            try:
                subprocess.run(
                    ["git", "worktree", "remove", str(wt_path)],
                    cwd=repo_path,
                    check=True,
                    capture_output=True,
                    text=True,
                )
                log.info("Pruned worktree: %s", wt_path)
            except subprocess.CalledProcessError as e:
                log.warning("Failed to prune worktree %s: %s", wt_path, e.stderr)
                continue

        pruned.append(wt_path)

    return pruned
