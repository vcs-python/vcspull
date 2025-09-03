"""Tests for vcspull fmt command."""

from __future__ import annotations

import logging
import pathlib
import typing as t

import pytest
import yaml

from vcspull.cli.fmt import format_config, format_config_file, normalize_repo_config

if t.TYPE_CHECKING:
    from _pytest.logging import LogCaptureFixture


@pytest.fixture
def clear_logging_handlers() -> t.Generator[None, None, None]:
    """Clear logging handlers to prevent duplicate log messages in tests."""
    # Store original handlers
    original_handlers = logging.root.handlers[:]
    # Clear all handlers
    logging.root.handlers = []
    yield
    # Restore original handlers
    logging.root.handlers = original_handlers


class TestNormalizeRepoConfig:
    """Test normalization of repository configurations."""

    def test_compact_to_verbose(self) -> None:
        """Test converting compact format to verbose format."""
        compact = "git+https://github.com/user/repo.git"
        normalized = normalize_repo_config(compact)
        assert normalized == {"repo": compact}

    def test_url_to_repo_key(self) -> None:
        """Test converting url key to repo key."""
        config_with_url = {"url": "git+https://github.com/user/repo.git"}
        normalized = normalize_repo_config(config_with_url)
        assert normalized == {"repo": "git+https://github.com/user/repo.git"}

    def test_already_normalized(self) -> None:
        """Test that already normalized configs are unchanged."""
        config = {"repo": "git+https://github.com/user/repo.git"}
        normalized = normalize_repo_config(config)
        assert normalized == config

    def test_preserve_extra_fields(self) -> None:
        """Test that extra fields are preserved."""
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

    def test_both_url_and_repo(self) -> None:
        """Test when both url and repo keys exist."""
        config = {
            "url": "git+https://github.com/user/repo1.git",
            "repo": "git+https://github.com/user/repo2.git",
        }
        normalized = normalize_repo_config(config)
        # Should keep as-is when both exist
        assert normalized == config


class TestFormatConfig:
    """Test configuration formatting."""

    def test_sort_directories(self) -> None:
        """Test that directories are sorted alphabetically."""
        config = {
            "~/zzz/": {"repo1": "url1"},
            "~/aaa/": {"repo2": "url2"},
            "~/mmm/": {"repo3": "url3"},
        }
        formatted, changes = format_config(config)
        assert list(formatted.keys()) == ["~/aaa/", "~/mmm/", "~/zzz/"]
        assert changes > 0

    def test_sort_repositories(self) -> None:
        """Test that repositories within directories are sorted."""
        config = {
            "~/projects/": {
                "zebra": "url1",
                "alpha": "url2",
                "beta": "url3",
            }
        }
        formatted, changes = format_config(config)
        assert list(formatted["~/projects/"].keys()) == ["alpha", "beta", "zebra"]
        assert changes > 0

    def test_compact_format_conversion(self) -> None:
        """Test conversion of compact format to verbose."""
        config = {
            "~/projects/": {
                "repo1": "git+https://github.com/user/repo1.git",
                "repo2": {"url": "git+https://github.com/user/repo2.git"},
                "repo3": {"repo": "git+https://github.com/user/repo3.git"},
            }
        }
        formatted, changes = format_config(config)

        # repo1 should be converted from compact to verbose
        assert formatted["~/projects/"]["repo1"] == {
            "repo": "git+https://github.com/user/repo1.git"
        }
        # repo2 should have url converted to repo
        assert formatted["~/projects/"]["repo2"] == {
            "repo": "git+https://github.com/user/repo2.git"
        }
        # repo3 should stay the same
        assert formatted["~/projects/"]["repo3"] == {
            "repo": "git+https://github.com/user/repo3.git"
        }
        assert changes == 2  # repo1 and repo2 changed

    def test_no_changes_needed(self) -> None:
        """Test when no formatting changes are needed."""
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

    def test_complex_formatting(self) -> None:
        """Test complex formatting with multiple changes."""
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

        # Check directory sorting
        assert list(formatted.keys()) == ["~/aaa/", "~/zzz/"]

        # Check repository sorting in ~/zzz/
        assert list(formatted["~/zzz/"].keys()) == ["alpha", "beta", "zebra"]

        # Check format conversions
        assert formatted["~/aaa/"]["repo1"] == {"repo": "another-compact"}
        assert formatted["~/zzz/"]["zebra"] == {"repo": "compact-url"}
        assert formatted["~/zzz/"]["alpha"] == {"repo": "verbose-url"}
        assert formatted["~/zzz/"]["beta"]["repo"] == "already-good"
        assert formatted["~/zzz/"]["beta"]["remotes"] == {"upstream": "upstream-url"}

        # Should have multiple changes
        assert changes > 0


