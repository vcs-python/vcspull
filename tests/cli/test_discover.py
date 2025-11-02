"""Tests for vcspull discover command."""

from __future__ import annotations

import subprocess
import typing as t

import pytest
from syrupy.assertion import SnapshotAssertion

from vcspull.cli.discover import discover_repos

if t.TYPE_CHECKING:
    import pathlib

    from _pytest.monkeypatch import MonkeyPatch


def init_git_repo(repo_path: pathlib.Path, remote_url: str) -> None:
    """Initialize a git repository with a remote."""
    repo_path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init"], cwd=repo_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "remote", "add", "origin", remote_url],
        cwd=repo_path,
        check=True,
        capture_output=True,
    )


class DiscoverFixture(t.NamedTuple):
    """Fixture for discover test cases."""

    test_id: str
    repos_to_create: list[tuple[str, str]]  # (name, remote_url)
    recursive: bool
    workspace_override: str | None
    dry_run: bool
    yes: bool
    expected_repo_count: int
    config_relpath: str | None
    preexisting_config: dict[str, t.Any] | None
    user_input: str | None
    expected_workspace_labels: set[str] | None
    merge_duplicates: bool
    preexisting_yaml: str | None


DISCOVER_FIXTURES: list[DiscoverFixture] = [
    DiscoverFixture(
        test_id="discover-single-level",
        repos_to_create=[
            ("repo1", "git+https://github.com/user/repo1.git"),
            ("repo2", "git+https://github.com/user/repo2.git"),
        ],
        recursive=False,
        workspace_override=None,
        dry_run=False,
        yes=True,
        expected_repo_count=2,
        config_relpath=".vcspull.yaml",
        preexisting_config=None,
        user_input=None,
        expected_workspace_labels={"~/code/"},
        merge_duplicates=True,
        preexisting_yaml=None,
    ),
    DiscoverFixture(
        test_id="discover-recursive",
        repos_to_create=[
            ("repo1", "git+https://github.com/user/repo1.git"),
            ("subdir/repo2", "git+https://github.com/user/repo2.git"),
            ("subdir/nested/repo3", "git+https://github.com/user/repo3.git"),
        ],
        recursive=True,
        workspace_override=None,
        dry_run=False,
        yes=True,
        expected_repo_count=3,
        config_relpath=".vcspull.yaml",
        preexisting_config=None,
        user_input=None,
        expected_workspace_labels={"~/code/"},
        merge_duplicates=True,
        preexisting_yaml=None,
    ),
    DiscoverFixture(
        test_id="discover-dry-run",
        repos_to_create=[
            ("repo1", "git+https://github.com/user/repo1.git"),
        ],
        recursive=False,
        workspace_override=None,
        dry_run=True,
        yes=True,
        expected_repo_count=0,  # Nothing written in dry-run
        config_relpath=".vcspull.yaml",
        preexisting_config=None,
        user_input=None,
        expected_workspace_labels=None,
        merge_duplicates=True,
        preexisting_yaml=None,
    ),
    DiscoverFixture(
        test_id="discover-default-config",
        repos_to_create=[
            ("repo1", "git+https://github.com/user/repo1.git"),
        ],
        recursive=False,
        workspace_override=None,
        dry_run=False,
        yes=True,
        expected_repo_count=1,
        config_relpath=None,
        preexisting_config=None,
        user_input=None,
        expected_workspace_labels={"~/code/"},
        merge_duplicates=True,
        preexisting_yaml=None,
    ),
    DiscoverFixture(
        test_id="discover-workspace-normalization",
        repos_to_create=[
            ("repo1", "git+https://github.com/user/repo1.git"),
        ],
        recursive=False,
        workspace_override=None,
        dry_run=False,
        yes=True,
        expected_repo_count=2,
        config_relpath=".vcspull.yaml",
        preexisting_config={
            "~/code": {
                "existing": {"repo": "git+https://github.com/user/existing.git"},
            },
        },
        user_input=None,
        expected_workspace_labels={"~/code/"},
        merge_duplicates=True,
        preexisting_yaml=None,
    ),
    DiscoverFixture(
        test_id="discover-interactive-confirm",
        repos_to_create=[
            ("repo1", "git+https://github.com/user/repo1.git"),
        ],
        recursive=False,
        workspace_override=None,
        dry_run=False,
        yes=False,
        expected_repo_count=1,
        config_relpath=".vcspull.yaml",
        preexisting_config=None,
        user_input="y",
        expected_workspace_labels={"~/code/"},
        merge_duplicates=True,
        preexisting_yaml=None,
    ),
    DiscoverFixture(
        test_id="discover-interactive-abort",
        repos_to_create=[
            ("repo1", "git+https://github.com/user/repo1.git"),
        ],
        recursive=False,
        workspace_override=None,
        dry_run=False,
        yes=False,
        expected_repo_count=0,
        config_relpath=".vcspull.yaml",
        preexisting_config=None,
        user_input="n",
        expected_workspace_labels=None,
        merge_duplicates=True,
        preexisting_yaml=None,
    ),
    DiscoverFixture(
        test_id="discover-no-merge",
        repos_to_create=[
            ("repo3", "git+https://github.com/user/repo3.git"),
        ],
        recursive=False,
        workspace_override=None,
        dry_run=False,
        yes=True,
        expected_repo_count=2,
        config_relpath=".vcspull.yaml",
        preexisting_config=None,
        user_input=None,
        expected_workspace_labels={"~/code/"},
        merge_duplicates=False,
        preexisting_yaml="""
~/code/:
  repo1:
    repo: git+https://example.com/repo1.git
~/code/:
  repo2:
    repo: git+https://example.com/repo2.git
""",
    ),
]


