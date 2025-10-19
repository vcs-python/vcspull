"""Tests for vcspull status command."""

from __future__ import annotations

import json
import pathlib
import subprocess
import typing as t

import pytest
import yaml

from vcspull.cli.status import check_repo_status, status_repos

if t.TYPE_CHECKING:
    from _pytest.monkeypatch import MonkeyPatch


def create_test_config(config_path: pathlib.Path, repos: dict[str, t.Any]) -> None:
    """Create a test config file."""
    with config_path.open("w") as f:
        yaml.dump(repos, f)


def init_git_repo(repo_path: pathlib.Path) -> None:
    """Initialize a git repository."""
    repo_path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init"], cwd=repo_path, check=True, capture_output=True)


def git(repo_path: pathlib.Path, *args: str) -> subprocess.CompletedProcess[bytes]:
    """Run a git command in the provided repository."""
    return subprocess.run(
        ["git", *args],
        cwd=repo_path,
        check=True,
        capture_output=True,
    )


def configure_git_identity(repo_path: pathlib.Path) -> None:
    """Configure Git author information for disposable repositories."""
    git(repo_path, "config", "user.email", "ci@example.com")
    git(repo_path, "config", "user.name", "vcspull-tests")


def commit_file(
    repo_path: pathlib.Path,
    filename: str,
    content: str,
    message: str,
) -> None:
    """Create a file, add it, and commit."""
    file_path = repo_path / filename
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content)
    git(repo_path, "add", filename)
    git(repo_path, "commit", "-m", message)


def setup_repo_with_remote(
    base_path: pathlib.Path,
) -> tuple[pathlib.Path, pathlib.Path]:
    """Create a repository with a bare remote and an initial commit."""
    remote_path = base_path / "remote.git"
    subprocess.run(
        ["git", "init", "--bare", str(remote_path)],
        check=True,
        capture_output=True,
    )

    repo_path = base_path / "workspace" / "project"
    repo_path.mkdir(parents=True, exist_ok=True)
    git(repo_path, "init")
    configure_git_identity(repo_path)
    commit_file(repo_path, "README.md", "initial", "feat: initial commit")
    git(repo_path, "branch", "-M", "main")
    git(repo_path, "remote", "add", "origin", str(remote_path))
    git(repo_path, "push", "-u", "origin", "main")

    return repo_path, remote_path


class CheckRepoStatusFixture(t.NamedTuple):
    """Fixture for check_repo_status test cases."""

    test_id: str
    create_repo: bool
    create_git: bool
    expected_exists: bool
    expected_is_git: bool


CHECK_REPO_STATUS_FIXTURES: list[CheckRepoStatusFixture] = [
    CheckRepoStatusFixture(
        test_id="repo-exists-with-git",
        create_repo=True,
        create_git=True,
        expected_exists=True,
        expected_is_git=True,
    ),
    CheckRepoStatusFixture(
        test_id="repo-exists-no-git",
        create_repo=True,
        create_git=False,
        expected_exists=True,
        expected_is_git=False,
    ),
    CheckRepoStatusFixture(
        test_id="repo-missing",
        create_repo=False,
        create_git=False,
        expected_exists=False,
        expected_is_git=False,
    ),
]


class StatusRunFixture(t.NamedTuple):
    """Fixture for end-to-end status command runs."""

    test_id: str
    workspace_filter: str | None
    output_ndjson: bool
    expected_names: list[str]


STATUS_RUN_FIXTURES: list[StatusRunFixture] = [
    StatusRunFixture(
        test_id="workspace-filter",
        workspace_filter="~/code/",
        output_ndjson=False,
        expected_names=["repo1"],
    ),
    StatusRunFixture(
        test_id="ndjson-output",
        workspace_filter=None,
        output_ndjson=True,
        expected_names=["repo1"],
    ),
]


class StatusDetailedFixture(t.NamedTuple):
    """Fixture for detailed status scenarios."""

    test_id: str
    make_dirty: bool
    local_ahead: bool
    local_behind: bool
    expected_clean: bool
    expected_ahead: int
    expected_behind: int


STATUS_DETAILED_FIXTURES: list[StatusDetailedFixture] = [
    StatusDetailedFixture(
        test_id="clean-in-sync",
        make_dirty=False,
        local_ahead=False,
        local_behind=False,
        expected_clean=True,
        expected_ahead=0,
        expected_behind=0,
    ),
    StatusDetailedFixture(
        test_id="dirty-working-tree",
        make_dirty=True,
        local_ahead=False,
        local_behind=False,
        expected_clean=False,
        expected_ahead=0,
        expected_behind=0,
    ),
    StatusDetailedFixture(
        test_id="ahead-of-remote",
        make_dirty=False,
        local_ahead=True,
        local_behind=False,
        expected_clean=True,
        expected_ahead=1,
        expected_behind=0,
    ),
    StatusDetailedFixture(
        test_id="behind-remote",
        make_dirty=False,
        local_ahead=False,
        local_behind=True,
        expected_clean=True,
        expected_ahead=0,
        expected_behind=1,
    ),
]


