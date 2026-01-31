"""Tests for vcspull worktree functionality."""

from __future__ import annotations

import pathlib
import subprocess
import typing as t

import pytest

from vcspull import config as vcspull_config, exc
from vcspull._internal.worktree_sync import (
    WorktreeAction,
    _get_ref_type_and_value,
    _resolve_worktree_path,
    list_existing_worktrees,
    plan_worktree_sync,
    prune_worktrees,
    sync_all_worktrees,
    sync_worktree,
    validate_worktree_config,
)
from vcspull.cli.discover import is_git_worktree
from vcspull.types import RawConfigDict, WorktreeConfigDict

if t.TYPE_CHECKING:
    from libvcs.sync.git import GitSync


# ---------------------------------------------------------------------------
# Config Parsing Fixtures and Tests
# ---------------------------------------------------------------------------


class WorktreeConfigFixture(t.NamedTuple):
    """Fixture for worktree config parsing tests."""

    test_id: str
    config: dict[str, t.Any]
    expected_worktrees: int
    expected_ref_types: list[str]
    expected_error: str | None = None


WORKTREE_CONFIG_FIXTURES = [
    WorktreeConfigFixture(
        test_id="single_tag_worktree",
        config={"worktrees": [{"dir": "../proj-v1", "tag": "v1.0.0"}]},
        expected_worktrees=1,
        expected_ref_types=["tag"],
    ),
    WorktreeConfigFixture(
        test_id="single_branch_worktree",
        config={"worktrees": [{"dir": "../proj-dev", "branch": "develop"}]},
        expected_worktrees=1,
        expected_ref_types=["branch"],
    ),
    WorktreeConfigFixture(
        test_id="single_commit_worktree",
        config={"worktrees": [{"dir": "../proj-abc", "commit": "abc123"}]},
        expected_worktrees=1,
        expected_ref_types=["commit"],
    ),
    WorktreeConfigFixture(
        test_id="multiple_mixed_worktrees",
        config={
            "worktrees": [
                {"dir": "../v1", "tag": "v1.0.0"},
                {"dir": "../v2", "tag": "v2.0.0"},
                {"dir": "../main", "branch": "main"},
                {"dir": "../hotfix", "commit": "deadbeef"},
            ]
        },
        expected_worktrees=4,
        expected_ref_types=["tag", "tag", "branch", "commit"],
    ),
    WorktreeConfigFixture(
        test_id="empty_worktrees_list",
        config={"worktrees": []},
        expected_worktrees=0,
        expected_ref_types=[],
    ),
    WorktreeConfigFixture(
        test_id="relative_dir_path",
        config={"worktrees": [{"dir": "../sibling-dir", "tag": "v1.0.0"}]},
        expected_worktrees=1,
        expected_ref_types=["tag"],
    ),
    WorktreeConfigFixture(
        test_id="absolute_dir_path",
        config={"worktrees": [{"dir": "/tmp/worktree", "tag": "v1.0.0"}]},
        expected_worktrees=1,
        expected_ref_types=["tag"],
    ),
]


@pytest.mark.parametrize(
    list(WorktreeConfigFixture._fields),
    WORKTREE_CONFIG_FIXTURES,
    ids=[fixture.test_id for fixture in WORKTREE_CONFIG_FIXTURES],
)
def test_worktree_config_parsing(
    test_id: str,
    config: dict[str, t.Any],
    expected_worktrees: int,
    expected_ref_types: list[str],
    expected_error: str | None,
    tmp_path: pathlib.Path,
) -> None:
    """Test worktree configuration parsing."""
    worktrees_raw = config.get("worktrees", [])

    # Build a full config structure
    full_config = {
        "~/repos/": {
            "myproject": {
                "repo": "git+https://github.com/user/project.git",
                **config,
            },
        },
    }

    if expected_error:
        with pytest.raises(exc.VCSPullException, match=expected_error):
            typed_config = t.cast("RawConfigDict", full_config)
            vcspull_config.extract_repos(typed_config, cwd=tmp_path)
    else:
        # Validate each worktree individually
        for wt in worktrees_raw:
            validate_worktree_config(wt)

        assert len(worktrees_raw) == expected_worktrees

        for idx, wt in enumerate(worktrees_raw):
            ref_info = _get_ref_type_and_value(wt)
            assert ref_info is not None
            ref_type, _ = ref_info
            assert ref_type == expected_ref_types[idx]


class WorktreeConfigErrorFixture(t.NamedTuple):
    """Fixture for worktree config error tests."""

    test_id: str
    wt_config: dict[str, t.Any]
    expected_error_pattern: str