class TestFormatConfigFile:
    """Test the format_config_file function."""

    def test_format_file_no_write(
        self,
        tmp_path: pathlib.Path,
        caplog: LogCaptureFixture,
        clear_logging_handlers: None,
    ) -> None:
        """Test formatting without writing changes."""
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

        with config_file.open("w", encoding="utf-8") as f:
            yaml.dump(original_config, f)

        with caplog.at_level(logging.INFO):
            format_config_file(str(config_file), write=False)

        # Check that file was not modified
        with config_file.open(encoding="utf-8") as f:
            saved_config = yaml.safe_load(f)
        assert saved_config == original_config

        # Check log messages
        assert "formatting issue" in caplog.text
        assert "Run with --write to apply" in caplog.text

    def test_format_file_with_write(
        self,
        tmp_path: pathlib.Path,
        caplog: LogCaptureFixture,
        clear_logging_handlers: None,
    ) -> None:
        """Test formatting with writing changes."""
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

        with config_file.open("w", encoding="utf-8") as f:
            yaml.dump(original_config, f)

        with caplog.at_level(logging.INFO):
            format_config_file(str(config_file), write=True)

        # Check that file was modified
        with config_file.open(encoding="utf-8") as f:
            saved_config = yaml.safe_load(f)

        # Check formatting was applied
        assert list(saved_config.keys()) == ["~/aaa/", "~/zzz/"]
        assert saved_config["~/aaa/"]["repo3"] == {"repo": "url3"}
        assert saved_config["~/zzz/"]["repo1"] == {"repo": "url1"}
        assert saved_config["~/zzz/"]["repo2"] == {"repo": "url2"}
        assert list(saved_config["~/zzz/"].keys()) == ["repo1", "repo2"]

        # Check log messages
        assert "Successfully formatted" in caplog.text

    def test_already_formatted(
        self,
        tmp_path: pathlib.Path,
        caplog: LogCaptureFixture,
        clear_logging_handlers: None,
    ) -> None:
        """Test when file is already correctly formatted."""
        config_file = tmp_path / ".vcspull.yaml"
        config = {
            "~/aaa/": {
                "repo1": {"repo": "url1"},
            },
            "~/bbb/": {
                "repo2": {"repo": "url2"},
            },
        }

        with config_file.open("w", encoding="utf-8") as f:
            yaml.dump(config, f)

        with caplog.at_level(logging.INFO):
            format_config_file(str(config_file), write=False)

        assert "already formatted correctly" in caplog.text

    def test_nonexistent_file(
        self,
        tmp_path: pathlib.Path,
        caplog: LogCaptureFixture,
        clear_logging_handlers: None,
    ) -> None:
        """Test handling of nonexistent config file."""
        config_file = tmp_path / "nonexistent.yaml"

        with caplog.at_level(logging.ERROR):
            format_config_file(str(config_file), write=False)

        assert "not found" in caplog.text

    def test_invalid_yaml(
        self,
        tmp_path: pathlib.Path,
        caplog: LogCaptureFixture,
        clear_logging_handlers: None,
    ) -> None:
        """Test handling of invalid YAML."""
        config_file = tmp_path / ".vcspull.yaml"
        config_file.write_text("invalid: yaml: content:", encoding="utf-8")

        with caplog.at_level(logging.ERROR):
            format_config_file(str(config_file), write=False)

        assert "Error loading config" in caplog.text

    def test_no_config_found(
        self,
        tmp_path: pathlib.Path,
        caplog: LogCaptureFixture,
        monkeypatch: pytest.MonkeyPatch,
        clear_logging_handlers: None,
    ) -> None:
        """Test when no config file is found."""
        monkeypatch.chdir(tmp_path)

        with caplog.at_level(logging.ERROR):
            format_config_file(None, write=False)

        assert "No configuration file found" in caplog.text

    def test_detailed_change_reporting(
        self,
        tmp_path: pathlib.Path,
        caplog: LogCaptureFixture,
        clear_logging_handlers: None,
    ) -> None:
        """Test detailed reporting of changes."""
        config_file = tmp_path / ".vcspull.yaml"
        # Write YAML manually to preserve key order
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
            format_config_file(str(config_file), write=False)

        # Check detailed change reporting
        assert "3 repositories from compact to verbose format" in caplog.text
        assert "2 repositories from 'url' to 'repo' key" in caplog.text
        assert "Directories will be sorted alphabetically" in caplog.text
