"""Tests for vcspull list command."""

from __future__ import annotations

import json
import typing as t

import pytest
import yaml

from vcspull.cli.list import list_repos

if t.TYPE_CHECKING:
    import pathlib

    from _pytest.monkeypatch import MonkeyPatch


ConfigData: t.TypeAlias = dict[str, dict[str, dict[str, str]]]


def create_test_config(config_path: pathlib.Path, repos: ConfigData) -> None:
    """Create a test config file."""
    with config_path.open("w", encoding="utf-8") as f:
        yaml.dump(repos, f)


class ListReposFixture(t.NamedTuple):
    """Fixture for list repos test cases."""

    test_id: str
    config_data: ConfigData
    patterns: list[str]
    tree: bool
    output_json: bool
    output_ndjson: bool
    workspace_filter: str | None
    expected_repo_names: list[str]


LIST_REPOS_FIXTURES: list[ListReposFixture] = [
    ListReposFixture(
        test_id="list-all-repos",
        config_data={
            "~/code/": {
                "flask": {"repo": "git+https://github.com/pallets/flask.git"},
                "django": {"repo": "git+https://github.com/django/django.git"},
            },
        },
        patterns=[],
        tree=False,
        output_json=False,
        output_ndjson=False,
        workspace_filter=None,
        expected_repo_names=["flask", "django"],
    ),
    ListReposFixture(
        test_id="list-with-pattern",
        config_data={
            "~/code/": {
                "flask": {"repo": "git+https://github.com/pallets/flask.git"},
                "django": {"repo": "git+https://github.com/django/django.git"},
                "requests": {"repo": "git+https://github.com/psf/requests.git"},
            },
        },
        patterns=["fla*"],
        tree=False,
        output_json=False,
        output_ndjson=False,
        workspace_filter=None,
        expected_repo_names=["flask"],
    ),
    ListReposFixture(
        test_id="list-json-output",
        config_data={
            "~/code/": {
                "flask": {"repo": "git+https://github.com/pallets/flask.git"},
            },
        },
        patterns=[],
        tree=False,
        output_json=True,
        output_ndjson=False,
        workspace_filter=None,
        expected_repo_names=["flask"],
    ),
    ListReposFixture(
        test_id="list-ndjson-output",
        config_data={
            "~/code/": {
                "flask": {"repo": "git+https://github.com/pallets/flask.git"},
            },
        },
        patterns=[],
        tree=False,
        output_json=False,
        output_ndjson=True,
        workspace_filter=None,
        expected_repo_names=["flask"],
    ),
    ListReposFixture(
        test_id="list-workspace-filter",
        config_data={
            "~/code/": {
                "flask": {"repo": "git+https://github.com/pallets/flask.git"},
            },
            "~/work/": {
                "internal": {"repo": "git+https://github.com/user/internal.git"},
            },
        },
        patterns=[],
        tree=False,
        output_json=False,
        output_ndjson=False,
        workspace_filter="~/code/",
        expected_repo_names=["flask"],
    ),
]


