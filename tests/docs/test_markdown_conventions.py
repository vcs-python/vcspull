"""Regression tests for Markdown documentation conventions."""

from __future__ import annotations

import pathlib
import re
import shlex
import typing as t

import pytest

from vcspull.cli import create_parser

DOCS_ROOT = pathlib.Path(__file__).parents[2] / "docs"
FENCE_RE = re.compile(
    r"^```(?P<info>[^\n`]*)\n(?P<body>.*?)^```", re.MULTILINE | re.DOTALL
)


class MarkdownFileFixture(t.NamedTuple):
    """Fixture for Markdown files under docs."""

    test_id: str
    path: pathlib.Path


class DocsCommandFixture(t.NamedTuple):
    """Fixture for a harvested vcspull docs command."""

    test_id: str
    command: str


def _docs_markdown_files() -> list[MarkdownFileFixture]:
    """Return Markdown docs files, excluding generated Sphinx output."""
    paths = sorted(
        path
        for path in DOCS_ROOT.rglob("*.md")
        if "_build" not in path.relative_to(DOCS_ROOT).parts
    )
    return [
        MarkdownFileFixture(
            test_id=path.relative_to(DOCS_ROOT).as_posix(),
            path=path,
        )
        for path in paths
    ]


MARKDOWN_FILE_FIXTURES = _docs_markdown_files()


def _slug(text: str) -> str:
    """Return a readable test ID slug."""
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:90]


def _command_lines(source: str) -> t.Iterator[str]:
    """Yield shell command lines from a docs fence."""
    current: list[str] = []
    for line in source.splitlines():
        if line.startswith("$ "):
            if current:
                yield " ".join(current)
            current = [line[2:].rstrip("\\").strip()]
            if not line.rstrip().endswith("\\"):
                yield " ".join(current)
                current = []
            continue
        if current and line.startswith(("    ", "\t")):
            current.append(line.rstrip("\\").strip())
            if not line.rstrip().endswith("\\"):
                yield " ".join(current)
                current = []
    if current:
        yield " ".join(current)


def _vcspull_command(command: str) -> str | None:
    """Return the vcspull portion of a shell command."""
    try:
        tokens = shlex.split(command)
    except ValueError as exc:
        msg = f"could not parse docs command {command!r}"
        raise AssertionError(msg) from exc
    if not tokens or tokens[0] != "vcspull":
        return None
    command_tokens: list[str] = []
    for token in tokens:
        if token in {"|", ">", ">>", "2>", "2>>"}:
            break
        command_tokens.append(token)
    return shlex.join(command_tokens)


def _docs_vcspull_commands() -> list[DocsCommandFixture]:
    """Return vcspull commands shown in Markdown docs examples."""
    commands: list[DocsCommandFixture] = []
    seen: set[str] = set()
    for fixture in MARKDOWN_FILE_FIXTURES:
        text = fixture.path.read_text()
        for match in FENCE_RE.finditer(text):
            info = match.group("info").strip().split(maxsplit=1)[0]
            if info not in {"console", "vcspull-console"}:
                continue
            for shell_command in _command_lines(match.group("body")):
                command = _vcspull_command(shell_command)
                if command is None or command in seen:
                    continue
                seen.add(command)
                commands.append(
                    DocsCommandFixture(
                        test_id=f"{fixture.test_id}:{_slug(command)}",
                        command=command,
                    ),
                )
    return commands


DOCS_COMMAND_FIXTURES = _docs_vcspull_commands()


@pytest.mark.parametrize(
    list(MarkdownFileFixture._fields),
    MARKDOWN_FILE_FIXTURES,
    ids=[fixture.test_id for fixture in MARKDOWN_FILE_FIXTURES],
)
def test_shell_commands_use_console_blocks(test_id: str, path: pathlib.Path) -> None:
    """Shell commands should use prompt-aware console blocks."""
    text = path.read_text()
    shell_fences: list[str] = []
    for match in FENCE_RE.finditer(text):
        info = match.group("info").strip().split(maxsplit=1)[0]
        if info in {"bash", "sh", "shell", "zsh"}:
            shell_fences.append(info)

    assert shell_fences == [], (
        f"{test_id} uses {shell_fences!r} fenced blocks for shell commands; "
        "use ```console with a $ prompt instead"
    )


@pytest.mark.parametrize(
    list(MarkdownFileFixture._fields),
    MARKDOWN_FILE_FIXTURES,
    ids=[fixture.test_id for fixture in MARKDOWN_FILE_FIXTURES],
)
def test_console_blocks_are_command_only(test_id: str, path: pathlib.Path) -> None:
    """Console blocks should not include command output."""
    text = path.read_text()
    output_lines: list[str] = []
    for match in FENCE_RE.finditer(text):
        info = match.group("info").strip().split(maxsplit=1)[0]
        if info != "console":
            continue
        for line in match.group("body").splitlines():
            if line.startswith(("$ ", "    ", "\t")) or not line:
                continue
            output_lines.append(line)

    assert output_lines == [], (
        f"{test_id} has output in a console fence: {output_lines!r}; "
        "use vcspull-console for command plus output or vcspull-output for output only"
    )


@pytest.mark.parametrize(
    list(DocsCommandFixture._fields),
    DOCS_COMMAND_FIXTURES,
    ids=[fixture.test_id for fixture in DOCS_COMMAND_FIXTURES],
)
def test_docs_vcspull_commands_parse(test_id: str, command: str) -> None:
    """Documentation vcspull command examples should match the real parser."""
    parser = create_parser(return_subparsers=False)
    try:
        parser.parse_args(shlex.split(command)[1:])
    except SystemExit as exc:
        msg = f"{test_id} contains a command that argparse rejects: {command}"
        raise AssertionError(msg) from exc
