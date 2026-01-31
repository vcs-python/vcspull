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