class DiscoverLoadEdgeFixture(t.NamedTuple):
    """Fixture describing discover configuration loading edge cases."""

    test_id: str
    mode: t.Literal["multi_home", "non_dict", "exception"]
    expected_log_fragment: str


DISCOVER_LOAD_EDGE_FIXTURES: list[DiscoverLoadEdgeFixture] = [
    DiscoverLoadEdgeFixture(
        test_id="multiple-home-configs",
        mode="multi_home",
        expected_log_fragment="Multiple home_config files found",
    ),
    DiscoverLoadEdgeFixture(
        test_id="non-dict-config",
        mode="non_dict",
        expected_log_fragment="is not a valid YAML dictionary",
    ),
    DiscoverLoadEdgeFixture(
        test_id="config-reader-exception",
        mode="exception",
        expected_log_fragment="Error loading YAML",
    ),
]


class DiscoverNormalizationFixture(t.NamedTuple):
    """Fixture for normalization-only save branches."""

    test_id: str
    preexisting_config: dict[str, dict[str, dict[str, str]]]
    expected_workspace_label: str


DISCOVER_NORMALIZATION_FIXTURES: list[DiscoverNormalizationFixture] = [
    DiscoverNormalizationFixture(
        test_id="normalizes-and-saves-existing",
        preexisting_config={
            "~/code": {
                "existing-repo": {"repo": "git+https://example.com/existing.git"},
            },
        },
        expected_workspace_label="~/code/",
    ),
]


class DiscoverInvalidWorkspaceFixture(t.NamedTuple):
    """Fixture describing non-dict workspace entries."""

    test_id: str
    workspace_section: list[str]
    expected_warning: str


DISCOVER_INVALID_WORKSPACE_FIXTURES: list[DiscoverInvalidWorkspaceFixture] = [
    DiscoverInvalidWorkspaceFixture(
        test_id="non-dict-workspace-entry",
        workspace_section=[],
        expected_warning="Workspace root",
    ),
]


class DiscoverExistingSummaryFixture(t.NamedTuple):
    """Fixture asserting existing repository summary messaging."""

    test_id: str
    repo_count: int
    expected_log_fragment: str


DISCOVER_EXISTING_SUMMARY_FIXTURES: list[DiscoverExistingSummaryFixture] = [
    DiscoverExistingSummaryFixture(
        test_id="existing-summary-detailed",
        repo_count=3,
        expected_log_fragment="Found 3 existing repositories in configuration:",
    ),
    DiscoverExistingSummaryFixture(
        test_id="existing-summary-aggregate",
        repo_count=6,
        expected_log_fragment="Found 6 existing repositories already in configuration.",
    ),
]


