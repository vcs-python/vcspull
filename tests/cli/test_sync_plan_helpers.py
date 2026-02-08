"""Tests for sync planner helper utilities."""

from __future__ import annotations

import subprocess
import typing as t

import pytest

from vcspull.cli._output import PlanAction
from vcspull.cli.sync import SyncPlanConfig, _determine_plan_action, _maybe_fetch

if t.TYPE_CHECKING:
    import pathlib


class MaybeFetchFixture(t.NamedTuple):
    """Fixture for _maybe_fetch behaviours."""

    test_id: str
    fetch: bool
    offline: bool
    create_repo: bool
    create_git_dir: bool
    subprocess_behavior: str | None
    expected_result: tuple[bool, str | None]


MAYBE_FETCH_FIXTURES: list[MaybeFetchFixture] = [
    MaybeFetchFixture(
        test_id="offline-short-circuit",
        fetch=True,
        offline=True,
        create_repo=True,
        create_git_dir=True,
        subprocess_behavior=None,
        expected_result=(True, None),
    ),
    MaybeFetchFixture(
        test_id="no-git-directory",
        fetch=True,
        offline=False,
        create_repo=True,
        create_git_dir=False,
        subprocess_behavior=None,
        expected_result=(True, None),
    ),
    MaybeFetchFixture(
        test_id="missing-git-executable",
        fetch=True,
        offline=False,
        create_repo=True,
        create_git_dir=True,
        subprocess_behavior="file-not-found",
        expected_result=(False, "git executable not found"),
    ),
    MaybeFetchFixture(
        test_id="fetch-non-zero-exit",
        fetch=True,
        offline=False,
        create_repo=True,
        create_git_dir=True,
        subprocess_behavior="non-zero",
        expected_result=(False, "remote rejected"),
    ),
    MaybeFetchFixture(
        test_id="fetch-oserror",
        fetch=True,
        offline=False,
        create_repo=True,
        create_git_dir=True,
        subprocess_behavior="os-error",
        expected_result=(False, "Permission denied"),
    ),
    MaybeFetchFixture(
        test_id="fetch-disabled",
        fetch=False,
        offline=False,
        create_repo=True,
        create_git_dir=True,
        subprocess_behavior="non-zero",
        expected_result=(True, None),
    ),
]


@pytest.mark.parametrize(
    list(MaybeFetchFixture._fields),
    MAYBE_FETCH_FIXTURES,
    ids=[fixture.test_id for fixture in MAYBE_FETCH_FIXTURES],
)
def test_maybe_fetch_behaviour(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    test_id: str,
    fetch: bool,
    offline: bool,
    create_repo: bool,
    create_git_dir: bool,
    subprocess_behavior: str | None,
    expected_result: tuple[bool, str | None],
) -> None:
    """Ensure _maybe_fetch handles subprocess outcomes correctly."""
    repo_path = tmp_path / "repo"
    if create_repo:
        repo_path.mkdir()
    if create_git_dir:
        (repo_path / ".git").mkdir(parents=True, exist_ok=True)

    if subprocess_behavior:

        def _patched_run(
            *args: t.Any,
            **kwargs: t.Any,
        ) -> subprocess.CompletedProcess[str]:
            if subprocess_behavior == "file-not-found":
                error_message = "git executable not found"
                raise FileNotFoundError(error_message)
            if subprocess_behavior == "os-error":
                error_message = "Permission denied"
                raise OSError(error_message)
            if subprocess_behavior == "non-zero":
                return subprocess.CompletedProcess(
                    args=args[0],
                    returncode=1,
                    stdout="",
                    stderr="remote rejected",
                )
            return subprocess.CompletedProcess(
                args=args[0],
                returncode=0,
                stdout="",
                stderr="",
            )

        monkeypatch.setattr("subprocess.run", _patched_run)

    result = _maybe_fetch(
        repo_path=repo_path,
        config=SyncPlanConfig(fetch=fetch, offline=offline),
    )

    assert result == expected_result


