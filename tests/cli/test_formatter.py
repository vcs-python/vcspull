"""Tests for VcspullHelpFormatter colorization."""

from __future__ import annotations

import types
import typing as t

import pytest

from vcspull.cli._formatter import VcspullHelpFormatter

if t.TYPE_CHECKING:
    from vcspull.cli._formatter import _HelpTheme


def _make_theme() -> types.SimpleNamespace:
    """Build a mock theme with short marker strings for easy assertions."""
    return types.SimpleNamespace(
        heading="<H>",
        reset="<R>",
        label="<L>",
        long_option="<LO>",
        short_option="<SO>",
        prog="<P>",
        action="<A>",
    )


def _make_formatter(
    *,
    theme: types.SimpleNamespace | None,
) -> VcspullHelpFormatter:
    """Create a formatter whose examples use ``theme`` on every Python.

    ``_theme`` belongs to argparse (a read-only property on 3.15), so the
    mock is supplied through :meth:`VcspullHelpFormatter._example_theme`.
    """

    class _PinnedFormatter(VcspullHelpFormatter):
        def _example_theme(self) -> _HelpTheme | None:
            return t.cast("_HelpTheme | None", theme)

    return _PinnedFormatter(prog="vcspull")


# ------------------------------------------------------------------
# _fill_text tests
# ------------------------------------------------------------------


def test_fill_text_no_theme() -> None:
    """Without a theme, _fill_text delegates to super() unmodified."""
    # On Python 3.14+ argparse always supplies a theme (with empty strings
    # when NO_COLOR is set); None exercises the pre-3.14 path.
    fmt = _make_formatter(theme=None)

    text = "examples:\n  vcspull sync --dry-run\n"
    result = fmt._fill_text(text, width=80, indent="")
    # No marker strings should appear (we didn't inject our mock theme)
    assert "<H>" not in result
    assert "<R>" not in result
    assert "<P>" not in result


def test_fill_text_with_theme() -> None:
    """With a theme, example sections are colorized."""
    theme = _make_theme()
    fmt = _make_formatter(theme=theme)

    text = "examples:\n  vcspull sync --dry-run\n"
    result = fmt._fill_text(text, width=80, indent="")

    # "examples:" heading is colorized
    assert "<H>examples:<R>" in result
    # Program name is colorized
    assert "<P>vcspull<R>" in result
    # Subcommand is colorized
    assert "<A>sync<R>" in result
    # Long option (flag-only) is colorized
    assert "<LO>--dry-run<R>" in result


def test_fill_text_non_example_text() -> None:
    """Non-example description text is not colorized."""
    theme = _make_theme()
    fmt = _make_formatter(theme=theme)

    text = "This is a regular description.\nNo examples here.\n"
    result = fmt._fill_text(text, width=80, indent="")

    assert "<H>" not in result
    assert "<P>" not in result
    assert "<A>" not in result
    assert "<LO>" not in result
    assert "<SO>" not in result
    assert "<L>" not in result


def test_fill_text_section_heading_variant() -> None:
    """Section headings like 'sync examples:' are also colorized."""
    theme = _make_theme()
    fmt = _make_formatter(theme=theme)

    text = "sync examples:\n  vcspull sync myrepo\n"
    result = fmt._fill_text(text, width=80, indent="")

    assert "<H>sync examples:<R>" in result
    assert "<P>vcspull<R>" in result


# ------------------------------------------------------------------
# _colorize_example_line tests (parameterized)
# ------------------------------------------------------------------


class ColorizeLineFixture(t.NamedTuple):
    """Fixture for parameterized _colorize_example_line tests."""

    test_id: str
    input_line: str
    expected_fragments: list[str]
    unexpected_fragments: list[str]


COLORIZE_LINE_FIXTURES: list[ColorizeLineFixture] = [
    ColorizeLineFixture(
        test_id="prog-only",
        input_line="vcspull",
        expected_fragments=["<P>vcspull<R>"],
        unexpected_fragments=["<A>"],
    ),
    ColorizeLineFixture(
        test_id="prog-and-subcommand",
        input_line="vcspull sync",
        expected_fragments=["<P>vcspull<R>", "<A>sync<R>"],
        unexpected_fragments=[],
    ),
    ColorizeLineFixture(
        test_id="long-option-flag",
        input_line="vcspull sync --dry-run",
        expected_fragments=["<LO>--dry-run<R>"],
        unexpected_fragments=["<L>--dry-run"],
    ),
    ColorizeLineFixture(
        test_id="long-option-with-value",
        input_line="vcspull sync --file myconfig.yaml",
        expected_fragments=["<LO>--file<R>", "<L>myconfig.yaml<R>"],
        unexpected_fragments=[],
    ),
    ColorizeLineFixture(
        test_id="short-option-flag",
        input_line="vcspull sync -n",
        expected_fragments=["<SO>-n<R>"],
        unexpected_fragments=["<L>-n"],
    ),
    ColorizeLineFixture(
        test_id="short-option-with-value",
        input_line="vcspull sync -f myconfig.yaml",
        expected_fragments=["<SO>-f<R>", "<L>myconfig.yaml<R>"],
        unexpected_fragments=[],
    ),
    ColorizeLineFixture(
        test_id="bare-argument-no-color",
        input_line="vcspull sync myrepo",
        expected_fragments=["<P>vcspull<R>", "<A>sync<R>", "myrepo"],
        unexpected_fragments=["<P>myrepo", "<A>myrepo", "<LO>myrepo", "<SO>myrepo"],
    ),
    ColorizeLineFixture(
        test_id="exit-on-error-flag",
        input_line="vcspull sync --exit-on-error myrepo",
        expected_fragments=["<LO>--exit-on-error<R>", "myrepo"],
        unexpected_fragments=["<L>myrepo"],
    ),
    ColorizeLineFixture(
        test_id="name-expects-value",
        input_line="vcspull add --name mylib",
        expected_fragments=["<LO>--name<R>", "<L>mylib<R>"],
        unexpected_fragments=[],
    ),
    ColorizeLineFixture(
        test_id="max-concurrent-expects-value",
        input_line="vcspull status --max-concurrent 4",
        expected_fragments=["<LO>--max-concurrent<R>", "<L>4<R>"],
        unexpected_fragments=[],
    ),
]


@pytest.mark.parametrize(
    list(ColorizeLineFixture._fields),
    COLORIZE_LINE_FIXTURES,
    ids=[fixture.test_id for fixture in COLORIZE_LINE_FIXTURES],
)
def test_colorize_example_line(
    test_id: str,
    input_line: str,
    expected_fragments: list[str],
    unexpected_fragments: list[str],
) -> None:
    """Token classification in _colorize_example_line applies correct colors."""
    del test_id
    theme = _make_theme()
    fmt = _make_formatter(theme=theme)

    result = fmt._colorize_example_line(
        content=input_line, theme=theme, expect_value=False
    )

    for fragment in expected_fragments:
        assert fragment in result.text, f"Expected {fragment!r} in {result.text!r}"
    for fragment in unexpected_fragments:
        assert fragment not in result.text, (
            f"Unexpected {fragment!r} found in {result.text!r}"
        )
