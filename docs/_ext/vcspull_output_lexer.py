"""Pygments lexer for vcspull CLI output.

This module provides a custom Pygments lexer for highlighting vcspull command
output (list, status, sync, search) with semantic colors matching the CLI.
"""

from __future__ import annotations

from pygments.lexer import RegexLexer, bygroups
from pygments.token import (
    Comment,
    Generic,
    Name,
    Number,
    Punctuation,
    Text,
    Whitespace,
)


class VcspullOutputLexer(RegexLexer):
    """Lexer for vcspull CLI output.

    Highlights vcspull command output including list, status, sync, and search
    results with semantic coloring.

    Token mapping to vcspull semantic colors:
    - SUCCESS (green): Generic.Inserted - checkmarks, "up to date", "synced"
    - WARNING (yellow): Name.Exception - warning symbols, "dirty", "behind"
    - ERROR (red): Generic.Error - error symbols, "missing", "error"
    - INFO (cyan): Name.Function - repository names
    - HIGHLIGHT (magenta): Generic.Subheading - workspace headers
    - MUTED (blue/gray): Comment - bullets, arrows, labels

    Examples
    --------
    >>> from pygments.token import Token
    >>> lexer = VcspullOutputLexer()
    >>> tokens = list(lexer.get_tokens("• flask → ~/code/flask"))
    >>> tokens[0]
    (Token.Comment, '•')
    >>> tokens[2]
    (Token.Name.Function, 'flask')
    """

    name = "vcspull Output"
    aliases = ["vcspull-output", "vcspull"]  # noqa: RUF012
    filenames: list[str] = []  # noqa: RUF012
    mimetypes = ["text/x-vcspull-output"]  # noqa: RUF012

    tokens = {  # noqa: RUF012
        "root": [
            # Newlines
            (r"\n", Whitespace),
            # Workspace header - path ending with / at start of line or after newline
            # Matched by looking for ~/path/ or /path/ pattern as a whole line
            (r"(~?/[-a-zA-Z0-9_.~/+]+/)(?=\s*$|\s*\n)", Generic.Subheading),
            # Success symbol with repo name (green) - for sync output like "✓ repo"
            (
                r"(✓)(\s+)([a-zA-Z][-a-zA-Z0-9_.]+)(?=\s+[~/]|\s*$)",
                bygroups(Generic.Inserted, Whitespace, Name.Function),  # type: ignore[no-untyped-call]
            ),
            # Success symbol standalone (green)
            (r"✓", Generic.Inserted),
            # Warning symbol with repo name (yellow)
            (
                r"(⚠)(\s+)([a-zA-Z][-a-zA-Z0-9_.]+)(?=\s+[~/]|:|\s*$)",
                bygroups(Name.Exception, Whitespace, Name.Function),  # type: ignore[no-untyped-call]
            ),
            # Warning symbol standalone (yellow)
            (r"⚠", Name.Exception),
            # Error symbol with repo name (red)
            (
                r"(✗)(\s+)([a-zA-Z][-a-zA-Z0-9_.]+)(?=\s+[~/]|:|\s*$)",
                bygroups(Generic.Error, Whitespace, Name.Function),  # type: ignore[no-untyped-call]
            ),
            # Error symbol standalone (red)
            (r"✗", Generic.Error),
            # Clone/add symbol with repo name (green)
            (
                r"(\+)(\s+)([a-zA-Z][-a-zA-Z0-9_.]+)",
                bygroups(Generic.Inserted, Whitespace, Name.Function),  # type: ignore[no-untyped-call]
            ),
            # Update/change symbol with repo name (yellow)
            (
                r"(~)(\s+)([a-zA-Z][-a-zA-Z0-9_.]+)",
                bygroups(Name.Exception, Whitespace, Name.Function),  # type: ignore[no-untyped-call]
            ),
            # Bullet (muted)
            (r"•", Comment),
            # Arrow (muted)
            (r"→", Comment),
            # Status messages - success (green) - must be at word boundary
            (r"\bup to date\b", Generic.Inserted),
            (r"\bsynced\b", Generic.Inserted),
            (r"\bexists?\b", Generic.Inserted),
            (r"\bahead by \d+\b", Generic.Inserted),
            # Status messages - warning (yellow)
            (r"\bdirty\b", Name.Exception),
            (r"\bbehind(?: by \d+)?\b", Name.Exception),
            (r"\bdiverged\b", Name.Exception),
            (r"\bnot a git repo\b", Name.Exception),
            # Status messages - error (red)
            (r"(?<=: )missing\b", Generic.Error),  # "missing" after colon
            (r"\berror\b", Generic.Error),
            (r"\bfailed\b", Generic.Error),
            # Labels (muted)
            (
                r"(Summary:|Progress:|Path:|Branch:|url:|workspace:|Ahead/Behind:)",
                Generic.Heading,
            ),
            # Git URLs
            (r"git\+https?://[^\s]+", Name.Tag),
            # Paths with ~/ - include + for c++ directories
            (r"~?/[-a-zA-Z0-9_.~/+]+(?![\w/+])", Name.Variable),
            # Repository names (identifiers followed by colon or arrow or space+path)
            # This is tricky - we want to highlight names in context
            (
                r"([a-zA-Z][-a-zA-Z0-9_.]+)(\s*)(→)",
                bygroups(Name.Function, Whitespace, Comment),  # type: ignore[no-untyped-call]
            ),
            (
                r"([a-zA-Z][-a-zA-Z0-9_.]+)(:)",
                bygroups(Name.Function, Punctuation),  # type: ignore[no-untyped-call]
            ),
            # Count labels in summaries
            (
                r"(\d+)(\s+)(repositories|repos|exist|missing|synced|failed|blocked|errors)",
                bygroups(Number.Integer, Whitespace, Name.Label),  # type: ignore[no-untyped-call]
            ),
            # Numbers
            (r"\d+", Number.Integer),
            # Whitespace
            (r"[ \t]+", Whitespace),
            # Punctuation
            (r"[,():]", Punctuation),
            # Fallback - any other text
            (r"[^\s•→✓✗⚠+~:,()]+", Text),
        ],
    }


def tokenize_output(text: str) -> list[tuple[str, str]]:
    """Tokenize vcspull output and return list of (token_type, value) tuples.

    Parameters
    ----------
    text : str
        vcspull CLI output text to tokenize.

    Returns
    -------
    list[tuple[str, str]]
        List of (token_type_name, text_value) tuples.

    Examples
    --------
    >>> result = tokenize_output("• flask → ~/code/flask")
    >>> result[0]
    ('Token.Comment', '•')
    >>> result[2]
    ('Token.Name.Function', 'flask')
    """
    lexer = VcspullOutputLexer()
    return [
        (str(tok_type), tok_value) for tok_type, tok_value in lexer.get_tokens(text)
    ]