class DeterminePlanActionFixture(t.NamedTuple):
    """Fixture for _determine_plan_action outcomes."""

    test_id: str
    status: dict[str, t.Any]
    config: SyncPlanConfig
    expected_action: PlanAction
    expected_detail: str


DETERMINE_PLAN_ACTION_FIXTURES: list[DeterminePlanActionFixture] = [
    DeterminePlanActionFixture(
        test_id="missing-repo",
        status={"exists": False},
        config=SyncPlanConfig(fetch=False, offline=False),
        expected_action=PlanAction.CLONE,
        expected_detail="missing",
    ),
    DeterminePlanActionFixture(
        test_id="not-git",
        status={"exists": True, "is_git": False},
        config=SyncPlanConfig(fetch=True, offline=False),
        expected_action=PlanAction.UPDATE,
        expected_detail="non-git VCS (detailed plan not available)",
    ),
    DeterminePlanActionFixture(
        test_id="dirty-working-tree",
        status={"exists": True, "is_git": True, "clean": False},
        config=SyncPlanConfig(fetch=True, offline=False),
        expected_action=PlanAction.BLOCKED,
        expected_detail="working tree has local changes",
    ),
    DeterminePlanActionFixture(
        test_id="diverged",
        status={"exists": True, "is_git": True, "clean": True, "ahead": 2, "behind": 3},
        config=SyncPlanConfig(fetch=True, offline=False),
        expected_action=PlanAction.BLOCKED,
        expected_detail="diverged (ahead 2, behind 3)",
    ),
    DeterminePlanActionFixture(
        test_id="behind-remote",
        status={"exists": True, "is_git": True, "clean": True, "ahead": 0, "behind": 4},
        config=SyncPlanConfig(fetch=True, offline=False),
        expected_action=PlanAction.UPDATE,
        expected_detail="behind 4",
    ),
    DeterminePlanActionFixture(
        test_id="ahead-remote",
        status={"exists": True, "is_git": True, "clean": True, "ahead": 1, "behind": 0},
        config=SyncPlanConfig(fetch=True, offline=False),
        expected_action=PlanAction.BLOCKED,
        expected_detail="ahead by 1",
    ),
    DeterminePlanActionFixture(
        test_id="up-to-date",
        status={"exists": True, "is_git": True, "clean": True, "ahead": 0, "behind": 0},
        config=SyncPlanConfig(fetch=True, offline=False),
        expected_action=PlanAction.UNCHANGED,
        expected_detail="up to date",
    ),
    DeterminePlanActionFixture(
        test_id="offline-remote-unknown",
        status={
            "exists": True,
            "is_git": True,
            "clean": True,
            "ahead": None,
            "behind": None,
        },
        config=SyncPlanConfig(fetch=True, offline=True),
        expected_action=PlanAction.UPDATE,
        expected_detail="remote state unknown (offline)",
    ),
    DeterminePlanActionFixture(
        test_id="needs-fetch",
        status={
            "exists": True,
            "is_git": True,
            "clean": True,
            "ahead": None,
            "behind": None,
        },
        config=SyncPlanConfig(fetch=True, offline=False),
        expected_action=PlanAction.UPDATE,
        expected_detail="remote state unknown; use --fetch",
    ),
]


@pytest.mark.parametrize(
    list(DeterminePlanActionFixture._fields),
    DETERMINE_PLAN_ACTION_FIXTURES,
    ids=[fixture.test_id for fixture in DETERMINE_PLAN_ACTION_FIXTURES],
)
def test_determine_plan_action(
    test_id: str,
    status: dict[str, t.Any],
    config: SyncPlanConfig,
    expected_action: PlanAction,
    expected_detail: str,
) -> None:
    """Verify _determine_plan_action handles edge cases."""
    action, detail = _determine_plan_action(status, config=config)
    assert action is expected_action
    assert detail == expected_detail