WORKTREE_CONFIG_ERROR_FIXTURES = [
    WorktreeConfigErrorFixture(
        test_id="missing_dir_error",
        wt_config={"tag": "v1.0.0"},
        expected_error_pattern="missing required 'dir' field",
    ),
    WorktreeConfigErrorFixture(
        test_id="no_ref_specified_error",
        wt_config={"dir": "../proj"},
        expected_error_pattern="must specify one of",
    ),
    WorktreeConfigErrorFixture(
        test_id="multiple_refs_error",
        wt_config={"dir": "../proj", "tag": "v1", "branch": "main"},
        expected_error_pattern="cannot specify multiple",
    ),
]


@pytest.mark.parametrize(
    list(WorktreeConfigErrorFixture._fields),
    WORKTREE_CONFIG_ERROR_FIXTURES,
    ids=[fixture.test_id for fixture in WORKTREE_CONFIG_ERROR_FIXTURES],
)
def test_worktree_config_validation_errors(
    test_id: str,
    wt_config: dict[str, t.Any],
    expected_error_pattern: str,
) -> None:
    """Test worktree configuration validation errors."""
    with pytest.raises(exc.WorktreeConfigError, match=expected_error_pattern):
        validate_worktree_config(t.cast(WorktreeConfigDict, wt_config))


# ---------------------------------------------------------------------------
# Worktree Path Resolution Tests
# ---------------------------------------------------------------------------


def test_resolve_worktree_path_relative(tmp_path: pathlib.Path) -> None:
    """Test relative worktree path resolution."""
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()

    wt_config: WorktreeConfigDict = {"dir": "../sibling", "tag": "v1.0.0"}

    resolved = _resolve_worktree_path(wt_config, workspace_root)

    # Should resolve to parent/sibling
    expected = (workspace_root.parent / "sibling").resolve()
    assert resolved == expected


def test_resolve_worktree_path_absolute(tmp_path: pathlib.Path) -> None:
    """Test absolute worktree path resolution."""
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()

    absolute_path = tmp_path / "absolute" / "worktree"
    wt_config: WorktreeConfigDict = {"dir": str(absolute_path), "tag": "v1.0.0"}

    resolved = _resolve_worktree_path(wt_config, workspace_root)

    assert resolved == absolute_path


# ---------------------------------------------------------------------------
# Git Worktree Detection Tests
# ---------------------------------------------------------------------------


def test_is_git_worktree_regular_repo(git_repo: GitSync) -> None:
    """Regular git repository should not be detected as worktree."""
    assert not is_git_worktree(git_repo.path)


def test_is_git_worktree_empty_dir(tmp_path: pathlib.Path) -> None:
    """Empty directory should not be detected as worktree."""
    assert not is_git_worktree(tmp_path)


def test_is_git_worktree_actual_worktree(
    git_repo: GitSync, tmp_path: pathlib.Path
) -> None:
    """Actual git worktree should be detected."""
    worktree_path = tmp_path / "my-worktree"

    # Create a worktree
    subprocess.run(
        ["git", "worktree", "add", str(worktree_path), "HEAD", "--detach"],
        cwd=git_repo.path,
        check=True,
        capture_output=True,
    )

    assert is_git_worktree(worktree_path)


# ---------------------------------------------------------------------------
# Worktree Sync Planning Tests
# ---------------------------------------------------------------------------


class WorktreeSyncPlanFixture(t.NamedTuple):
    """Fixture for worktree sync planning tests."""

    test_id: str
    ref_type: str
    ref_value: str
    worktree_exists: bool
    expected_action: WorktreeAction


WORKTREE_SYNC_PLAN_FIXTURES = [
    WorktreeSyncPlanFixture(
        test_id="create_new_worktree",
        ref_type="tag",
        ref_value="v1.0.0",
        worktree_exists=False,
        expected_action=WorktreeAction.CREATE,
    ),
]


def test_plan_worktree_sync_missing_ref(
    git_repo: GitSync,
    tmp_path: pathlib.Path,
) -> None:
    """Test planning with a non-existent ref shows error."""
    workspace_root = git_repo.path.parent
    worktrees_config: list[WorktreeConfigDict] = [
        {"dir": "../nonexistent-wt", "tag": "v999.0.0"},
    ]

    entries = plan_worktree_sync(git_repo.path, worktrees_config, workspace_root)

    assert len(entries) == 1
    assert entries[0].action == WorktreeAction.ERROR
    assert "not found" in (entries[0].error or "").lower()


