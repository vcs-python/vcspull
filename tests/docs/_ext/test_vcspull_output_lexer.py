"""Tests for vcspull_output_lexer Pygments extension."""

from __future__ import annotations

import typing as t

import pytest
from pygments.token import Token
from vcspull_output_lexer import (  # type: ignore[import-not-found]
    VcspullOutputLexer,
    tokenize_output,
)

# --- List output tests ---


class ListOutputFixture(t.NamedTuple):
    """Test fixture for list output patterns."""

    test_id: str
    input_text: str
    expected_tokens: list[tuple[t.Any, str]]


LIST_OUTPUT_FIXTURES: list[ListOutputFixture] = [
    ListOutputFixture(
        test_id="basic_list_item",
        input_text="• flask → ~/code/flask",
        expected_tokens=[
            (Token.Comment, "•"),
            (Token.Name.Function, "flask"),
            (Token.Comment, "→"),
            (Token.Name.Variable, "~/code/flask"),
        ],
    ),
    ListOutputFixture(
        test_id="path_with_plus",
        input_text="• GeographicLib → ~/study/c++/GeographicLib",
        expected_tokens=[
            (Token.Comment, "•"),
            (Token.Name.Function, "GeographicLib"),
            (Token.Comment, "→"),
            (Token.Name.Variable, "~/study/c++/GeographicLib"),
        ],
    ),
    ListOutputFixture(
        test_id="repo_with_dots",
        input_text="• pytest-django → ~/code/pytest-django",
        expected_tokens=[
            (Token.Comment, "•"),
            (Token.Name.Function, "pytest-django"),
            (Token.Comment, "→"),
            (Token.Name.Variable, "~/code/pytest-django"),
        ],
    ),
]


@pytest.mark.parametrize(
    ListOutputFixture._fields,
    LIST_OUTPUT_FIXTURES,
    ids=[f.test_id for f in LIST_OUTPUT_FIXTURES],
)
def test_list_output(
    test_id: str,
    input_text: str,
    expected_tokens: list[tuple[t.Any, str]],
) -> None:
    """Test list command output tokenization."""
    lexer = VcspullOutputLexer()
    tokens = [(t, v) for t, v in lexer.get_tokens(input_text) if v.strip()]
    assert tokens == expected_tokens


# --- Status output tests ---


class StatusOutputFixture(t.NamedTuple):
    """Test fixture for status output patterns."""

    test_id: str
    input_text: str
    expected_tokens: list[tuple[t.Any, str]]


STATUS_OUTPUT_FIXTURES: list[StatusOutputFixture] = [
    StatusOutputFixture(
        test_id="success_up_to_date",
        input_text="✓ flask: up to date",
        expected_tokens=[
            (Token.Generic.Inserted, "✓"),
            (Token.Name.Function, "flask"),
            (Token.Punctuation, ":"),
            (Token.Generic.Inserted, "up to date"),
        ],
    ),
    StatusOutputFixture(
        test_id="error_missing",
        input_text="✗ missing-repo: missing",
        expected_tokens=[
            (Token.Generic.Error, "✗"),
            (Token.Name.Function, "missing-repo"),
            (Token.Punctuation, ":"),
            (Token.Generic.Error, "missing"),
        ],
    ),
    StatusOutputFixture(
        test_id="warning_dirty",
        input_text="⚠ dirty-repo: dirty",
        expected_tokens=[
            (Token.Name.Exception, "⚠"),
            (Token.Name.Function, "dirty-repo"),
            (Token.Punctuation, ":"),
            (Token.Name.Exception, "dirty"),
        ],
    ),
    StatusOutputFixture(
        test_id="warning_behind",
        input_text="⚠ behind-repo: behind by 5",
        expected_tokens=[
            (Token.Name.Exception, "⚠"),
            (Token.Name.Function, "behind-repo"),
            (Token.Punctuation, ":"),
            (Token.Name.Exception, "behind by 5"),
        ],
    ),
]


@pytest.mark.parametrize(
    StatusOutputFixture._fields,
    STATUS_OUTPUT_FIXTURES,
    ids=[f.test_id for f in STATUS_OUTPUT_FIXTURES],
)
def test_status_output(
    test_id: str,
    input_text: str,
    expected_tokens: list[tuple[t.Any, str]],
) -> None:
    """Test status command output tokenization."""
    lexer = VcspullOutputLexer()
    tokens = [(t, v) for t, v in lexer.get_tokens(input_text) if v.strip()]
    assert tokens == expected_tokens


