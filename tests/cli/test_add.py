"""Tests for vcspull add command."""

from __future__ import annotations

import pathlib
import typing as t

import pytest

from vcspull.cli.add import add_repo

if t.TYPE_CHECKING:
    from _pytest.monkeypatch import MonkeyPatch


class AddRepoFixture(t.NamedTuple):
    """Fixture for add repo test cases."""

    test_id: str
    name: str
    url: str
    workspace_root: str | None
    path: str | None
    dry_run: bool
    expected_in_config: dict[str, t.Any]
    expected_log_messages: list[str]


ADD_REPO_FIXTURES: list[AddRepoFixture] = [
    AddRepoFixture(
        test_id="simple-add-default-workspace",
        name="myproject",
        url="git+https://github.com/user/myproject.git",
        workspace_root=None,
        path=None,
        dry_run=False,
        expected_in_config={
            "./": {
                "myproject": {"repo": "git+https://github.com/user/myproject.git"},
            },
        },
        expected_log_messages=["Successfully added 'myproject'"],
    ),
    AddRepoFixture(
        test_id="add-with-custom-workspace",
        name="flask",
        url="git+https://github.com/pallets/flask.git",
        workspace_root="~/code/",
        path=None,
        dry_run=False,
        expected_in_config={
            "~/code/": {
                "flask": {"repo": "git+https://github.com/pallets/flask.git"},
            },
        },
        expected_log_messages=["Successfully added 'flask'"],
    ),
    AddRepoFixture(
        test_id="dry-run-no-write",
        name="django",
        url="git+https://github.com/django/django.git",
        workspace_root=None,
        path=None,
        dry_run=True,
        expected_in_config={},  # Nothing written in dry-run
        expected_log_messages=["Would add 'django'"],
    ),
]


@pytest.mark.parametrize(
    list(AddRepoFixture._fields),
    ADD_REPO_FIXTURES,
    ids=[fixture.test_id for fixture in ADD_REPO_FIXTURES],
)
def test_add_repo(
    test_id: str,
    name: str,
    url: str,
    workspace_root: str | None,
    path: str | None,
    dry_run: bool,
    expected_in_config: dict[str, t.Any],
    expected_log_messages: list[str],
    tmp_path: pathlib.Path,
    monkeypatch: MonkeyPatch,
    caplog: t.Any,
) -> None:
    """Test adding a repository to the config."""
    # Set logging level to capture INFO messages
    import logging

    caplog.set_level(logging.INFO)

    # Set up temp directory as home
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)

    config_file = tmp_path / ".vcspull.yaml"

    # Run add_repo
    add_repo(
        name=name,
        url=url,
        config_file_path_str=str(config_file),
        path=path,
        workspace_root_path=workspace_root,
        dry_run=dry_run,
    )

    # Check log messages
    log_output = caplog.text
    for expected_msg in expected_log_messages:
        assert expected_msg in log_output, (
            f"Expected '{expected_msg}' in log output, got: {log_output}"
        )

    # Check config file
    if dry_run:
        # In dry-run mode, config file should not be created
        if len(expected_in_config) == 0:
            assert not config_file.exists(), (
                "Config file should not be created in dry-run mode"
            )
    else:
        # In normal mode, check the config was written correctly
        if len(expected_in_config) > 0:
            assert config_file.exists(), "Config file should be created"

            import yaml

            with config_file.open() as f:
                actual_config = yaml.safe_load(f)

            for workspace, repos in expected_in_config.items():
                assert workspace in actual_config, (
                    f"Workspace '{workspace}' should be in config"
                )
                for repo_name, repo_data in repos.items():
                    assert repo_name in actual_config[workspace], (
                        f"Repo '{repo_name}' should be in workspace '{workspace}'"
                    )
                    assert actual_config[workspace][repo_name] == repo_data


def test_add_repo_duplicate_warning(
    tmp_path: pathlib.Path,
    monkeypatch: MonkeyPatch,
    caplog: t.Any,
) -> None:
    """Test that adding a duplicate repository shows a warning."""
    import logging

    caplog.set_level(logging.INFO)

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)

    config_file = tmp_path / ".vcspull.yaml"

    # Add repo first time
    add_repo(
        name="myproject",
        url="git+https://github.com/user/myproject.git",
        config_file_path_str=str(config_file),
        path=None,
        workspace_root_path=None,
        dry_run=False,
    )

    # Clear logs
    caplog.clear()

    # Try to add again
    add_repo(
        name="myproject",
        url="git+https://github.com/user/myproject-v2.git",
        config_file_path_str=str(config_file),
        path=None,
        workspace_root_path=None,
        dry_run=False,
    )

    # Should have warning
    assert "already exists" in caplog.text


def test_add_repo_creates_new_file(
    tmp_path: pathlib.Path,
    monkeypatch: MonkeyPatch,
) -> None:
    """Test that add_repo creates a new config file if it doesn't exist."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)

    config_file = tmp_path / ".vcspull.yaml"
    assert not config_file.exists()

    add_repo(
        name="newrepo",
        url="git+https://github.com/user/newrepo.git",
        config_file_path_str=str(config_file),
        path=None,
        workspace_root_path=None,
        dry_run=False,
    )

    assert config_file.exists()

    import yaml

    with config_file.open() as f:
        config = yaml.safe_load(f)

    assert "./" in config
    assert "newrepo" in config["./"]
