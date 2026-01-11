"""Tests for vcspull_console_lexer Pygments extension."""

from __future__ import annotations

import typing as t

import pytest
from pygments.token import Token
from vcspull_console_lexer import (  # type: ignore[import-not-found]
    VcspullConsoleLexer,
)

# --- Console session tests ---


class ConsoleSessionFixture(t.NamedTuple):
    """Test fixture for console session patterns."""

    test_id: str
    input_text: str
    expected_tokens: list[tuple[t.Any, str]]


CONSOLE_SESSION_FIXTURES: list[ConsoleSessionFixture] = [
    ConsoleSessionFixture(
        test_id="command_with_list_output",
        input_text="$ vcspull list\n• flask → ~/code/flask\n",
        expected_tokens=[
            (Token.Generic.Prompt, "$ "),
            (Token.Text, "vcspull"),  # BashLexer tokenizes as Text
            (Token.Comment, "•"),
            (Token.Name.Function, "flask"),
            (Token.Comment, "→"),
            (Token.Name.Variable, "~/code/flask"),
        ],
    ),
    ConsoleSessionFixture(
        test_id="command_with_status_output",
        input_text="$ vcspull status\n✓ flask: up to date\n",
        expected_tokens=[
            (Token.Generic.Prompt, "$ "),
            (Token.Text, "vcspull"),  # BashLexer tokenizes as Text
            (Token.Generic.Inserted, "✓"),
            (Token.Name.Function, "flask"),
            (Token.Punctuation, ":"),
            (Token.Generic.Inserted, "up to date"),
        ],
    ),
    ConsoleSessionFixture(
        test_id="command_with_sync_output",
        input_text="$ vcspull sync\n+ new-repo ~/code/new-repo\n",
        expected_tokens=[
            (Token.Generic.Prompt, "$ "),
            (Token.Text, "vcspull"),  # BashLexer tokenizes as Text
            (Token.Generic.Inserted, "+"),
            (Token.Name.Function, "new-repo"),
            (Token.Name.Variable, "~/code/new-repo"),
        ],
    ),
    ConsoleSessionFixture(
        test_id="tree_view_with_workspace_header",
        input_text="$ vcspull list --tree\n~/code/\n  • flask → ~/code/flask\n",
        expected_tokens=[
            (Token.Generic.Prompt, "$ "),
            (Token.Text, "vcspull"),  # BashLexer tokenizes as Text
            (Token.Generic.Subheading, "~/code/"),
            (Token.Comment, "•"),
            (Token.Name.Function, "flask"),
            (Token.Comment, "→"),
            (Token.Name.Variable, "~/code/flask"),
        ],
    ),
]


@pytest.mark.parametrize(
    ConsoleSessionFixture._fields,
    CONSOLE_SESSION_FIXTURES,
    ids=[f.test_id for f in CONSOLE_SESSION_FIXTURES],
)
def test_console_session(
    test_id: str,
    input_text: str,
    expected_tokens: list[tuple[t.Any, str]],
) -> None:
    """Test console session tokenization."""
    lexer = VcspullConsoleLexer()
    tokens = [(t, v) for t, v in lexer.get_tokens(input_text) if v.strip()]
    for expected_token, expected_value in expected_tokens:
        assert (expected_token, expected_value) in tokens, (
            f"Expected ({expected_token}, {expected_value!r}) not found in tokens"
        )


# --- Prompt handling tests ---


def test_prompt_detection() -> None:
    """Test that shell prompts are detected and tokenized."""
    lexer = VcspullConsoleLexer()
    text = "$ vcspull list\n• flask → ~/code/flask\n"
    tokens = list(lexer.get_tokens(text))

    # Check that prompt is detected
    prompt_tokens = [(t, v) for t, v in tokens if t == Token.Generic.Prompt]
    assert len(prompt_tokens) == 1
    assert prompt_tokens[0][1] == "$ "


def test_multiline_output() -> None:
    """Test multiline vcspull output tokenization."""
    text = """$ vcspull list --tree
~/work/python/
  • flask → ~/work/python/flask
  • requests → ~/work/python/requests
"""
    lexer = VcspullConsoleLexer()
    tokens = [(t, v) for t, v in lexer.get_tokens(text) if v.strip()]

    # Check key tokens
    assert (Token.Generic.Prompt, "$ ") in tokens
    assert (Token.Generic.Subheading, "~/work/python/") in tokens
    assert (Token.Name.Function, "flask") in tokens
    assert (Token.Name.Function, "requests") in tokens


def test_warning_and_error_output() -> None:
    """Test warning and error symbols in output."""
    text = """$ vcspull status
✓ good-repo: up to date
⚠ dirty-repo: dirty
✗ missing-repo: missing
"""
    lexer = VcspullConsoleLexer()
    tokens = [(t, v) for t, v in lexer.get_tokens(text) if v.strip()]

    # Check success
    assert (Token.Generic.Inserted, "✓") in tokens
    assert (Token.Generic.Inserted, "up to date") in tokens

    # Check warning
    assert (Token.Name.Exception, "⚠") in tokens
    assert (Token.Name.Exception, "dirty") in tokens

    # Check error
    assert (Token.Generic.Error, "✗") in tokens
    assert (Token.Generic.Error, "missing") in tokens


def test_command_only_no_output() -> None:
    """Test command without output."""
    text = "$ vcspull list django flask\n"
    lexer = VcspullConsoleLexer()
    tokens = [(t, v) for t, v in lexer.get_tokens(text) if v.strip()]

    # Should have prompt and command tokens
    assert (Token.Generic.Prompt, "$ ") in tokens
    assert (Token.Text, "vcspull") in tokens  # BashLexer tokenizes as Text
