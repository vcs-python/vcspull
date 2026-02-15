"""Unit tests for sync plan output helpers."""

from __future__ import annotations

import io
import json
import typing as t
from contextlib import redirect_stdout

import pytest

from vcspull.cli._colors import ColorMode, Colors
from vcspull.cli._output import (
    OutputFormatter,
    OutputMode,
    PlanAction,
    PlanEntry,
    PlanSummary,
)
from vcspull.cli.sync import PlanProgressPrinter


class PlanEntryPayloadFixture(t.NamedTuple):
    """Fixture for PlanEntry payload serialization."""

    test_id: str
    kwargs: dict[str, t.Any]
    expected_keys: dict[str, t.Any]
    unexpected_keys: set[str]


PLAN_ENTRY_PAYLOAD_FIXTURES: list[PlanEntryPayloadFixture] = [
    PlanEntryPayloadFixture(
        test_id="clone-with-url",
        kwargs={
            "name": "repo-one",
            "path": "/tmp/repo-one",
            "workspace_root": "~/code/",
            "action": PlanAction.CLONE,
            "detail": "missing",
            "url": "git+https://example.com/repo-one.git",
        },
        expected_keys={
            "type": "operation",
            "action": "clone",
            "detail": "missing",
            "url": "git+https://example.com/repo-one.git",
        },
        unexpected_keys={"branch", "ahead", "behind", "dirty", "error"},
    ),
    PlanEntryPayloadFixture(
        test_id="update-with-status",
        kwargs={
            "name": "repo-two",
            "path": "/tmp/repo-two",
            "workspace_root": "~/code/",
            "action": PlanAction.UPDATE,
            "detail": "behind 2",
            "branch": "main",
            "remote_branch": "origin/main",
            "current_rev": "abc1234",
            "target_rev": "def5678",
            "ahead": 0,
            "behind": 2,
            "dirty": False,
        },
        expected_keys={
            "branch": "main",
            "remote_branch": "origin/main",
            "current_rev": "abc1234",
            "target_rev": "def5678",
            "ahead": 0,
            "behind": 2,
            "dirty": False,
        },
        unexpected_keys={"url", "error"},
    ),
]


@pytest.mark.parametrize(
    list(PlanEntryPayloadFixture._fields),
    PLAN_ENTRY_PAYLOAD_FIXTURES,
    ids=[fixture.test_id for fixture in PLAN_ENTRY_PAYLOAD_FIXTURES],
)
def test_plan_entry_to_payload(
    test_id: str,
    kwargs: dict[str, t.Any],
    expected_keys: dict[str, t.Any],
    unexpected_keys: set[str],
) -> None:
    """Ensure PlanEntry serialises optional fields correctly."""
    entry = PlanEntry(**kwargs)
    payload = entry.to_payload()

    for key, value in expected_keys.items():
        assert payload[key] == value

    for key in unexpected_keys:
        assert key not in payload

    assert payload["format_version"] == "1"
    assert payload["type"] == "operation"
    assert payload["name"] == kwargs["name"]
    assert payload["path"] == kwargs["path"]
    assert payload["workspace_root"] == kwargs["workspace_root"]


class PlanSummaryPayloadFixture(t.NamedTuple):
    """Fixture for PlanSummary payload serialization."""

    test_id: str
    summary: PlanSummary
    expected_total: int


PLAN_SUMMARY_PAYLOAD_FIXTURES: list[PlanSummaryPayloadFixture] = [
    PlanSummaryPayloadFixture(
        test_id="basic-counts",
        summary=PlanSummary(clone=1, update=2, unchanged=3, blocked=4, errors=5),
        expected_total=15,
    ),
    PlanSummaryPayloadFixture(
        test_id="with-duration",
        summary=PlanSummary(
            clone=0,
            update=1,
            unchanged=0,
            blocked=0,
            errors=0,
            duration_ms=120,
        ),
        expected_total=1,
    ),
]


@pytest.mark.parametrize(
    list(PlanSummaryPayloadFixture._fields),
    PLAN_SUMMARY_PAYLOAD_FIXTURES,
    ids=[fixture.test_id for fixture in PLAN_SUMMARY_PAYLOAD_FIXTURES],
)
def test_plan_summary_to_payload(
    test_id: str,
    summary: PlanSummary,
    expected_total: int,
) -> None:
    """Validate PlanSummary total and serialization behaviour."""
    payload = summary.to_payload()
    assert payload["total"] == expected_total
    assert payload["clone"] == summary.clone
    assert payload["update"] == summary.update
    assert payload["unchanged"] == summary.unchanged
    assert payload["blocked"] == summary.blocked
    assert payload["errors"] == summary.errors
    if summary.duration_ms is not None:
        assert payload["duration_ms"] == summary.duration_ms
    else:
        assert "duration_ms" not in payload


def test_output_formatter_json_mode_empty_buffer_emits_empty_array() -> None:
    """OutputFormatter should emit an empty JSON array when buffer has no items."""
    formatter = OutputFormatter(mode=OutputMode.JSON)
    captured = io.StringIO()
    with redirect_stdout(captured):
        formatter.finalize()

    output = json.loads(captured.getvalue())
    assert output == []


def test_output_formatter_json_mode_finalises_buffer() -> None:
    """OutputFormatter should flush buffered JSON payloads on finalize."""
    entry = PlanEntry(
        name="repo-buffer",
        path="/tmp/repo-buffer",
        workspace_root="~/code/",
        action=PlanAction.CLONE,
    )
    formatter = OutputFormatter(mode=OutputMode.JSON)
    captured = io.StringIO()
    with redirect_stdout(captured):
        formatter.emit(entry)
        formatter.emit(PlanSummary(clone=1))
        formatter.finalize()

    output = json.loads(captured.getvalue())
    assert len(output) == 2
    assert output[0]["name"] == "repo-buffer"
    assert output[1]["type"] == "summary"


def test_plan_progress_printer_updates_and_finishes() -> None:
    """Progress printer should render a single line and terminate cleanly."""
    colors = Colors(mode=ColorMode.NEVER)
    printer = PlanProgressPrinter(total=3, colors=colors, enabled=True)
    buffer = io.StringIO()
    printer._stream = buffer

    summary = PlanSummary(clone=1)
    printer.update(summary, processed=1)
    assert "Progress: 1/3" in buffer.getvalue()

    printer.finish()
    assert buffer.getvalue().endswith("\n")
