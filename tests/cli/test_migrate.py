"""Tests for vcspull migrate command."""

from __future__ import annotations

import logging
import typing as t

import pytest
import yaml

from vcspull.cli import cli
from vcspull.cli.migrate import migrate_config, migrate_config_file
from vcspull.config import save_config_yaml

if t.TYPE_CHECKING:
    import pathlib

    from _pytest.monkeypatch import MonkeyPatch


class MigrateConfigFixture(t.NamedTuple):
    """Fixture for migrate_config relocation cases."""

    test_id: str
    raw_config: dict[str, t.Any]
    expected_config: dict[str, t.Any]
    expected_changes: int


MIGRATE_CONFIG_FIXTURES: list[MigrateConfigFixture] = [
    MigrateConfigFixture(
        test_id="legacy-shallow",
        raw_config={"~/code/": {"flask": {"repo": "git+x", "shallow": True}}},
        expected_config={
            "~/code/": {"flask": {"repo": "git+x", "options": {"shallow": True}}},
        },
        expected_changes=1,
    ),
    MigrateConfigFixture(
        test_id="already-options",
        raw_config={
            "~/code/": {"flask": {"repo": "git+x", "options": {"shallow": True}}},
        },
        expected_config={
            "~/code/": {"flask": {"repo": "git+x", "options": {"shallow": True}}},
        },
        expected_changes=0,
    ),
    MigrateConfigFixture(
        test_id="depth-wins",
        raw_config={
            "~/code/": {"flask": {"repo": "git+x", "shallow": True, "depth": 5}}
        },
        expected_config={
            "~/code/": {"flask": {"repo": "git+x", "options": {"depth": 5}}},
        },
        expected_changes=1,
    ),
    MigrateConfigFixture(
        test_id="preserves-pin",
        raw_config={
            "~/code/": {
                "flask": {"repo": "git+x", "rev": "v1", "options": {"pin": True}},
            },
        },
        expected_config={
            "~/code/": {
                "flask": {"repo": "git+x", "options": {"pin": True, "rev": "v1"}},
            },
        },
        expected_changes=1,
    ),
    MigrateConfigFixture(
        test_id="string-entry-untouched",
        raw_config={"~/code/": {"flask": "git+x"}},
        expected_config={"~/code/": {"flask": "git+x"}},
        expected_changes=0,
    ),
]


@pytest.mark.parametrize(
    list(MigrateConfigFixture._fields),
    MIGRATE_CONFIG_FIXTURES,
    ids=[f.test_id for f in MIGRATE_CONFIG_FIXTURES],
)
def test_migrate_config(
    test_id: str,
    raw_config: dict[str, t.Any],
    expected_config: dict[str, t.Any],
    expected_changes: int,
) -> None:
    """migrate_config relocates legacy keys and counts rewritten entries."""
    migrated, change_count = migrate_config(raw_config)
    assert migrated == expected_config
    assert change_count == expected_changes


def test_migrate_config_file_write(
    tmp_path: pathlib.Path,
    monkeypatch: MonkeyPatch,
) -> None:
    """Migrate --write rewrites legacy entries into the options: form."""
    monkeypatch.setenv("HOME", str(tmp_path))
    config_file = tmp_path / ".vcspull.yaml"
    save_config_yaml(
        config_file,
        {
            "~/code/": {
                "flask": {"repo": "git+https://example.com/flask.git", "rev": "v1"},
                "django": {
                    "repo": "git+https://example.com/django.git",
                    "shallow": True,
                    "depth": 5,
                },
            },
        },
    )

    migrate_config_file(str(config_file), write=True)

    result = yaml.safe_load(config_file.read_text(encoding="utf-8"))
    assert result["~/code/"]["flask"] == {
        "repo": "git+https://example.com/flask.git",
        "options": {"rev": "v1"},
    }
    assert result["~/code/"]["django"] == {
        "repo": "git+https://example.com/django.git",
        "options": {"depth": 5},
    }


def test_migrate_config_file_dry_run(
    tmp_path: pathlib.Path,
    monkeypatch: MonkeyPatch,
) -> None:
    """Migrate without --write leaves the file untouched."""
    monkeypatch.setenv("HOME", str(tmp_path))
    config_file = tmp_path / ".vcspull.yaml"
    save_config_yaml(
        config_file,
        {"~/code/": {"flask": {"repo": "git+x", "shallow": True}}},
    )
    before = config_file.read_text(encoding="utf-8")

    migrate_config_file(str(config_file), write=False)

    assert config_file.read_text(encoding="utf-8") == before


def test_migrate_idempotent(
    tmp_path: pathlib.Path,
    monkeypatch: MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A second migrate --write run makes no changes."""
    monkeypatch.setenv("HOME", str(tmp_path))
    config_file = tmp_path / ".vcspull.yaml"
    save_config_yaml(
        config_file,
        {"~/code/": {"flask": {"repo": "git+x", "shallow": True}}},
    )

    migrate_config_file(str(config_file), write=True)
    after_first = config_file.read_text(encoding="utf-8")

    with caplog.at_level(logging.INFO, logger="vcspull.cli.migrate"):
        migrate_config_file(str(config_file), write=True)

    assert config_file.read_text(encoding="utf-8") == after_first
    assert any("already nests" in record.getMessage() for record in caplog.records)


def test_migrate_cli_end_to_end(
    tmp_path: pathlib.Path,
    monkeypatch: MonkeyPatch,
) -> None:
    """`vcspull migrate -f FILE --write` rewrites the file."""
    monkeypatch.setenv("HOME", str(tmp_path))
    config_file = tmp_path / ".vcspull.yaml"
    save_config_yaml(
        config_file,
        {"~/code/": {"flask": {"repo": "git+x", "shallow": True}}},
    )

    cli(["migrate", "-f", str(config_file), "--write"])

    result = yaml.safe_load(config_file.read_text(encoding="utf-8"))
    assert result["~/code/"]["flask"] == {"repo": "git+x", "options": {"shallow": True}}