# --- Sync output tests ---


class SyncOutputFixture(t.NamedTuple):
    """Test fixture for sync output patterns."""

    test_id: str
    input_text: str
    expected_tokens: list[tuple[t.Any, str]]


SYNC_OUTPUT_FIXTURES: list[SyncOutputFixture] = [
    SyncOutputFixture(
        test_id="clone_with_url",
        input_text="+ new-repo ~/code/new-repo git+https://github.com/user/repo",
        expected_tokens=[
            (Token.Generic.Inserted, "+"),
            (Token.Name.Function, "new-repo"),
            (Token.Name.Variable, "~/code/new-repo"),
            (Token.Name.Tag, "git+https://github.com/user/repo"),
        ],
    ),
    SyncOutputFixture(
        test_id="update_repo",
        input_text="~ old-repo ~/code/old-repo",
        expected_tokens=[
            (Token.Name.Exception, "~"),
            (Token.Name.Function, "old-repo"),
            (Token.Name.Variable, "~/code/old-repo"),
        ],
    ),
    SyncOutputFixture(
        test_id="unchanged_repo",
        input_text="✓ stable ~/code/stable",
        expected_tokens=[
            (Token.Generic.Inserted, "✓"),
            (Token.Name.Function, "stable"),
            (Token.Name.Variable, "~/code/stable"),
        ],
    ),
]


@pytest.mark.parametrize(
    SyncOutputFixture._fields,
    SYNC_OUTPUT_FIXTURES,
    ids=[f.test_id for f in SYNC_OUTPUT_FIXTURES],
)
def test_sync_output(
    test_id: str,
    input_text: str,
    expected_tokens: list[tuple[t.Any, str]],
) -> None:
    """Test sync command output tokenization."""
    lexer = VcspullOutputLexer()
    tokens = [(t, v) for t, v in lexer.get_tokens(input_text) if v.strip()]
    assert tokens == expected_tokens


# --- Summary output tests ---


class SummaryOutputFixture(t.NamedTuple):
    """Test fixture for summary output patterns."""

    test_id: str
    input_text: str
    expected_tokens: list[tuple[t.Any, str]]


SUMMARY_OUTPUT_FIXTURES: list[SummaryOutputFixture] = [
    SummaryOutputFixture(
        test_id="basic_summary",
        input_text="Summary: 10 repositories, 8 exist, 2 missing",
        expected_tokens=[
            (Token.Generic.Heading, "Summary:"),
            (Token.Literal.Number.Integer, "10"),
            (Token.Name.Label, "repositories"),
            (Token.Punctuation, ","),
            (Token.Literal.Number.Integer, "8"),
            (Token.Name.Label, "exist"),
            (Token.Punctuation, ","),
            (Token.Literal.Number.Integer, "2"),
            (Token.Name.Label, "missing"),
        ],
    ),
]


@pytest.mark.parametrize(
    SummaryOutputFixture._fields,
    SUMMARY_OUTPUT_FIXTURES,
    ids=[f.test_id for f in SUMMARY_OUTPUT_FIXTURES],
)
def test_summary_output(
    test_id: str,
    input_text: str,
    expected_tokens: list[tuple[t.Any, str]],
) -> None:
    """Test summary line tokenization."""
    lexer = VcspullOutputLexer()
    tokens = [(t, v) for t, v in lexer.get_tokens(input_text) if v.strip()]
    assert tokens == expected_tokens


# --- Workspace header tests ---


class WorkspaceHeaderFixture(t.NamedTuple):
    """Test fixture for workspace header patterns."""

    test_id: str
    input_text: str
    expected_tokens: list[tuple[t.Any, str]]


WORKSPACE_HEADER_FIXTURES: list[WorkspaceHeaderFixture] = [
    WorkspaceHeaderFixture(
        test_id="home_relative_path",
        input_text="~/work/python/",
        expected_tokens=[
            (Token.Generic.Subheading, "~/work/python/"),
        ],
    ),
    WorkspaceHeaderFixture(
        test_id="absolute_path",
        input_text="/home/user/code/",
        expected_tokens=[
            (Token.Generic.Subheading, "/home/user/code/"),
        ],
    ),
]


