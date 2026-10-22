"""Tests for vcspull migrate command."""

from __future__ import annotations

import logging
import typing as t

import pytest
import yaml

from vcspull._internal.config_reader import DuplicateAwareConfigReader
from vcspull.cli import cli
from vcspull.cli.migrate import (
    migrate_config,
    migrate_config_file,
    migrate_single_config,
)
from vcspull.config import save_config_yaml, save_config_yaml_with_items

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
        raw_config={"~/code/": {"flask": {"repo": "git+ssh://x", "shallow": True}}},
        expected_config={
            "~/code/": {"flask": {"repo": "git+ssh://x", "git": {"depth": 1}}},
        },
        expected_changes=1,
    ),
    MigrateConfigFixture(
        test_id="legacy-options",
        raw_config={
            "~/code/": {"flask": {"repo": "git+ssh://x", "options": {"shallow": True}}},
        },
        expected_config={
            "~/code/": {"flask": {"repo": "git+ssh://x", "git": {"depth": 1}}},
        },
        expected_changes=1,
    ),
    MigrateConfigFixture(
        test_id="depth-wins",
        raw_config={
            "~/code/": {"flask": {"repo": "git+ssh://x", "shallow": True, "depth": 5}}
        },
        expected_config={
            "~/code/": {"flask": {"repo": "git+ssh://x", "git": {"depth": 5}}},
        },
        expected_changes=1,
    ),
    MigrateConfigFixture(
        test_id="preserves-pin",
        raw_config={
            "~/code/": {
                "flask": {"repo": "git+ssh://x", "rev": "v1", "options": {"pin": True}},
            },
        },
        expected_config={
            "~/code/": {
                "flask": {
                    "repo": "git+ssh://x",
                    "pin": True,
                    "working_copy": {"rev": "v1"},
                },
            },
        },
        expected_changes=1,
    ),
    MigrateConfigFixture(
        test_id="string-entry-untouched",
        raw_config={"~/code/": {"flask": "git+ssh://x"}},
        expected_config={"~/code/": {"flask": "git+ssh://x"}},
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
    """Migrate --write separates checkout targets and backend options."""
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
        "working_copy": {"rev": "v1"},
    }
    assert result["~/code/"]["django"] == {
        "repo": "git+https://example.com/django.git",
        "git": {"depth": 5},
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
        {"~/code/": {"flask": {"repo": "git+ssh://x", "shallow": True}}},
    )
    before = config_file.read_text(encoding="utf-8")

    migrate_config_file(str(config_file), write=False)

    assert config_file.read_text(encoding="utf-8") == before


def test_migrate_invalid_entry_keeps_file(
    tmp_path: pathlib.Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A later invalid entry prevents every write and identifies its location."""
    config_file = tmp_path / "repos.yaml"
    save_config_yaml(
        config_file,
        {
            "~/code/": {
                "valid": {"repo": "git+ssh://x", "depth": 2},
                "invalid": {"repo": "hg+y", "options": {"deph": 5}},
            }
        },
    )
    before = config_file.read_bytes()

    assert not migrate_single_config(config_file, write=True)

    assert config_file.read_bytes() == before
    message = caplog.records[-1].getMessage()
    for location in ("repos.yaml", "~/code/", "invalid", "options.deph"):
        assert location in message


def test_migrate_preserves_duplicate_workspace_sections(tmp_path: pathlib.Path) -> None:
    """Each repeated workspace section keeps its repositories and order."""
    config_file = tmp_path / "repos.yaml"
    save_config_yaml_with_items(
        config_file,
        [
            ("~/code/", {"first": {"repo": "git+ssh://x", "options": {"rev": "one"}}}),
            ("~/code/", {"second": {"repo": "hg+y", "options": {"rev": "two"}}}),
        ],
    )

    assert migrate_single_config(config_file, write=True)

    _, _, items = DuplicateAwareConfigReader.load_with_duplicates(config_file)
    assert items == [
        ("~/code/", {"first": {"repo": "git+ssh://x", "working_copy": {"rev": "one"}}}),
        ("~/code/", {"second": {"repo": "hg+y", "working_copy": {"rev": "two"}}}),
    ]
    before = config_file.read_bytes()
    assert migrate_single_config(config_file, write=True)
    assert config_file.read_bytes() == before


def test_migrate_cli_exits_nonzero_on_invalid_options(tmp_path: pathlib.Path) -> None:
    """Scripts can distinguish a rejected migration from a successful preview."""
    config_file = tmp_path / "repos.yaml"
    save_config_yaml(
        config_file,
        {"~/code/": {"repo": {"repo": "git+ssh://x", "options": {"deph": 1}}}},
    )
    with pytest.raises(SystemExit) as error:
        cli(["migrate", "--file", str(config_file), "--write"])
    assert error.value.code == 1


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
        {"~/code/": {"flask": {"repo": "git+ssh://x", "shallow": True}}},
    )

    migrate_config_file(str(config_file), write=True)
    after_first = config_file.read_text(encoding="utf-8")

    with caplog.at_level(logging.INFO, logger="vcspull.cli.migrate"):
        migrate_config_file(str(config_file), write=True)

    assert config_file.read_text(encoding="utf-8") == after_first
    assert any("already uses" in record.getMessage() for record in caplog.records)


def test_migrate_cli_end_to_end(
    tmp_path: pathlib.Path,
    monkeypatch: MonkeyPatch,
) -> None:
    """`vcspull migrate -f FILE --write` rewrites the file."""
    monkeypatch.setenv("HOME", str(tmp_path))
    config_file = tmp_path / ".vcspull.yaml"
    save_config_yaml(
        config_file,
        {"~/code/": {"flask": {"repo": "git+ssh://x", "shallow": True}}},
    )

    cli(["migrate", "-f", str(config_file), "--write"])

    result = yaml.safe_load(config_file.read_text(encoding="utf-8"))
    assert result["~/code/"]["flask"] == {"repo": "git+ssh://x", "git": {"depth": 1}}
