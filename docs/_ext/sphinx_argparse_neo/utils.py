"""Text processing utilities for sphinx_argparse_neo.

This module provides utilities for cleaning argparse output before rendering:
- strip_ansi: Remove ANSI escape codes (for when FORCE_COLOR is set)
- escape_rst_emphasis: Escape asterisks that would trigger RST warnings

These utilities can be enabled/disabled via Sphinx config options:
- argparse_strip_ansi (default: True)
- argparse_escape_rst_emphasis (default: True)
"""

from __future__ import annotations

import re

# ANSI escape code pattern - matches CSI sequences like \033[32m, \033[1;34m, etc.
_ANSI_RE = re.compile(r"\033\[[;?0-9]*[a-zA-Z]")

# Match asterisks that would trigger RST emphasis (preceded by delimiter like
# - or space) but NOT asterisks already escaped or in code/literal contexts.
# This catches patterns like "django-*" which would cause
# "Inline emphasis start-string without end-string" warnings.
_RST_EMPHASIS_RE = re.compile(r"(?<=[^\s\\])-\*(?=[^\s*]|$)")


def strip_ansi(text: str) -> str:
    r"""Remove ANSI escape codes from text.

    When FORCE_COLOR is set in the environment, argparse may include ANSI
    escape codes in its output. This function removes them so the output
    renders correctly in Sphinx documentation.

    Parameters
    ----------
    text : str
        Text potentially containing ANSI codes.

    Returns
    -------
    str
        Text with ANSI codes removed.

    Examples
    --------
    >>> strip_ansi("plain text")
    'plain text'
    >>> strip_ansi("\033[32mgreen\033[0m")
    'green'
    >>> strip_ansi("\033[1;34mbold blue\033[0m")
    'bold blue'
    """
    return _ANSI_RE.sub("", text)


def escape_rst_emphasis(text: str) -> str:
    r"""Escape asterisks that would trigger RST inline emphasis.

    In reStructuredText, ``*text*`` creates emphasis. When argparse help text
    contains patterns like ``django-*``, the dash (a delimiter character) followed
    by asterisk triggers emphasis detection, causing warnings like:
    "Inline emphasis start-string without end-string."

    This function escapes such asterisks with a backslash so they render literally.

    Parameters
    ----------
    text : str
        Text potentially containing problematic asterisks.

    Returns
    -------
    str
        Text with asterisks escaped where needed.

    Examples
    --------
    >>> escape_rst_emphasis('vcspull list "django-*"')
    'vcspull list "django-\\*"'
    >>> escape_rst_emphasis("plain text")
    'plain text'
    >>> escape_rst_emphasis("already \\* escaped")
    'already \\* escaped'
    >>> escape_rst_emphasis("*emphasis* is ok")
    '*emphasis* is ok'
    """
    return _RST_EMPHASIS_RE.sub(r"-\*", text)