@pytest.mark.parametrize(
    WorkspaceHeaderFixture._fields,
    WORKSPACE_HEADER_FIXTURES,
    ids=[f.test_id for f in WORKSPACE_HEADER_FIXTURES],
)
def test_workspace_header(
    test_id: str,
    input_text: str,
    expected_tokens: list[tuple[t.Any, str]],
) -> None:
    """Test workspace header tokenization."""
    lexer = VcspullOutputLexer()
    tokens = [(t, v) for t, v in lexer.get_tokens(input_text) if v.strip()]
    assert tokens == expected_tokens


# --- Multiline tests ---


def test_multiline_list_output() -> None:
    """Test multiline list output with workspace header."""
    text = """~/work/python/
  • flask → ~/work/python/flask
  • requests → ~/work/python/requests"""

    lexer = VcspullOutputLexer()
    tokens = [(t, v) for t, v in lexer.get_tokens(text) if v.strip()]

    # Check key tokens are present
    assert (Token.Generic.Subheading, "~/work/python/") in tokens
    assert (Token.Name.Function, "flask") in tokens
    assert (Token.Name.Function, "requests") in tokens
    assert (Token.Name.Variable, "~/work/python/flask") in tokens
    assert (Token.Name.Variable, "~/work/python/requests") in tokens


def test_multiline_sync_output() -> None:
    """Test multiline sync plan output."""
    text = """~/work/python/
+ new-lib ~/work/python/new-lib git+https://github.com/user/new-lib
~ old-lib ~/work/python/old-lib
✓ stable-lib ~/work/python/stable-lib"""

    lexer = VcspullOutputLexer()
    tokens = [(t, v) for t, v in lexer.get_tokens(text) if v.strip()]

    # Check symbols
    assert (Token.Generic.Inserted, "+") in tokens
    assert (Token.Name.Exception, "~") in tokens
    assert (Token.Generic.Inserted, "✓") in tokens

    # Check repo names
    assert (Token.Name.Function, "new-lib") in tokens
    assert (Token.Name.Function, "old-lib") in tokens
    assert (Token.Name.Function, "stable-lib") in tokens


# --- tokenize_output helper tests ---


def test_tokenize_output_basic() -> None:
    """Test the tokenize_output helper function."""
    result = tokenize_output("• flask → ~/code/flask")
    assert result[0] == ("Token.Comment", "•")
    assert ("Token.Name.Function", "flask") in result
    assert ("Token.Comment", "→") in result
    assert ("Token.Name.Variable", "~/code/flask") in result


def test_tokenize_output_empty() -> None:
    """Test tokenize_output with empty string."""
    result = tokenize_output("")
    # Should only have a trailing newline token
    assert len(result) == 1
    assert result[0][0] == "Token.Text.Whitespace"


# --- URL and prompt tests ---


def test_url_in_parentheses() -> None:
    """Test plain HTTPS URLs in parentheses are tokenized correctly."""
    text = "  + pytest-docker (https://github.com/avast/pytest-docker)"
    lexer = VcspullOutputLexer()
    tokens = [(t, v) for t, v in lexer.get_tokens(text) if v.strip()]

    assert (Token.Generic.Inserted, "+") in tokens
    assert (Token.Name.Function, "pytest-docker") in tokens
    assert (Token.Punctuation, "(") in tokens
    assert (Token.Name.Tag, "https://github.com/avast/pytest-docker") in tokens
    assert (Token.Punctuation, ")") in tokens


def test_interactive_prompt() -> None:
    """Test interactive prompt [y/N] patterns."""
    text = "? Import this repository? [y/N]: y"
    lexer = VcspullOutputLexer()
    tokens = [(t, v) for t, v in lexer.get_tokens(text) if v.strip()]

    assert (Token.Generic.Prompt, "?") in tokens
    assert (Token.Comment, "[y/N]") in tokens


def test_vcspull_add_output() -> None:
    """Test full vcspull add output with all patterns."""
    text = """Found new repository to import:
  + pytest-docker (https://github.com/avast/pytest-docker)
  • workspace: ~/study/python/
? Import this repository? [y/N]: y"""

    lexer = VcspullOutputLexer()
    tokens = [(t, v) for t, v in lexer.get_tokens(text) if v.strip()]

    # Check key tokens
    assert (Token.Generic.Inserted, "+") in tokens
    assert (Token.Name.Function, "pytest-docker") in tokens
    assert (Token.Name.Tag, "https://github.com/avast/pytest-docker") in tokens
    assert (Token.Comment, "•") in tokens
    assert (Token.Generic.Heading, "workspace:") in tokens
    assert (Token.Generic.Prompt, "?") in tokens
    assert (Token.Comment, "[y/N]") in tokens
