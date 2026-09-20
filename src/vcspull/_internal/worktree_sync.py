"""Core worktree synchronization logic for vcspull."""

from __future__ import annotations

import dataclasses
import enum
import logging
import pathlib
import subprocess
import typing as t
from collections.abc import Mapping

from libvcs import (
    SyncPolicy,
    SyncResult,
    SyncTarget,
    WorkingCopyPosition,
    exc as vcs_exc,
)
from libvcs.sync.git import GitSync

from vcspull import exc
from vcspull._internal.sync import (
    checkout_settings,
    create_sync_project,
    require_discard_authorization,
)
from vcspull.types import WorktreeConfigDict
from vcspull.validator import validate_working_copy

log = logging.getLogger(__name__)


class WorktreeAction(enum.Enum):
    """Actions that can be taken on a worktree during sync."""

    CREATE = "create"
    """Worktree doesn't exist, will be created."""

    UPDATE = "update"
    """Configured position or attachment requires an update."""

    UNCHANGED = "unchanged"
    """Checkout is kept by policy or already matches its target."""

    BLOCKED = "blocked"
    """Dirty policy prevents updating this checkout."""

    ERROR = "error"
    """Operation failed (ref not found, permission, etc.)."""


@dataclasses.dataclass
class WorktreeCheck:
    """A single check performed during worktree planning."""

    name: str
    """Check name: 'validate_config', 'ref_exists', 'worktree_exists', 'is_dirty'."""

    passed: bool
    """Whether the check passed."""

    detail: str
    """Human-readable description of the check result."""

    exception: exc.WorktreeError | None = None
    """Typed exception if the check failed."""


@dataclasses.dataclass
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

    exists: bool | None = False
    """Whether the worktree currently exists."""

    is_dirty: bool | None = False
    """Whether the worktree has uncommitted changes."""

    current_ref: str | None = None
    """Current HEAD reference if worktree exists."""

    position: WorkingCopyPosition | None = None
    """Observed native position before synchronization."""

    target_position: WorkingCopyPosition | None = None
    """Configured target resolved from available native metadata."""

    drifted: bool | None = None
    """Whether the observed and configured OIDs differ; None if unresolved."""

    result: SyncResult | None = None
    """Complete native outcome, including retained recovery identity."""

    status: t.Literal["timed_out", "interrupted"] | None = None
    """Forced termination leaves the native operation outcome uncertain."""

    retained_recoveries: tuple[SyncResult, ...] = ()
    """Records discovered after the mutation worker stopped."""

    checks: list[WorktreeCheck] = dataclasses.field(default_factory=list)
    """Ordered audit trail of checks performed during planning."""


@dataclasses.dataclass
class WorktreeSyncResult:
    """Result of a worktree sync operation."""

    entries: list[WorktreePlanEntry] = dataclasses.field(default_factory=list)
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


class WorktreeInterrupted(KeyboardInterrupt):
    """Carry completed and interrupted entries to the CLI before exiting."""

    def __init__(self, result: WorktreeSyncResult) -> None:
        self.result = result
        super().__init__()


def worktree_entry_data(entry: WorktreePlanEntry) -> dict[str, t.Any]:
    """Serialize operation metadata without native exception objects."""
    return {
        "worktree_path": str(entry.worktree_path),
        "ref_type": entry.ref_type,
        "ref_value": entry.ref_value,
        "action": entry.action.value,
        "detail": entry.detail,
        "error": entry.error,
        "exists": entry.exists,
        "is_dirty": entry.is_dirty,
        "current_ref": entry.current_ref,
        "position": dataclasses.asdict(entry.position) if entry.position else None,
        "target_position": dataclasses.asdict(entry.target_position)
        if entry.target_position
        else None,
        "drifted": entry.drifted,
        "checks": [
            {"name": check.name, "passed": check.passed, "detail": check.detail}
            for check in entry.checks
        ],
    }


