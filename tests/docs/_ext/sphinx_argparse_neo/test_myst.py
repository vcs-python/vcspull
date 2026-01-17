"""Tests for sphinx_argparse_neo.myst module."""

from __future__ import annotations

import typing as t

import pytest
from docutils import nodes
from sphinx_argparse_neo.myst import (
    _parse_fenced_code,
    _parse_inline_myst,
    detect_format,
    parse_help_text,
    parse_myst,
)

# --- detect_format tests ---


class DetectFormatFixture(t.NamedTuple):
    """Test fixture for detect_format function."""

    test_id: str
    text: str
    expected: str


DETECT_FORMAT_FIXTURES: list[DetectFormatFixture] = [
    DetectFormatFixture(
        test_id="plain_text",
        text="Plain text without markup",
        expected="rst",
    ),
    DetectFormatFixture(
        test_id="rst_ref_role",
        text="Check :ref:`docs` for more",
        expected="rst",
    ),
    DetectFormatFixture(
        test_id="rst_doc_role",
        text="See :doc:`guide` for details",
        expected="rst",
    ),
    DetectFormatFixture(
        test_id="rst_class_role",
        text="Use :class:`MyClass` instead",
        expected="rst",
    ),
    DetectFormatFixture(
        test_id="rst_func_role",
        text="Call :func:`my_function`",
        expected="rst",
    ),
    DetectFormatFixture(
        test_id="rst_directive",
        text=".. note:: This is important",
        expected="rst",
    ),
    DetectFormatFixture(
        test_id="myst_link",
        text="See [the docs](https://example.com)",
        expected="myst",
    ),
    DetectFormatFixture(
        test_id="myst_fenced_code",
        text="```python\ncode\n```",
        expected="myst",
    ),
    DetectFormatFixture(
        test_id="myst_directive",
        text="{note}\nThis is important",
        expected="myst",
    ),
    DetectFormatFixture(
        test_id="myst_image",
        text="![alt text](image.png)",
        expected="myst",
    ),
    DetectFormatFixture(
        test_id="empty_string",
        text="",
        expected="rst",
    ),
]


@pytest.mark.parametrize(
    DetectFormatFixture._fields,
    DETECT_FORMAT_FIXTURES,
    ids=[f.test_id for f in DETECT_FORMAT_FIXTURES],
)
def test_detect_format(test_id: str, text: str, expected: str) -> None:
    """Test format detection."""
    assert detect_format(text) == expected


# --- _parse_fenced_code tests ---


def test_parse_fenced_code_python() -> None:
    """Test parsing Python fenced code block."""
    text = "```python\nprint('hello')\n```"
    node = _parse_fenced_code(text)

    assert node is not None
    assert isinstance(node, nodes.literal_block)
    assert node["language"] == "python"
    assert "print" in node.astext()


def test_parse_fenced_code_no_language() -> None:
    """Test parsing fenced code block without language."""
    text = "```\nsome code\n```"
    node = _parse_fenced_code(text)

    assert node is not None
    assert node["language"] == "text"


def test_parse_fenced_code_multiline() -> None:
    """Test parsing multiline fenced code."""
    text = "```bash\necho 'line1'\necho 'line2'\n```"
    node = _parse_fenced_code(text)

    assert node is not None
    assert "line1" in node.astext()
    assert "line2" in node.astext()


def test_parse_fenced_code_invalid() -> None:
    """Test parsing invalid fenced code."""
    text = "not a code block"
    node = _parse_fenced_code(text)

    assert node is None


def test_parse_fenced_code_single_line() -> None:
    """Test parsing single line (no closing fence)."""
    text = "```"
    node = _parse_fenced_code(text)

    assert node is None


# --- _parse_inline_myst tests ---


def test_parse_inline_myst_plain_text() -> None:
    """Test parsing plain text."""
    parent = nodes.paragraph()
    _parse_inline_myst("Plain text", parent)

    assert len(parent.children) == 1
    assert isinstance(parent.children[0], nodes.Text)
    assert parent.astext() == "Plain text"


def test_parse_inline_myst_link() -> None:
    """Test parsing markdown link."""
    parent = nodes.paragraph()
    _parse_inline_myst("See [docs](https://example.com)", parent)

    # Should have text + reference
    refs = [c for c in parent.children if isinstance(c, nodes.reference)]
    assert len(refs) == 1
    assert refs[0]["refuri"] == "https://example.com"
    assert refs[0].astext() == "docs"


def test_parse_inline_myst_code() -> None:
    """Test parsing inline code."""
    parent = nodes.paragraph()
    _parse_inline_myst("Use `code` here", parent)

    literals = [c for c in parent.children if isinstance(c, nodes.literal)]
    assert len(literals) == 1
    assert literals[0].astext() == "code"


def test_parse_inline_myst_bold() -> None:
    """Test parsing bold text."""
    parent = nodes.paragraph()
    _parse_inline_myst("This is **bold** text", parent)

    strong = [c for c in parent.children if isinstance(c, nodes.strong)]
    assert len(strong) == 1
    assert strong[0].astext() == "bold"


