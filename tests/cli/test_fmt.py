"""Tests for vcspull fmt command."""

from __future__ import annotations

import contextlib
import logging
import pathlib
import textwrap
import typing as t

import pytest
import yaml

from vcspull.cli import cli
from vcspull.cli.fmt import format_config, format_config_file, normalize_repo_config
from vcspull.config import (
    canonicalize_workspace_path,
    normalize_workspace_roots,
    workspace_root_label,
)

if t.TYPE_CHECKING:
    from _pytest.logging import LogCaptureFixture


def _assert_yaml_snapshot(config_path: pathlib.Path, expected: str) -> None:
    """Compare saved YAML config against an expected snapshot."""
    snapshot = textwrap.dedent(expected).strip("\n") + "\n"
    content = config_path.read_text(encoding="utf-8")
    assert content == snapshot


class WorkspaceRootFixture(t.NamedTuple):
    """Fixture for workspace root normalization cases."""

    test_id: str
    config_factory: t.Callable[[pathlib.Path], dict[str, t.Any]]


WORKSPACE_ROOT_FIXTURES: list[WorkspaceRootFixture] = [
    WorkspaceRootFixture(
        test_id="tilde-mixed-trailing-slash",
        config_factory=lambda _base: {
            "~/study/c": {
                "cpython": {"repo": "git+https://github.com/python/cpython.git"},
            },
            "~/study/c/": {
                "tmux": {"repo": "git+https://github.com/tmux/tmux.git"},
            },
        },
    ),
    WorkspaceRootFixture(
        test_id="home-vs-absolute",
        config_factory=lambda base: {
            str(base / "study" / "c"): {
                "cpython": {"repo": "git+https://github.com/python/cpython.git"},
            },
            "~/study/c/": {
                "tmux": {"repo": "git+https://github.com/tmux/tmux.git"},
            },
        },
    ),
    WorkspaceRootFixture(
        test_id="relative-vs-tilde",
        config_factory=lambda _base: {
            "./study/c": {
                "cpython": {"repo": "git+https://github.com/python/cpython.git"},
            },
            "~/study/c/": {
                "tmux": {"repo": "git+https://github.com/tmux/tmux.git"},
            },
        },
    ),
]


@pytest.mark.parametrize(
    list(WorkspaceRootFixture._fields),
    [
        (
            fixture.test_id,
            fixture.config_factory,
        )
        for fixture in WORKSPACE_ROOT_FIXTURES
    ],
    ids=[fixture.test_id for fixture in WORKSPACE_ROOT_FIXTURES],
)
def test_workspace_root_normalization(
    test_id: str,
    config_factory: t.Callable[[pathlib.Path], dict[str, t.Any]],
) -> None:
    """Ensure format_config merges duplicate workspace roots."""
    home_dir = pathlib.Path.home()
    config = config_factory(home_dir)

    canonical_paths = {
        canonicalize_workspace_path(label, cwd=home_dir) for label in config
    }
    expected_labels = [
        workspace_root_label(path, cwd=home_dir, home=home_dir)
        for path in sorted(canonical_paths, key=lambda p: p.as_posix())
    ]

    normalized_config, _map, conflicts, merge_changes = normalize_workspace_roots(
        config,
        cwd=home_dir,
        home=home_dir,
    )
    assert conflicts == []
    assert sorted(normalized_config.keys()) == expected_labels
    formatted, _changes = format_config(normalized_config)
    assert sorted(formatted.keys()) == expected_labels
    assert merge_changes >= len(config) - len(canonical_paths)


def test_normalize_repo_config_compact_to_verbose() -> None:
    """Compact repository config should expand to verbose form."""
    compact = "git+https://github.com/user/repo.git"
    normalized = normalize_repo_config(compact)
    assert normalized == {"repo": compact}


def test_normalize_repo_config_url_to_repo() -> None:
    """Entries using url key should be converted to repo."""
    config_with_url = {"url": "git+https://github.com/user/repo.git"}
    normalized = normalize_repo_config(config_with_url)
    assert normalized == {"repo": "git+https://github.com/user/repo.git"}


def test_normalize_repo_config_already_verbose() -> None:
    """Verbose configs should remain unchanged."""
    config = {"repo": "git+https://github.com/user/repo.git"}
    normalized = normalize_repo_config(config)
    assert normalized == config


