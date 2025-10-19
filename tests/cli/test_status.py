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
    repo_path = tmp_path / "code" / "myrepo"

    config_data = {
        str(tmp_path / "code") + "/": {
            "myrepo": {"repo": "git+https://github.com/user/myrepo.git"},
        },
    }
    create_test_config(config_file, config_data)

    init_git_repo(repo_path)

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

    # Should show path in detailed mode
    assert "Path:" in captured.out or str(repo_path) in captured.out


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
