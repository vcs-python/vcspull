"""Shared checkout settings and sync outcomes for CLI commands."""

from __future__ import annotations

import dataclasses
import typing as t
from collections.abc import Mapping

from libvcs import BaseSync, SyncPolicy, SyncResult, SyncTarget

from vcspull.validator import validate_working_copy


@dataclasses.dataclass(frozen=True)
class SyncExecution:
    """Keep the backend instance and its complete synchronization result."""

    project: BaseSync
    result: SyncResult


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
