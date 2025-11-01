"""Output formatting utilities for vcspull CLI."""

from __future__ import annotations

import json
import sys
import typing as t
from dataclasses import dataclass, field
from enum import Enum


class OutputMode(Enum):
    """Output format modes."""

    HUMAN = "human"
    JSON = "json"
    NDJSON = "ndjson"


class PlanAction(Enum):
    """Supported plan actions for repository synchronization."""

    CLONE = "clone"
    UPDATE = "update"
    UNCHANGED = "unchanged"
    BLOCKED = "blocked"
    ERROR = "error"


@dataclass
class PlanEntry:
    """Represents a single planned action for a repository."""

    name: str
    path: str
    workspace_root: str
    action: PlanAction
    detail: str | None = None
    url: str | None = None
    branch: str | None = None
    remote_branch: str | None = None
    current_rev: str | None = None
    target_rev: str | None = None
    ahead: int | None = None
    behind: int | None = None
    dirty: bool | None = None
    error: str | None = None
    diagnostics: list[str] = field(default_factory=list)

    def to_payload(self) -> dict[str, t.Any]:
        """Convert the plan entry into a serialisable payload."""
        payload: dict[str, t.Any] = {
            "format_version": "1",
            "type": "operation",
            "name": self.name,
            "path": self.path,
            "workspace_root": self.workspace_root,
            "action": self.action.value,
        }
        if self.detail:
            payload["detail"] = self.detail
        if self.url:
            payload["url"] = self.url
        if self.branch:
            payload["branch"] = self.branch
        if self.remote_branch:
            payload["remote_branch"] = self.remote_branch
        if self.current_rev:
            payload["current_rev"] = self.current_rev
        if self.target_rev:
            payload["target_rev"] = self.target_rev
        if isinstance(self.ahead, int):
            payload["ahead"] = self.ahead
        if isinstance(self.behind, int):
            payload["behind"] = self.behind
        if isinstance(self.dirty, bool):
            payload["dirty"] = self.dirty
        if self.error:
            payload["error"] = self.error
        if self.diagnostics:
            payload["diagnostics"] = list(self.diagnostics)
        return payload


@dataclass
class PlanSummary:
    """Aggregate summary for a synchronization plan."""

    clone: int = 0
    update: int = 0
    unchanged: int = 0
    blocked: int = 0
    errors: int = 0
    duration_ms: int | None = None

    def total(self) -> int:
        """Return the total number of repositories accounted for."""
        return self.clone + self.update + self.unchanged + self.blocked + self.errors

    def to_payload(self) -> dict[str, t.Any]:
        """Convert the summary to a serialisable payload."""
        payload: dict[str, t.Any] = {
            "format_version": "1",
            "type": "summary",
            "clone": self.clone,
            "update": self.update,
            "unchanged": self.unchanged,
            "blocked": self.blocked,
            "errors": self.errors,
            "total": self.total(),
        }
        if isinstance(self.duration_ms, int):
            payload["duration_ms"] = self.duration_ms
        return payload


@dataclass
class PlanRenderOptions:
    """Rendering options for human plan output."""

    show_unchanged: bool = False
    summary_only: bool = False
    long: bool = False
    verbosity: int = 0
    relative_paths: bool = False


@dataclass
class PlanResult:
    """Container for plan entries and their summary."""

    entries: list[PlanEntry]
    summary: PlanSummary

    def to_workspace_mapping(self) -> dict[str, list[PlanEntry]]:
        """Group plan entries by workspace root."""
        grouped: dict[str, list[PlanEntry]] = {}
        for entry in self.entries:
            grouped.setdefault(entry.workspace_root, []).append(entry)
        return grouped

    def to_json_object(self) -> dict[str, t.Any]:
        """Return the JSON structure for ``--json`` output."""
        workspaces: list[dict[str, t.Any]] = []
        for workspace_root, entries in self.to_workspace_mapping().items():
            workspaces.append(
                {
                    "path": workspace_root,
                    "operations": [entry.to_payload() for entry in entries],
                },
            )
        return {
            "format_version": "1",
            "workspaces": workspaces,
            "summary": self.summary.to_payload(),
        }


class OutputFormatter:
    """Manages output formatting for different modes (human, JSON, NDJSON)."""

    def __init__(self, mode: OutputMode = OutputMode.HUMAN) -> None:
        """Initialize the output formatter.

        Parameters
        ----------
        mode : OutputMode
            The output mode to use (human, json, ndjson)
        """
        self.mode = mode
        self._json_buffer: list[dict[str, t.Any]] = []

    def emit(self, data: dict[str, t.Any] | PlanEntry | PlanSummary) -> None:
        """Emit a data event.

        Parameters
        ----------
        data : dict | PlanEntry | PlanSummary
            Event data to emit. PlanEntry and PlanSummary instances are serialised
            automatically.
        """
        if isinstance(data, (PlanEntry, PlanSummary)):
            payload = data.to_payload()
        else:
            payload = data

        if self.mode == OutputMode.NDJSON:
            # Stream one JSON object per line immediately
            sys.stdout.write(json.dumps(payload) + "\n")
            sys.stdout.flush()
        elif self.mode == OutputMode.JSON:
            # Buffer for later output as single array
            self._json_buffer.append(payload)
        # Human mode: handled by specific command implementations

    def emit_text(self, text: str) -> None:
        """Emit human-readable text (only in HUMAN mode).

        Parameters
        ----------
        text : str
            Text to output
        """
        if self.mode == OutputMode.HUMAN:
            sys.stdout.write(text + "\n")
            sys.stdout.flush()

    def finalize(self) -> None:
        """Finalize output (flush JSON buffer if needed)."""
        if self.mode == OutputMode.JSON and self._json_buffer:
            sys.stdout.write(json.dumps(self._json_buffer, indent=2) + "\n")
            sys.stdout.flush()
            self._json_buffer.clear()


def get_output_mode(json_flag: bool, ndjson_flag: bool) -> OutputMode:
    """Determine output mode from command flags.

    Parameters
    ----------
    json_flag : bool
        Whether --json was specified
    ndjson_flag : bool
        Whether --ndjson was specified

    Returns
    -------
    OutputMode
        The determined output mode (NDJSON takes precedence over JSON)
    """
    if ndjson_flag:
        return OutputMode.NDJSON
    if json_flag:
        return OutputMode.JSON
    return OutputMode.HUMAN