def test_plan_worktree_sync_create_tag(
    git_repo: GitSync,
    tmp_path: pathlib.Path,
) -> None:
    """Test planning a new tag worktree shows CREATE action."""
    workspace_root = git_repo.path.parent

    # Create a tag in the repo
    subprocess.run(
        ["git", "tag", "v1.0.0"],
        cwd=git_repo.path,
        check=True,
        capture_output=True,
    )

    worktrees_config: list[WorktreeConfigDict] = [
        {"dir": "../tag-wt", "tag": "v1.0.0"},
    ]

    entries = plan_worktree_sync(git_repo.path, worktrees_config, workspace_root)

    assert len(entries) == 1
    assert entries[0].action == WorktreeAction.CREATE
    assert entries[0].ref_type == "tag"
    assert entries[0].ref_value == "v1.0.0"


def test_plan_worktree_sync_existing_tag_unchanged(
    git_repo: GitSync,
    tmp_path: pathlib.Path,
) -> None:
    """Test planning an existing tag worktree shows UNCHANGED action."""
    workspace_root = git_repo.path.parent
    worktree_path = workspace_root / "tag-wt"

    # Create a tag in the repo
    subprocess.run(
        ["git", "tag", "v1.0.0"],
        cwd=git_repo.path,
        check=True,
        capture_output=True,
    )

    # Create the worktree
    subprocess.run(
        ["git", "worktree", "add", str(worktree_path), "v1.0.0", "--detach"],
        cwd=git_repo.path,
        check=True,
        capture_output=True,
    )

    worktrees_config: list[WorktreeConfigDict] = [
        {"dir": str(worktree_path), "tag": "v1.0.0"},
    ]

    entries = plan_worktree_sync(git_repo.path, worktrees_config, workspace_root)

    assert len(entries) == 1
    assert entries[0].action == WorktreeAction.UNCHANGED


def test_plan_worktree_sync_dirty_worktree_blocked(
    git_repo: GitSync,
    tmp_path: pathlib.Path,
) -> None:
    """Test planning a dirty worktree shows BLOCKED action."""
    workspace_root = git_repo.path.parent
    worktree_path = workspace_root / "dirty-wt"

    # Create a worktree
    subprocess.run(
        ["git", "worktree", "add", str(worktree_path), "HEAD", "--detach"],
        cwd=git_repo.path,
        check=True,
        capture_output=True,
    )

    # Make the worktree dirty
    dirty_file = worktree_path / "uncommitted.txt"
    dirty_file.write_text("dirty content")

    # Get the commit SHA
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=git_repo.path,
        capture_output=True,
        text=True,
        check=True,
    )
    commit_sha = result.stdout.strip()

    worktrees_config: list[WorktreeConfigDict] = [
        {"dir": str(worktree_path), "commit": commit_sha},
    ]

    entries = plan_worktree_sync(git_repo.path, worktrees_config, workspace_root)

    assert len(entries) == 1
    assert entries[0].action == WorktreeAction.BLOCKED
    assert entries[0].is_dirty is True
    assert "uncommitted" in (entries[0].detail or "").lower()


# ---------------------------------------------------------------------------
# Worktree Sync Execution Tests
# ---------------------------------------------------------------------------


def test_sync_worktree_create_tag(
    git_repo: GitSync,
    tmp_path: pathlib.Path,
) -> None:
    """Test creating a tag worktree."""
    workspace_root = git_repo.path.parent
    worktree_path = workspace_root / "new-tag-wt"

    # Create a tag in the repo
    subprocess.run(
        ["git", "tag", "v2.0.0"],
        cwd=git_repo.path,
        check=True,
        capture_output=True,
    )

    wt_config: WorktreeConfigDict = {"dir": str(worktree_path), "tag": "v2.0.0"}

    entry = sync_worktree(git_repo.path, wt_config, workspace_root)

    assert entry.action == WorktreeAction.CREATE
    assert worktree_path.exists()
    assert (worktree_path / ".git").is_file()  # Worktrees have .git file, not dir


def test_sync_worktree_create_branch(
    git_repo: GitSync,
    tmp_path: pathlib.Path,
) -> None:
    """Test creating a branch worktree."""
    workspace_root = git_repo.path.parent
    worktree_path = workspace_root / "branch-wt"

    # Create a branch in the repo
    subprocess.run(
        ["git", "branch", "feature-branch"],
        cwd=git_repo.path,
        check=True,
        capture_output=True,
    )

    wt_config: WorktreeConfigDict = {
        "dir": str(worktree_path),
        "branch": "feature-branch",
    }

    entry = sync_worktree(git_repo.path, wt_config, workspace_root)

    assert entry.action == WorktreeAction.CREATE
    assert worktree_path.exists()


