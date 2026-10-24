"""Custom help formatter used by vcspull CLI."""

from __future__ import annotations

import argparse
import re
import typing as t

OPTIONS_EXPECTING_VALUE = {
    "-f",
    "--file",
    "-w",
    "--workspace",
    "--workspace-root",
    "--log-level",
    "--path",
    "--color",
    "--field",
    "--max-concurrent",
    "--name",
    "--url",
    "--pin",
    "--depth",
    "--region",
    "--profile",
    "--token",
    "-m",
    "--mode",
    "-l",
    "--language",
    "--topics",
    "--min-stars",
    "--limit",
}

OPTIONS_FLAG_ONLY = {
    "-h",
    "--help",
    "--write",
    "--all",
    "-a",
    "--recursive",
    "-r",
    "--yes",
    "-y",
    "--shallow",
    "--dry-run",
    "-n",
    "--json",
    "--ndjson",
    "--tree",
    "--detailed",
    "-d",
    "-i",
    "--ignore-case",
    "-S",
    "--smart-case",
    "-F",
    "--fixed-strings",
    "--word-regexp",
    "-v",
    "--invert-match",
    "--any",
    "--exit-on-error",
    "-x",
    "--fetch",
    "--long",
    "--offline",
    "--relative-paths",
    "--show-unchanged",
    "--summary-only",
    "--version",
    "-V",
    "--no-concurrent",
    "--sequential",
    "--no-merge",
    "--verbose",
    "--flatten-groups",
    "--archived",
    "--forks",
    "--https",
}


class _HelpTheme(t.Protocol):
    """Protocol describing the argparse color theme.

    Python 3.14+ exposes ``_colorize.get_theme().argparse`` as ``_theme`` on
    ``HelpFormatter`` instances (an attribute on 3.14, a read-only property on
    3.15).  This protocol documents the attributes consumed by
    :meth:`VcspullHelpFormatter._fill_text` and
    :meth:`VcspullHelpFormatter._colorize_example_line`.
    """

    heading: str
    reset: str
    label: str
    long_option: str
    short_option: str
    prog: str
    action: str


class VcspullHelpFormatter(argparse.RawDescriptionHelpFormatter):
    """Extend argparse help colorization to example command sections.

    Python 3.14+ natively colorizes usage and option groups via
    ``_set_color()`` / ``_colorize.get_theme().argparse``.  This
    formatter reads the same theme to additionally colorize the
    "examples:" blocks in description text, applying distinct colors to
    program names, subcommands, long/short options, and option values.
    It only reads ``_theme``: argparse owns that name.

    Below Python 3.14 there is no theme, and ``_fill_text`` falls through
    to the base class unchanged.  With ``NO_COLOR`` set, argparse's theme
    holds empty strings, so examples come out plain.
    """

    def _example_theme(self) -> _HelpTheme | None:
        """Return argparse's help theme, or None below Python 3.14.

        Examples
        --------
        >>> import sys
        >>> theme = VcspullHelpFormatter("vcspull")._example_theme()
        >>> (theme is None) == (sys.version_info < (3, 14))
        True
        """
        return t.cast("_HelpTheme | None", getattr(self, "_theme", None))

    def _fill_text(self, text: str, width: int, indent: str) -> str:
        theme = self._example_theme()
        if not text or theme is None:
            return super()._fill_text(text, width, indent)

        lines = text.splitlines(keepends=True)
        formatted_lines: list[str] = []
        in_examples_block = False
        expect_value = False

        for line in lines:
            if line.strip() == "":
                in_examples_block = False
                expect_value = False
                formatted_lines.append(f"{indent}{line}")
                continue

            has_newline = line.endswith("\n")
            stripped_line = line.rstrip("\n")
            leading_length = len(stripped_line) - len(stripped_line.lstrip(" "))
            leading = stripped_line[:leading_length]
            content = stripped_line[leading_length:]
            content_lower = content.lower()
            is_section_heading = (
                content_lower.endswith("examples:") and content_lower != "examples:"
            )

            if is_section_heading or content_lower == "examples:":
                formatted_content = f"{theme.heading}{content}{theme.reset}"
                in_examples_block = True
                expect_value = False
            elif in_examples_block:
                colored_content = self._colorize_example_line(
                    content,
                    theme=theme,
                    expect_value=expect_value,
                )
                expect_value = colored_content.expect_value
                formatted_content = colored_content.text
            else:
                formatted_content = stripped_line

            newline = "\n" if has_newline else ""
            formatted_lines.append(f"{indent}{leading}{formatted_content}{newline}")

        return "".join(formatted_lines)

    class _ColorizedLine(t.NamedTuple):
        text: str
        expect_value: bool

    def _colorize_example_line(
        self,
        content: str,
        *,
        theme: _HelpTheme,
        expect_value: bool,
    ) -> _ColorizedLine:
        parts: list[str] = []
        expecting_value = expect_value
        first_token = True
        colored_subcommand = False

        for match in re.finditer(r"\s+|\S+", content):
            token = match.group()
            if token.isspace():
                parts.append(token)
                continue

            if expecting_value:
                color = theme.label
                expecting_value = False
            elif token.startswith("--"):
                color = theme.long_option
                expecting_value = (
                    token not in OPTIONS_FLAG_ONLY and token in OPTIONS_EXPECTING_VALUE
                )
            elif token.startswith("-"):
                color = theme.short_option
                expecting_value = (
                    token not in OPTIONS_FLAG_ONLY and token in OPTIONS_EXPECTING_VALUE
                )
            elif first_token:
                color = theme.prog
            elif not colored_subcommand:
                color = theme.action
                colored_subcommand = True
            else:
                color = None

            first_token = False

            if color:
                parts.append(f"{color}{token}{theme.reset}")
            else:
                parts.append(token)

        return self._ColorizedLine(text="".join(parts), expect_value=expecting_value)
