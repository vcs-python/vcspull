"""Tests for sphinx_argparse_neo text processing utilities."""

from __future__ import annotations

import typing as t

import pytest
from sphinx_argparse_neo.utils import escape_rst_emphasis, strip_ansi

# --- strip_ansi tests ---


class StripAnsiFixture(t.NamedTuple):
    """Test fixture for strip_ansi function."""

    test_id: str
    input_text: str
    expected: str


STRIP_ANSI_FIXTURES: list[StripAnsiFixture] = [
    StripAnsiFixture(
        test_id="plain_text",
        input_text="hello",
        expected="hello",
    ),
    StripAnsiFixture(
        test_id="green_color",
        input_text="\033[32mgreen\033[0m",
        expected="green",
    ),
    StripAnsiFixture(
        test_id="bold_blue",
        input_text="\033[1;34mbold\033[0m",
        expected="bold",
    ),
    StripAnsiFixture(
        test_id="multiple_codes",
        input_text="\033[1m\033[32mtest\033[0m",
        expected="test",
    ),
    StripAnsiFixture(
        test_id="empty_string",
        input_text="",
        expected="",
    ),
    StripAnsiFixture(
        test_id="mixed_content",
        input_text="pre\033[31mred\033[0mpost",
        expected="preredpost",
    ),
    StripAnsiFixture(
        test_id="reset_only",
        input_text="\033[0m",
        expected="",
    ),
    StripAnsiFixture(
        test_id="sgr_params",
        input_text="\033[38;5;196mred256\033[0m",
        expected="red256",
    ),
]


@pytest.mark.parametrize(
    StripAnsiFixture._fields,
    STRIP_ANSI_FIXTURES,
    ids=[f.test_id for f in STRIP_ANSI_FIXTURES],
)
def test_strip_ansi(test_id: str, input_text: str, expected: str) -> None:
    """Test ANSI escape code stripping."""
    assert strip_ansi(input_text) == expected


# --- escape_rst_emphasis tests ---


class EscapeRstEmphasisFixture(t.NamedTuple):
    """Test fixture for escape_rst_emphasis function."""

    test_id: str
    input_text: str
    expected: str


ESCAPE_RST_EMPHASIS_FIXTURES: list[EscapeRstEmphasisFixture] = [
    EscapeRstEmphasisFixture(
        test_id="plain_text_unchanged",
        input_text="plain text",
        expected="plain text",
    ),
    EscapeRstEmphasisFixture(
        test_id="glob_pattern_escaped",
        input_text='vcspull list "django-*"',
        expected='vcspull list "django-\\*"',
    ),
    EscapeRstEmphasisFixture(
        test_id="multiple_glob_patterns",
        input_text='vcspull sync "flask-*" "django-*"',
        expected='vcspull sync "flask-\\*" "django-\\*"',
    ),
    EscapeRstEmphasisFixture(
        test_id="asterisk_at_end",
        input_text="pattern-*",
        expected="pattern-\\*",
    ),
    EscapeRstEmphasisFixture(
        test_id="already_escaped_unchanged",
        input_text="already-\\* escaped",
        expected="already-\\* escaped",
    ),
    EscapeRstEmphasisFixture(
        test_id="valid_emphasis_unchanged",
        input_text="*emphasis* is ok",
        expected="*emphasis* is ok",
    ),
    EscapeRstEmphasisFixture(
        test_id="strong_emphasis_unchanged",
        input_text="**strong** text",
        expected="**strong** text",
    ),
    EscapeRstEmphasisFixture(
        test_id="space_before_asterisk_unchanged",
        input_text="space * asterisk",
        expected="space * asterisk",
    ),
    EscapeRstEmphasisFixture(
        test_id="asterisk_after_dot_unchanged",
        input_text="regex.*pattern",
        expected="regex.*pattern",
    ),
    EscapeRstEmphasisFixture(
        test_id="single_asterisk_unchanged",
        input_text="vcspull sync '*'",
        expected="vcspull sync '*'",
    ),
    EscapeRstEmphasisFixture(
        test_id="empty_string",
        input_text="",
        expected="",
    ),
    EscapeRstEmphasisFixture(
        test_id="underscore_asterisk_unchanged",
        input_text="name_*pattern",
        expected="name_*pattern",
    ),
    EscapeRstEmphasisFixture(
        test_id="dash_asterisk_with_following_char",
        input_text="repo-*-suffix",
        expected="repo-\\*-suffix",
    ),
]


@pytest.mark.parametrize(
    EscapeRstEmphasisFixture._fields,
    ESCAPE_RST_EMPHASIS_FIXTURES,
    ids=[f.test_id for f in ESCAPE_RST_EMPHASIS_FIXTURES],
)
def test_escape_rst_emphasis(test_id: str, input_text: str, expected: str) -> None:
    """Test RST emphasis escaping for argparse patterns."""
    assert escape_rst_emphasis(input_text) == expected
