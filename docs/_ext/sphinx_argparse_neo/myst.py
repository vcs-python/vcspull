"""MyST markdown support for argparse help text.

This module provides utilities for parsing help text that may contain
MyST markdown syntax, converting it to docutils nodes.
"""

from __future__ import annotations

import re
import typing as t

from docutils import nodes
from docutils.statemachine import StringList

if t.TYPE_CHECKING:
    from docutils.parsers.rst.states import RSTState


# Patterns that indicate MyST markdown
MYST_PATTERNS = [
    re.compile(r"^```"),  # Fenced code blocks
    re.compile(r"^\{[a-z]+\}"),  # MyST directives {note}, {warning}, etc.
    re.compile(r"\[.+\]\(.+\)"),  # Markdown links [text](url)
    re.compile(r"!\[.+\]\(.+\)"),  # Markdown images ![alt](url)
]

# Patterns that indicate RST
RST_PATTERNS = [
    re.compile(r"^\.\. "),  # RST directives
    re.compile(r":ref:`"),  # RST roles
    re.compile(r":doc:`"),  # RST doc role
    re.compile(r":class:`"),  # RST class role
    re.compile(r":func:`"),  # RST func role
    re.compile(r":meth:`"),  # RST method role
    re.compile(r":mod:`"),  # RST module role
]


def detect_format(text: str) -> str:
    r"""Detect whether text is RST or MyST format.

    Parameters
    ----------
    text : str
        The text to analyze.

    Returns
    -------
    str
        Either "rst" or "myst".

    Examples
    --------
    >>> detect_format("Plain text without markup")
    'rst'
    >>> detect_format("Check :ref:`docs` for more")
    'rst'
    >>> detect_format("See [the docs](https://example.com)")
    'myst'
    >>> detect_format("```python\\ncode\\n```")
    'myst'
    >>> detect_format("{note}\\nThis is important")
    'myst'
    """
    # Check for MyST patterns
    for pattern in MYST_PATTERNS:
        if pattern.search(text):
            return "myst"

    # Check for RST patterns
    for pattern in RST_PATTERNS:
        if pattern.search(text):
            return "rst"

    # Default to RST (simpler, and plain text is valid RST)
    return "rst"


def parse_myst(text: str) -> list[nodes.Node]:
    """Parse MyST markdown text to docutils nodes.

    This is a simplified parser that handles common MyST patterns.
    For full MyST support, use the myst-parser extension.

    Parameters
    ----------
    text : str
        MyST markdown text.

    Returns
    -------
    list[nodes.Node]
        Parsed docutils nodes.

    Examples
    --------
    >>> result = parse_myst("Simple text")
    >>> len(result)
    1
    >>> isinstance(result[0], nodes.paragraph)
    True
    """
    result_nodes: list[nodes.Node] = []

    # Split into paragraphs
    paragraphs = text.split("\n\n")

    for para_text in paragraphs:
        para_text = para_text.strip()
        if not para_text:
            continue

        # Check for fenced code blocks
        if para_text.startswith("```"):
            code_node = _parse_fenced_code(para_text)
            if code_node:
                result_nodes.append(code_node)
            continue

        # Parse as paragraph with inline markup
        para = nodes.paragraph()
        _parse_inline_myst(para_text, para)
        result_nodes.append(para)

    return result_nodes


def _parse_fenced_code(text: str) -> nodes.literal_block | None:
    r"""Parse a fenced code block.

    Parameters
    ----------
    text : str
        Text starting with ```.

    Returns
    -------
    nodes.literal_block | None
        Code block node, or None if parsing fails.

    Examples
    --------
    >>> node = _parse_fenced_code("```python\\nprint('hi')\\n```")
    >>> node["language"]
    'python'
    >>> "print" in node.astext()
    True
    """
    lines = text.split("\n")
    if len(lines) < 2:
        return None

    # First line: ```language
    first_line = lines[0].strip()
    if not first_line.startswith("```"):
        return None

    language = first_line[3:].strip() or "text"

    # Find closing ```
    code_lines: list[str] = []
    for line in lines[1:]:
        if line.strip() == "```":
            break
        code_lines.append(line)

    code_text = "\n".join(code_lines)
    node = nodes.literal_block(code_text, code_text)
    node["language"] = language
    return node