def _worktree_entry_from_data(
    data: Mapping[str, t.Any], path: pathlib.Path, ref_type: str, ref_value: str
) -> WorktreePlanEntry:
    """Validate the worker's metadata before it can count as a completed action."""
    fields = dict(data)
    expected = {
        "worktree_path",
        "ref_type",
        "ref_value",
        "action",
        "detail",
        "error",
        "exists",
        "is_dirty",
        "current_ref",
        "position",
        "target_position",
        "drifted",
        "checks",
    }
    if fields.keys() != expected:
        message = "unexpected worktree metadata fields"
        raise ValueError(message)
    for key in ("worktree_path", "ref_type", "ref_value"):
        if not isinstance(fields[key], str):
            raise TypeError(key)
    if pathlib.Path(fields["worktree_path"]) != path:
        message = "worker returned a different worktree path"
        raise ValueError(message)
    if (fields["ref_type"], fields["ref_value"]) != (ref_type, ref_value):
        message = "worker returned a different worktree selector"
        raise ValueError(message)
    for key in ("detail", "error", "current_ref"):
        if fields[key] is not None and not isinstance(fields[key], str):
            raise TypeError(key)
    for key in ("exists", "is_dirty", "drifted"):
        if fields[key] is not None and type(fields[key]) is not bool:
            raise TypeError(key)
    fields["worktree_path"] = path
    fields["action"] = WorktreeAction(fields["action"])
    for name in ("position", "target_position"):
        position = fields[name]
        if position is not None:
            for key in ("revision", "ref_name", "ref_kind"):
                if not isinstance(position[key], str):
                    message = f"{name}.{key}"
                    raise TypeError(message)
            for key in ("follows", "mixed", "switched"):
                if type(position[key]) is not bool:
                    message = f"{name}.{key}"
                    raise TypeError(message)
            if position["ref_kind"] not in {"branch", "tag", "commit"}:
                message = "invalid Git position kind"
                raise ValueError(message)
            fields[name] = WorkingCopyPosition(**position)
    if not isinstance(fields["checks"], list):
        message = "checks must be a list"
        raise TypeError(message)
    for check in fields["checks"]:
        if (
            not isinstance(check, dict)
            or check.keys() != {"name", "passed", "detail"}
            or not isinstance(check["name"], str)
            or type(check["passed"]) is not bool
            or not isinstance(check["detail"], str)
        ):
            message = "invalid worktree check"
            raise TypeError(message)
    fields["checks"] = [WorktreeCheck(**check) for check in fields["checks"]]
    return WorktreePlanEntry(**fields)


def _sync_worktree_process(
    repo_path: pathlib.Path,
    wt_config: WorktreeConfigDict,
    workspace_root: pathlib.Path,
    *,
    allow_discard: bool,
    repo_config: Mapping[str, t.Any] | None,
    timeout: float,
) -> WorktreePlanEntry:
    """Stop one owned worktree process before reporting results or recovery."""
    from vcspull._internal.sync_process import SyncInterrupted, run_sync_process

    path = _resolve_worktree_path(wt_config, workspace_root)
    repo = {**(repo_config or {}), "path": path, "vcs": "git"}
    repo.setdefault("url", str(repo_path))
    interrupted = False
    try:
        outcome = run_sync_process(
            repo,
            progress_callback=lambda *args: None,
            timeout=timeout,
            is_human=False,
            yes=allow_discard,
            worktree={
                "repo_path": repo_path,
                "workspace_root": workspace_root,
                "config": wt_config,
                "repo_config": dict(repo_config) if repo_config is not None else None,
            },
        )
    except SyncInterrupted as error:
        interrupted = True
        outcome = error.outcome
    ref_type, ref_value = _get_ref_type_and_value(wt_config) or ("unknown", "unknown")
    entry = WorktreePlanEntry(
        path, ref_type, ref_value, WorktreeAction.ERROR, exists=None, is_dirty=None
    )
    if outcome.worktree is not None:
        try:
            entry = _worktree_entry_from_data(
                outcome.worktree, path, ref_type, ref_value
            )
        except (TypeError, ValueError, KeyError) as error:
            entry.error = f"invalid worktree result: {error}"
    elif outcome.status == "synced":
        entry.error = "worker did not report a complete worktree result"
    entry.result = outcome.result
    entry.retained_recoveries = outcome.retained_recoveries
    if entry.error is not None and entry.result is not None and entry.result.ok:
        entry.result.add_error("worker", entry.error)
    if interrupted or outcome.status == "timed_out":
        entry.status = "interrupted" if interrupted else "timed_out"
        entry.action = WorktreeAction.ERROR
        entry.error = "worktree interrupted" if interrupted else "worktree timed out"
    elif outcome.status == "failed" and entry.action != WorktreeAction.BLOCKED:
        entry.action = WorktreeAction.ERROR
        entry.error = entry.error or str(outcome.error)
    return entry