def test_normalize_repo_config_preserves_extras() -> None:
    """Extra fields should be preserved during normalization."""
    config = {
        "url": "git+https://github.com/user/repo.git",
        "remotes": {"upstream": "git+https://github.com/upstream/repo.git"},
        "shell_command_after": "ln -sf /foo /bar",
    }
    normalized = normalize_repo_config(config)
    assert normalized == {
        "repo": "git+https://github.com/user/repo.git",
        "remotes": {"upstream": "git+https://github.com/upstream/repo.git"},
        "shell_command_after": "ln -sf /foo /bar",
    }


def test_normalize_repo_config_both_url_and_repo() -> None:
    """When url and repo keys coexist, keep config unchanged."""
    config = {
        "url": "git+https://github.com/user/repo1.git",
        "repo": "git+https://github.com/user/repo2.git",
    }
    normalized = normalize_repo_config(config)
    assert normalized == config


def test_format_config_sorts_directories() -> None:
    """Workspace roots should be sorted alphabetically."""
    config = {
        "~/zzz/": {"repo1": "url1"},
        "~/aaa/": {"repo2": "url2"},
        "~/mmm/": {"repo3": "url3"},
    }
    formatted, changes = format_config(config)
    assert list(formatted.keys()) == ["~/aaa/", "~/mmm/", "~/zzz/"]
    assert changes > 0


def test_format_config_sorts_repositories() -> None:
    """Repositories within a workspace root should be sorted."""
    config = {
        "~/projects/": {
            "zebra": "url1",
            "alpha": "url2",
            "beta": "url3",
        },
    }
    formatted, changes = format_config(config)
    assert list(formatted["~/projects/"].keys()) == ["alpha", "beta", "zebra"]
    assert changes > 0


def test_format_config_converts_compact_entries() -> None:
    """Compact repository entries should convert to verbose form."""
    config = {
        "~/projects/": {
            "repo1": "git+https://github.com/user/repo1.git",
            "repo2": {"url": "git+https://github.com/user/repo2.git"},
            "repo3": {"repo": "git+https://github.com/user/repo3.git"},
        },
    }
    formatted, changes = format_config(config)
    assert formatted["~/projects/"]["repo1"] == {
        "repo": "git+https://github.com/user/repo1.git",
    }
    assert formatted["~/projects/"]["repo2"] == {
        "repo": "git+https://github.com/user/repo2.git",
    }
    assert formatted["~/projects/"]["repo3"] == {
        "repo": "git+https://github.com/user/repo3.git",
    }
    assert changes == 2


def test_format_config_no_changes_when_already_normalized() -> None:
    """Formatter should report zero changes for already-normalized configs."""
    config = {
        "~/aaa/": {
            "alpha": {"repo": "url1"},
            "beta": {"repo": "url2"},
        },
        "~/bbb/": {
            "charlie": {"repo": "url3"},
        },
    }
    formatted, changes = format_config(config)
    assert formatted == config
    assert changes == 0


def test_format_config_complex_changes() -> None:
    """Formatter should handle sorting and conversions together."""
    config = {
        "~/zzz/": {
            "zebra": "compact-url",
            "alpha": {"url": "verbose-url"},
            "beta": {
                "repo": "already-good",
                "remotes": {"upstream": "upstream-url"},
            },
        },
        "~/aaa/": {
            "repo1": "another-compact",
        },
    }
    formatted, changes = format_config(config)
    assert list(formatted.keys()) == ["~/aaa/", "~/zzz/"]
    assert list(formatted["~/zzz/"].keys()) == ["alpha", "beta", "zebra"]
    assert formatted["~/aaa/"]["repo1"] == {"repo": "another-compact"}
    assert formatted["~/zzz/"]["zebra"] == {"repo": "compact-url"}
    assert formatted["~/zzz/"]["alpha"] == {"repo": "verbose-url"}
    assert formatted["~/zzz/"]["beta"]["repo"] == "already-good"
    assert formatted["~/zzz/"]["beta"]["remotes"] == {"upstream": "upstream-url"}
    assert changes > 0


