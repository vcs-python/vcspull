"""Tests for vcspull.cli.add_from_fs using libvcs fixtures."""

from __future__ import annotations

import subprocess
import typing as t

import yaml

from vcspull.cli.add_from_fs import add_from_filesystem, get_git_origin_url
from vcspull.config import save_config_yaml

if t.TYPE_CHECKING:
    import pathlib

    import pytest
    from _pytest.logging import LogCaptureFixture
    from libvcs.pytest_plugin import CreateRepoPytestFixtureFn


class TestGetGitOriginUrl:
    """Test get_git_origin_url function with real git repos."""

    def test_success(
        self,
        create_git_remote_repo: CreateRepoPytestFixtureFn,
        tmp_path: pathlib.Path,
        git_commit_envvars: dict[str, str],
    ) -> None:
        """Test successfully getting origin URL from a git repository."""
        # Create a remote repository
        remote_path = create_git_remote_repo()
        remote_url = f"file://{remote_path}"

        # Clone it
        local_repo_path = tmp_path / "test_repo"
        subprocess.run(
            ["git", "clone", remote_url, str(local_repo_path)],
            check=True,
            capture_output=True,
            env=git_commit_envvars,
        )

        # Test getting origin URL
        url = get_git_origin_url(local_repo_path)
        assert url == remote_url

    def test_no_remote(
        self,
        tmp_path: pathlib.Path,
        git_commit_envvars: dict[str, str],
        caplog: LogCaptureFixture,
    ) -> None:
        """Test handling repository with no origin remote."""
        # Create a local git repo without remote
        repo_path = tmp_path / "local_only"
        repo_path.mkdir()
        subprocess.run(
            ["git", "init"],
            cwd=repo_path,
            check=True,
            capture_output=True,
            env=git_commit_envvars,
        )

        # Should return None and log debug message
        caplog.set_level("DEBUG")
        url = get_git_origin_url(repo_path)
        assert url is None
        assert "Could not get origin URL" in caplog.text

    def test_not_git_repo(
        self,
        tmp_path: pathlib.Path,
        caplog: LogCaptureFixture,
    ) -> None:
        """Test handling non-git directory."""
        # Create a regular directory
        regular_dir = tmp_path / "not_git"
        regular_dir.mkdir()

        # Should return None
        caplog.set_level("DEBUG")
        url = get_git_origin_url(regular_dir)
        assert url is None
        assert "Could not get origin URL" in caplog.text