def _get_ref_type_and_value(
    wt_config: WorktreeConfigDict,
) -> tuple[str, str] | None:
    """Extract the reference type and value from worktree config.

    Returns
    -------
    tuple[str, str] | None
        Tuple of (ref_type, ref_value) or None if invalid config.

    Examples
    --------
    >>> _get_ref_type_and_value({"dir": "../v1", "tag": "v1.0.0"})
    ('tag', 'v1.0.0')
    >>> _get_ref_type_and_value({"dir": "../dev", "branch": "develop"})
    ('branch', 'develop')
    >>> _get_ref_type_and_value({"dir": "../abc", "commit": "abc123"})
    ('commit', 'abc123')
    >>> _get_ref_type_and_value({"dir": "../empty"}) is None
    True
    >>> multi = {"dir": "../multi", "tag": "v1", "branch": "main"}
    >>> _get_ref_type_and_value(multi) is None
    True
    >>> _get_ref_type_and_value({"dir": "../wt", "tag": ""}) is None
    True
    """
    refs = [
        (kind, value)
        for kind, value in (
            ("tag", wt_config.get("tag")),
            ("branch", wt_config.get("branch")),
            ("commit", wt_config.get("commit")),
            ("rev", wt_config.get("rev")),
        )
        if value is not None and value != ""
    ]
    if len(refs) != 1:
        return None
    kind, value = refs[0]
    return kind, str(value)


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

    Examples
    --------
    >>> validate_worktree_config({"dir": "../v1", "tag": "v1.0.0"})
    >>> validate_worktree_config({"dir": "../dev", "branch": "develop"})
    >>> validate_worktree_config({"tag": "v1.0.0"})  # Missing dir
    Traceback (most recent call last):
        ...
    vcspull.exc.WorktreeConfigError: Worktree config: missing required 'dir' field
    >>> validate_worktree_config({"dir": "../proj"})  # No ref
    Traceback (most recent call last):
        ...
    vcspull.exc.WorktreeConfigError: Worktree config: must specify one of: ...
    """
    try:
        validate_working_copy(wt_config, location="Worktree config", worktree=True)
    except exc.VCSPullException as error:
        raise exc.WorktreeConfigError(str(error)) from error


def _is_worktree_dirty(worktree_path: pathlib.Path) -> bool:
    """Check if a worktree has uncommitted changes.

    Returns ``True`` if dirty **or** if the check fails (fail-safe).
    This prevents destructive operations when the dirty state is unknown.

    Parameters
    ----------
    worktree_path : pathlib.Path
        Path to the worktree directory.

    Returns
    -------
    bool
        True if the worktree has uncommitted changes or if the check fails.

    Examples
    --------
    >>> import pathlib
    >>> _is_worktree_dirty(pathlib.Path("/nonexistent/path"))
    True
    """
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=worktree_path,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            log.warning(
                "git status failed for %s (returncode %d), assuming dirty",
                worktree_path,
                result.returncode,
            )
            return True
        # If there's any output, the worktree is dirty
        return bool(result.stdout.strip())
    except (FileNotFoundError, OSError):
        # If we can't check, assume dirty to avoid destructive operations
        log.warning("Cannot check dirty state for %s, assuming dirty", worktree_path)
        return True


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

    Examples
    --------
    >>> import pathlib
    >>> _ref_exists(pathlib.Path("/nonexistent/repo"), "v1.0.0", "tag")
    False
    >>> _ref_exists(pathlib.Path("/nonexistent/repo"), "main", "branch")
    False
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
            # Check local branch namespace explicitly (not tags/notes)
            result = subprocess.run(
                ["git", "rev-parse", "--verify", f"refs/heads/{ref}"],
                cwd=repo_path,
                capture_output=True,
                check=False,
            )
            if result.returncode != 0:
                # Try remote-tracking branch namespace
                result = subprocess.run(
                    ["git", "rev-parse", "--verify", f"refs/remotes/origin/{ref}"],
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

    Examples
    --------
    >>> import pathlib
    >>> _get_worktree_head(pathlib.Path("/nonexistent/worktree")) is None
    True
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
    except (FileNotFoundError, OSError) as e:
        # Expected when worktree_path doesn't exist or git binary not found.
        # Return None to indicate HEAD could not be determined.
        log.debug("Could not get HEAD for %s: %s", worktree_path, e)
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

    Examples
    --------
    >>> import pathlib
    >>> _worktree_exists(pathlib.Path("/repo"), pathlib.Path("/nonexistent"))
    False
    >>> repo_dir = tmp_path / "repo"
    >>> repo_dir.mkdir()
    >>> _worktree_exists(repo_dir, tmp_path / "missing")
    False
    """
    if not worktree_path.exists():
        return False

    # Check if it's a valid git worktree pointing to this repo
    git_file = worktree_path / ".git"
    if git_file.is_file():
        try:
            content = git_file.read_text().strip()
            # Worktrees have "gitdir: <path>/.git/worktrees/<name>"
            # Submodules have "gitdir: <path>/.git/modules/<name>"
            if not content.startswith("gitdir:") or "/worktrees/" not in content:
                return False
            # Verify it points back to the expected repo's worktrees directory
            gitdir = content.split("gitdir:", 1)[1].strip()
            gitdir_path = pathlib.Path(gitdir)
            if not gitdir_path.is_absolute():
                gitdir_path = (worktree_path / gitdir_path).resolve()
            repo_git_dir = (repo_path / ".git").resolve()
            try:
                gitdir_path.relative_to(repo_git_dir)
            except ValueError:
                return False
            else:
                return True
        except (OSError, PermissionError):
            return False
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

    Examples
    --------
    >>> import pathlib
    >>> workspace = pathlib.Path("/home/user/code")
    >>> wt = {"dir": "../sibling", "tag": "v1.0.0"}
    >>> _resolve_worktree_path(wt, workspace)
    PosixPath('/home/user/sibling')
    >>> wt_abs = {"dir": "/tmp/worktree", "tag": "v1.0.0"}
    >>> _resolve_worktree_path(wt_abs, workspace)
    PosixPath('/tmp/worktree')
    """
    dir_path = pathlib.Path(wt_config["dir"]).expanduser()

    if dir_path.is_absolute():
        return dir_path.resolve()

    # Relative paths are resolved relative to workspace root
    return (workspace_root / dir_path).resolve()


def _worktree_project(
    repo_path: pathlib.Path,
    worktree_path: pathlib.Path,
    repo_config: Mapping[str, t.Any] | None,
) -> GitSync:
    values = dict(repo_config or {"url": str(repo_path)})
    values["path"] = worktree_path
    project = create_sync_project(values, vcs="git")
    assert isinstance(project, GitSync)
    return project


def require_worktree_authorization(
    configs: list[WorktreeConfigDict], *, allow_discard: bool
) -> None:
    """Reject unauthorized discard before any checkout in an operation mutates."""
    for config in configs:
        _, policy = checkout_settings(config, worktree=True)
        require_discard_authorization(policy, allow_discard=allow_discard)


def plan_worktree_sync(
    repo_path: pathlib.Path,
    worktrees_config: list[WorktreeConfigDict],
    workspace_root: pathlib.Path,
    *,
    repo_config: Mapping[str, t.Any] | None = None,
) -> list[WorktreePlanEntry]:
    """Inspect local worktree targets and policy without fetching or changing refs.

    Unavailable target metadata produces an error plan. Execution can resolve it
    after an authorized fetch; planning never performs that fetch implicitly.

    >>> entries = plan_worktree_sync(
    ...     pathlib.Path("/nonexistent/repo"),
    ...     [{"dir": "../wt", "tag": "v1.0.0"}],
    ...     pathlib.Path("/nonexistent"),
    ... )
    >>> entries[0].action == WorktreeAction.ERROR
    True
    """
    entries = []
    for config in worktrees_config:
        ref_type, ref_value = _get_ref_type_and_value(config) or ("unknown", "unknown")
        entry = WorktreePlanEntry(
            worktree_path=pathlib.Path(config.get("dir", "unknown")),
            ref_type=ref_type,
            ref_value=ref_value,
            action=WorktreeAction.ERROR,
        )
        entries.append(entry)
        try:
            validate_worktree_config(config)
            target, policy = checkout_settings(config, worktree=True)
            entry.checks.append(WorktreeCheck("validate_config", True, "config valid"))
            entry.worktree_path = _resolve_worktree_path(config, workspace_root)
            entry.exists = _worktree_exists(repo_path, entry.worktree_path)
            if entry.worktree_path.exists() and not entry.exists:
                message = "destination is not a registered worktree"
                raise exc.WorktreeConfigError(message)
            project = _worktree_project(
                repo_path,
                entry.worktree_path if entry.exists else repo_path,
                repo_config,
            )
            try:
                entry.target_position = project.resolve_target(target)
            except (vcs_exc.LibVCSException, OSError, ValueError) as error:
                ref_error = exc.WorktreeRefNotFoundError(
                    ref_value, ref_type, str(repo_path)
                )
                entry.checks.append(
                    WorktreeCheck("ref_exists", False, str(error), ref_error)
                )
                raise ref_error from error
            entry.checks.append(
                WorktreeCheck("ref_exists", True, "target resolved locally")
            )
            entry.checks.append(
                WorktreeCheck(
                    "worktree_exists",
                    True,
                    f"worktree {'exists' if entry.exists else 'not found'}"
                    f" at {entry.worktree_path}",
                )
            )
            if not entry.exists:
                entry.action = WorktreeAction.CREATE
                entry.detail = "will create configured worktree"
                continue
            entry.position = project.get_position()
            entry.current_ref = entry.position.revision
            entry.is_dirty = project.is_dirty()
            entry.drifted = entry.position.revision != entry.target_position.revision
            dirty_error = (
                exc.WorktreeDirtyError(str(entry.worktree_path))
                if entry.is_dirty
                else None
            )
            blocked = (
                entry.is_dirty and policy.dirty == "abort" and policy.drift == "follow"
            )
            entry.checks.append(
                WorktreeCheck(
                    "is_dirty",
                    not blocked,
                    str(dirty_error) if entry.is_dirty else "worktree is clean",
                    dirty_error if blocked else None,
                )
            )
            if policy.drift != "follow":
                entry.action = WorktreeAction.UNCHANGED
                entry.detail = "checkout kept by drift policy"
            elif blocked:
                entry.action = WorktreeAction.BLOCKED
                entry.detail = str(dirty_error)
            else:
                attach = entry.target_position.follows and not config.get(
                    "detach", False
                )
                attachment_changed = (
                    attach
                    and (
                        not entry.position.follows
                        or entry.position.ref_name != entry.target_position.ref_name
                    )
                ) or (not attach and entry.position.follows)
                entry.action = (
                    WorktreeAction.UPDATE
                    if entry.drifted or attachment_changed
                    else WorktreeAction.UNCHANGED
                )
                entry.detail = (
                    "configured target differs"
                    if entry.action == WorktreeAction.UPDATE
                    else "already at configured target"
                )
        except (
            exc.VCSPullException,
            vcs_exc.LibVCSException,
            OSError,
            ValueError,
        ) as error:
            entry.action = WorktreeAction.ERROR
            entry.error = str(error)
            if not entry.checks:
                entry.checks.append(
                    WorktreeCheck(
                        "validate_config",
                        False,
                        str(error),
                        t.cast(exc.WorktreeError, error),
                    )
                )
    return entries


def _prepare_worktree(project: GitSync) -> SyncResult:
    """Check existing native ownership before the separate worktree-add command."""
    return project.update_repo(
        target=SyncTarget(commit=project.get_position().revision),
        policy=SyncPolicy(drift="keep"),
    )


def sync_worktree(
    repo_path: pathlib.Path,
    wt_config: WorktreeConfigDict,
    workspace_root: pathlib.Path,
    *,
    dry_run: bool = False,
    allow_discard: bool = False,
    repo_config: Mapping[str, t.Any] | None = None,
) -> WorktreePlanEntry:
    """Synchronize a linked checkout and retain its complete native outcome.

    Discard requires explicit caller authorization, including clean and missing
    worktrees. Missing paths use native worktree-add; they are never cloned.

    >>> entry = sync_worktree(
    ...     pathlib.Path("/nonexistent/repo"),
    ...     {"dir": "../wt", "tag": "v1.0.0"},
    ...     pathlib.Path("/nonexistent"), dry_run=True,
    ... )
    >>> entry.action == WorktreeAction.ERROR
    True
    """
    if not dry_run:
        require_worktree_authorization([wt_config], allow_discard=allow_discard)
    entries = plan_worktree_sync(
        repo_path, [wt_config], workspace_root, repo_config=repo_config
    )
    if not entries:
        return WorktreePlanEntry(
            _resolve_worktree_path(wt_config, workspace_root),
            "unknown",
            "unknown",
            WorktreeAction.ERROR,
            error="internal: planning produced no entries",
        )
    entry = entries[0]
    if dry_run:
        return entry
    try:
        validate_worktree_config(wt_config)
        target, policy = checkout_settings(wt_config, worktree=True)
        path = _resolve_worktree_path(wt_config, workspace_root)
        exists = _worktree_exists(repo_path, path)
        if path.exists() and not exists:
            message = "destination is not a registered worktree"
            raise exc.WorktreeConfigError(message)
        project = _worktree_project(
            repo_path, path if exists else repo_path, repo_config
        )
        if not exists:
            guard = _prepare_worktree(project)
            if not guard.ok:
                entry.result = guard
            else:
                resolved = project.resolve_target(target)
                entry.target_position = resolved
                attach = resolved.follows and not wt_config.get("detach", False)
                _create_worktree(
                    repo_path,
                    path,
                    "branch" if attach else "commit",
                    resolved.ref_name if attach else resolved.revision,
                    {**wt_config, "detach": not attach},
                    start_point=resolved.revision,
                )
                project = _worktree_project(repo_path, path, repo_config)
        if entry.result is None:
            execution_policy = policy if exists else SyncPolicy(dirty=policy.dirty)
            entry.result = project.update_repo(
                set_remotes=repo_config is not None,
                target=target,
                policy=execution_policy,
                detach=wt_config.get("detach", False),
            )
        result = entry.result
        if not result.ok:
            entry.action = (
                WorktreeAction.BLOCKED
                if any(error.step == "dirty" for error in result.errors)
                else WorktreeAction.ERROR
            )
            entry.error = "; ".join(
                f"{error.step}: {error.message}" for error in result.errors
            )
            entry.detail = entry.error
        else:
            entry.target_position = project.resolve_target(target)
            if entry.position is not None:
                entry.drifted = (
                    entry.position.revision != entry.target_position.revision
                )
            entry.error = None
            entry.action = (
                WorktreeAction.CREATE
                if not exists
                else WorktreeAction.UPDATE
                if result.update_state == "completed"
                else WorktreeAction.UNCHANGED
            )
            entry.detail = {
                WorktreeAction.CREATE: "created configured worktree",
                WorktreeAction.UPDATE: "worktree updated",
                WorktreeAction.UNCHANGED: "checkout kept or target already matched",
            }[entry.action]
    except (
        exc.VCSPullException,
        vcs_exc.LibVCSException,
        OSError,
        ValueError,
        subprocess.CalledProcessError,
    ) as error:
        entry.action = WorktreeAction.ERROR
        entry.error = str(error)
        if entry.result is None:
            entry.result = SyncResult()
        entry.result.add_error("worktree", str(error), error)
    return entry


def _create_worktree(
    repo_path: pathlib.Path,
    worktree_path: pathlib.Path,
    ref_type: str,
    ref_value: str,
    wt_config: WorktreeConfigDict,
    *,
    start_point: str | None = None,
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

    Raises
    ------
    subprocess.CalledProcessError
        If the git command fails (e.g., ref not found).
    FileNotFoundError
        If the repository path does not exist.

    Examples
    --------
    This function requires a valid git repository. When called with an invalid
    path, it raises FileNotFoundError:

    >>> import pathlib
    >>> _create_worktree(
    ...     pathlib.Path("/nonexistent"),
    ...     pathlib.Path("/tmp/wt"),
    ...     "tag",
    ...     "v1.0.0",
    ...     {"dir": "../wt", "tag": "v1.0.0"},
    ... )  # doctest: +ELLIPSIS
    Traceback (most recent call last):
        ...
    FileNotFoundError: ...
    """
    cmd = ["git", "worktree", "add"]

    # Determine if we should detach
    detach = wt_config.get("detach")
    if detach is None:
        # Default: detach for tags and commits, not for branches
        detach = ref_type in ("tag", "commit", "rev")

    if detach:
        cmd.append("--detach")

    # Handle locking
    # git worktree add --lock does NOT support --reason, so when lock_reason
    # is specified, we skip --lock here and use "git worktree lock --reason" after
    lock_reason = wt_config.get("lock_reason")
    should_lock = wt_config.get("lock")
    if should_lock and not lock_reason:
        # Lock without reason - can use --lock flag directly
        cmd.append("--lock")

    if ref_type == "branch" and not detach and start_point is not None:
        branch_exists = (
            subprocess.run(
                ["git", "show-ref", "--verify", "--quiet", f"refs/heads/{ref_value}"],
                cwd=repo_path,
                capture_output=True,
                check=False,
            ).returncode
            == 0
        )
        if not branch_exists:
            cmd.extend(["-b", ref_value])
            ref_value = start_point
    cmd.append(str(worktree_path))
    cmd.append(ref_value)

    subprocess.run(
        cmd,
        cwd=repo_path,
        check=True,
        capture_output=True,
        text=True,
    )

    # Apply lock with reason via separate command
    # This handles both cases:
    # 1. lock=True with lock_reason - lock with reason
    # 2. lock_reason without explicit lock=True - also locks with reason
    if lock_reason:
        lock_cmd = [
            "git",
            "worktree",
            "lock",
            "--reason",
            lock_reason,
            str(worktree_path),
        ]
        try:
            subprocess.run(
                lock_cmd,
                cwd=repo_path,
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError as e:
            log.warning(
                "Worktree created at %s but lock failed: %s",
                worktree_path,
                e.stderr.strip() if e.stderr else str(e),
            )


def _update_worktree(worktree_path: pathlib.Path, branch: str) -> None:
    """Follow a branch with native fast-forward and dirty-abort safeguards.

    Parameters
    ----------
    worktree_path : pathlib.Path
        Path to the worktree.
    branch : str
        The expected branch name.

    Raises
    ------
    WorktreeError
        If native synchronization fails.
    FileNotFoundError
        If the worktree path does not exist.

    Examples
    --------
    This function requires a valid git worktree. When called with an invalid
    path, it raises FileNotFoundError:

    >>> import pathlib
    >>> _update_worktree(pathlib.Path("/nonexistent"), "main")  # doctest: +ELLIPSIS
    Traceback (most recent call last):
        ...
    FileNotFoundError: ...
    """
    if not worktree_path.exists():
        raise FileNotFoundError(str(worktree_path))
    project = _worktree_project(worktree_path, worktree_path, None)
    result = project.update_repo(target=SyncTarget(branch=branch), policy=SyncPolicy())
    if not result.ok:
        raise exc.WorktreeError("; ".join(error.message for error in result.errors))


def sync_all_worktrees(
    repo_path: pathlib.Path,
    worktrees_config: list[WorktreeConfigDict],
    workspace_root: pathlib.Path,
    *,
    dry_run: bool = False,
    allow_discard: bool = False,
    repo_config: Mapping[str, t.Any] | None = None,
    timeout: float | None = None,
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

    Examples
    --------
    >>> import pathlib
    >>> result = sync_all_worktrees(
    ...     pathlib.Path("/nonexistent/repo"),
    ...     [{"dir": "../wt", "tag": "v1.0.0"}],
    ...     pathlib.Path("/nonexistent"),
    ...     dry_run=True,
    ... )
    >>> result.errors
    1
    >>> len(result.entries)
    1
    """
    if not dry_run:
        require_worktree_authorization(worktrees_config, allow_discard=allow_discard)
    result = WorktreeSyncResult()

    for wt_config in worktrees_config:
        if timeout is not None and not dry_run:
            entry = _sync_worktree_process(
                repo_path,
                wt_config,
                workspace_root,
                allow_discard=allow_discard,
                repo_config=repo_config,
                timeout=timeout,
            )
        else:
            entry = sync_worktree(
                repo_path,
                wt_config,
                workspace_root,
                dry_run=dry_run,
                allow_discard=allow_discard,
                repo_config=repo_config,
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
        if entry.status == "interrupted":
            raise WorktreeInterrupted(result)
        if entry.status == "timed_out":
            break

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

    Examples
    --------
    >>> import pathlib
    >>> list_existing_worktrees(pathlib.Path("/nonexistent/repo"))
    []
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
                paths.append(path.resolve())

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

    Examples
    --------
    >>> import pathlib
    >>> prune_worktrees(
    ...     pathlib.Path("/nonexistent/repo"),
    ...     [],
    ...     pathlib.Path("/nonexistent"),
    ...     dry_run=True,
    ... )
    []
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