@pytest.mark.parametrize(
    list(CheckRepoStatusFixture._fields),
    CHECK_REPO_STATUS_FIXTURES,
    ids=[fixture.test_id for fixture in CHECK_REPO_STATUS_FIXTURES],
)
def test_check_repo_status(
    test_id: str,
    create_repo: bool,
    create_git: bool,
    expected_exists: bool,
    expected_is_git: bool,
    tmp_path: pathlib.Path,
) -> None:
    """Test checking individual repository status."""
    repo_path = tmp_path / "test-repo"

    if create_repo:
        if create_git:
            init_git_repo(repo_path)
        else:
            repo_path.mkdir(parents=True)

    repo_dict: t.Any = {"name": "test-repo", "path": str(repo_path)}

    status = check_repo_status(repo_dict, detailed=False)

    assert status["exists"] == expected_exists
    assert status["is_git"] == expected_is_git
    assert status["name"] == "test-repo"


def test_status_repos_all(
    tmp_path: pathlib.Path,
    monkeypatch: MonkeyPatch,
    capsys: t.Any,
) -> None:
    """Test checking status of all repositories."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)

    # Create config with repos
    config_file = tmp_path / ".vcspull.yaml"
    repo1_path = tmp_path / "code" / "repo1"

    config_data = {
        str(tmp_path / "code") + "/": {
            "repo1": {"repo": "git+https://github.com/user/repo1.git"},
            "repo2": {"repo": "git+https://github.com/user/repo2.git"},
        },
    }
    create_test_config(config_file, config_data)

    # Create one repo, leave other missing
    init_git_repo(repo1_path)

    # Run status
    status_repos(
        repo_patterns=[],
        config_path=config_file,
        workspace_root=None,
        detailed=False,
        output_json=False,
        output_ndjson=False,
        color="never",
    )

    captured = capsys.readouterr()

    # Should mention repo1 exists
    assert "repo1" in captured.out
    # Should mention repo2 is missing
    assert "repo2" in captured.out
    assert "missing" in captured.out.lower()
    # Should have summary
    assert "Summary" in captured.out


def test_status_repos_json_output(
    tmp_path: pathlib.Path,
    monkeypatch: MonkeyPatch,
    capsys: t.Any,
) -> None:
    """Test status output in JSON format."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)

    config_file = tmp_path / ".vcspull.yaml"
    repo_path = tmp_path / "code" / "myrepo"

    config_data = {
        str(tmp_path / "code") + "/": {
            "myrepo": {"repo": "git+https://github.com/user/myrepo.git"},
        },
    }
    create_test_config(config_file, config_data)

    # Create the repo
    init_git_repo(repo_path)

    # Run status with JSON output
    status_repos(
        repo_patterns=[],
        config_path=config_file,
        workspace_root=None,
        detailed=False,
        output_json=True,
        output_ndjson=False,
        color="never",
    )

    captured = capsys.readouterr()

    # Parse JSON output
    output_data = json.loads(captured.out)
    assert isinstance(output_data, list)

    # Find status and summary entries
    status_entries = [item for item in output_data if item.get("reason") == "status"]
    summary_entries = [item for item in output_data if item.get("reason") == "summary"]

    assert len(status_entries) > 0
    assert len(summary_entries) == 1

    # Check status entry
    repo_status = status_entries[0]
    assert repo_status["name"] == "myrepo"
    assert repo_status["exists"] is True
    assert repo_status["is_git"] is True


def test_status_repos_detailed(
    tmp_path: pathlib.Path,
    monkeypatch: MonkeyPatch,
    capsys: t.Any,
) -> None:
    """Test detailed status output."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)

    config_file = tmp_path / ".vcspull.yaml"
    repo_path, remote_path = setup_repo_with_remote(tmp_path)

    config_data = {
        str(repo_path.parent) + "/": {
            "project": {"repo": f"git+file://{remote_path}"},
        },
    }
    create_test_config(config_file, config_data)

    # Run status with detailed mode
    status_repos(
        repo_patterns=[],
        config_path=config_file,
        workspace_root=None,
        detailed=True,
        output_json=False,
        output_ndjson=False,
        color="never",
    )

    captured = capsys.readouterr()

    # Should show path and branch details in detailed mode
    assert "Path:" in captured.out or str(repo_path) in captured.out
    assert "Branch:" in captured.out
    assert "Ahead/Behind:" in captured.out


def test_status_repos_pattern_filter(
    tmp_path: pathlib.Path,
    monkeypatch: MonkeyPatch,
    capsys: t.Any,
) -> None:
    """Test status with pattern filtering."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)

    config_file = tmp_path / ".vcspull.yaml"

    config_data = {
        str(tmp_path / "code") + "/": {
            "flask": {"repo": "git+https://github.com/pallets/flask.git"},
            "django": {"repo": "git+https://github.com/django/django.git"},
        },
    }
    create_test_config(config_file, config_data)

    # Run status with pattern
    status_repos(
        repo_patterns=["fla*"],
        config_path=config_file,
        workspace_root=None,
        detailed=False,
        output_json=False,
        output_ndjson=False,
        color="never",
    )

    captured = capsys.readouterr()

    # Should only show flask
    assert "flask" in captured.out
    assert "django" not in captured.out


