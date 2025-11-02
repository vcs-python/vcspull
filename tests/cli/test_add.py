"""Tests for vcspull add command."""

from __future__ import annotations

import argparse
import logging
import subprocess
import typing as t

import pytest

from vcspull.cli.add import add_repo, handle_add_command
from vcspull.util import contract_user_home

if t.TYPE_CHECKING:
    import pathlib

    from _pytest.monkeypatch import MonkeyPatch


class AddRepoFixture(t.NamedTuple):
    """Fixture for add repo test cases."""

    test_id: str
    name: str
    url: str
    workspace_root: str | None
    path_relative: str | None
    dry_run: bool
    use_default_config: bool
    preexisting_config: dict[str, t.Any] | None
    expected_in_config: dict[str, t.Any]
    expected_log_messages: list[str]


def init_git_repo(repo_path: pathlib.Path, remote_url: str | None) -> None:
    """Initialize a git repository with an optional origin remote."""
    repo_path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q", str(repo_path)], check=True)
    if remote_url:
        subprocess.run(
            ["git", "-C", str(repo_path), "remote", "add", "origin", remote_url],
            check=True,
        )


ADD_REPO_FIXTURES: list[AddRepoFixture] = [
    AddRepoFixture(
        test_id="simple-add-default-workspace",
        name="myproject",
        url="git+https://github.com/user/myproject.git",
        workspace_root=None,
        path_relative=None,
        dry_run=False,
        use_default_config=False,
        preexisting_config=None,
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
        path_relative=None,
        dry_run=False,
        use_default_config=False,
        preexisting_config=None,
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
        path_relative=None,
        dry_run=True,
        use_default_config=False,
        preexisting_config=None,
        expected_in_config={},  # Nothing written in dry-run
        expected_log_messages=["Would add 'django'"],
    ),
    AddRepoFixture(
        test_id="default-config-created-when-missing",
        name="autoproject",
        url="git+https://github.com/user/autoproject.git",
        workspace_root=None,
        path_relative=None,
        dry_run=False,
        use_default_config=True,
        preexisting_config=None,
        expected_in_config={
            "./": {
                "autoproject": {
                    "repo": "git+https://github.com/user/autoproject.git",
                },
            },
        },
        expected_log_messages=[
            "No config specified and no default found",
            "Successfully added 'autoproject'",
        ],
    ),
    AddRepoFixture(
        test_id="path-inferrs-workspace-root",
        name="lib",
        url="git+https://github.com/user/lib.git",
        workspace_root=None,
        path_relative="code/lib",
        dry_run=False,
        use_default_config=False,
        preexisting_config=None,
        expected_in_config={
            "~/code/lib/": {
                "lib": {"repo": "git+https://github.com/user/lib.git"},
            },
        },
        expected_log_messages=["Successfully added 'lib'"],
    ),
    AddRepoFixture(
        test_id="normalizes-existing-workspace-label",
        name="extra",
        url="git+https://github.com/user/extra.git",
        workspace_root=None,
        path_relative=None,
        dry_run=False,
        use_default_config=False,
        preexisting_config={
            "~/code": {
                "existing": {"repo": "git+https://github.com/user/existing.git"},
            },
        },
        expected_in_config={
            "~/code/": {
                "existing": {"repo": "git+https://github.com/user/existing.git"},
            },
            "./": {
                "extra": {"repo": "git+https://github.com/user/extra.git"},
            },
        },
        expected_log_messages=["Successfully added 'extra'"],
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
    path_relative: str | None,
    dry_run: bool,
    use_default_config: bool,
    preexisting_config: dict[str, t.Any] | None,
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

    target_config_file = tmp_path / ".vcspull.yaml"
    config_argument: str | None = (
        None if use_default_config else str(target_config_file)
    )

    if preexisting_config is not None:
        import yaml

        target_config_file.write_text(
            yaml.dump(preexisting_config),
            encoding="utf-8",
        )

    path_argument = str(tmp_path / path_relative) if path_relative else None

    # Run add_repo
    add_repo(
        name=name,
        url=url,
        config_file_path_str=config_argument,
        path=path_argument,
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
        if len(expected_in_config) == 0 and not use_default_config:
            assert not target_config_file.exists(), (
                "Config file should not be created in dry-run mode"
            )
    # In normal mode, check the config was written correctly
    elif len(expected_in_config) > 0:
        assert target_config_file.exists(), "Config file should be created"

        import yaml

        with target_config_file.open() as f:
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


def test_add_repo_merges_duplicate_workspace_roots(
    tmp_path: pathlib.Path,
    monkeypatch: MonkeyPatch,
    caplog: t.Any,
) -> None:
    """Duplicate workspace roots are merged without losing repositories."""
    import yaml

    caplog.set_level(logging.INFO)

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)

    config_file = tmp_path / ".vcspull.yaml"
    config_file.write_text(
        (
            "~/study/python/:\n"
            "  repo1:\n"
            "    repo: git+https://example.com/repo1.git\n"
            "~/study/python/:\n"
            "  repo2:\n"
            "    repo: git+https://example.com/repo2.git\n"
        ),
        encoding="utf-8",
    )

    add_repo(
        name="pytest-docker",
        url="git+https://github.com/avast/pytest-docker.git",
        config_file_path_str=str(config_file),
        path=str(tmp_path / "study/python/pytest-docker"),
        workspace_root_path="~/study/python/",
        dry_run=False,
    )

    with config_file.open() as fh:
        merged_config = yaml.safe_load(fh)

    assert "~/study/python/" in merged_config
    repos = merged_config["~/study/python/"]
    assert set(repos.keys()) == {"repo1", "repo2", "pytest-docker"}

    assert "Merged" in caplog.text


class PathAddFixture(t.NamedTuple):
    """Fixture describing CLI path-mode add scenarios."""

    test_id: str
    remote_url: str | None
    assume_yes: bool
    prompt_response: str | None
    dry_run: bool
    expected_written: bool
    expected_url_kind: str  # "remote" or "path"
    override_name: str | None
    expected_warning: str | None


PATH_ADD_FIXTURES: list[PathAddFixture] = [
    PathAddFixture(
        test_id="path-auto-confirm",
        remote_url="https://github.com/avast/pytest-docker",
        assume_yes=True,
        prompt_response=None,
        dry_run=False,
        expected_written=True,
        expected_url_kind="remote",
        override_name=None,
        expected_warning=None,
    ),
    PathAddFixture(
        test_id="path-interactive-accept",
        remote_url="https://github.com/example/project",
        assume_yes=False,
        prompt_response="y",
        dry_run=False,
        expected_written=True,
        expected_url_kind="remote",
        override_name="project-alias",
        expected_warning=None,
    ),
    PathAddFixture(
        test_id="path-interactive-decline",
        remote_url="https://github.com/example/decline",
        assume_yes=False,
        prompt_response="n",
        dry_run=False,
        expected_written=False,
        expected_url_kind="remote",
        override_name=None,
        expected_warning=None,
    ),
    PathAddFixture(
        test_id="path-no-remote",
        remote_url=None,
        assume_yes=True,
        prompt_response=None,
        dry_run=False,
        expected_written=True,
        expected_url_kind="path",
        override_name=None,
        expected_warning="Unable to determine git remote",
    ),
]


@pytest.mark.parametrize(
    list(PathAddFixture._fields),
    PATH_ADD_FIXTURES,
    ids=[fixture.test_id for fixture in PATH_ADD_FIXTURES],
)
def test_handle_add_command_path_mode(
    test_id: str,
    remote_url: str | None,
    assume_yes: bool,
    prompt_response: str | None,
    dry_run: bool,
    expected_written: bool,
    expected_url_kind: str,
    override_name: str | None,
    expected_warning: str | None,
    tmp_path: pathlib.Path,
    monkeypatch: MonkeyPatch,
    caplog: t.Any,
) -> None:
    """CLI path mode prompts and adds repositories appropriately."""
    caplog.set_level(logging.INFO)

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)

    repo_path = tmp_path / "study/python/pytest-docker"
    init_git_repo(repo_path, remote_url)

    config_file = tmp_path / ".vcspull.yaml"

    expected_input = prompt_response if prompt_response is not None else "y"
    monkeypatch.setattr("builtins.input", lambda _: expected_input)

    args = argparse.Namespace(
        target=str(repo_path),
        url=None,
        override_name=override_name,
        config=str(config_file),
        path=None,
        workspace_root_path=None,
        dry_run=dry_run,
        assume_yes=assume_yes,
    )

    handle_add_command(args)

    log_output = caplog.text
    contracted_path = contract_user_home(repo_path)

    assert "Found new repository to import" in log_output
    assert contracted_path in log_output

    if dry_run:
        assert "skipped (dry-run)" in log_output

    if assume_yes:
        assert "auto-confirm" in log_output

    if expected_warning is not None:
        assert expected_warning in log_output

    repo_name = override_name or repo_path.name

    if expected_written:
        import yaml

        assert config_file.exists()
        with config_file.open(encoding="utf-8") as fh:
            config_data = yaml.safe_load(fh)

        workspace = "~/study/python/"
        assert workspace in config_data
        assert repo_name in config_data[workspace]

        repo_entry = config_data[workspace][repo_name]
        expected_url: str
        if expected_url_kind == "remote" and remote_url is not None:
            cleaned_remote = remote_url.strip()
            expected_url = (
                cleaned_remote
                if cleaned_remote.startswith("git+")
                else f"git+{cleaned_remote}"
            )
        else:
            expected_url = str(repo_path)

        assert repo_entry == {"repo": expected_url}
    else:
        if config_file.exists():
            import yaml

            with config_file.open(encoding="utf-8") as fh:
                config_data = yaml.safe_load(fh)
            if config_data is not None:
                workspace = config_data.get("~/study/python/")
                if workspace is not None:
                    assert repo_name not in workspace
        assert "Aborted import" in log_output
