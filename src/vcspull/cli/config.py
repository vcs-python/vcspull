"""Configuration scope introspection and project trust for vcspull."""

from __future__ import annotations

import logging
import os
import pathlib
import typing as t

from vcspull._internal import scopes
from vcspull._internal.config_reader import DuplicateAwareConfigReader
from vcspull._internal.private_path import PrivatePath
from vcspull.config import extract_repos, source_escapes

if t.TYPE_CHECKING:
    import argparse

    from vcspull.types import RawConfigDict

log = logging.getLogger(__name__)


def create_config_subparser(
    parser: argparse.ArgumentParser,
    scope_parent: argparse.ArgumentParser,
) -> None:
    """Create ``vcspull config`` argument subparser.

    Parameters
    ----------
    parser : argparse.ArgumentParser
        The ``config`` command parser.
    scope_parent : argparse.ArgumentParser
        Shared parent carrying ``--no-project`` and ``--trust-project``, so
        they parse after ``ls`` as well as before ``config``.
    """
    subparsers = parser.add_subparsers(dest="config_command")
    subparsers.add_parser(
        "ls",
        help="list the configuration scopes in effect",
        parents=[scope_parent],
    )


def create_trust_subparser(parser: argparse.ArgumentParser) -> None:
    """Create ``vcspull trust`` argument subparser."""
    parser.add_argument(
        "directory",
        metavar="DIR",
        nargs="?",
        help="project directory to trust (default: current directory)",
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--untrust",
        action="store_true",
        help="remove the directory from the trusted set",
    )
    group.add_argument(
        "--show",
        action="store_true",
        help="print the trusted project directories and exit",
    )


def _plural(count: int, singular: str, plural: str | None = None) -> str:
    """Return *count* with a correctly inflected noun.

    Examples
    --------
    >>> _plural(1, "repo")
    '1 repo'
    >>> _plural(0, "repo")
    '0 repos'
    >>> _plural(2, "repository", "repositories")
    '2 repositories'
    """
    return f"{count} {singular if count == 1 else plural or singular + 's'}"


def _note(declared: int, effective: int, *, untrusted: bool) -> str:
    """Return the parenthetical explaining why a file's count is not its whole.

    Examples
    --------
    >>> _note(2, 2, untrusted=False)
    ''
    >>> _note(2, 1, untrusted=False)
    ' (1 overridden)'
    >>> _note(2, 0, untrusted=True)
    ' (untrusted)'
    """
    if untrusted:
        return " (untrusted)"
    overridden = declared - effective
    return f" ({overridden} overridden)" if overridden else ""


def _declared_repos(path: pathlib.Path, cwd: pathlib.Path) -> list[pathlib.Path]:
    """Return the destination of every repository a single file declares."""
    try:
        content, _duplicates, _items = DuplicateAwareConfigReader.load_with_duplicates(
            path,
        )
        return [
            pathlib.Path(repo["path"]).parent / str(repo["name"])
            for repo in extract_repos(t.cast("RawConfigDict", content), cwd=cwd)
        ]
    except Exception:
        log.warning("could not read %s", PrivatePath(path))
        return []


class _ScopeRow(t.NamedTuple):
    """One line of ``vcspull config ls``."""

    scope: str
    path: str
    declared: list[pathlib.Path]
    untrusted: bool


def config_ls(
    *,
    include_project: bool = True,
    trust_project: bool = False,
    cwd: pathlib.Path | None = None,
) -> None:
    """Print the configuration scopes in effect, weakest first.

    Each row is a file, its scope, and how many repositories it declares. A
    file whose entries are overridden by a nearer one says so, and a project
    file awaiting trust is listed as untrusted rather than silently dropped —
    this is the command you reach for when ``vcspull list`` refuses to load
    something.

    Parameters
    ----------
    include_project : bool
        Set ``False`` to show the stack as ``--no-project`` resolves it.
    trust_project : bool
        Treat escaping project configs as trusted, as ``--trust-project`` does.
    cwd : pathlib.Path, optional
        Working directory. Defaults to :meth:`pathlib.Path.cwd`.
    """
    cwd = cwd or pathlib.Path.cwd()
    sources = scopes.resolve_sources(cwd=cwd, include_project=include_project)

    if not sources:
        print("no configuration files found")
        return

    rows: list[_ScopeRow] = []
    winner: dict[pathlib.Path, int] = {}

    for index, source in enumerate(sources):
        declared = _declared_repos(source.path, cwd)
        untrusted = not trust_project and bool(source_escapes(source, cwd=cwd))
        rows.append(
            _ScopeRow(source.scope, str(PrivatePath(source.path)), declared, untrusted),
        )
        if untrusted:
            continue
        for key in declared:
            winner[key] = index

    scope_width = max(len(row.scope) for row in rows)
    path_width = max(len(row.path) for row in rows)

    for index, row in enumerate(rows):
        effective = sum(1 for owner in winner.values() if owner == index)
        count = _plural(len(row.declared), "repo") + _note(
            len(row.declared),
            effective,
            untrusted=row.untrusted,
        )
        print(f"{row.scope:<{scope_width}}  {row.path:<{path_width}}  {count}")

    print(f"\n{_plural(len(winner), 'repository', 'repositories')} in effect.")
    if any(row.untrusted for row in rows):
        print("Untrusted configs are not loaded. Allow one with 'vcspull trust DIR'.")


def trust_command(
    directory: str | None,
    *,
    untrust: bool = False,
    show: bool = False,
    state_file: pathlib.Path | None = None,
) -> None:
    """Record, remove, or print trusted project directories.

    Parameters
    ----------
    directory : str | None
        Directory to trust or untrust. Defaults to the current directory.
    untrust : bool
        Remove the directory instead of adding it.
    show : bool
        Print the trusted set and make no change.
    state_file : pathlib.Path, optional
        File holding the record. Defaults to
        :func:`vcspull._internal.scopes.trust_state_file`.

    Examples
    --------
    >>> state = tmp_path / "trusted"
    >>> trust_command(None, show=True, state_file=state)
    no trusted project directories
    >>> api = tmp_path / "api"
    >>> api.mkdir()
    >>> trust_command(str(api), state_file=state)  # doctest: +ELLIPSIS
    trusted ...api
    >>> scopes.read_trusted(state) == frozenset({api})
    True
    >>> trust_command(str(api), untrust=True, state_file=state)  # doctest: +ELLIPSIS
    untrusted ...api
    >>> scopes.read_trusted(state)
    frozenset()
    """
    state_file = state_file or scopes.trust_state_file()

    if show:
        trusted = sorted(scopes.read_trusted(state_file))
        if not trusted:
            print("no trusted project directories")
        for entry in trusted:
            print(PrivatePath(entry))
        return

    raw = pathlib.Path(directory).expanduser() if directory else pathlib.Path.cwd()
    target = PrivatePath(os.path.realpath(raw))

    if untrust:
        scopes.untrust_directory(state_file, raw)
        print(f"untrusted {target}")
    else:
        scopes.trust_directory(state_file, raw)
        print(f"trusted {target}")