def test_format_config_file_without_write(
    tmp_path: pathlib.Path,
    caplog: LogCaptureFixture,
) -> None:
    """format_config_file should log issues without modifying when write=False."""
    config_file = tmp_path / ".vcspull.yaml"
    original_config = {
        "~/zzz/": {
            "repo2": "url2",
            "repo1": {"url": "url1"},
        },
        "~/aaa/": {
            "repo3": "url3",
        },
    }

    config_file.write_text(yaml.dump(original_config), encoding="utf-8")

    with caplog.at_level(logging.INFO):
        format_config_file(str(config_file), write=False, format_all=False)

    saved_config = yaml.safe_load(config_file.read_text(encoding="utf-8"))
    assert saved_config == original_config
    assert "formatting issue" in caplog.text
    assert "Run with --write to apply" in caplog.text


def test_format_config_file_with_write(tmp_path: pathlib.Path) -> None:
    """format_config_file should rewrite file when write=True."""
    config_file = tmp_path / ".vcspull.yaml"
    original_config = {
        "~/zzz/": {
            "repo2": "url2",
            "repo1": {"url": "url1"},
        },
    }
    config_file.write_text(yaml.dump(original_config), encoding="utf-8")

    format_config_file(str(config_file), write=True, format_all=False)

    saved_config = yaml.safe_load(config_file.read_text(encoding="utf-8"))
    assert saved_config["~/zzz/"]["repo1"] == {"repo": "url1"}


def test_format_config_file_invalid_yaml(
    tmp_path: pathlib.Path,
    caplog: LogCaptureFixture,
) -> None:
    """Invalid YAML should be reported without crashing."""
    config_file = tmp_path / ".vcspull.yaml"
    config_file.write_text("invalid: yaml: content:", encoding="utf-8")

    with caplog.at_level(logging.ERROR):
        format_config_file(str(config_file), write=False, format_all=False)

    assert "Error loading config" in caplog.text


