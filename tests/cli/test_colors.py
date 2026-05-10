"""Tests for vcspull CLI color mode resolution."""

from __future__ import annotations

import typing as t

from vcspull.cli._colors import ColorMode, Colors

if t.TYPE_CHECKING:
    from _pytest.monkeypatch import MonkeyPatch


def test_color_mode_always_overrides_no_color(monkeypatch: MonkeyPatch) -> None:
    """An explicit color request wins over the NO_COLOR environment default."""
    monkeypatch.setenv("NO_COLOR", "1")

    colors = Colors(ColorMode.ALWAYS)

    assert colors._enabled
    assert colors.info("repo") != "repo"


def test_color_mode_auto_respects_no_color(monkeypatch: MonkeyPatch) -> None:
    """Automatic color mode still respects NO_COLOR."""
    monkeypatch.setenv("NO_COLOR", "1")

    colors = Colors(ColorMode.AUTO)

    assert not colors._enabled
    assert colors.info("repo") == "repo"
