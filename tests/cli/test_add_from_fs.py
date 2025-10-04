"""Tests for vcspull add-from-fs command functionality."""

from __future__ import annotations

import contextlib
import subprocess
import typing as t

import pytest
import yaml

from vcspull.cli import cli
from vcspull.cli.add_from_fs import add_from_filesystem, get_git_origin_url

if t.TYPE_CHECKING:
    import pathlib

    from libvcs.pytest_plugin import CreateRepoPytestFixtureFn
    from typing_extensions import TypeAlias

    ExpectedOutput: TypeAlias = t.Optional[t.Union[str, list[str]]]


def setup_git_repo(
    path: pathlib.Path,
    remote_url: str | None,
    git_envvars: dict[str, str],
) -> None:
    """Set up a git repository."""
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["git", "init"],
        cwd=path,
        check=True,
        capture_output=True,
        env=git_envvars,
    )

    if remote_url:
        subprocess.run(
            ["git", "remote", "add", "origin", remote_url],
            cwd=path,
            check=True,
            capture_output=True,
            env=git_envvars,
        )


def clone_repo(
    remote_url: str,
    local_path: pathlib.Path,
    git_envvars: dict[str, str],
) -> None:
    """Clone a git repository."""
    subprocess.run(
        ["git", "clone", remote_url, str(local_path)],
        check=True,
        capture_output=True,
        env=git_envvars,
    )


class AddFromFsFixture(t.NamedTuple):
    """Pytest fixture for vcspull add-from-fs command."""

    # pytest internal: used for naming test
    test_id: str

    # test parameters
    repo_setup: list[tuple[str, str, bool]]  # (name, subdir, has_remote)
    cli_args: list[str]
    initial_config: dict[str, t.Any] | None
    expected_config_contains: dict[str, t.Any] | None
    expected_in_output: ExpectedOutput = None
    expected_not_in_output: ExpectedOutput = None
    expected_log_level: str = "INFO"
    should_create_config: bool = False
    user_input: str | None = None  # For confirmation prompts