@pytest.mark.parametrize(
    list(DiscoverFixture._fields),
    DISCOVER_FIXTURES,
    ids=[fixture.test_id for fixture in DISCOVER_FIXTURES],
)
def test_discover_repos(
    test_id: str,
    repos_to_create: list[tuple[str, str]],
    recursive: bool,
    workspace_override: str | None,
    dry_run: bool,
    yes: bool,
    expected_repo_count: int,
    config_relpath: str | None,
    preexisting_config: dict[str, t.Any] | None,
    user_input: str | None,
    expected_workspace_labels: set[str] | None,
    merge_duplicates: bool,
    preexisting_yaml: str | None,
    tmp_path: pathlib.Path,
    monkeypatch: MonkeyPatch,
    caplog: t.Any,
    snapshot: SnapshotAssertion,
) -> None:
    """Test discovering repositories from filesystem."""
    import logging

    caplog.set_level(logging.INFO)

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)

    scan_dir = tmp_path / "code"
    scan_dir.mkdir()

    # Create git repos
    for repo_name, remote_url in repos_to_create:
        repo_path = scan_dir / repo_name
        init_git_repo(repo_path, remote_url)

    if config_relpath is None:
        target_config_file = tmp_path / ".vcspull.yaml"
        config_argument = None
    else:
        target_config_file = tmp_path / config_relpath
        target_config_file.parent.mkdir(parents=True, exist_ok=True)
        config_argument = str(target_config_file)

    if preexisting_yaml is not None:
        target_config_file.write_text(preexisting_yaml, encoding="utf-8")
    elif preexisting_config is not None:
        import yaml

        target_config_file.write_text(
            yaml.dump(preexisting_config),
            encoding="utf-8",
        )

    if user_input is not None:
        monkeypatch.setattr("builtins.input", lambda _: user_input)

    # Run discover
    discover_repos(
        scan_dir_str=str(scan_dir),
        config_file_path_str=config_argument,
        recursive=recursive,
        workspace_root_override=workspace_override,
        yes=yes,
        dry_run=dry_run,
        merge_duplicates=merge_duplicates,
    )

    if preexisting_yaml is not None or not merge_duplicates:
        normalized_log = caplog.text.replace(str(target_config_file), "<config>")
        snapshot.assert_match({"test_id": test_id, "log": normalized_log})

    if dry_run:
        # In dry-run mode, config file should not be created/modified
        if expected_repo_count == 0:
            assert "Dry run complete" in caplog.text
        return

    # Check config file was created and has expected repos
    if expected_repo_count > 0:
        assert target_config_file.exists()

        import yaml

        with target_config_file.open() as f:
            config = yaml.safe_load(f)

        if expected_workspace_labels is not None:
            assert set(config.keys()) == expected_workspace_labels

        # Count repos in config
        total_repos = sum(
            len(repos) for repos in config.values() if isinstance(repos, dict)
        )
        assert total_repos == expected_repo_count, (
            f"Expected {expected_repo_count} repos, got {total_repos}"
        )


@pytest.mark.parametrize(
    list(DiscoverLoadEdgeFixture._fields),
    DISCOVER_LOAD_EDGE_FIXTURES,
    ids=[fixture.test_id for fixture in DISCOVER_LOAD_EDGE_FIXTURES],
)
def test_discover_config_load_edges(
    test_id: str,
    mode: t.Literal["multi_home", "non_dict", "exception"],
    expected_log_fragment: str,
    tmp_path: pathlib.Path,
    monkeypatch: MonkeyPatch,
    caplog: t.Any,
) -> None:
    """Ensure discover handles configuration loading edge cases gracefully."""
    import logging

    caplog.set_level(logging.INFO)

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)

    scan_dir = tmp_path / "scan"
    scan_dir.mkdir(parents=True, exist_ok=True)

    if mode == "multi_home":
        fake_paths = [tmp_path / "a.yaml", tmp_path / "b.yaml"]
        monkeypatch.setattr(
            "vcspull.cli.discover.find_home_config_files",
            lambda filetype=None: fake_paths,
        )
        discover_repos(
            scan_dir_str=str(scan_dir),
            config_file_path_str=None,
            recursive=False,
            workspace_root_override=None,
            yes=True,
            dry_run=False,
        )
    else:
        config_file = tmp_path / "config.yaml"
        config_file.write_text("[]\n", encoding="utf-8")

        if mode == "non_dict":
            monkeypatch.setattr(
                "vcspull.cli.discover.DuplicateAwareConfigReader.load_with_duplicates",
                lambda _path: (["invalid"], {}),
            )
        else:  # mode == "exception"

            def _raise(_path: pathlib.Path) -> t.NoReturn:
                error_message = "ConfigReader failed"
                raise ValueError(error_message)

            monkeypatch.setattr(
                "vcspull.cli.discover.DuplicateAwareConfigReader.load_with_duplicates",
                _raise,
            )

        discover_repos(
            scan_dir_str=str(scan_dir),
            config_file_path_str=str(config_file),
            recursive=False,
            workspace_root_override=None,
            yes=True,
            dry_run=False,
        )

    assert expected_log_fragment in caplog.text