class TestAddFromFilesystem:
    """Test add_from_filesystem with real git repositories."""

    def test_single_repo(
        self,
        create_git_remote_repo: CreateRepoPytestFixtureFn,
        tmp_path: pathlib.Path,
        git_commit_envvars: dict[str, str],
        caplog: LogCaptureFixture,
    ) -> None:
        """Test scanning directory with one git repository."""
        caplog.set_level("INFO")

        # Create a scan directory
        scan_dir = tmp_path / "projects"
        scan_dir.mkdir()

        # Create and clone a repository
        remote_path = create_git_remote_repo()
        remote_url = f"file://{remote_path}"
        repo_name = "myproject"
        local_repo_path = scan_dir / repo_name

        subprocess.run(
            ["git", "clone", remote_url, str(local_repo_path)],
            check=True,
            capture_output=True,
            env=git_commit_envvars,
        )

        # Create config file path
        config_file = tmp_path / ".vcspull.yaml"

        # Run add_from_filesystem
        add_from_filesystem(
            scan_dir_str=str(scan_dir),
            config_file_path_str=str(config_file),
            recursive=True,
            base_dir_key_arg=None,
            yes=True,
        )

        # Verify config file was created with correct content
        assert config_file.exists()
        with config_file.open() as f:
            config_data = yaml.safe_load(f)

        # Check the repository was added with correct structure
        expected_key = str(scan_dir) + "/"
        assert expected_key in config_data
        assert repo_name in config_data[expected_key]
        assert config_data[expected_key][repo_name] == {"repo": remote_url}

        # Check log messages
        assert f"Adding '{repo_name}' ({remote_url})" in caplog.text
        assert f"Successfully updated {config_file}" in caplog.text

    def test_multiple_repos_recursive(
        self,
        create_git_remote_repo: CreateRepoPytestFixtureFn,
        tmp_path: pathlib.Path,
        git_commit_envvars: dict[str, str],
        caplog: LogCaptureFixture,
    ) -> None:
        """Test scanning directory recursively with multiple git repositories."""
        caplog.set_level("INFO")

        # Create directory structure
        scan_dir = tmp_path / "workspace"
        scan_dir.mkdir()
        subdir = scan_dir / "subfolder"
        subdir.mkdir()

        # Create multiple repositories
        repos = []
        for _i, (parent, name) in enumerate(
            [
                (scan_dir, "repo1"),
                (scan_dir, "repo2"),
                (subdir, "nested_repo"),
            ],
        ):
            remote_path = create_git_remote_repo()
            remote_url = f"file://{remote_path}"
            local_path = parent / name

            subprocess.run(
                ["git", "clone", remote_url, str(local_path)],
                check=True,
                capture_output=True,
                env=git_commit_envvars,
            )
            repos.append((name, remote_url))

        # Create config file
        config_file = tmp_path / ".vcspull.yaml"

        # Run add_from_filesystem recursively
        add_from_filesystem(
            scan_dir_str=str(scan_dir),
            config_file_path_str=str(config_file),
            recursive=True,
            base_dir_key_arg=None,
            yes=True,
        )

        # Verify all repos were added
        with config_file.open() as f:
            config_data = yaml.safe_load(f)

        expected_key = str(scan_dir) + "/"
        assert expected_key in config_data

        for name, url in repos:
            assert name in config_data[expected_key]
            assert config_data[expected_key][name] == {"repo": url}

    def test_non_recursive(
        self,
        create_git_remote_repo: CreateRepoPytestFixtureFn,
        tmp_path: pathlib.Path,
        git_commit_envvars: dict[str, str],
    ) -> None:
        """Test non-recursive scan only finds top-level repos."""
        # Create directory structure
        scan_dir = tmp_path / "workspace"
        scan_dir.mkdir()
        nested_dir = scan_dir / "nested"
        nested_dir.mkdir()

        # Create repos at different levels
        # Top-level repo
        remote1 = create_git_remote_repo()
        subprocess.run(
            ["git", "clone", f"file://{remote1}", str(scan_dir / "top_repo")],
            check=True,
            capture_output=True,
            env=git_commit_envvars,
        )

        # Nested repo (should not be found)
        remote2 = create_git_remote_repo()
        subprocess.run(
            ["git", "clone", f"file://{remote2}", str(nested_dir / "nested_repo")],
            check=True,
            capture_output=True,
            env=git_commit_envvars,
        )

        config_file = tmp_path / ".vcspull.yaml"

        # Run non-recursive scan
        add_from_filesystem(
            scan_dir_str=str(scan_dir),
            config_file_path_str=str(config_file),
            recursive=False,
            base_dir_key_arg=None,
            yes=True,
        )

        # Verify only top-level repo was found
        with config_file.open() as f:
            config_data = yaml.safe_load(f)

        expected_key = str(scan_dir) + "/"
        assert "top_repo" in config_data[expected_key]
        assert "nested_repo" not in config_data[expected_key]

    def test_custom_base_dir_key(
        self,
        create_git_remote_repo: CreateRepoPytestFixtureFn,
        tmp_path: pathlib.Path,
        git_commit_envvars: dict[str, str],
    ) -> None:
        """Test using a custom base directory key."""
        # Create and clone a repo
        scan_dir = tmp_path / "repos"
        scan_dir.mkdir()

        remote_path = create_git_remote_repo()
        remote_url = f"file://{remote_path}"
        repo_name = "test_repo"

        subprocess.run(
            ["git", "clone", remote_url, str(scan_dir / repo_name)],
            check=True,
            capture_output=True,
            env=git_commit_envvars,
        )

        config_file = tmp_path / ".vcspull.yaml"
        custom_key = "~/my_projects/"

        # Run with custom base dir key
        add_from_filesystem(
            scan_dir_str=str(scan_dir),
            config_file_path_str=str(config_file),
            recursive=True,
            base_dir_key_arg=custom_key,
            yes=True,
        )

        # Verify custom key was used
        with config_file.open() as f:
            config_data = yaml.safe_load(f)

        assert custom_key in config_data
        assert repo_name in config_data[custom_key]

    def test_skip_existing_repos(
        self,
        create_git_remote_repo: CreateRepoPytestFixtureFn,
        tmp_path: pathlib.Path,
        git_commit_envvars: dict[str, str],
        caplog: LogCaptureFixture,
    ) -> None:
        """Test that existing repos in config are skipped."""
        caplog.set_level("INFO")

        # Create a repo
        scan_dir = tmp_path / "repos"
        scan_dir.mkdir()

        remote_path = create_git_remote_repo()
        remote_url = f"file://{remote_path}"
        repo_name = "existing_repo"

        subprocess.run(
            ["git", "clone", remote_url, str(scan_dir / repo_name)],
            check=True,
            capture_output=True,
            env=git_commit_envvars,
        )

        # Pre-create config with this repo
        config_file = tmp_path / ".vcspull.yaml"
        config_data = {str(scan_dir) + "/": {repo_name: remote_url}}
        save_config_yaml(config_file, config_data)

        # Run add_from_filesystem
        add_from_filesystem(
            scan_dir_str=str(scan_dir),
            config_file_path_str=str(config_file),
            recursive=True,
            base_dir_key_arg=None,
            yes=True,
        )

        # Verify enhanced output for existing repos
        assert "Found 1 existing repositories in configuration:" in caplog.text
        assert f"• {repo_name} ({remote_url})" in caplog.text
        assert f"at {scan_dir!s}/{repo_name} in {config_file}" in caplog.text
        assert (
            "All found repositories already exist in the configuration. Nothing to do."
            in caplog.text
        )

    def test_user_confirmation(
        self,
        create_git_remote_repo: CreateRepoPytestFixtureFn,
        tmp_path: pathlib.Path,
        git_commit_envvars: dict[str, str],
        monkeypatch: pytest.MonkeyPatch,
        caplog: LogCaptureFixture,
    ) -> None:
        """Test user confirmation prompt."""
        caplog.set_level("INFO")

        # Create a repo
        scan_dir = tmp_path / "repos"
        scan_dir.mkdir()

        remote_path = create_git_remote_repo()
        remote_url = f"file://{remote_path}"

        subprocess.run(
            ["git", "clone", remote_url, str(scan_dir / "repo1")],
            check=True,
            capture_output=True,
            env=git_commit_envvars,
        )

        config_file = tmp_path / ".vcspull.yaml"

        # Mock user input as "n" (no)
        monkeypatch.setattr("builtins.input", lambda _: "n")

        # Run without --yes flag
        add_from_filesystem(
            scan_dir_str=str(scan_dir),
            config_file_path_str=str(config_file),
            recursive=True,
            base_dir_key_arg=None,
            yes=False,
        )

        # Verify aborted
        assert "Aborted by user" in caplog.text
        assert not config_file.exists()

    def test_no_repos_found(
        self,
        tmp_path: pathlib.Path,
        caplog: LogCaptureFixture,
    ) -> None:
        """Test handling when no git repositories are found."""
        caplog.set_level("INFO")

        # Create empty directory
        scan_dir = tmp_path / "empty"
        scan_dir.mkdir()

        config_file = tmp_path / ".vcspull.yaml"

        # Run scan
        add_from_filesystem(
            scan_dir_str=str(scan_dir),
            config_file_path_str=str(config_file),
            recursive=True,
            base_dir_key_arg=None,
            yes=True,
        )

        # Verify appropriate message
        assert f"No git repositories found in {scan_dir}" in caplog.text
        assert not config_file.exists()

    def test_repo_without_origin(
        self,
        tmp_path: pathlib.Path,
        git_commit_envvars: dict[str, str],
        caplog: LogCaptureFixture,
    ) -> None:
        """Test handling repository without origin remote."""
        caplog.set_level("WARNING")

        # Create scan directory
        scan_dir = tmp_path / "repos"
        scan_dir.mkdir()

        # Create local git repo without remote
        repo_path = scan_dir / "local_only"
        repo_path.mkdir()
        subprocess.run(
            ["git", "init"],
            cwd=repo_path,
            check=True,
            capture_output=True,
            env=git_commit_envvars,
        )

        config_file = tmp_path / ".vcspull.yaml"

        # Run scan
        add_from_filesystem(
            scan_dir_str=str(scan_dir),
            config_file_path_str=str(config_file),
            recursive=True,
            base_dir_key_arg=None,
            yes=True,
        )

        # Verify warning and repo was skipped
        assert (
            f"Could not determine remote URL for git repository at {repo_path}"
            in caplog.text
        )
        assert not config_file.exists()  # No repos added, so no file created

    def test_detailed_existing_repos_output(
        self,
        create_git_remote_repo: CreateRepoPytestFixtureFn,
        tmp_path: pathlib.Path,
        git_commit_envvars: dict[str, str],
        caplog: LogCaptureFixture,
    ) -> None:
        """Test detailed output when multiple repositories already exist."""
        caplog.set_level("INFO")

        # Create scan directory with multiple repos
        scan_dir = tmp_path / "existing_repos"
        scan_dir.mkdir()

        # Create multiple repositories
        repos_data = []
        for _i, repo_name in enumerate(["repo1", "repo2", "repo3"]):
            remote_path = create_git_remote_repo()
            remote_url = f"file://{remote_path}"
            local_repo_path = scan_dir / repo_name

            subprocess.run(
                ["git", "clone", remote_url, str(local_repo_path)],
                check=True,
                capture_output=True,
                env=git_commit_envvars,
            )
            repos_data.append((repo_name, remote_url))

        # Pre-create config with all repos
        config_file = tmp_path / ".vcspull.yaml"
        config_data = {str(scan_dir) + "/": dict(repos_data)}
        save_config_yaml(config_file, config_data)

        # Run add_from_filesystem
        add_from_filesystem(
            scan_dir_str=str(scan_dir),
            config_file_path_str=str(config_file),
            recursive=True,
            base_dir_key_arg=None,
            yes=True,
        )

        # Verify detailed output
        assert "Found 3 existing repositories in configuration:" in caplog.text

        # Check each repository is listed with correct details
        for repo_name, remote_url in repos_data:
            assert f"• {repo_name} ({remote_url})" in caplog.text
            assert f"at {scan_dir!s}/{repo_name} in {config_file}" in caplog.text

        # Verify final message
        assert (
            "All found repositories already exist in the configuration. Nothing to do."
            in caplog.text
        )

    def test_mixed_existing_and_new_repos(
        self,
        create_git_remote_repo: CreateRepoPytestFixtureFn,
        tmp_path: pathlib.Path,
        git_commit_envvars: dict[str, str],
        caplog: LogCaptureFixture,
    ) -> None:
        """Test output when some repos exist and some are new."""
        caplog.set_level("INFO")

        # Create scan directory
        scan_dir = tmp_path / "mixed_repos"
        scan_dir.mkdir()

        # Create repositories
        existing_repo_data = []
        new_repo_data = []

        # Create two existing repos
        for _i, repo_name in enumerate(["existing1", "existing2"]):
            remote_path = create_git_remote_repo()
            remote_url = f"file://{remote_path}"
            local_repo_path = scan_dir / repo_name

            subprocess.run(
                ["git", "clone", remote_url, str(local_repo_path)],
                check=True,
                capture_output=True,
                env=git_commit_envvars,
            )
            existing_repo_data.append((repo_name, remote_url))

        # Create two new repos
        for _i, repo_name in enumerate(["new1", "new2"]):
            remote_path = create_git_remote_repo()
            remote_url = f"file://{remote_path}"
            local_repo_path = scan_dir / repo_name

            subprocess.run(
                ["git", "clone", remote_url, str(local_repo_path)],
                check=True,
                capture_output=True,
                env=git_commit_envvars,
            )
            new_repo_data.append((repo_name, remote_url))

        # Pre-create config with only existing repos
        config_file = tmp_path / ".vcspull.yaml"
        config_data = {str(scan_dir) + "/": dict(existing_repo_data)}
        save_config_yaml(config_file, config_data)

        # Run add_from_filesystem
        add_from_filesystem(
            scan_dir_str=str(scan_dir),
            config_file_path_str=str(config_file),
            recursive=True,
            base_dir_key_arg=None,
            yes=True,
        )

        # Verify existing repos are listed
        assert "Found 2 existing repositories in configuration:" in caplog.text
        for repo_name, remote_url in existing_repo_data:
            assert f"• {repo_name} ({remote_url})" in caplog.text
            assert f"at {scan_dir!s}/{repo_name} in {config_file}" in caplog.text

        # Verify new repos are added
        for repo_name, remote_url in new_repo_data:
            assert f"Adding '{repo_name}' ({remote_url})" in caplog.text

        assert "Successfully updated" in caplog.text

    def test_many_existing_repos_summary(
        self,
        create_git_remote_repo: CreateRepoPytestFixtureFn,
        tmp_path: pathlib.Path,
        git_commit_envvars: dict[str, str],
        caplog: LogCaptureFixture,
    ) -> None:
        """Test that many existing repos show summary instead of full list."""
        caplog.set_level("INFO")

        # Create scan directory
        scan_dir = tmp_path / "many_repos"
        scan_dir.mkdir()

        # Create many existing repos (more than 5)
        existing_repo_data = []
        for i in range(8):
            repo_name = f"existing{i}"
            remote_path = create_git_remote_repo()
            remote_url = f"file://{remote_path}"
            local_repo_path = scan_dir / repo_name

            subprocess.run(
                ["git", "clone", remote_url, str(local_repo_path)],
                check=True,
                capture_output=True,
                env=git_commit_envvars,
            )
            existing_repo_data.append((repo_name, remote_url))

        # Create one new repo
        new_remote = create_git_remote_repo()
        new_url = f"file://{new_remote}"
        subprocess.run(
            ["git", "clone", new_url, str(scan_dir / "new_repo")],
            check=True,
            capture_output=True,
            env=git_commit_envvars,
        )

        # Pre-create config with existing repos
        config_file = tmp_path / ".vcspull.yaml"
        config_data = {str(scan_dir) + "/": dict(existing_repo_data)}
        save_config_yaml(config_file, config_data)

        # Run add_from_filesystem
        add_from_filesystem(
            scan_dir_str=str(scan_dir),
            config_file_path_str=str(config_file),
            recursive=True,
            base_dir_key_arg=None,
            yes=True,
        )

        # Verify summary message for many repos
        assert "Found 8 existing repositories already in configuration." in caplog.text
        # Should NOT list individual repos
        assert "• existing0" not in caplog.text
        assert "• existing7" not in caplog.text

        # Verify new repo is shown clearly
        assert "Found 1 new repository to add:" in caplog.text
        assert "+ new_repo" in caplog.text