ADD_FROM_FS_FIXTURES: list[AddFromFsFixture] = [
    # Single repository scan
    AddFromFsFixture(
        test_id="single-repo",
        repo_setup=[("myproject", "", True)],  # One repo with remote
        cli_args=["add-from-fs", ".", "-y"],
        initial_config=None,
        should_create_config=True,
        expected_config_contains={"has_repos": True},  # Will verify dynamically
        expected_in_output=[
            "Found 1 new repository to add:",
            "+ myproject",
            "Successfully updated",
        ],
    ),
    # Multiple repositories non-recursive
    AddFromFsFixture(
        test_id="multiple-repos-non-recursive",
        repo_setup=[
            ("repo1", "", True),
            ("repo2", "", True),
            ("nested", "subdir", True),  # Should be ignored without -r
        ],
        cli_args=["add-from-fs", ".", "-y"],
        initial_config=None,
        should_create_config=True,
        expected_config_contains={"has_repos": True},
        expected_in_output=[
            "Found 2 new repositories to add:",
            "+ repo1",
            "+ repo2",
            "Successfully updated",
        ],
        expected_not_in_output="nested",
    ),
    # Recursive scan
    AddFromFsFixture(
        test_id="recursive-scan",
        repo_setup=[
            ("repo1", "", True),
            ("nested", "subdir", True),
        ],
        cli_args=["add-from-fs", ".", "-r", "-y"],
        initial_config=None,
        should_create_config=True,
        expected_config_contains={"has_repos": True},
        expected_in_output=[
            "Found 2 new repositories to add:",
            "+ repo1",
            "+ nested",
            "Successfully updated",
        ],
    ),
    # Custom base directory key
    AddFromFsFixture(
        test_id="custom-base-dir",
        repo_setup=[("myrepo", "", True)],
        cli_args=["add-from-fs", ".", "--base-dir-key", "~/custom/path", "-y"],
        initial_config=None,
        should_create_config=True,
        expected_config_contains={
            "~/custom/path/": {"myrepo": {}},
        },  # Just check repo exists
        expected_in_output=[
            "Found 1 new repository to add:",
            "Successfully updated",
        ],
    ),
    # No repositories found
    AddFromFsFixture(
        test_id="no-repos",
        repo_setup=[],  # No repositories
        cli_args=["add-from-fs", ".", "-y"],
        initial_config=None,
        should_create_config=False,
        expected_config_contains=None,
        expected_in_output="No git repositories found",
    ),
    # Repository without remote
    AddFromFsFixture(
        test_id="repo-without-remote",
        repo_setup=[("local_only", "", False)],  # No remote
        cli_args=["add-from-fs", ".", "-y"],
        initial_config=None,
        should_create_config=False,
        expected_config_contains=None,
        expected_in_output="No git repositories found",
        expected_log_level="WARNING",
    ),
    # All repositories already exist
    AddFromFsFixture(
        test_id="all-existing",
        repo_setup=[("existing1", "", True), ("existing2", "", True)],
        cli_args=["add-from-fs", ".", "-y"],
        initial_config={"dynamic": "will_be_set_in_test"},  # Will be set dynamically
        should_create_config=False,
        expected_config_contains=None,
        expected_in_output=[
            "Found 2 existing repositories",
            "All found repositories already exist",
        ],
    ),
    # Mixed existing and new
    AddFromFsFixture(
        test_id="mixed-existing-new",
        repo_setup=[
            ("existing", "", True),
            ("newrepo", "", True),
        ],
        cli_args=["add-from-fs", ".", "-y"],
        initial_config={"dynamic": "will_be_set_in_test"},  # Will be set for existing
        should_create_config=False,
        expected_config_contains={"has_repos": True},
        expected_in_output=[
            "Found 1 existing repositories",  # Note: plural form in message
            "Found 1 new repository to add:",
            "+ newrepo",
            "Successfully updated",
        ],
    ),
    # User confirmation - yes
    AddFromFsFixture(
        test_id="user-confirm-yes",
        repo_setup=[("repo_confirm", "", True)],
        cli_args=["add-from-fs", "."],  # No -y flag
        initial_config=None,
        should_create_config=True,
        expected_config_contains={"has_repos": True},
        expected_in_output=[
            "Found 1 new repository to add:",
            "Successfully updated",
        ],
        user_input="y\n",
    ),
    # User confirmation - no
    AddFromFsFixture(
        test_id="user-confirm-no",
        repo_setup=[("repo_no_confirm", "", True)],
        cli_args=["add-from-fs", "."],  # No -y flag
        initial_config=None,
        should_create_config=False,
        expected_config_contains=None,
        expected_in_output=[
            "Found 1 new repository to add:",
            "Aborted by user",
        ],
        user_input="n\n",
    ),
]