def test_format_config_file_missing_config(
    tmp_path: pathlib.Path,
    caplog: LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Formatting without available config should emit an error."""
    monkeypatch.chdir(tmp_path)

    with caplog.at_level(logging.ERROR):
        format_config_file(None, write=False, format_all=False)

    assert "No configuration file found" in caplog.text


def test_format_config_file_reports_changes(
    tmp_path: pathlib.Path,
    caplog: LogCaptureFixture,
) -> None:
    """Detailed change summary should be logged for pending updates."""
    config_file = tmp_path / ".vcspull.yaml"
    yaml_content = """~/zzz/:
  compact1: url1
  compact2: url2
  verbose1:
    url: url3
  verbose2:
    url: url4
~/aaa/:
  repo: url5
"""
    config_file.write_text(yaml_content, encoding="utf-8")

    with caplog.at_level(logging.INFO):
        format_config_file(str(config_file), write=False, format_all=False)

    text = caplog.text
    assert "compact to verbose format" in text
    assert "from 'url' to 'repo' key" in text
    assert "Directories will be sorted alphabetically" in text
    assert "Run with --write to apply" in text


def test_format_all_configs(
    tmp_path: pathlib.Path,
    caplog: LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """format_config_file with --all should process discovered configs."""
    config_dir = tmp_path / ".config" / "vcspull"
    config_dir.mkdir(parents=True)

    home_config = tmp_path / ".vcspull.yaml"
    home_config.write_text(
        yaml.dump({"~/projects/": {"repo1": {"repo": "url1"}}}),
        encoding="utf-8",
    )

    work_config = config_dir / "work.yaml"
    work_config.write_text(
        """~/work/:
  repo2: url2
  repo1: url1
""",
        encoding="utf-8",
    )

    local_root = tmp_path / "project"
    local_root.mkdir()
    local_config = local_root / ".vcspull.yaml"
    local_config.write_text(
        yaml.dump({"./": {"repo3": {"url": "url3"}}}),
        encoding="utf-8",
    )

    monkeypatch.chdir(local_root)

    def fake_find_config_files(include_home: bool = False) -> list[pathlib.Path]:
        files: list[pathlib.Path] = [work_config]
        if include_home:
            files.insert(0, home_config)
        return files

    def fake_find_home_config_files(
        filetype: list[str] | None = None,
    ) -> list[pathlib.Path]:
        return [home_config]

    monkeypatch.setattr(
        "vcspull.cli.fmt.find_config_files",
        fake_find_config_files,
    )
    monkeypatch.setattr(
        "vcspull.cli.fmt.find_home_config_files",
        fake_find_home_config_files,
    )

    with caplog.at_level(logging.INFO):
        format_config_file(None, write=False, format_all=True)

    text = caplog.text
    assert "Found 3 configuration files to format" in text
    assert str(home_config) in text
    assert str(work_config) in text
    assert str(local_config) in text
    assert "already formatted correctly" in text
    assert "Repositories in ~/work/ will be sorted alphabetically" in text
    assert "All 3 configuration files processed successfully" in text


def test_format_config_detects_and_merges_duplicate_roots(
    tmp_path: pathlib.Path,
    caplog: LogCaptureFixture,
) -> None:
    """Duplicate workspace roots should be detected and merged by default."""
    config_file = tmp_path / ".vcspull.yaml"
    config_file.write_text(
        """~/study/c/:
  repo1: url1
~/study/c/:
  repo2: url2
""",
        encoding="utf-8",
    )

    with caplog.at_level(logging.INFO):
        format_config_file(str(config_file), write=False, format_all=False)

    text = caplog.text
    assert "Merged" in text
    assert "workspace root" in text


def test_format_config_no_merge_flag_skips_duplicate_merge(
    tmp_path: pathlib.Path,
    caplog: LogCaptureFixture,
) -> None:
    """--no-merge should prevent duplicate workspace roots from being combined."""
    config_file = tmp_path / ".vcspull.yaml"
    config_file.write_text(
        """~/study/c/:
  repo1: url1
~/study/c/:
  repo2: url2
""",
        encoding="utf-8",
    )

    with caplog.at_level(logging.WARNING):
        format_config_file(
            str(config_file),
            write=True,
            format_all=False,
            merge_roots=False,
        )

    text = caplog.text
    assert "skipping merge" in text
    _assert_yaml_snapshot(
        config_file,
        """~/study/c/:
  repo2:
    repo: url2
""",
    )


def test_format_config_merges_duplicate_roots_when_writing(
    tmp_path: pathlib.Path,
) -> None:
    """When merging, formatted file should contain combined repositories."""
    config_file = tmp_path / ".vcspull.yaml"
    config_file.write_text(
        """~/study/c/:
  repo1: url1
~/study/c/:
  repo2: url2
""",
        encoding="utf-8",
    )

    format_config_file(str(config_file), write=True, format_all=False)

    _assert_yaml_snapshot(
        config_file,
        """~/study/c/:
  repo1:
    repo: url1
  repo2:
    repo: url2
""",
    )


class FmtIntegrationFixture(t.NamedTuple):
    """Fixture for parametrized fmt CLI integration tests."""

    test_id: str
    cli_args: list[str]
    expected_log_fragment: str
    expected_yaml: str


FMT_CLI_FIXTURES: list[FmtIntegrationFixture] = [
    FmtIntegrationFixture(
        test_id="merge-default",
        cli_args=["fmt", "-f", "{config}", "--write"],
        expected_log_fragment="Merged",
        expected_yaml="""~/study/c/:
  repo1:
    repo: url1
  repo2:
    repo: url2
""",
    ),
    FmtIntegrationFixture(
        test_id="no-merge",
        cli_args=["fmt", "-f", "{config}", "--write", "--no-merge"],
        expected_log_fragment="skipping merge",
        expected_yaml="""~/study/c/:
  repo2:
    repo: url2
""",
    ),
]


@pytest.mark.parametrize(
    list(FmtIntegrationFixture._fields),
    FMT_CLI_FIXTURES,
    ids=[fixture.test_id for fixture in FMT_CLI_FIXTURES],
)
def test_fmt_cli_integration(
    tmp_path: pathlib.Path,
    caplog: LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
    test_id: str,
    cli_args: list[str],
    expected_log_fragment: str,
    expected_yaml: str,
) -> None:
    """Run vcspull fmt via CLI to ensure duplicate handling respects flags."""
    config_file = tmp_path / ".vcspull.yaml"
    config_file.write_text(
        """~/study/c/:
  repo1: url1
~/study/c/:
  repo2: url2
""",
        encoding="utf-8",
    )

    monkeypatch.chdir(tmp_path)

    formatted_args = [
        arg.format(config=str(config_file)) if "{config}" in arg else arg
        for arg in cli_args
    ]

    with caplog.at_level(logging.INFO), contextlib.suppress(SystemExit):
        cli(formatted_args)

    _assert_yaml_snapshot(config_file, expected_yaml)
    assert expected_log_fragment in caplog.text
