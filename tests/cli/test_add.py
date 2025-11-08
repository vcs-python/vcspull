"""Tests for vcspull add command."""

from __future__ import annotations

import argparse
import logging
import os
import re
import subprocess
import textwrap
import typing as t

import pytest

from vcspull._internal.config_reader import DuplicateAwareConfigReader
from vcspull._internal.private_path import PrivatePath
from vcspull.cli.add import add_repo, create_add_subparser, handle_add_command

if t.TYPE_CHECKING:
    import pathlib

    from _pytest.monkeypatch import MonkeyPatch
    from syrupy.assertion import SnapshotAssertion


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
        path_relative="myproject",
        dry_run=False,
        use_default_config=False,
        preexisting_config=None,
        expected_in_config={
            "~/": {
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
        path_relative="autoproject",
        dry_run=False,
        use_default_config=True,
        preexisting_config=None,
        expected_in_config={
            "~/": {
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
            "~/code/": {
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
        path_relative="extra",
        dry_run=False,
        use_default_config=False,
        preexisting_config={
            "~/code": {
                "existing": {"repo": "git+https://github.com/user/existing.git"},
            },
        },
        expected_in_config={
            "~/code": {
                "existing": {"repo": "git+https://github.com/user/existing.git"},
            },
            "~/": {
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
    repo_path = tmp_path / "myproject"
    repo_path.mkdir()

    # Add repo first time
    add_repo(
        name="myproject",
        url="git+https://github.com/user/myproject.git",
        config_file_path_str=str(config_file),
        path=str(repo_path),
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
        path=str(repo_path),
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

    repo_path = tmp_path / "newrepo"
    repo_path.mkdir()

    add_repo(
        name="newrepo",
        url="git+https://github.com/user/newrepo.git",
        config_file_path_str=str(config_file),
        path=str(repo_path),
        workspace_root_path=None,
        dry_run=False,
    )

    assert config_file.exists()

    import yaml

    with config_file.open() as f:
        config = yaml.safe_load(f)

    assert "~/" in config
    assert "newrepo" in config["~/"]


class AddDuplicateMergeFixture(t.NamedTuple):
    """Fixture describing duplicate merge toggles for add_repo."""

    test_id: str
    merge_duplicates: bool
    expected_repo_names: set[str]
    expected_warning: str | None


ADD_DUPLICATE_MERGE_FIXTURES: list[AddDuplicateMergeFixture] = [
    AddDuplicateMergeFixture(
        test_id="merge-on",
        merge_duplicates=True,
        expected_repo_names={"repo1", "repo2", "pytest-docker"},
        expected_warning=None,
    ),
    AddDuplicateMergeFixture(
        test_id="merge-off",
        merge_duplicates=False,
        expected_repo_names={"repo2", "pytest-docker"},
        expected_warning="Duplicate workspace root",
    ),
]


@pytest.mark.parametrize(
    list(AddDuplicateMergeFixture._fields),
    ADD_DUPLICATE_MERGE_FIXTURES,
    ids=[fixture.test_id for fixture in ADD_DUPLICATE_MERGE_FIXTURES],
)
def test_add_repo_duplicate_merge_behavior(
    test_id: str,
    merge_duplicates: bool,
    expected_repo_names: set[str],
    expected_warning: str | None,
    tmp_path: pathlib.Path,
    monkeypatch: MonkeyPatch,
    caplog: t.Any,
    snapshot: SnapshotAssertion,
) -> None:
    """Duplicate workspace roots log appropriately based on merge toggle."""
    import yaml

    caplog.set_level(logging.INFO)

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)

    config_file = tmp_path / ".vcspull.yaml"
    config_file.write_text(
        textwrap.dedent(
            """\
            ~/study/python/:
              repo1:
                repo: git+https://example.com/repo1.git
            ~/study/python/:
              repo2:
                repo: git+https://example.com/repo2.git
            """,
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
        merge_duplicates=merge_duplicates,
    )

    with config_file.open(encoding="utf-8") as fh:
        config_after = yaml.safe_load(fh)

    assert "~/study/python/" in config_after
    repos = config_after["~/study/python/"]
    assert set(repos.keys()) == expected_repo_names

    if expected_warning is not None:
        assert expected_warning in caplog.text

    normalized_log = caplog.text.replace(str(config_file), "<config>")
    normalized_log = re.sub(r"add\.py:\d+", "add.py:<line>", normalized_log)
    snapshot.assert_match({"test_id": test_id, "log": normalized_log})


class PathAddFixture(t.NamedTuple):
    """Fixture describing CLI path-mode add scenarios."""

    test_id: str
    remote_url: str | None
    explicit_url: str | None
    assume_yes: bool
    prompt_response: str | None
    dry_run: bool
    expected_written: bool
    expected_url_kind: str  # "remote", "path", or "explicit"
    override_name: str | None
    expected_warning: str | None
    merge_duplicates: bool
    preexisting_yaml: str | None
    use_relative_repo_path: bool
    workspace_override: str | None
    expected_workspace_label: str
    preserve_config_path_in_log: bool


PATH_ADD_FIXTURES: list[PathAddFixture] = [
    PathAddFixture(
        test_id="path-auto-confirm",
        remote_url="https://github.com/avast/pytest-docker",
        explicit_url=None,
        assume_yes=True,
        prompt_response=None,
        dry_run=False,
        expected_written=True,
        expected_url_kind="remote",
        override_name=None,
        expected_warning=None,
        merge_duplicates=True,
        preexisting_yaml=None,
        use_relative_repo_path=False,
        workspace_override=None,
        expected_workspace_label="~/study/python/",
        preserve_config_path_in_log=False,
    ),
    PathAddFixture(
        test_id="path-interactive-accept",
        remote_url="https://github.com/example/project",
        explicit_url=None,
        assume_yes=False,
        prompt_response="y",
        dry_run=False,
        expected_written=True,
        expected_url_kind="remote",
        override_name="project-alias",
        expected_warning=None,
        merge_duplicates=True,
        preexisting_yaml=None,
        use_relative_repo_path=False,
        workspace_override=None,
        expected_workspace_label="~/study/python/",
        preserve_config_path_in_log=False,
    ),
    PathAddFixture(
        test_id="path-interactive-decline",
        remote_url="https://github.com/example/decline",
        explicit_url=None,
        assume_yes=False,
        prompt_response="n",
        dry_run=False,
        expected_written=False,
        expected_url_kind="remote",
        override_name=None,
        expected_warning=None,
        merge_duplicates=True,
        preexisting_yaml=None,
        use_relative_repo_path=False,
        workspace_override=None,
        expected_workspace_label="~/study/python/",
        preserve_config_path_in_log=False,
    ),
    PathAddFixture(
        test_id="path-no-remote",
        remote_url=None,
        explicit_url=None,
        assume_yes=True,
        prompt_response=None,
        dry_run=False,
        expected_written=True,
        expected_url_kind="path",
        override_name=None,
        expected_warning="Unable to determine git remote",
        merge_duplicates=True,
        preexisting_yaml=None,
        use_relative_repo_path=False,
        workspace_override=None,
        expected_workspace_label="~/study/python/",
        preserve_config_path_in_log=False,
    ),
    PathAddFixture(
        test_id="path-no-merge",
        remote_url="https://github.com/example/no-merge",
        explicit_url=None,
        assume_yes=True,
        prompt_response=None,
        dry_run=False,
        expected_written=True,
        expected_url_kind="remote",
        override_name=None,
        expected_warning="Duplicate workspace root",
        merge_duplicates=False,
        preexisting_yaml="""
~/study/python/:
  repo1:
    repo: git+https://example.com/repo1.git
~/study/python/:
  repo2:
    repo: git+https://example.com/repo2.git
""",
        use_relative_repo_path=False,
        workspace_override=None,
        expected_workspace_label="~/study/python/",
        preserve_config_path_in_log=False,
    ),
    PathAddFixture(
        test_id="path-explicit-url",
        remote_url=None,
        explicit_url="https://github.com/manual/source",
        assume_yes=True,
        prompt_response=None,
        dry_run=False,
        expected_written=True,
        expected_url_kind="explicit",
        override_name=None,
        expected_warning=None,
        merge_duplicates=True,
        preexisting_yaml=None,
        use_relative_repo_path=False,
        workspace_override=None,
        expected_workspace_label="~/study/python/",
        preserve_config_path_in_log=False,
    ),
    PathAddFixture(
        test_id="path-relative-derives-workspace",
        remote_url="https://github.com/example/rel",
        explicit_url=None,
        assume_yes=True,
        prompt_response=None,
        dry_run=False,
        expected_written=True,
        expected_url_kind="remote",
        override_name=None,
        expected_warning=None,
        merge_duplicates=True,
        preexisting_yaml=None,
        use_relative_repo_path=True,
        workspace_override=None,
        expected_workspace_label="~/study/python/",
        preserve_config_path_in_log=False,
    ),
    PathAddFixture(
        test_id="path-workspace-override",
        remote_url="https://github.com/example/workspace",
        explicit_url=None,
        assume_yes=True,
        prompt_response=None,
        dry_run=False,
        expected_written=True,
        expected_url_kind="remote",
        override_name=None,
        expected_warning=None,
        merge_duplicates=True,
        preexisting_yaml=None,
        use_relative_repo_path=False,
        workspace_override="~/custom/",
        expected_workspace_label="~/custom/",
        preserve_config_path_in_log=False,
    ),
    PathAddFixture(
        test_id="path-dry-run-shows-tilde-config",
        remote_url="https://github.com/example/tilde",
        explicit_url=None,
        assume_yes=False,
        prompt_response=None,
        dry_run=True,
        expected_written=False,
        expected_url_kind="remote",
        override_name=None,
        expected_warning=None,
        merge_duplicates=True,
        preexisting_yaml=None,
        use_relative_repo_path=False,
        workspace_override=None,
        expected_workspace_label="~/study/python/",
        preserve_config_path_in_log=True,
    ),
    PathAddFixture(
        test_id="path-explicit-dot-workspace",
        remote_url="https://github.com/example/dot",
        explicit_url=None,
        assume_yes=True,
        prompt_response=None,
        dry_run=False,
        expected_written=True,
        expected_url_kind="remote",
        override_name=None,
        expected_warning=None,
        merge_duplicates=True,
        preexisting_yaml=None,
        use_relative_repo_path=False,
        workspace_override="./",
        expected_workspace_label="./",
        preserve_config_path_in_log=False,
    ),
    PathAddFixture(
        test_id="path-explicit-dot-workspace-no-merge",
        remote_url="https://github.com/example/dot-nomerge",
        explicit_url=None,
        assume_yes=True,
        prompt_response=None,
        dry_run=False,
        expected_written=True,
        expected_url_kind="remote",
        override_name=None,
        expected_warning=None,
        merge_duplicates=False,
        preexisting_yaml=None,
        use_relative_repo_path=False,
        workspace_override="./",
        expected_workspace_label="./",
        preserve_config_path_in_log=False,
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
    explicit_url: str | None,
    assume_yes: bool,
    prompt_response: str | None,
    dry_run: bool,
    expected_written: bool,
    expected_url_kind: str,
    override_name: str | None,
    expected_warning: str | None,
    merge_duplicates: bool,
    preexisting_yaml: str | None,
    use_relative_repo_path: bool,
    workspace_override: str | None,
    expected_workspace_label: str,
    preserve_config_path_in_log: bool,
    tmp_path: pathlib.Path,
    monkeypatch: MonkeyPatch,
    caplog: t.Any,
    snapshot: SnapshotAssertion,
) -> None:
    """CLI path mode prompts and adds repositories appropriately."""
    caplog.set_level(logging.INFO)

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)

    repo_path = tmp_path / "study/python/pytest-docker"
    init_git_repo(repo_path, remote_url)

    config_file = tmp_path / ".vcspull.yaml"

    if preexisting_yaml is not None:
        config_file.write_text(preexisting_yaml, encoding="utf-8")

    expected_input = prompt_response if prompt_response is not None else "y"
    monkeypatch.setattr("builtins.input", lambda _: expected_input)

    repo_arg: str
    if use_relative_repo_path:
        repo_arg = os.fspath(repo_path.relative_to(tmp_path))
    else:
        repo_arg = str(repo_path)

    args = argparse.Namespace(
        repo_path=repo_arg,
        url=explicit_url,
        override_name=override_name,
        config=str(config_file),
        workspace_root_path=workspace_override,
        dry_run=dry_run,
        assume_yes=assume_yes,
        merge_duplicates=merge_duplicates,
    )

    handle_add_command(args)

    log_output = caplog.text
    contracted_path = str(PrivatePath(repo_path))

    assert "Found new repository to import" in log_output
    assert contracted_path in log_output

    normalized_log = log_output.replace(str(config_file), "<config>")
    normalized_log = normalized_log.replace(str(repo_path), "<repo_path>")
    normalized_log = re.sub(r"add\.py:\d+", "add.py:<line>", normalized_log)
    if preserve_config_path_in_log:
        assert str(PrivatePath(config_file)) in log_output
        snapshot.assert_match(
            {
                "test_id": test_id,
                "log": normalized_log.replace("<config>", "~/.vcspull.yaml"),
            }
        )
    else:
        snapshot.assert_match({"test_id": test_id, "log": normalized_log})

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

        workspace = expected_workspace_label
        assert workspace in config_data
        assert repo_name in config_data[workspace]

        repo_entry = config_data[workspace][repo_name]
        expected_url: str
        if expected_url_kind == "explicit" and explicit_url is not None:
            expected_url = (
                explicit_url
                if explicit_url.startswith("git+")
                else f"git+{explicit_url}"
            )
        elif expected_url_kind == "remote" and remote_url is not None:
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
        if not dry_run:
            assert "Aborted import" in log_output


def test_add_repo_dry_run_contracts_config_path(
    tmp_path: pathlib.Path,
    monkeypatch: MonkeyPatch,
    caplog: t.Any,
) -> None:
    """Dry-run logging shows tilde-shortened config file paths."""
    caplog.set_level(logging.INFO)

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)

    config_path = tmp_path / ".vcspull.yaml"

    add_repo(
        name="tilde-repo",
        url="git+https://example.com/tilde-repo.git",
        config_file_path_str=str(config_path),
        path=str(tmp_path / "projects/tilde-repo"),
        workspace_root_path=None,
        dry_run=True,
    )

    assert "~/.vcspull.yaml" in caplog.text


def test_add_parser_rejects_extra_positional() -> None:
    """Passing both name and URL should raise a parse error in the new parser."""
    parser = argparse.ArgumentParser(prog="vcspull")
    subparsers = parser.add_subparsers(dest="command", required=True)
    add_parser = subparsers.add_parser("add")
    create_add_subparser(add_parser)

    with pytest.raises(SystemExit):
        parser.parse_args(["add", "name", "https://example.com/repo.git"])


class NoMergePreservationFixture(t.NamedTuple):
    """Fixture for asserting --no-merge keeps duplicate sections intact."""

    test_id: str
    initial_yaml: str
    expected_original_repos: tuple[str, ...]
    new_repo_name: str
    new_repo_url: str
    workspace_label: str


NO_MERGE_PRESERVATION_FIXTURES: list[NoMergePreservationFixture] = [
    NoMergePreservationFixture(
        test_id="duplicate-root-yaml",
        initial_yaml=textwrap.dedent(
            """\
            ~/study/python/:
              Flexget:
                repo: git+https://github.com/Flexget/Flexget.git
              MyST-Parser:
                repo: git@github.com:executablebooks/MyST-Parser.git
              RootTheBox:
                repo: git+https://github.com/moloch--/RootTheBox.git
            ~/study/python/:
              bubbles:
                repo: git+https://github.com/Stiivi/bubbles.git
              cubes:
                repo: git+https://github.com/Stiivi/cubes.git
            """
        ),
        expected_original_repos=(
            "Flexget",
            "MyST-Parser",
            "RootTheBox",
            "bubbles",
            "cubes",
        ),
        new_repo_name="pytest-docker",
        new_repo_url="git+https://github.com/avast/pytest-docker",
        workspace_label="~/study/python/",
    ),
]


@pytest.mark.parametrize(
    list(NoMergePreservationFixture._fields),
    NO_MERGE_PRESERVATION_FIXTURES,
    ids=[fixture.test_id for fixture in NO_MERGE_PRESERVATION_FIXTURES],
)
def test_add_repo_no_merge_preserves_duplicate_sections(
    test_id: str,
    initial_yaml: str,
    expected_original_repos: tuple[str, ...],
    new_repo_name: str,
    new_repo_url: str,
    workspace_label: str,
    tmp_path: pathlib.Path,
    monkeypatch: MonkeyPatch,
) -> None:
    """CLI add should not drop duplicate workspace sections when --no-merge."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)

    config_file = tmp_path / ".vcspull.yaml"
    config_file.write_text(initial_yaml, encoding="utf-8")

    repo_path = tmp_path / "study/python" / new_repo_name
    repo_path.mkdir(parents=True, exist_ok=True)

    (
        _initial_config,
        initial_duplicates,
        initial_items,
    ) = DuplicateAwareConfigReader.load_with_duplicates(config_file)
    assert workspace_label in initial_duplicates
    assert len(initial_duplicates[workspace_label]) == 2
    assert [key for key, _ in initial_items] == [workspace_label, workspace_label]

    add_repo(
        name=new_repo_name,
        url=new_repo_url,
        config_file_path_str=str(config_file),
        path=str(repo_path),
        workspace_root_path=workspace_label,
        dry_run=False,
        merge_duplicates=False,
    )

    (
        _final_config,
        duplicate_sections,
        final_items,
    ) = DuplicateAwareConfigReader.load_with_duplicates(config_file)

    assert [key for key, _ in final_items] == [
        workspace_label,
        workspace_label,
    ], f"{test_id}: final items unexpectedly merged"

    assert workspace_label in duplicate_sections, f"{test_id}: workspace missing"
    workspace_entries = duplicate_sections[workspace_label]
    assert len(workspace_entries) == 2, f"{test_id}: duplicate sections collapsed"

    combined_repos: set[str] = set()
    contains_new_repo = False

    for entry in workspace_entries:
        assert isinstance(entry, dict), f"{test_id}: workspace entry not dict"
        combined_repos.update(entry.keys())
        if new_repo_name in entry:
            contains_new_repo = True

    expected_repos = set(expected_original_repos) | {new_repo_name}
    assert combined_repos == expected_repos, f"{test_id}: repositories mismatch"
    assert contains_new_repo, f"{test_id}: new repo missing from duplicate sections"


def test_handle_add_command_workspace_label_from_workspace_root(
    tmp_path: pathlib.Path,
    monkeypatch: MonkeyPatch,
    caplog: t.Any,
) -> None:
    """CLI add should label workspace roots with their tilde path even from root cwd."""
    caplog.set_level(logging.INFO)

    monkeypatch.setenv("HOME", str(tmp_path))

    workspace_root = tmp_path / "study/python"
    repo_path = workspace_root / "pytest-docker"
    init_git_repo(repo_path, remote_url="https://github.com/avast/pytest-docker")

    monkeypatch.chdir(workspace_root)

    config_file = tmp_path / ".vcspull.yaml"

    args = argparse.Namespace(
        repo_path=str(repo_path),
        url=None,
        override_name=None,
        config=str(config_file),
        workspace_root_path=None,
        dry_run=False,
        assume_yes=True,
        merge_duplicates=True,
    )

    handle_add_command(args)

    expected_label = "~/study/python/"
    assert expected_label in caplog.text

    import yaml

    with config_file.open(encoding="utf-8") as fh:
        config_data = yaml.safe_load(fh)

    assert expected_label in config_data


@pytest.mark.parametrize("merge_duplicates", [True, False])
def test_handle_add_command_workspace_label_variants(
    merge_duplicates: bool,
    tmp_path: pathlib.Path,
    monkeypatch: MonkeyPatch,
    caplog: t.Any,
) -> None:
    """Path-first adds should keep tilde workspaces regardless of merge flag."""
    caplog.set_level(logging.INFO)

    monkeypatch.setenv("HOME", str(tmp_path))

    workspace_root = tmp_path / "study/python"
    repo_path = workspace_root / "pytest-docker"
    init_git_repo(repo_path, remote_url="https://github.com/avast/pytest-docker")

    monkeypatch.chdir(workspace_root)

    config_file = tmp_path / ".vcspull.yaml"

    args = argparse.Namespace(
        repo_path=str(repo_path),
        url=None,
        override_name=None,
        config=str(config_file),
        workspace_root_path=None,
        dry_run=False,
        assume_yes=True,
        merge_duplicates=merge_duplicates,
    )

    handle_add_command(args)

    expected_label = "~/study/python/"

    assert expected_label in caplog.text

    import yaml

    with config_file.open(encoding="utf-8") as fh:
        config_data = yaml.safe_load(fh) or {}

    assert expected_label in config_data
    assert "./" not in config_data


def test_handle_add_command_preserves_existing_dot_workspace_section(
    tmp_path: pathlib.Path,
    monkeypatch: MonkeyPatch,
    caplog: t.Any,
) -> None:
    """Existing './' sections should be preserved when they match the workspace."""
    caplog.set_level(logging.INFO)

    monkeypatch.setenv("HOME", str(tmp_path))

    workspace_root = tmp_path / "study/python"
    repo_path = workspace_root / "pytest-docker"
    init_git_repo(repo_path, remote_url="https://github.com/avast/pytest-docker")

    monkeypatch.chdir(workspace_root)

    config_file = tmp_path / ".vcspull.yaml"
    import yaml

    config_file.write_text(
        yaml.dump(
            {
                "./": {
                    "existing": {
                        "repo": "git+https://github.com/example/existing.git",
                    },
                },
            },
        ),
        encoding="utf-8",
    )

    args = argparse.Namespace(
        repo_path=str(repo_path),
        url=None,
        override_name=None,
        config=str(config_file),
        workspace_root_path=None,
        dry_run=False,
        assume_yes=True,
        merge_duplicates=True,
    )

    handle_add_command(args)

    with config_file.open(encoding="utf-8") as fh:
        config_data = yaml.safe_load(fh) or {}

    assert "./" in config_data
    assert "existing" in config_data["./"]
    assert "pytest-docker" in config_data["./"]