@pytest.mark.parametrize(
    list(AddFromFsFixture._fields),
    ADD_FROM_FS_FIXTURES,
    ids=[test.test_id for test in ADD_FROM_FS_FIXTURES],
)
def test_add_from_fs_cli(
    tmp_path: pathlib.Path,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
    create_git_remote_repo: CreateRepoPytestFixtureFn,
    git_commit_envvars: dict[str, str],
    test_id: str,
    repo_setup: list[tuple[str, str, bool]],
    cli_args: list[str],
    initial_config: dict[str, t.Any] | None,
    expected_config_contains: dict[str, t.Any] | None,
    expected_in_output: ExpectedOutput,
    expected_not_in_output: ExpectedOutput,
    expected_log_level: str,
    should_create_config: bool,
    user_input: str | None,
) -> None:
    """Test vcspull add-from-fs command through CLI."""
    # Set up scan directory
    scan_dir = tmp_path / "scan_dir"
    scan_dir.mkdir()

    # Set up repositories based on fixture
    repo_urls = {}
    for repo_name, subdir, has_remote in repo_setup:
        repo_parent = scan_dir / subdir if subdir else scan_dir
        repo_parent.mkdir(exist_ok=True, parents=True)
        repo_path = repo_parent / repo_name

        if has_remote:
            # Create remote and clone
            remote_path = create_git_remote_repo()
            remote_url = f"file://{remote_path}"
            clone_repo(remote_url, repo_path, git_commit_envvars)
            repo_urls[repo_name] = remote_url
        else:
            # Create local repo without remote
            setup_git_repo(repo_path, None, git_commit_envvars)

    # Set up config file
    config_file = tmp_path / ".vcspull.yaml"

    # Handle dynamic initial config for existing repo tests
    if initial_config and "dynamic" in initial_config:
        if test_id == "all-existing":
            # All repos should be in config
            initial_config = {
                str(scan_dir) + "/": {
                    name: {"repo": repo_urls[name]}
                    for name, _, has_remote in repo_setup
                    if has_remote
                },
            }
        elif test_id == "mixed-existing-new":
            # Only "existing" repo should be in config
            initial_config = {
                str(scan_dir) + "/": {"existing": {"repo": repo_urls["existing"]}},
            }

    if initial_config:
        yaml_content = yaml.dump(initial_config, default_flow_style=False)
        config_file.write_text(yaml_content, encoding="utf-8")

    # Update CLI args to use correct scan directory
    cli_args = [cli_args[0], "-c", str(config_file), str(scan_dir), *cli_args[2:]]

    # Change to tmp directory
    monkeypatch.chdir(tmp_path)

    # Mock user input if needed
    if user_input:
        monkeypatch.setattr("builtins.input", lambda _: user_input.strip())

    # Run CLI command
    with contextlib.suppress(SystemExit):
        cli(cli_args)

    # Capture output
    captured = capsys.readouterr()
    output = "".join([*caplog.messages, captured.out, captured.err])

    # Strip ANSI codes for comparison
    import re

    clean_output = re.sub(r"\x1b\[[0-9;]*m", "", output)

    # Check expected output
    if expected_in_output is not None:
        if isinstance(expected_in_output, str):
            expected_in_output = [expected_in_output]
        for needle in expected_in_output:
            assert needle in clean_output, (
                f"Expected '{needle}' in output, got: {clean_output}"
            )

    if expected_not_in_output is not None:
        if isinstance(expected_not_in_output, str):
            expected_not_in_output = [expected_not_in_output]
        for needle in expected_not_in_output:
            assert needle not in clean_output, f"Unexpected '{needle}' in output"

    # Verify config file
    if should_create_config or (initial_config and expected_config_contains):
        assert config_file.exists(), "Config file should exist"

        # Load and verify config
        with config_file.open() as f:
            config_data = yaml.safe_load(f)

        # Check expected config contents
        if expected_config_contains:
            if "has_repos" in expected_config_contains:
                # Just check that repos were added
                assert config_data, "Config should have content"
                assert any(isinstance(v, dict) for v in config_data.values()), (
                    "Should have repo entries"
                )
            else:
                for key, value in expected_config_contains.items():
                    assert key in config_data, f"Expected key '{key}' in config"
                    if isinstance(value, dict):
                        for subkey, subvalue in value.items():
                            assert subkey in config_data[key], (
                                f"Expected '{subkey}' in config['{key}']"
                            )
                            # If subvalue is empty dict, just check that the key exists
                            if subvalue == {}:
                                assert isinstance(config_data[key][subkey], dict)
                            elif subvalue != t.Any:
                                assert config_data[key][subkey] == subvalue