@pytest.mark.parametrize(
    list(StatusRunFixture._fields),
    STATUS_RUN_FIXTURES,
    ids=[fixture.test_id for fixture in STATUS_RUN_FIXTURES],
)
def test_status_repos_workspace_filter_and_ndjson(
    test_id: str,
    workspace_filter: str | None,
    output_ndjson: bool,
    expected_names: list[str],
    tmp_path: pathlib.Path,
    monkeypatch: MonkeyPatch,
    capsys: t.Any,
) -> None:
    """Test status workspace filtering and NDJSON output."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)

    config_file = tmp_path / ".vcspull.yaml"
    repo_path = tmp_path / "code" / "repo1"
    other_repo_path = tmp_path / "work" / "repo2"

    config_data = {
        str(tmp_path / "code") + "/": {
            "repo1": {"repo": "git+https://github.com/user/repo1.git"},
        },
        str(tmp_path / "work") + "/": {
            "repo2": {"repo": "git+https://github.com/user/repo2.git"},
        },
    }
    create_test_config(config_file, config_data)

    init_git_repo(repo_path)
    init_git_repo(other_repo_path)

    status_repos(
        repo_patterns=[],
        config_path=config_file,
        workspace_root=workspace_filter,
        detailed=False,
        output_json=False,
        output_ndjson=output_ndjson,
        color="never",
    )

    captured = capsys.readouterr()

    if output_ndjson:
        status_entries = []
        for line in captured.out.splitlines():
            line = line.strip()
            if not line:
                continue
            payload = json.loads(line)
            if payload.get("reason") == "status":
                status_entries.append(payload)
        names = [entry["name"] for entry in status_entries]
        for expected in expected_names:
            assert expected in names
    else:
        for expected in expected_names:
            assert expected in captured.out
        # Ensure other repo is not shown when filtered
        if workspace_filter:
            assert "repo2" not in captured.out


@pytest.mark.parametrize(
    list(StatusDetailedFixture._fields),
    STATUS_DETAILED_FIXTURES,
    ids=[fixture.test_id for fixture in STATUS_DETAILED_FIXTURES],
)
def test_status_repos_detailed_metrics(
    test_id: str,
    make_dirty: bool,
    local_ahead: bool,
    local_behind: bool,
    expected_clean: bool,
    expected_ahead: int,
    expected_behind: int,
    tmp_path: pathlib.Path,
    monkeypatch: MonkeyPatch,
    capsys: t.Any,
) -> None:
    """Detailed output includes branch and ahead/behind counters."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)

    repo_path, remote_path = setup_repo_with_remote(tmp_path)

    if make_dirty:
        dirty_file = repo_path / f"dirty-{test_id}.txt"
        dirty_file.write_text("dirty worktree")

    if local_ahead:
        commit_file(
            repo_path,
            f"ahead-{test_id}.txt",
            "ahead",
            f"feat: ahead commit for {test_id}",
        )

    if local_behind:
        other_clone = tmp_path / "other"
        subprocess.run(
            ["git", "clone", str(remote_path), str(other_clone)],
            check=True,
            capture_output=True,
        )
        git(other_clone, "checkout", "-B", "main", "origin/main")
        configure_git_identity(other_clone)
        commit_file(
            other_clone,
            f"remote-{test_id}.txt",
            "remote",
            f"feat: remote commit for {test_id}",
        )
        git(other_clone, "push", "origin", "main")
        git(repo_path, "fetch", "origin")

    config_file = tmp_path / ".vcspull.yaml"
    config_data = {
        str(repo_path.parent) + "/": {
            "project": {"repo": f"git+file://{remote_path}"},
        },
    }
    create_test_config(config_file, config_data)

    status_repos(
        repo_patterns=[],
        config_path=config_file,
        workspace_root=None,
        detailed=True,
        output_json=True,
        output_ndjson=False,
        color="never",
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    status_entries = [entry for entry in payload if entry.get("reason") == "status"]
    assert len(status_entries) == 1

    entry = status_entries[0]
    assert entry["name"] == "project"
    assert entry["branch"] == "main"
    assert entry["clean"] == expected_clean
    assert entry["ahead"] == expected_ahead
    assert entry["behind"] == expected_behind
