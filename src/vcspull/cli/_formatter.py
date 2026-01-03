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
}

OPTIONS_FLAG_ONLY = {
    "-h",
    "--help",
    "--write",
    "--all",
    "--recursive",
    "-r",
    "--yes",
    "-y",
    "--dry-run",
    "-n",
    "--json",
    "--ndjson",
    "--tree",
    "--detailed",
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
}


class VcspullHelpFormatter(argparse.RawDescriptionHelpFormatter):
    """Render description blocks while colorizing example sections when possible."""

    def _fill_text(self, text: str, width: int, indent: str) -> str:
        theme = getattr(self, "_theme", None)
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
        theme: t.Any,
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