class TestGetGitOriginUrl:
    """Unit tests for get_git_origin_url function."""

    def test_get_origin_url_success(
        self,
        create_git_remote_repo: CreateRepoPytestFixtureFn,
        tmp_path: pathlib.Path,
        git_commit_envvars: dict[str, str],
    ) -> None:
        """Test successfully getting origin URL."""
        # Create and clone a repo
        remote_path = create_git_remote_repo()
        remote_url = f"file://{remote_path}"
        local_path = tmp_path / "test_repo"

        clone_repo(remote_url, local_path, git_commit_envvars)

        # Test getting URL
        url = get_git_origin_url(local_path)
        assert url == remote_url

    def test_get_origin_url_no_remote(
        self,
        tmp_path: pathlib.Path,
        git_commit_envvars: dict[str, str],
    ) -> None:
        """Test handling repo without origin."""
        repo_path = tmp_path / "local_only"
        setup_git_repo(repo_path, None, git_commit_envvars)

        url = get_git_origin_url(repo_path)
        assert url is None

    def test_get_origin_url_not_git(
        self,
        tmp_path: pathlib.Path,
    ) -> None:
        """Test handling non-git directory."""
        regular_dir = tmp_path / "not_git"
        regular_dir.mkdir()

        url = get_git_origin_url(regular_dir)
        assert url is None


class TestAddFromFilesystemUnit:
    """Unit tests for add_from_filesystem function."""

    def test_direct_call_simple(
        self,
        create_git_remote_repo: CreateRepoPytestFixtureFn,
        tmp_path: pathlib.Path,
        git_commit_envvars: dict[str, str],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Test direct add_from_filesystem call."""
        # Set up a repo
        scan_dir = tmp_path / "repos"
        scan_dir.mkdir()

        remote_path = create_git_remote_repo()
        remote_url = f"file://{remote_path}"
        repo_path = scan_dir / "test_repo"
        clone_repo(remote_url, repo_path, git_commit_envvars)

        config_file = tmp_path / ".vcspull.yaml"

        # Call function directly
        add_from_filesystem(
            scan_dir_str=str(scan_dir),
            config_file_path_str=str(config_file),
            recursive=False,
            base_dir_key_arg=None,
            yes=True,
        )

        # Verify config created
        assert config_file.exists()
        with config_file.open() as f:
            config_data = yaml.safe_load(f)

        expected_key = str(scan_dir) + "/"
        assert expected_key in config_data
        assert "test_repo" in config_data[expected_key]

    def test_many_existing_repos_summary(
        self,
        create_git_remote_repo: CreateRepoPytestFixtureFn,
        tmp_path: pathlib.Path,
        git_commit_envvars: dict[str, str],
        capsys: pytest.CaptureFixture[str],
        caplog: pytest.LogCaptureFixture,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test summary output when many repos already exist."""
        scan_dir = tmp_path / "many_repos"
        scan_dir.mkdir()

        # Create many repos (>5 for summary mode)
        repo_data = {}
        for i in range(8):
            remote_path = create_git_remote_repo()
            remote_url = f"file://{remote_path}"
            repo_name = f"repo{i}"
            repo_path = scan_dir / repo_name
            clone_repo(remote_url, repo_path, git_commit_envvars)
            repo_data[repo_name] = {"repo": remote_url}

        # Pre-create config with all repos
        config_file = tmp_path / ".vcspull.yaml"
        initial_config = {str(scan_dir) + "/": repo_data}
        yaml_content = yaml.dump(initial_config, default_flow_style=False)
        config_file.write_text(yaml_content, encoding="utf-8")

        # Change to tmp directory
        monkeypatch.chdir(tmp_path)

        # Run scan through CLI
        with contextlib.suppress(SystemExit):
            cli(["add-from-fs", str(scan_dir), "-c", str(config_file), "-y"])

        # Check for summary message (not detailed list)
        captured = capsys.readouterr()
        output = "\n".join(caplog.messages) + captured.out + captured.err

        # Strip ANSI codes
        import re

        clean_output = re.sub(r"\x1b\[[0-9;]*m", "", output)

        assert "Found 8 existing repositories already in configuration" in clean_output
        assert "All found repositories already exist" in clean_output


def test_add_from_fs_help(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Test add-from-fs command help output."""
    with contextlib.suppress(SystemExit):
        cli(["add-from-fs", "--help"])

    captured = capsys.readouterr()
    output = captured.out + captured.err

    # Check help content
    assert "Scan a directory for git repositories" in output
    assert "scan_dir" in output
    assert "--recursive" in output
    assert "--base-dir-key" in output
    assert "--yes" in output
    assert "--config" in output
