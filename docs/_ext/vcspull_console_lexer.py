"""Pygments lexer for vcspull CLI sessions (command + output).

This module provides a custom Pygments lexer for highlighting vcspull command
sessions, combining shell command highlighting with semantic output highlighting.
"""

from __future__ import annotations

import re

from pygments.lexer import Lexer, do_insertions, line_re  # type: ignore[attr-defined]
from pygments.lexers.shell import BashLexer
from pygments.token import Generic, Text

try:
    # When running as Sphinx extension (docs/_ext in path)
    from vcspull_output_lexer import (
        VcspullOutputLexer,  # type: ignore[import-not-found]
    )
except ImportError:
    # When running via pytest (relative import)
    from .vcspull_output_lexer import VcspullOutputLexer


class VcspullConsoleLexer(Lexer):
    r"""Lexer for vcspull CLI sessions with semantic output highlighting.

    Extends BashSessionLexer pattern but delegates output lines to
    VcspullOutputLexer for semantic coloring of vcspull command output.

    Examples
    --------
    Test prompt detection on a simple command line:

    >>> from pygments.token import Token
    >>> lexer = VcspullConsoleLexer()
    >>> tokens = list(lexer.get_tokens("$ vcspull list"))
    >>> any(t == Token.Generic.Prompt for t, v in tokens)
    True
    """

    name = "Vcspull Console"
    aliases = ["vcspull-console"]  # noqa: RUF012
    filenames: list[str] = []  # noqa: RUF012
    mimetypes = ["text/x-vcspull-console"]  # noqa: RUF012

    _venv = re.compile(r"^(\([^)]*\))(\s*)")
    _ps1rgx = re.compile(
        r"^((?:(?:\[.*?\])|(?:\(\S+\))?(?:| |sh\S*?|\w+\S+[@:]\S+(?:\s+\S+)"
        r"?|\[\S+[@:][^\n]+\].+))\s*[$#%]\s*)(.*\n?)"
    )
    _ps2 = "> "

    def get_tokens_unprocessed(  # type: ignore[no-untyped-def]
        self,
        text: str,
    ):
        """Tokenize text with shell commands and vcspull output.

        Parameters
        ----------
        text : str
            The text to tokenize.

        Yields
        ------
        tuple[int, TokenType, str]
            Tuples of (index, token_type, value).
        """
        innerlexer = BashLexer(**self.options)
        outputlexer = VcspullOutputLexer(**self.options)

        pos = 0
        curcode = ""
        insertions = []
        backslash_continuation = False

        for match in line_re.finditer(text):
            line = match.group()

            venv_match = self._venv.match(line)
            if venv_match:
                venv = venv_match.group(1)
                venv_whitespace = venv_match.group(2)
                insertions.append(
                    (len(curcode), [(0, Generic.Prompt.VirtualEnv, venv)])
                )
                if venv_whitespace:
                    insertions.append((len(curcode), [(0, Text, venv_whitespace)]))
                line = line[venv_match.end() :]

            m = self._ps1rgx.match(line)
            if m:
                if not insertions:
                    pos = match.start()

                insertions.append((len(curcode), [(0, Generic.Prompt, m.group(1))]))
                curcode += m.group(2)
                backslash_continuation = curcode.endswith("\\\n")
            elif backslash_continuation:
                if line.startswith(self._ps2):
                    insertions.append(
                        (len(curcode), [(0, Generic.Prompt, line[: len(self._ps2)])])
                    )
                    curcode += line[len(self._ps2) :]
                else:
                    curcode += line
                backslash_continuation = curcode.endswith("\\\n")
            else:
                if insertions:
                    toks = innerlexer.get_tokens_unprocessed(curcode)
                    for i, t, v in do_insertions(insertions, toks):
                        yield pos + i, t, v
                # Use VcspullOutputLexer for output lines
                for i, t, v in outputlexer.get_tokens_unprocessed(line):
                    yield match.start() + i, t, v
                insertions = []
                curcode = ""

        if insertions:
            for i, t, v in do_insertions(
                insertions, innerlexer.get_tokens_unprocessed(curcode)
            ):
                yield pos + i, t, v