def test_parse_inline_myst_italic() -> None:
    """Test parsing italic text with asterisks."""
    parent = nodes.paragraph()
    _parse_inline_myst("This is *italic* text", parent)

    emphasis = [c for c in parent.children if isinstance(c, nodes.emphasis)]
    assert len(emphasis) == 1
    assert emphasis[0].astext() == "italic"


def test_parse_inline_myst_multiple_patterns() -> None:
    """Test parsing text with multiple inline patterns."""
    parent = nodes.paragraph()
    _parse_inline_myst("Use `code` and [link](url) here", parent)

    literals = [c for c in parent.children if isinstance(c, nodes.literal)]
    refs = [c for c in parent.children if isinstance(c, nodes.reference)]

    assert len(literals) == 1
    assert len(refs) == 1


# --- parse_myst tests ---


def test_parse_myst_simple_paragraph() -> None:
    """Test parsing simple paragraph."""
    result = parse_myst("Simple text")

    assert len(result) == 1
    assert isinstance(result[0], nodes.paragraph)


def test_parse_myst_multiple_paragraphs() -> None:
    """Test parsing multiple paragraphs."""
    result = parse_myst("Para 1\n\nPara 2")

    assert len(result) == 2
    assert all(isinstance(n, nodes.paragraph) for n in result)


def test_parse_myst_fenced_code() -> None:
    """Test parsing paragraph with fenced code."""
    result = parse_myst("```python\ncode\n```")

    assert len(result) == 1
    assert isinstance(result[0], nodes.literal_block)


def test_parse_myst_mixed_content() -> None:
    """Test parsing mixed content."""
    result = parse_myst("Intro text\n\n```python\ncode\n```\n\nConclusion")

    assert len(result) == 3
    assert isinstance(result[0], nodes.paragraph)
    assert isinstance(result[1], nodes.literal_block)
    assert isinstance(result[2], nodes.paragraph)


def test_parse_myst_empty_string() -> None:
    """Test parsing empty string."""
    result = parse_myst("")

    assert result == []


def test_parse_myst_whitespace_only() -> None:
    """Test parsing whitespace-only string."""
    result = parse_myst("   \n\n   ")

    assert result == []


# --- parse_help_text tests ---


def test_parse_help_text_auto_rst() -> None:
    """Test auto-detecting RST format."""
    result = parse_help_text("See :ref:`docs` for more", "auto")

    assert len(result) >= 1


def test_parse_help_text_auto_myst() -> None:
    """Test auto-detecting MyST format."""
    result = parse_help_text("See [docs](url) for more", "auto")

    assert len(result) >= 1


def test_parse_help_text_explicit_rst() -> None:
    """Test explicit RST format."""
    result = parse_help_text("Plain text", "rst")

    assert len(result) == 1
    assert isinstance(result[0], nodes.paragraph)


def test_parse_help_text_explicit_myst() -> None:
    """Test explicit MyST format."""
    result = parse_help_text("**bold** text", "myst")

    assert len(result) == 1
    # Should parse as MyST with bold
    para = result[0]
    strong = [c for c in para.children if isinstance(c, nodes.strong)]
    assert len(strong) == 1


def test_parse_help_text_empty() -> None:
    """Test parsing empty text."""
    result = parse_help_text("", "auto")

    assert result == []


def test_parse_help_text_none_format() -> None:
    """Test with None state (falls back to simple paragraph)."""
    result = parse_help_text("Test text", "rst", state=None)

    assert len(result) == 1
    assert isinstance(result[0], nodes.paragraph)


# --- Edge cases ---


def test_detect_format_myst_link_in_middle() -> None:
    """Test detecting MyST format when link is in middle of text."""
    text = "For details, see [the documentation](https://docs.example.com) here."
    assert detect_format(text) == "myst"


def test_detect_format_rst_role_in_middle() -> None:
    """Test detecting RST format when role is in middle of text."""
    text = "For details, see :doc:`guide` for more information."
    assert detect_format(text) == "rst"


def test_parse_myst_consecutive_code_blocks() -> None:
    """Test parsing consecutive code blocks."""
    text = "```python\ncode1\n```\n\n```bash\ncode2\n```"
    result = parse_myst(text)

    assert len(result) == 2
    assert all(isinstance(n, nodes.literal_block) for n in result)


def test_parse_myst_link_with_special_chars() -> None:
    """Test parsing link with special characters in URL."""
    parent = nodes.paragraph()
    _parse_inline_myst("[link](https://example.com/path?query=1&other=2)", parent)

    refs = [c for c in parent.children if isinstance(c, nodes.reference)]
    assert len(refs) == 1
    assert refs[0]["refuri"] == "https://example.com/path?query=1&other=2"


def test_parse_myst_nested_formatting() -> None:
    """Test that bold inside code doesn't interfere."""
    parent = nodes.paragraph()
    _parse_inline_myst("Use `**not bold**` for literal", parent)

    # The **not bold** should be inside the literal, not processed as bold
    literals = [c for c in parent.children if isinstance(c, nodes.literal)]
    assert len(literals) == 1
    assert "**not bold**" in literals[0].astext()