def test_sync_worktree_dry_run_no_create(
    git_repo: GitSync,
    tmp_path: pathlib.Path,
) -> None:
    """Test dry run doesn't create worktree."""
    workspace_root = git_repo.path.parent
    worktree_path = workspace_root / "dry-run-wt"

    # Create a tag in the repo
    subprocess.run(
        ["git", "tag", "v3.0.0"],
        cwd=git_repo.path,
        check=True,
        capture_output=True,
    )

    wt_config: WorktreeConfigDict = {"dir": str(worktree_path), "tag": "v3.0.0"}

    entry = sync_worktree(git_repo.path, wt_config, workspace_root, dry_run=True)

    assert entry.action == WorktreeAction.CREATE
    assert not worktree_path.exists()


# ---------------------------------------------------------------------------
# Worktree Prune Tests
# ---------------------------------------------------------------------------


def test_prune_worktrees_removes_orphaned(
    git_repo: GitSync,
    tmp_path: pathlib.Path,
) -> None:
    """Test pruning removes worktrees not in config."""
    workspace_root = git_repo.path.parent

    # Create worktrees
    wt1_path = workspace_root / "wt-configured"
    wt2_path = workspace_root / "wt-orphaned"

    subprocess.run(
        ["git", "worktree", "add", str(wt1_path), "HEAD", "--detach"],
        cwd=git_repo.path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "worktree", "add", str(wt2_path), "HEAD", "--detach"],
        cwd=git_repo.path,
        check=True,
        capture_output=True,
    )

    # Get commit SHA for config
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=git_repo.path,
        capture_output=True,
        text=True,
        check=True,
    )
    commit_sha = result.stdout.strip()

    # Only wt1 is in config
    config_worktrees: list[WorktreeConfigDict] = [
        {"dir": str(wt1_path), "commit": commit_sha},
    ]

    pruned = prune_worktrees(
        git_repo.path,
        config_worktrees,
        workspace_root,
    )

    assert len(pruned) == 1
    assert wt2_path in pruned
    assert not wt2_path.exists()
    assert wt1_path.exists()


def test_prune_worktrees_dry_run_no_remove(
    git_repo: GitSync,
    tmp_path: pathlib.Path,
) -> None:
    """Test dry run doesn't remove worktrees."""
    workspace_root = git_repo.path.parent

    wt_path = workspace_root / "wt-orphaned-dry"

    subprocess.run(
        ["git", "worktree", "add", str(wt_path), "HEAD", "--detach"],
        cwd=git_repo.path,
        check=True,
        capture_output=True,
    )

    pruned = prune_worktrees(
        git_repo.path,
        [],  # No configured worktrees
        workspace_root,
        dry_run=True,
    )

    assert len(pruned) == 1
    assert wt_path in pruned
    assert wt_path.exists()  # Still exists because dry_run


def test_list_existing_worktrees(
    git_repo: GitSync,
    tmp_path: pathlib.Path,
) -> None:
    """Test listing existing worktrees."""
    workspace_root = git_repo.path.parent

    wt1_path = workspace_root / "list-wt-1"
    wt2_path = workspace_root / "list-wt-2"

    subprocess.run(
        ["git", "worktree", "add", str(wt1_path), "HEAD", "--detach"],
        cwd=git_repo.path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "worktree", "add", str(wt2_path), "HEAD", "--detach"],
        cwd=git_repo.path,
        check=True,
        capture_output=True,
    )

    worktrees = list_existing_worktrees(git_repo.path)

    assert len(worktrees) == 2
    # Convert to set for comparison
    worktree_set = {wt.resolve() for wt in worktrees}
    assert wt1_path.resolve() in worktree_set
    assert wt2_path.resolve() in worktree_set


# ---------------------------------------------------------------------------
# Config Integration Tests
# ---------------------------------------------------------------------------


def test_extract_repos_with_worktrees(tmp_path: pathlib.Path) -> None:
    """Test extract_repos parses worktrees correctly."""
    raw_config = {
        "~/repos/": {
            "myproject": {
                "repo": "git+https://github.com/user/project.git",
                "worktrees": [
                    {"dir": "../myproject-v1", "tag": "v1.0.0"},
                    {"dir": "../myproject-dev", "branch": "develop"},
                ],
            },
        },
    }

    typed_config = t.cast("RawConfigDict", raw_config)
    repos = vcspull_config.extract_repos(typed_config, cwd=tmp_path)

    assert len(repos) == 1
    repo = repos[0]
    assert "worktrees" in repo
    worktrees = repo["worktrees"]
    assert worktrees is not None
    assert len(worktrees) == 2
    assert worktrees[0]["tag"] == "v1.0.0"
    assert worktrees[1]["branch"] == "develop"