def _parse_inline_myst(text: str, parent: nodes.Element) -> None:
    """Parse inline MyST markup and add to parent node.

    Parameters
    ----------
    text : str
        Text with potential inline markup.
    parent : nodes.Element
        Parent node to add children to.
    """
    # Pattern for markdown links: [text](url)
    link_pattern = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")

    # Pattern for inline code: `code`
    code_pattern = re.compile(r"`([^`]+)`")

    # Pattern for bold: **text**
    bold_pattern = re.compile(r"\*\*([^*]+)\*\*")

    # Pattern for italic: *text* or _text_
    italic_pattern = re.compile(r"(?<!\*)\*([^*]+)\*(?!\*)|_([^_]+)_")

    # Simple approach: process patterns in order of precedence
    remaining = text

    while remaining:
        # Find the earliest match
        matches: list[tuple[int, int, str, nodes.Node | None]] = []

        # Check links
        link_match = link_pattern.search(remaining)
        if link_match:
            link_text, url = link_match.groups()
            ref = nodes.reference(link_text, link_text, refuri=url)
            matches.append((link_match.start(), link_match.end(), "link", ref))

        # Check inline code
        code_match = code_pattern.search(remaining)
        if code_match:
            code_text = code_match.group(1)
            literal = nodes.literal(code_text, code_text)
            matches.append((code_match.start(), code_match.end(), "code", literal))

        # Check bold
        bold_match = bold_pattern.search(remaining)
        if bold_match:
            bold_text = bold_match.group(1)
            strong = nodes.strong(bold_text, bold_text)
            matches.append((bold_match.start(), bold_match.end(), "bold", strong))

        # Check italic
        italic_match = italic_pattern.search(remaining)
        if italic_match:
            italic_text = italic_match.group(1) or italic_match.group(2)
            emphasis = nodes.emphasis(italic_text, italic_text)
            matches.append(
                (italic_match.start(), italic_match.end(), "italic", emphasis)
            )

        if not matches:
            # No more patterns, add remaining text
            if remaining:
                parent.append(nodes.Text(remaining))
            break

        # Find earliest match
        matches.sort(key=lambda x: x[0])
        start, end, _, node = matches[0]

        # Add text before match
        if start > 0:
            parent.append(nodes.Text(remaining[:start]))

        # Add matched node
        if node is not None:
            parent.append(node)

        # Continue with remaining text
        remaining = remaining[end:]


def parse_help_text(
    text: str,
    help_format: str,
    state: RSTState | None = None,
) -> list[nodes.Node]:
    """Parse help text to docutils nodes.

    Parameters
    ----------
    text : str
        The help text to parse.
    help_format : str
        The format: "rst", "myst", or "auto".
    state : RSTState | None
        RST state for parsing RST content.

    Returns
    -------
    list[nodes.Node]
        Parsed docutils nodes.

    Examples
    --------
    >>> nodes_list = parse_help_text("Simple help text", "auto")
    >>> len(nodes_list)
    1
    >>> parse_help_text("See [docs](url)", "auto")[0].__class__.__name__
    'paragraph'
    """
    if not text:
        return []

    # Determine format
    if help_format == "auto":
        help_format = detect_format(text)

    if help_format == "myst":
        return parse_myst(text)

    # RST format
    if state is not None:
        # Use the state machine to parse RST
        container = nodes.container()
        state.nested_parse(
            StringList(text.split("\n")),
            0,
            container,
        )
        return list(container.children)

    # No state machine, return simple paragraph
    para = nodes.paragraph(text=text)
    return [para]