@pytest.mark.parametrize(
    list(ListReposFixture._fields),
    LIST_REPOS_FIXTURES,
    ids=[fixture.test_id for fixture in LIST_REPOS_FIXTURES],
)
def test_list_repos(
    test_id: str,
    config_data: ConfigData,
    patterns: list[str],
    tree: bool,
    output_json: bool,
    output_ndjson: bool,
    workspace_filter: str | None,
    expected_repo_names: list[str],
    tmp_path: pathlib.Path,
    monkeypatch: MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Test listing repositories."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)

    config_file = tmp_path / ".vcspull.yaml"
    create_test_config(config_file, config_data)

    # Run list_repos
    list_repos(
        repo_patterns=patterns,
        config_path=config_file,
        workspace_root=workspace_filter,
        tree=tree,
        output_json=output_json,
        output_ndjson=output_ndjson,
        color="never",
    )

    captured = capsys.readouterr()

    if output_json:
        # Parse JSON output
        output_data = json.loads(captured.out)
        assert isinstance(output_data, list)
        repo_names_in_output = [item["name"] for item in output_data]
        for expected_name in expected_repo_names:
            assert expected_name in repo_names_in_output
    elif output_ndjson:
        # Parse NDJSON output
        lines = [line for line in captured.out.strip().split("\n") if line]
        repo_names_in_output = [json.loads(line)["name"] for line in lines]
        for expected_name in expected_repo_names:
            assert expected_name in repo_names_in_output
    else:
        # Human-readable output
        for expected_name in expected_repo_names:
            assert expected_name in captured.out


def test_list_repos_tree_mode(
    tmp_path: pathlib.Path,
    monkeypatch: MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Test listing repositories in tree mode."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)

    config_file = tmp_path / ".vcspull.yaml"
    config_data = {
        "~/code/": {
            "flask": {"repo": "git+https://github.com/pallets/flask.git"},
        },
        "~/work/": {
            "myproject": {"repo": "git+https://github.com/user/myproject.git"},
        },
    }
    create_test_config(config_file, config_data)

    list_repos(
        repo_patterns=[],
        config_path=config_file,
        workspace_root=None,
        tree=True,
        output_json=False,
        output_ndjson=False,
        color="never",
    )

    captured = capsys.readouterr()

    # Should show repos (workspace roots may be normalized to paths)
    assert "flask" in captured.out
    assert "myproject" in captured.out
    # Tree mode should group repos
    assert "•" in captured.out


def test_list_repos_empty_config(
    tmp_path: pathlib.Path,
    monkeypatch: MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Test listing with empty config shows appropriate message."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)

    config_file = tmp_path / ".vcspull.yaml"
    create_test_config(config_file, {})

    list_repos(
        repo_patterns=[],
        config_path=config_file,
        workspace_root=None,
        tree=False,
        output_json=False,
        output_ndjson=False,
        color="never",
    )

    captured = capsys.readouterr()
    assert "No repositories found" in captured.out


def test_list_repos_pattern_no_match(
    tmp_path: pathlib.Path,
    monkeypatch: MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Test listing with pattern that matches nothing."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)

    config_file = tmp_path / ".vcspull.yaml"
    config_data = {
        "~/code/": {
            "flask": {"repo": "git+https://github.com/pallets/flask.git"},
        },
    }
    create_test_config(config_file, config_data)

    list_repos(
        repo_patterns=["nonexistent*"],
        config_path=config_file,
        workspace_root=None,
        tree=False,
        output_json=False,
        output_ndjson=False,
        color="never",
    )

    captured = capsys.readouterr()
    assert "No repositories found" in captured.out


# Tests for path contraction in JSON output


class PathContractionFixture(t.NamedTuple):
    """Fixture for testing path contraction in JSON/NDJSON output."""

    test_id: str
    output_json: bool
    output_ndjson: bool
    tree: bool


PATH_CONTRACTION_FIXTURES: list[PathContractionFixture] = [
    PathContractionFixture(
        test_id="json-output-contracts-paths",
        output_json=True,
        output_ndjson=False,
        tree=False,
    ),
    PathContractionFixture(
        test_id="ndjson-output-contracts-paths",
        output_json=False,
        output_ndjson=True,
        tree=False,
    ),
    PathContractionFixture(
        test_id="json-tree-output-contracts-paths",
        output_json=True,
        output_ndjson=False,
        tree=True,
    ),
]


@pytest.mark.parametrize(
    list(PathContractionFixture._fields),
    PATH_CONTRACTION_FIXTURES,
    ids=[fixture.test_id for fixture in PATH_CONTRACTION_FIXTURES],
)
def test_list_repos_path_contraction(
    test_id: str,
    output_json: bool,
    output_ndjson: bool,
    tree: bool,
    tmp_path: pathlib.Path,
    monkeypatch: MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Test that JSON/NDJSON output contracts home directory paths."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)

    config_file = tmp_path / ".vcspull.yaml"
    config_data = {
        "~/code/": {
            "flask": {"repo": "git+https://github.com/pallets/flask.git"},
            "django": {"repo": "git+https://github.com/django/django.git"},
        },
    }
    create_test_config(config_file, config_data)

    list_repos(
        repo_patterns=[],
        config_path=config_file,
        workspace_root=None,
        tree=tree,
        output_json=output_json,
        output_ndjson=output_ndjson,
        color="never",
    )

    captured = capsys.readouterr()

    if output_json:
        output_data = json.loads(captured.out)
        assert isinstance(output_data, list)
        for item in output_data:
            path = item["path"]
            # Path should start with ~/ not /home/<user>/
            assert path.startswith("~/"), f"Path {path} should be contracted to ~/..."
            assert not path.startswith(str(tmp_path)), (
                f"Path {path} should not contain absolute home path"
            )
    elif output_ndjson:
        lines = [line for line in captured.out.strip().split("\n") if line]
        for line in lines:
            item = json.loads(line)
            path = item["path"]
            # Path should start with ~/ not /home/<user>/
            assert path.startswith("~/"), f"Path {path} should be contracted to ~/..."
            assert not path.startswith(str(tmp_path)), (
                f"Path {path} should not contain absolute home path"
            )