def test_discover_skips_repos_without_remote(
    tmp_path: pathlib.Path,
    monkeypatch: MonkeyPatch,
    caplog: t.Any,
) -> None:
    """Test that discover skips git repos without a remote."""
    import logging

    caplog.set_level(logging.INFO)

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)

    scan_dir = tmp_path / "code"
    scan_dir.mkdir()

    # Create a repo without remote
    repo_path = scan_dir / "no-remote"
    repo_path.mkdir()
    subprocess.run(["git", "init"], cwd=repo_path, check=True, capture_output=True)

    config_file = tmp_path / ".vcspull.yaml"

    discover_repos(
        scan_dir_str=str(scan_dir),
        config_file_path_str=str(config_file),
        recursive=False,
        workspace_root_override=None,
        yes=True,
        dry_run=False,
    )

    # Should log a warning
    assert "Could not determine remote URL" in caplog.text


def test_discover_shows_existing_repos(
    tmp_path: pathlib.Path,
    monkeypatch: MonkeyPatch,
    caplog: t.Any,
) -> None:
    """Test that discover shows which repos already exist in config."""
    import logging

    caplog.set_level(logging.INFO)

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)

    scan_dir = tmp_path / "code"
    scan_dir.mkdir()

    # Create a git repo
    repo_path = scan_dir / "existing-repo"
    init_git_repo(repo_path, "git+https://github.com/user/existing-repo.git")

    config_file = tmp_path / ".vcspull.yaml"

    # First discovery
    discover_repos(
        scan_dir_str=str(scan_dir),
        config_file_path_str=str(config_file),
        recursive=False,
        workspace_root_override=None,
        yes=True,
        dry_run=False,
    )

    # Clear logs
    caplog.clear()

    # Second discovery (should find existing repo)
    discover_repos(
        scan_dir_str=str(scan_dir),
        config_file_path_str=str(config_file),
        recursive=False,
        workspace_root_override=None,
        yes=True,
        dry_run=False,
    )

    # Should mention existing repos
    assert "existing" in caplog.text.lower() or "already" in caplog.text.lower()


