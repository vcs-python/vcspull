"""Tests for duplicate-preserving config writer utilities."""

from __future__ import annotations

import pathlib
import textwrap
import typing as t

import pytest

from vcspull.config import save_config_yaml_with_items

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
