"""Tests for commands shown in CLI help text."""

from __future__ import annotations

import contextlib
import io
import re
import shlex
import typing as t

import pytest

from vcspull import cli as cli_module
from vcspull.cli import create_parser


class HelpCommandFixture(t.NamedTuple):
    """Fixture for a command harvested from help text."""

    test_id: str
    source: str
    command: str


def _slug(text: str) -> str:
    """Return a readable test ID slug."""
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:90]


def _help_descriptions() -> dict[str, str]:
    """Return CLI description constants that contain example commands."""
    return {
        name: value
        for name, value in vars(cli_module).items()
        if name.endswith("_DESCRIPTION") and isinstance(value, str)
    }


def _help_commands() -> list[HelpCommandFixture]:
    """Harvest vcspull commands from CLI help descriptions."""
    commands: list[HelpCommandFixture] = []
    seen: set[tuple[str, str]] = set()
    for name, text in sorted(_help_descriptions().items()):
        for line in text.splitlines():
            command = line.strip()
            if not command.startswith("vcspull "):
                continue
            key = (name, command)
            if key in seen:
                continue
            seen.add(key)
            commands.append(
                HelpCommandFixture(
                    test_id=f"{name.lower()}:{_slug(command)}",
                    source=name,
                    command=command,
                ),
            )
    return commands


HELP_COMMAND_FIXTURES = _help_commands()


def test_help_commands_were_harvested() -> None:
    """The harvest should cover source help text examples."""
    assert len(HELP_COMMAND_FIXTURES) >= 20
    assert any(fixture.source == "CLI_DESCRIPTION" for fixture in HELP_COMMAND_FIXTURES)


@pytest.mark.parametrize(
    list(HelpCommandFixture._fields),
    HELP_COMMAND_FIXTURES,
    ids=[fixture.test_id for fixture in HELP_COMMAND_FIXTURES],
)
def test_help_commands_parse(test_id: str, source: str, command: str) -> None:
    """Commands shown in help text should match the real parser."""
    parser = create_parser(return_subparsers=False)
    stderr = io.StringIO()
    with contextlib.redirect_stderr(stderr):
        try:
            parser.parse_args(shlex.split(command)[1:])
        except SystemExit as exc:
            msg = f"{source} example {test_id} is rejected by argparse: {command}"
            raise AssertionError(msg) from exc
