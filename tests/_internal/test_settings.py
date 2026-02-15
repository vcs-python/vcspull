"""Tests for vcspull._internal.settings."""

from __future__ import annotations

import pathlib
import typing as t

import pytest

from vcspull._internal.settings import (
    SETTINGS_FILENAME,
    VcspullSettings,
    load_settings,
    resolve_style,
)
from vcspull.types import ConfigStyle


class SettingsFixture(t.NamedTuple):
    """Fixture for settings loading test cases."""

    test_id: str
    toml_content: str | None  # None = no file
    expected_style: ConfigStyle


SETTINGS_FIXTURES: list[SettingsFixture] = [
    SettingsFixture(
        "no-file-uses-default",
        None,
        ConfigStyle.STANDARD,
    ),
    SettingsFixture(
        "explicit-standard",
        'config_style = "standard"\n',
        ConfigStyle.STANDARD,
    ),
    SettingsFixture(
        "explicit-concise",
        'config_style = "concise"\n',
        ConfigStyle.CONCISE,
    ),
    SettingsFixture(
        "explicit-verbose",
        'config_style = "verbose"\n',
        ConfigStyle.VERBOSE,
    ),
    SettingsFixture(
        "invalid-value-falls-back",
        'config_style = "invalid"\n',
        ConfigStyle.STANDARD,
    ),
    SettingsFixture(
        "empty-file-uses-default",
        "",
        ConfigStyle.STANDARD,
    ),
    SettingsFixture(
        "no-style-key-uses-default",
        'other_key = "value"\n',
        ConfigStyle.STANDARD,
    ),
]


@pytest.mark.parametrize(
    list(SettingsFixture._fields),
    SETTINGS_FIXTURES,
    ids=[f.test_id for f in SETTINGS_FIXTURES],
)
def test_load_settings(
    test_id: str,
    toml_content: str | None,
    expected_style: ConfigStyle,
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """load_settings should parse TOML correctly or fall back to defaults."""
    del test_id

    config_dir = tmp_path / "vcspull"
    config_dir.mkdir()

    if toml_content is not None:
        settings_file = config_dir / SETTINGS_FILENAME
        settings_file.write_text(toml_content, encoding="utf-8")

    monkeypatch.setattr("vcspull._internal.settings.get_config_dir", lambda: config_dir)

    settings = load_settings()
    assert settings.config_style == expected_style


def test_load_settings_invalid_toml(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Malformed TOML should fall back to defaults without crashing."""
    config_dir = tmp_path / "vcspull"
    config_dir.mkdir()
    settings_file = config_dir / SETTINGS_FILENAME
    settings_file.write_text("this is not valid toml [[[", encoding="utf-8")

    monkeypatch.setattr("vcspull._internal.settings.get_config_dir", lambda: config_dir)

    settings = load_settings()
    assert settings.config_style == ConfigStyle.STANDARD


def test_resolve_style_cli_overrides_settings() -> None:
    """CLI --style flag should take precedence over settings."""
    settings = VcspullSettings(config_style=ConfigStyle.VERBOSE)
    assert resolve_style("concise", settings=settings) == ConfigStyle.CONCISE


def test_resolve_style_uses_settings_when_cli_none() -> None:
    """When no CLI flag, settings value should be used."""
    settings = VcspullSettings(config_style=ConfigStyle.VERBOSE)
    assert resolve_style(None, settings=settings) == ConfigStyle.VERBOSE


def test_resolve_style_default_when_both_none(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When no CLI flag and no settings file, default to standard."""
    config_dir = tmp_path / "vcspull"
    config_dir.mkdir()
    monkeypatch.setattr("vcspull._internal.settings.get_config_dir", lambda: config_dir)

    assert resolve_style(None) == ConfigStyle.STANDARD


def test_resolve_style_invalid_cli_value() -> None:
    """Invalid CLI value should fall back to standard."""
    assert resolve_style("nonexistent") == ConfigStyle.STANDARD
