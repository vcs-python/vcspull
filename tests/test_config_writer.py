"""Tests for config writer utilities."""

from __future__ import annotations

import textwrap
import typing as t

import pytest

from vcspull.config import save_config_yaml, save_config_yaml_with_items

if t.TYPE_CHECKING:
    import pathlib

FixtureEntry = tuple[str, dict[str, t.Any]]


@pytest.mark.parametrize(
    ("entries", "expected_yaml"),
    [
        (
            (
                (
                    "~/study/python/",
                    {"Flexget": {"repo": "git+https://github.com/Flexget/Flexget.git"}},
                ),
                (
                    "~/study/python/",
                    {"bubbles": {"repo": "git+https://github.com/Stiivi/bubbles.git"}},
                ),
            ),
            textwrap.dedent(
                """\
                ~/study/python/:
                  Flexget:
                    repo: git+https://github.com/Flexget/Flexget.git
                ~/study/python/:
                  bubbles:
                    repo: git+https://github.com/Stiivi/bubbles.git
                """,
            ),
        ),
    ],
)
def test_save_config_yaml_with_items_preserves_duplicate_sections(
    entries: tuple[FixtureEntry, ...],
    expected_yaml: str,
    tmp_path: pathlib.Path,
) -> None:
    """Writing duplicates should round-trip without collapsing sections."""
    config_path = tmp_path / ".vcspull.yaml"

    save_config_yaml_with_items(config_path, list(entries))

    yaml_text = config_path.read_text(encoding="utf-8")
    assert yaml_text == expected_yaml


def test_save_config_yaml_atomic_write(
    tmp_path: pathlib.Path,
) -> None:
    """Test that save_config_yaml uses atomic write (no temp files left)."""
    config_path = tmp_path / ".vcspull.yaml"
    data = {"~/code/": {"myrepo": {"repo": "git+https://example.com/repo.git"}}}

    save_config_yaml(config_path, data)

    # File should exist with correct content
    assert config_path.exists()
    content = config_path.read_text(encoding="utf-8")
    assert "myrepo" in content

    # No temp files should be left in the directory
    tmp_files = [f for f in tmp_path.iterdir() if f.name.startswith(".")]
    assert tmp_files == [config_path]


def test_save_config_yaml_atomic_preserves_existing_on_error(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that existing config is preserved if atomic write fails."""
    config_path = tmp_path / ".vcspull.yaml"
    original_content = (
        "~/code/:\n  existing: {repo: git+https://example.com/repo.git}\n"
    )
    config_path.write_text(original_content, encoding="utf-8")

    # Mock Path.replace to simulate a failure after temp file is written
    disk_error_msg = "Simulated disk error"

    import pathlib as _pathlib

    def failing_replace(self: _pathlib.Path, target: t.Any) -> _pathlib.Path:
        raise OSError(disk_error_msg)

    monkeypatch.setattr(_pathlib.Path, "replace", failing_replace)

    data = {"~/new/": {"newrepo": {"repo": "git+https://example.com/new.git"}}}
    with pytest.raises(OSError, match="Simulated disk error"):
        save_config_yaml(config_path, data)

    # Original file should be untouched
    assert config_path.read_text(encoding="utf-8") == original_content

    # No temp files should remain
    tmp_files = [
        f for f in tmp_path.iterdir() if f.name.startswith(".") and f != config_path
    ]
    assert tmp_files == []