def test_extract_repos_worktrees_validation_error(tmp_path: pathlib.Path) -> None:
    """Test extract_repos raises error for invalid worktree config."""
    raw_config = {
        "~/repos/": {
            "myproject": {
                "repo": "git+https://github.com/user/project.git",
                "worktrees": [
                    {"dir": "../myproject-v1"},  # Missing ref
                ],
            },
        },
    }

    with pytest.raises(exc.VCSPullException, match="must specify one of"):
        typed_config = t.cast("RawConfigDict", raw_config)
        vcspull_config.extract_repos(typed_config, cwd=tmp_path)


# ---------------------------------------------------------------------------
# CLI Integration Tests (basic)
# ---------------------------------------------------------------------------


def test_cli_worktree_help(capsys: pytest.CaptureFixture[str]) -> None:
    """Test vcspull worktree --help works."""
    from vcspull.cli import cli

    with pytest.raises(SystemExit) as exc_info:
        cli(["worktree", "--help"])

    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "worktree" in captured.out.lower()


def test_cli_worktree_list_no_config(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Test vcspull worktree list with no worktrees configured."""
    from vcspull.cli import cli

    # Create a minimal config without worktrees
    config_path = tmp_path / ".vcspull.yaml"
    config_path.write_text(
        """\
~/repos/:
  myproject:
    repo: git+https://github.com/user/project.git
""",
        encoding="utf-8",
    )

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path))

    cli(["worktree", "list", "-f", str(config_path)])

    captured = capsys.readouterr()
    assert "No repositories with worktrees configured" in captured.out


def test_sync_command_include_worktrees_flag_exists() -> None:
    """Test that --include-worktrees flag is available on sync command."""
    from vcspull.cli import create_parser

    parser = create_parser(return_subparsers=False)

    # Parse with the flag - should not raise
    args = parser.parse_args(["sync", "--include-worktrees", "--dry-run", "*"])
    assert args.include_worktrees is True
    assert args.dry_run is True


# ---------------------------------------------------------------------------
# Additional CLI Tests for Coverage
# ---------------------------------------------------------------------------


def test_cli_worktree_list_with_worktrees(
    git_repo: GitSync,
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Test vcspull worktree list with actual worktrees configured."""
    from vcspull.cli import cli

    # Create a tag in the repo
    subprocess.run(
        ["git", "tag", "v1.0.0"],
        cwd=git_repo.path,
        check=True,
        capture_output=True,
    )

    # Create config with worktrees
    config_path = tmp_path / ".vcspull.yaml"
    config_path.write_text(
        f"""\
{git_repo.path.parent}/:
  {git_repo.path.name}:
    repo: git+file://{git_repo.path}
    worktrees:
      - dir: ../{git_repo.path.name}-v1
        tag: v1.0.0
""",
        encoding="utf-8",
    )

    monkeypatch.chdir(tmp_path)

    cli(["worktree", "list", "-f", str(config_path)])

    captured = capsys.readouterr()
    assert git_repo.path.name in captured.out
    assert "v1.0.0" in captured.out


def test_cli_worktree_sync_dry_run(
    git_repo: GitSync,
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Test vcspull worktree sync --dry-run."""
    from vcspull.cli import cli

    # Create a tag in the repo
    subprocess.run(
        ["git", "tag", "v2.0.0"],
        cwd=git_repo.path,
        check=True,
        capture_output=True,
    )

    worktree_path = git_repo.path.parent / f"{git_repo.path.name}-v2"

    # Create config with worktrees
    config_path = tmp_path / ".vcspull.yaml"
    config_path.write_text(
        f"""\
{git_repo.path.parent}/:
  {git_repo.path.name}:
    repo: git+file://{git_repo.path}
    worktrees:
      - dir: {worktree_path}
        tag: v2.0.0
""",
        encoding="utf-8",
    )

    monkeypatch.chdir(tmp_path)

    cli(["worktree", "sync", "--dry-run", "-f", str(config_path)])

    captured = capsys.readouterr()
    assert "Would sync" in captured.out or "Summary" in captured.out
    # Worktree should NOT be created in dry-run
    assert not worktree_path.exists()


def test_cli_worktree_sync_creates_worktree(
    git_repo: GitSync,
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Test vcspull worktree sync actually creates worktrees."""
    from vcspull.cli import cli

    # Create a tag in the repo
    subprocess.run(
        ["git", "tag", "v3.0.0"],
        cwd=git_repo.path,
        check=True,
        capture_output=True,
    )

    worktree_path = git_repo.path.parent / f"{git_repo.path.name}-v3"

    # Create config with worktrees
    config_path = tmp_path / ".vcspull.yaml"
    config_path.write_text(
        f"""\
{git_repo.path.parent}/:
  {git_repo.path.name}:
    repo: git+file://{git_repo.path}
    worktrees:
      - dir: {worktree_path}
        tag: v3.0.0
""",
        encoding="utf-8",
    )

    monkeypatch.chdir(tmp_path)

    cli(["worktree", "sync", "-f", str(config_path)])

    captured = capsys.readouterr()
    assert "Synced" in captured.out or "Summary" in captured.out
    # Worktree SHOULD be created
    assert worktree_path.exists()
    assert (worktree_path / ".git").is_file()


def test_cli_worktree_prune_dry_run(
    git_repo: GitSync,
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Test vcspull worktree prune --dry-run."""
    from vcspull.cli import cli

    # Create an orphaned worktree (not in config)
    orphan_path = git_repo.path.parent / "orphaned-wt"
    subprocess.run(
        ["git", "worktree", "add", str(orphan_path), "HEAD", "--detach"],
        cwd=git_repo.path,
        check=True,
        capture_output=True,
    )

    # Get commit SHA for config
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=git_repo.path,
        capture_output=True,
        text=True,
        check=True,
    )
    commit_sha = result.stdout.strip()

    # Create config with no worktrees (so orphan should be pruned)
    config_path = tmp_path / ".vcspull.yaml"
    config_path.write_text(
        f"""\
{git_repo.path.parent}/:
  {git_repo.path.name}:
    repo: git+file://{git_repo.path}
    worktrees:
      - dir: {git_repo.path.parent / "configured-wt"}
        commit: {commit_sha}
""",
        encoding="utf-8",
    )

    monkeypatch.chdir(tmp_path)

    cli(["worktree", "prune", "--dry-run", "-f", str(config_path)])

    captured = capsys.readouterr()
    assert "Would prune" in captured.out
    # Orphan should still exist because it's dry-run
    assert orphan_path.exists()


# ---------------------------------------------------------------------------
# Additional worktree_sync.py Edge Case Tests for Coverage
# ---------------------------------------------------------------------------


def test_validate_worktree_config_empty_dir() -> None:
    """Test validate_worktree_config with empty dir."""
    from vcspull._internal.worktree_sync import validate_worktree_config

    with pytest.raises(exc.WorktreeConfigError, match="missing required 'dir' field"):
        validate_worktree_config(t.cast(WorktreeConfigDict, {"dir": "", "tag": "v1"}))


def test_plan_worktree_sync_invalid_config_error(
    git_repo: GitSync,
    tmp_path: pathlib.Path,
) -> None:
    """Test plan_worktree_sync with invalid config shows ERROR action."""
    workspace_root = git_repo.path.parent

    # Invalid config: missing dir
    worktrees_config: list[WorktreeConfigDict] = [
        t.cast(WorktreeConfigDict, {"tag": "v1.0.0"}),  # Missing "dir"
    ]

    entries = plan_worktree_sync(git_repo.path, worktrees_config, workspace_root)

    assert len(entries) == 1
    assert entries[0].action == WorktreeAction.ERROR
    assert "dir" in (entries[0].error or "").lower()


def test_sync_worktree_branch_update(
    git_repo: GitSync,
    tmp_path: pathlib.Path,
) -> None:
    """Test sync_worktree with existing branch worktree shows UPDATE action."""
    workspace_root = git_repo.path.parent
    worktree_path = workspace_root / "branch-update-wt"

    # Create a branch
    subprocess.run(
        ["git", "branch", "update-branch"],
        cwd=git_repo.path,
        check=True,
        capture_output=True,
    )

    # Create the worktree first
    subprocess.run(
        ["git", "worktree", "add", str(worktree_path), "update-branch"],
        cwd=git_repo.path,
        check=True,
        capture_output=True,
    )

    wt_config: WorktreeConfigDict = {
        "dir": str(worktree_path),
        "branch": "update-branch",
    }

    # Plan should show UPDATE action
    entries = plan_worktree_sync(git_repo.path, [wt_config], workspace_root)

    assert len(entries) == 1
    assert entries[0].action == WorktreeAction.UPDATE
    assert entries[0].exists is True


def test_sync_worktree_executes_update(
    git_repo: GitSync,
    tmp_path: pathlib.Path,
) -> None:
    """Test sync_worktree UPDATE action attempts git pull.

    Coverage: Lines 547-559 (UPDATE execution path in sync_worktree).

    Note: Since git_repo is a local-only repo without a remote, git pull fails.
    This tests that the UPDATE path IS exercised and handles the error correctly.
    The error path (lines 554-559) converts it to ERROR action.
    """
    workspace_root = git_repo.path.parent
    worktree_path = workspace_root / "update-exec-wt"

    # Create a branch
    subprocess.run(
        ["git", "branch", "update-exec-branch"],
        cwd=git_repo.path,
        check=True,
        capture_output=True,
    )

    # Create the worktree
    subprocess.run(
        ["git", "worktree", "add", str(worktree_path), "update-exec-branch"],
        cwd=git_repo.path,
        check=True,
        capture_output=True,
    )

    wt_config: WorktreeConfigDict = {
        "dir": str(worktree_path),
        "branch": "update-exec-branch",
    }

    # Sync without dry_run - attempts UPDATE but fails because no tracking info
    entry = sync_worktree(git_repo.path, wt_config, workspace_root, dry_run=False)

    # The UPDATE path was executed (lines 547-549), but git pull failed (lines 554-559)
    assert entry.action == WorktreeAction.ERROR
    assert entry.exists is True
    assert "no tracking information" in (entry.error or "").lower()


def test_sync_all_worktrees_counts_mixed(
    git_repo: GitSync,
    tmp_path: pathlib.Path,
) -> None:
    """Test sync_all_worktrees correctly counts each action type.

    Coverage: Lines 713-722 (action counting in sync_all_worktrees).

    Note: This test uses dry_run=True to count planning actions without
    executing, since git pull fails on local-only repos without remotes.
    """
    workspace_root = git_repo.path.parent

    # Create a valid tag
    subprocess.run(
        ["git", "tag", "v-count-test"],
        cwd=git_repo.path,
        check=True,
        capture_output=True,
    )

    # Create a branch and its worktree (for UPDATE)
    subprocess.run(
        ["git", "branch", "count-branch"],
        cwd=git_repo.path,
        check=True,
        capture_output=True,
    )
    branch_wt_path = workspace_root / "count-branch-wt"
    subprocess.run(
        ["git", "worktree", "add", str(branch_wt_path), "count-branch"],
        cwd=git_repo.path,
        check=True,
        capture_output=True,
    )

    # Create a tag worktree (for UNCHANGED)
    tag_wt_path = workspace_root / "count-tag-wt"
    subprocess.run(
        ["git", "worktree", "add", str(tag_wt_path), "v-count-test", "--detach"],
        cwd=git_repo.path,
        check=True,
        capture_output=True,
    )

    # Create a dirty worktree (for BLOCKED)
    dirty_wt_path = workspace_root / "count-dirty-wt"
    subprocess.run(
        ["git", "worktree", "add", str(dirty_wt_path), "HEAD", "--detach"],
        cwd=git_repo.path,
        check=True,
        capture_output=True,
    )
    # Make it dirty by adding an untracked file
    (dirty_wt_path / "dirty.txt").write_text("dirty content")

    # Get commit SHA for the dirty worktree config
    git_result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=git_repo.path,
        capture_output=True,
        text=True,
        check=True,
    )
    commit_sha = git_result.stdout.strip()

    worktrees_config: list[WorktreeConfigDict] = [
        # CREATE: new worktree for existing tag
        {"dir": str(workspace_root / "count-new-wt"), "tag": "v-count-test"},
        # UPDATE: existing branch worktree
        {"dir": str(branch_wt_path), "branch": "count-branch"},
        # UNCHANGED: existing tag worktree
        {"dir": str(tag_wt_path), "tag": "v-count-test"},
        # BLOCKED: dirty worktree
        {"dir": str(dirty_wt_path), "commit": commit_sha},
        # ERROR: invalid ref
        {"dir": str(workspace_root / "count-error-wt"), "tag": "v-nonexistent-tag"},
    ]

    # Use dry_run to test the counting without git pull side effects
    sync_result = sync_all_worktrees(
        git_repo.path,
        worktrees_config,
        workspace_root,
        dry_run=True,
    )

    # Verify counts (all branches through lines 713-722)
    assert sync_result.created == 1
    assert sync_result.updated == 1
    assert sync_result.unchanged == 1
    assert sync_result.blocked == 1
    assert sync_result.errors == 1
    assert len(sync_result.entries) == 5


def test_worktree_exists_with_git_dir(tmp_path: pathlib.Path) -> None:
    """Test _worktree_exists returns False for regular git directory."""
    from vcspull._internal.worktree_sync import _worktree_exists

    # Create a directory with .git as a directory (regular repo, not worktree)
    fake_repo = tmp_path / "fake_repo"
    fake_repo.mkdir()
    (fake_repo / ".git").mkdir()

    assert _worktree_exists(tmp_path, fake_repo) is False


def test_is_worktree_dirty_with_actual_dirty_state(
    git_repo: GitSync,
    tmp_path: pathlib.Path,
) -> None:
    """Test _is_worktree_dirty correctly detects dirty state."""
    from vcspull._internal.worktree_sync import _is_worktree_dirty

    worktree_path = git_repo.path.parent / "dirty-test-wt"

    # Create a clean worktree
    subprocess.run(
        ["git", "worktree", "add", str(worktree_path), "HEAD", "--detach"],
        cwd=git_repo.path,
        check=True,
        capture_output=True,
    )

    # Should be clean initially
    assert _is_worktree_dirty(worktree_path) is False

    # Make it dirty
    (worktree_path / "dirty.txt").write_text("dirty content")

    # Should now be dirty
    assert _is_worktree_dirty(worktree_path) is True


def test_ref_exists_with_commit(
    git_repo: GitSync,
) -> None:
    """Test _ref_exists correctly finds commits."""
    from vcspull._internal.worktree_sync import _ref_exists

    # Get current commit
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=git_repo.path,
        capture_output=True,
        text=True,
        check=True,
    )
    commit_sha = result.stdout.strip()

    assert _ref_exists(git_repo.path, commit_sha, "commit") is True
    assert _ref_exists(git_repo.path, "0000000000", "commit") is False


def test_get_worktree_head_with_actual_worktree(
    git_repo: GitSync,
    tmp_path: pathlib.Path,
) -> None:
    """Test _get_worktree_head returns commit SHA."""
    from vcspull._internal.worktree_sync import _get_worktree_head

    worktree_path = git_repo.path.parent / "head-test-wt"

    subprocess.run(
        ["git", "worktree", "add", str(worktree_path), "HEAD", "--detach"],
        cwd=git_repo.path,
        check=True,
        capture_output=True,
    )

    head = _get_worktree_head(worktree_path)
    assert head is not None
    assert len(head) == 40  # Full SHA


# ---------------------------------------------------------------------------
# CLI Coverage Gap Tests
# ---------------------------------------------------------------------------


def test_cli_worktree_sync_no_repos(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Test CLI sync shows message when no repos have worktrees.

    Coverage: Lines 270-273 in cli/worktree.py.
    """
    from vcspull.cli import cli

    # Create a config without worktrees key
    config_path = tmp_path / ".vcspull.yaml"
    config_path.write_text(
        """\
~/repos/:
  myproject:
    repo: git+https://github.com/user/project.git
""",
        encoding="utf-8",
    )

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path))

    cli(["worktree", "sync", "-f", str(config_path)])

    captured = capsys.readouterr()
    assert "No repositories with worktrees configured" in captured.out


def test_cli_worktree_prune_no_repos(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Test CLI prune shows message when no repos have worktrees.

    Coverage: Lines 338-341 in cli/worktree.py.
    """
    from vcspull.cli import cli

    # Create a config without worktrees key
    config_path = tmp_path / ".vcspull.yaml"
    config_path.write_text(
        """\
~/repos/:
  myproject:
    repo: git+https://github.com/user/project.git
""",
        encoding="utf-8",
    )

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path))

    cli(["worktree", "prune", "-f", str(config_path)])

    captured = capsys.readouterr()
    assert "No repositories with worktrees configured" in captured.out


def test_cli_worktree_prune_no_orphans(
    git_repo: GitSync,
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Test CLI prune shows 'No orphaned worktrees' when none exist.

    Coverage: Line 385 in cli/worktree.py.
    """
    from vcspull.cli import cli

    # Get commit SHA for config
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=git_repo.path,
        capture_output=True,
        text=True,
        check=True,
    )
    commit_sha = result.stdout.strip()

    # Create a worktree that IS configured (not orphaned)
    configured_wt = git_repo.path.parent / "configured-only-wt"
    subprocess.run(
        ["git", "worktree", "add", str(configured_wt), "HEAD", "--detach"],
        cwd=git_repo.path,
        check=True,
        capture_output=True,
    )

    # Create config where the existing worktree IS listed
    config_path = tmp_path / ".vcspull.yaml"
    config_path.write_text(
        f"""\
{git_repo.path.parent}/:
  {git_repo.path.name}:
    repo: git+file://{git_repo.path}
    worktrees:
      - dir: {configured_wt}
        commit: {commit_sha}
""",
        encoding="utf-8",
    )

    monkeypatch.chdir(tmp_path)

    cli(["worktree", "prune", "-f", str(config_path)])

    captured = capsys.readouterr()
    assert "No orphaned worktrees to prune" in captured.out