def test_discover_with_workspace_override(
    tmp_path: pathlib.Path,
    monkeypatch: MonkeyPatch,
) -> None:
    """Test discover with workspace root override."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)

    scan_dir = tmp_path / "code"
    scan_dir.mkdir()

    # Create a git repo
    repo_path = scan_dir / "myrepo"
    init_git_repo(repo_path, "git+https://github.com/user/myrepo.git")

    config_file = tmp_path / ".vcspull.yaml"

    # Discover with workspace override
    discover_repos(
        scan_dir_str=str(scan_dir),
        config_file_path_str=str(config_file),
        recursive=False,
        workspace_root_override="~/projects/",
        yes=True,
        dry_run=False,
    )

    import yaml

    with config_file.open() as f:
        config = yaml.safe_load(f)

    # Should use the overridden workspace root
    assert "~/projects/" in config
    assert "myrepo" in config["~/projects/"]


@pytest.mark.parametrize(
    list(DiscoverExistingSummaryFixture._fields),
    DISCOVER_EXISTING_SUMMARY_FIXTURES,
    ids=[fixture.test_id for fixture in DISCOVER_EXISTING_SUMMARY_FIXTURES],
)
def test_discover_existing_summary_branches(
    test_id: str,
    repo_count: int,
    expected_log_fragment: str,
    tmp_path: pathlib.Path,
    monkeypatch: MonkeyPatch,
    caplog: t.Any,
) -> None:
    """Ensure existing repository summaries cover both detailed and aggregate forms."""
    import logging

    import yaml

    caplog.set_level(logging.INFO)

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)

    scan_dir = tmp_path / "code"
    scan_dir.mkdir()

    repos_config: dict[str, dict[str, dict[str, str]]] = {"~/code/": {}}
    for idx in range(repo_count):
        repo_name = f"repo-{idx}"
        repo_path = scan_dir / repo_name
        init_git_repo(repo_path, f"git+https://example.com/{repo_name}.git")
        repos_config["~/code/"][repo_name] = {
            "repo": f"git+https://example.com/{repo_name}.git",
        }

    config_file = tmp_path / ".vcspull.yaml"
    config_file.write_text(yaml.dump(repos_config), encoding="utf-8")

    discover_repos(
        scan_dir_str=str(scan_dir),
        config_file_path_str=str(config_file),
        recursive=False,
        workspace_root_override=None,
        yes=True,
        dry_run=True,
    )

    assert expected_log_fragment in caplog.text


@pytest.mark.parametrize(
    list(DiscoverNormalizationFixture._fields),
    DISCOVER_NORMALIZATION_FIXTURES,
    ids=[fixture.test_id for fixture in DISCOVER_NORMALIZATION_FIXTURES],
)
def test_discover_normalization_only_save(
    test_id: str,
    preexisting_config: dict[str, dict[str, dict[str, str]]],
    expected_workspace_label: str,
    tmp_path: pathlib.Path,
    monkeypatch: MonkeyPatch,
    caplog: t.Any,
) -> None:
    """Normalization-only changes should still trigger a save."""
    import logging

    import yaml

    caplog.set_level(logging.INFO)

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)

    scan_dir = tmp_path / "code"
    scan_dir.mkdir()

    repo_path = scan_dir / "existing-repo"
    init_git_repo(repo_path, "git+https://example.com/existing.git")

    config_file = tmp_path / ".vcspull.yaml"
    config_file.write_text(yaml.dump(preexisting_config), encoding="utf-8")

    save_calls: list[tuple[pathlib.Path, dict[str, t.Any]]] = []

    def _fake_save(path: pathlib.Path, data: dict[str, t.Any]) -> None:
        save_calls.append((path, data))

    monkeypatch.setattr("vcspull.cli.discover.save_config_yaml", _fake_save)

    discover_repos(
        scan_dir_str=str(scan_dir),
        config_file_path_str=str(config_file),
        recursive=False,
        workspace_root_override=None,
        yes=True,
        dry_run=False,
    )

    assert save_calls, "Expected normalization changes to trigger a save."
    saved_path, saved_config = save_calls[-1]
    assert saved_path == config_file
    assert expected_workspace_label in saved_config
    assert "Successfully updated" in caplog.text


@pytest.mark.parametrize(
    list(DiscoverInvalidWorkspaceFixture._fields),
    DISCOVER_INVALID_WORKSPACE_FIXTURES,
    ids=[fixture.test_id for fixture in DISCOVER_INVALID_WORKSPACE_FIXTURES],
)
def test_discover_skips_non_dict_workspace(
    test_id: str,
    workspace_section: list[str],
    expected_warning: str,
    tmp_path: pathlib.Path,
    monkeypatch: MonkeyPatch,
    caplog: t.Any,
) -> None:
    """Repos targeting non-dict workspaces should be skipped without saving."""
    import logging

    import yaml

    caplog.set_level(logging.INFO)

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)

    scan_dir = tmp_path / "code"
    scan_dir.mkdir()

    repo_path = scan_dir / "new-repo"
    init_git_repo(repo_path, "git+https://example.com/new.git")

    config_file = tmp_path / ".vcspull.yaml"
    config_file.write_text(
        yaml.dump({"~/code/": workspace_section}),
        encoding="utf-8",
    )

    def _fail_save(path: pathlib.Path, data: dict[str, t.Any]) -> None:
        error_message = "save_config_yaml should not be called when skipping repo"
        raise AssertionError(error_message)

    monkeypatch.setattr("vcspull.cli.discover.save_config_yaml", _fail_save)

    discover_repos(
        scan_dir_str=str(scan_dir),
        config_file_path_str=str(config_file),
        recursive=False,
        workspace_root_override=None,
        yes=True,
        dry_run=False,
    )

    assert expected_warning in caplog.text
