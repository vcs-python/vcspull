"""Tests for configuration scope resolution, merging, and project trust."""

from __future__ import annotations

import os
import pathlib
import typing as t

import pytest

from vcspull import exc
from vcspull._internal import scopes

from .helpers import write_config


class WalkFixture(t.NamedTuple):
    """Fixture for the bounded upward walk."""

    test_id: str
    cwd: str
    ceilings: tuple[str, ...]
    expected: tuple[str, ...]


WALK_FIXTURES: list[WalkFixture] = [
    WalkFixture(
        test_id="stops-below-home",
        cwd="/home/u/work/api/src",
        ceilings=("/home/u",),
        expected=("/home/u/work", "/home/u/work/api", "/home/u/work/api/src"),
    ),
    WalkFixture(
        test_id="ceiling-itself-excluded",
        cwd="/home/u",
        ceilings=("/home/u",),
        expected=(),
    ),
    WalkFixture(
        test_id="outside-home-runs-to-root",
        cwd="/srv/app",
        ceilings=("/home/u",),
        expected=("/", "/srv", "/srv/app"),
    ),
    WalkFixture(
        test_id="custom-ceiling-overrides-home",
        cwd="/home/u/work/api",
        ceilings=("/home/u/work",),
        expected=("/home/u/work/api",),
    ),
    WalkFixture(
        test_id="no-ceiling-runs-to-root",
        cwd="/home/u/work",
        ceilings=(),
        expected=("/", "/home", "/home/u", "/home/u/work"),
    ),
]


@pytest.mark.parametrize(
    list(WalkFixture._fields),
    WALK_FIXTURES,
    ids=[fixture.test_id for fixture in WALK_FIXTURES],
)
def test_project_dirs_walk(
    test_id: str,
    cwd: str,
    ceilings: tuple[str, ...],
    expected: tuple[str, ...],
) -> None:
    """The walk yields ancestors outermost first and honours its ceiling."""
    result = scopes.project_dirs(
        pathlib.Path(cwd),
        ceilings=frozenset(pathlib.Path(ceiling) for ceiling in ceilings),
    )
    assert result == tuple(pathlib.Path(path) for path in expected)


def test_symlinked_home_stops_the_walk_and_loads_once(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A ``$HOME`` reached through a symlink is still the ceiling.

    Comparing unresolved paths let the walk run past ``$HOME``, which both
    re-read the home dotfile as a project config and exposed everything above
    it.
    """
    real_home = tmp_path / "real" / "u"
    (real_home / "work" / "proj").mkdir(parents=True)
    linked_home = tmp_path / "u"
    linked_home.symlink_to(real_home, target_is_directory=True)
    monkeypatch.setenv("HOME", str(linked_home))
    monkeypatch.delenv("VCSPULL_CEILING_PATHS", raising=False)

    write_config(
        real_home / ".vcspull.yaml",
        f"{tmp_path}/code/:\n  flask: git+https://example.com/flask.git\n",
    )

    for cwd in (real_home / "work" / "proj", linked_home / "work" / "proj"):
        sources = scopes.resolve_sources(cwd=cwd)
        assert [source.scope for source in sources] == ["user"]


def test_both_home_dotfiles_still_raise(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Owning ``~/.vcspull.yaml`` and ``~/.vcspull.json`` is still an error."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    write_config(home / ".vcspull.yaml", "{}\n")
    write_config(home / ".vcspull.json", "{}\n")

    with pytest.raises(exc.MultipleConfigWarning):
        scopes.resolve_sources(cwd=home / "work")


class ScopeDirFixture(t.NamedTuple):
    """Fixture for scope directories that must not crash the resolver."""

    test_id: str
    build: t.Callable[[pathlib.Path], None]
    expected: tuple[str, ...]


def _empty_config(directory: pathlib.Path) -> None:
    write_config(directory / "a.yaml", "# nothing here\n")


def _directory_named_like_a_config(directory: pathlib.Path) -> None:
    (directory / "a.yaml").mkdir()
    write_config(directory / "b.yaml", "{}\n")


def _unreadable(directory: pathlib.Path) -> None:
    write_config(directory / "a.yaml", "{}\n")
    directory.chmod(0o000)


SCOPE_DIR_FIXTURES: list[ScopeDirFixture] = [
    ScopeDirFixture(
        test_id="comment-only-file-is-listed",
        build=_empty_config,
        expected=("a.yaml",),
    ),
    ScopeDirFixture(
        test_id="directory-named-like-a-config-is-skipped",
        build=_directory_named_like_a_config,
        expected=("b.yaml",),
    ),
    ScopeDirFixture(
        test_id="unreadable-directory-yields-nothing",
        build=_unreadable,
        expected=(),
    ),
]


@pytest.mark.skipif(os.getuid() == 0, reason="root ignores directory permissions")
@pytest.mark.parametrize(
    list(ScopeDirFixture._fields),
    SCOPE_DIR_FIXTURES,
    ids=[fixture.test_id for fixture in SCOPE_DIR_FIXTURES],
)
def test_scope_directory_survives_hostile_contents(
    test_id: str,
    build: t.Callable[[pathlib.Path], None],
    expected: tuple[str, ...],
    tmp_path: pathlib.Path,
) -> None:
    """Listing a scope directory never raises, whatever is in it."""
    scope_dir = tmp_path / "scope"
    scope_dir.mkdir()
    build(scope_dir)
    try:
        assert (
            tuple(path.name for path in scopes._config_files_in(scope_dir)) == expected
        )
    finally:
        scope_dir.chmod(0o755)
