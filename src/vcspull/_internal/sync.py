"""Shared checkout settings and sync outcomes for CLI commands."""

from __future__ import annotations

import dataclasses
import datetime
import typing as t
from collections.abc import Callable, Mapping

from libvcs import BaseSync, SyncPolicy, SyncResult, SyncTarget
from libvcs._internal.shortcuts import create_project
from libvcs._internal.types import VCSLiteral
from libvcs.sync.git import GitOptions
from libvcs.sync.hg import HgOptions
from libvcs.sync.svn import SvnOptions

from vcspull.validator import validate_working_copy


@dataclasses.dataclass(frozen=True)
class SyncExecution:
    """Keep the backend instance and its complete synchronization result."""

    project: BaseSync
    result: SyncResult


def create_sync_project(
    repo: Mapping[str, t.Any],
    *,
    vcs: VCSLiteral,
    progress_callback: Callable[[str, datetime.datetime], None] | None = None,
) -> BaseSync:
    """Construct a typed backend without accessing or changing its checkout."""
    options_type = {"git": GitOptions, "hg": HgOptions, "svn": SvnOptions}[vcs]
    arguments: dict[str, t.Any] = {
        "url": repo.get("url", repo.get("pip_url", str(repo["path"]))),
        "path": repo["path"],
        "options": options_type(**repo.get(vcs, {})),
        "progress_callback": progress_callback,
    }
    if "remotes" in repo:
        arguments["remotes"] = repo["remotes"]
    return create_project(vcs=vcs, **arguments)


def checkout_settings(
    config: Mapping[str, t.Any] | None, *, worktree: bool = False
) -> tuple[SyncTarget | None, SyncPolicy]:
    """Translate a validated checkout without collapsing its selector kind.

    >>> target, policy = checkout_settings({"tag": "v1", "sync": {"drift": "keep"}})
    >>> target.tag, policy.drift
    ('v1', 'keep')
    >>> checkout_settings(None)
    (None, SyncPolicy(drift='follow', dirty='abort'))
    """
    if config is None:
        return None, SyncPolicy()
    values = dict(config)
    validate_working_copy(values, worktree=worktree)
    target = SyncTarget(
        **{
            key: values[key]
            for key in ("branch", "tag", "commit", "rev", "remote")
            if key in values
        }
    )
    return target, SyncPolicy(**values.get("sync", {}))


def sync_result_data(result: SyncResult) -> dict[str, t.Any]:
    """Serialize recovery identity and outcomes without exception objects.

    >>> sync_result_data(SyncResult())["preservation_state"]
    'not-needed'
    """
    return {
        "update_state": result.update_state,
        "preservation_state": result.preservation_state,
        "recovery": dataclasses.asdict(result.recovery) if result.recovery else None,
        "conflicts": [dataclasses.asdict(conflict) for conflict in result.conflicts],
        "errors": [
            {"step": error.step, "message": error.message} for error in result.errors
        ],
    }
