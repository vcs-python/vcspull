"""Configuration scope resolution and project trust.

vcspull reads configuration from four scopes. Weakest first, every scope is
unioned into one stack:

============ =========================================================
Scope        Location
============ =========================================================
``system``   ``/etc/vcspull/*.{yaml,yml,json}``
``user``     the user config directory, then ``~/.vcspull.{yaml,json}``
``project``  ``.vcspull.{yaml,yml,json}`` in each ancestor of the
             working directory, outermost first
============ =========================================================

Everything here is a resolver: it decides *which* files participate and
*whether* a project file may act, never what a file means. Nothing in this
module parses repository entries, and nothing prompts — a caller that needs
consent gets the list of offending destinations from :func:`requires_trust`
and decides how to ask.
"""

from __future__ import annotations

import os
import pathlib
import typing as t

from ..util import get_config_dir

if t.TYPE_CHECKING:
    from collections.abc import Mapping

ConfigScope = t.Literal["system", "user", "project", "external"]
"""Where a configuration file lives, and therefore how much it is trusted."""

CONFIG_SUFFIXES: t.Final = (".yaml", ".yml", ".json")
"""Recognized config suffixes, weakest first within a single directory."""

SYSTEM_CONFIG_DIR: t.Final = pathlib.Path("/etc/vcspull")
"""Machine-wide configuration directory."""

PROJECT_CONFIG_STEM: t.Final = ".vcspull"
"""Basename of a project configuration, before its suffix."""

_TRUTHY: t.Final = frozenset({"1", "true", "yes", "on"})


def _real(path: pathlib.Path) -> pathlib.Path:
    """Return *path* with ``~`` expanded and every symlink followed.

    Both sides of a containment or ceiling comparison go through this, so a
    symlinked ``$HOME`` stops the project walk and a symlinked workspace root
    cannot smuggle a destination back out of its directory.

    Examples
    --------
    >>> link = tmp_path / "link"
    >>> link.symlink_to(tmp_path, target_is_directory=True)
    >>> _real(link / "sub") == _real(tmp_path / "sub")
    True
    """
    return pathlib.Path(os.path.realpath(path.expanduser()))


class ConfigSource(t.NamedTuple):
    """One configuration file in the resolution stack.

    Sources are ordered weakest to strongest, so a later source overrides an
    earlier one for any repository they both name.
    """

    scope: ConfigScope
    """Scope this file was resolved from."""

    path: pathlib.Path
    """Absolute path to the configuration file."""

    trust_root: pathlib.Path
    """Directory whose trust governs this file. Its own directory, for a
    project config; the containing scope directory otherwise."""

    @property
    def gated(self) -> bool:
        """Return ``True`` when this source needs a containment check.

        Examples
        --------
        >>> project = ConfigSource(
        ...     "project", pathlib.Path("/w/.vcspull.yaml"), pathlib.Path("/w")
        ... )
        >>> project.gated
        True
        >>> ConfigSource(
        ...     "user", pathlib.Path("/h/.vcspull.yaml"), pathlib.Path("/h")
        ... ).gated
        False
        """
        return self.scope == "project"


def env_flag(name: str, environ: Mapping[str, str] = os.environ) -> bool:
    """Return whether an environment variable is set to a truthy word.

    Parameters
    ----------
    name : str
        Environment variable to read.
    environ : Mapping[str, str]
        Environment to read from. Defaults to :data:`os.environ`.

    Examples
    --------
    >>> env_flag("VCSPULL_YES", {"VCSPULL_YES": "1"})
    True
    >>> env_flag("VCSPULL_YES", {"VCSPULL_YES": "0"})
    False
    >>> env_flag("VCSPULL_YES", {})
    False
    """
    return environ.get(name, "").strip().lower() in _TRUTHY


def ceiling_paths(
    environ: Mapping[str, str] = os.environ,
    *,
    home: pathlib.Path,
) -> frozenset[pathlib.Path]:
    """Return the directories the upward walk stops at.

    ``VCSPULL_CEILING_PATHS`` replaces the default stop set. Setting it to an
    empty value lets the walk run to the filesystem root. Every entry is
    resolved, so a ceiling reached through a symlink still stops the walk.

    Parameters
    ----------
    environ : Mapping[str, str]
        Environment to read from. Defaults to :data:`os.environ`.
    home : pathlib.Path
        User home directory, the default ceiling.

    Examples
    --------
    >>> ceiling_paths({}, home=tmp_path) == frozenset({_real(tmp_path)})
    True
    >>> sorted(
    ...     ceiling_paths(
    ...         {"VCSPULL_CEILING_PATHS": f"/srv{os.pathsep}/opt"},
    ...         home=tmp_path,
    ...     )
    ... )
    [PosixPath('/opt'), PosixPath('/srv')]
    >>> ceiling_paths({"VCSPULL_CEILING_PATHS": ""}, home=tmp_path)
    frozenset()
    """
    raw = environ.get("VCSPULL_CEILING_PATHS")
    if raw is None:
        return frozenset({_real(home)})
    return frozenset(
        _real(pathlib.Path(entry)) for entry in raw.split(os.pathsep) if entry
    )


def project_dirs(
    cwd: pathlib.Path,
    *,
    ceilings: frozenset[pathlib.Path],
) -> tuple[pathlib.Path, ...]:
    """Return the ancestors of *cwd* that may hold a project config.

    Outermost first, so the returned order is weakest to strongest. A ceiling
    directory stops the walk and is itself excluded; the filesystem root ends
    it either way.

    Parameters
    ----------
    cwd : pathlib.Path
        Directory to walk up from.
    ceilings : frozenset of pathlib.Path
        Resolved directories to stop at, from :func:`ceiling_paths`.

    Examples
    --------
    >>> home = pathlib.Path("/home/u")
    >>> project_dirs(pathlib.Path("/home/u/work/api"), ceilings=frozenset({home}))
    (PosixPath('/home/u/work'), PosixPath('/home/u/work/api'))

    Standing on the ceiling yields nothing:

    >>> project_dirs(home, ceilings=frozenset({home}))
    ()

    Outside the ceiling, the walk runs to the root:

    >>> project_dirs(pathlib.Path("/srv/app"), ceilings=frozenset({home}))
    (PosixPath('/'), PosixPath('/srv'), PosixPath('/srv/app'))
    """
    walked: list[pathlib.Path] = []
    for directory in (cwd, *cwd.parents):
        if _real(directory) in ceilings:
            break
        walked.append(directory)
    walked.reverse()
    return tuple(walked)


def _config_files_in(directory: pathlib.Path) -> tuple[pathlib.Path, ...]:
    """Return sorted config files directly inside *directory*.

    A directory that cannot be listed, or one holding a *directory* named
    ``foo.yaml``, contributes nothing rather than raising.

    Examples
    --------
    >>> scope_dir = tmp_path / "scope"
    >>> (scope_dir / "not-a-file.yaml").mkdir(parents=True)
    >>> _ = (scope_dir / "b.json").write_text("{}", encoding="utf-8")
    >>> _ = (scope_dir / "a.yaml").write_text("", encoding="utf-8")
    >>> [path.name for path in _config_files_in(scope_dir)]
    ['a.yaml', 'b.json']
    >>> _config_files_in(tmp_path / "missing")
    ()
    """
    try:
        entries = sorted(directory.iterdir())
    except OSError:
        return ()
    return tuple(
        entry
        for entry in entries
        if entry.suffix in CONFIG_SUFFIXES and entry.is_file()
    )


def _project_files_in(directory: pathlib.Path) -> tuple[pathlib.Path, ...]:
    """Return the project configs directly inside *directory*.

    Examples
    --------
    >>> _ = (tmp_path / ".vcspull.yaml").write_text("", encoding="utf-8")
    >>> _ = (tmp_path / ".vcspull.json").write_text("{}", encoding="utf-8")
    >>> [path.name for path in _project_files_in(tmp_path)]
    ['.vcspull.yaml', '.vcspull.json']
    """
    found: list[pathlib.Path] = []
    for suffix in CONFIG_SUFFIXES:
        candidate = directory / f"{PROJECT_CONFIG_STEM}{suffix}"
        if candidate.is_file():
            found.append(candidate)
    return tuple(found)


def resolve_sources(
    *,
    cwd: pathlib.Path,
    home: pathlib.Path | None = None,
    environ: Mapping[str, str] = os.environ,
    include_project: bool = True,
) -> tuple[ConfigSource, ...]:
    """Return the configuration stack in effect, weakest source first.

    Parameters
    ----------
    cwd : pathlib.Path
        Working directory the project walk starts from.
    home : pathlib.Path, optional
        User home directory, the default project-walk ceiling. Defaults to
        :meth:`pathlib.Path.home`.
    environ : Mapping[str, str]
        Environment to read from. Defaults to :data:`os.environ`.
    include_project : bool
        Set ``False`` (or export ``VCSPULL_NO_PROJECT=1``) to drop the project
        scope and resolve only system and user configuration.

    Returns
    -------
    tuple of ConfigSource
        Existing files only, ordered weakest to strongest.

    Raises
    ------
    vcspull.exc.MultipleConfigWarning
        When both ``~/.vcspull.yaml`` and ``~/.vcspull.json`` exist.

    Examples
    --------
    A project config in the working directory joins the stack:

    >>> _ = (tmp_path / ".vcspull.yaml").write_text("", encoding="utf-8")
    >>> [source.scope for source in resolve_sources(cwd=tmp_path, home=tmp_path.parent)]
    ['project']

    ``VCSPULL_NO_PROJECT`` drops it:

    >>> resolve_sources(
    ...     cwd=tmp_path,
    ...     home=tmp_path.parent,
    ...     environ={"VCSPULL_NO_PROJECT": "1"},
    ... )
    ()
    """
    from ..config import find_home_config_files

    home = (home or pathlib.Path.home()).expanduser()
    sources: list[ConfigSource] = []

    sources.extend(
        ConfigSource("system", path, SYSTEM_CONFIG_DIR)
        for path in _config_files_in(SYSTEM_CONFIG_DIR)
    )

    user_dir = get_config_dir()
    sources.extend(
        ConfigSource("user", path, user_dir) for path in _config_files_in(user_dir)
    )

    # Delegated rather than reimplemented so that owning two home dotfiles
    # still raises MultipleConfigWarning, as it did before scopes existed.
    sources.extend(
        ConfigSource("user", path, path.parent) for path in find_home_config_files()
    )

    if include_project and not env_flag("VCSPULL_NO_PROJECT", environ):
        ceilings = ceiling_paths(environ, home=home)
        for directory in project_dirs(cwd, ceilings=ceilings):
            sources.extend(
                ConfigSource("project", path, directory)
                for path in _project_files_in(directory)
            )

    return tuple(sources)


def classify_scope(
    config_path: pathlib.Path,
    *,
    cwd: pathlib.Path,
    home: pathlib.Path,
    environ: Mapping[str, str] = os.environ,
) -> ConfigScope:
    """Return the scope a single configuration file belongs to.

    Unlike :func:`resolve_sources`, this answers the question for a path the
    caller already holds — a ``--file`` argument, or the file a write command
    is about to touch. A path that is neither user, system, nor inside the
    working directory is ``external``.

    Parameters
    ----------
    config_path : pathlib.Path
        Configuration file to classify.
    cwd : pathlib.Path
        Working directory.
    home : pathlib.Path
        User home directory.
    environ : Mapping[str, str]
        Environment to read from. Defaults to :data:`os.environ`.

    Examples
    --------
    >>> project = tmp_path / "proj"
    >>> project.mkdir()
    >>> classify_scope(
    ...     project / ".vcspull.yaml", cwd=project, home=tmp_path / "home"
    ... )
    'project'
    >>> classify_scope(
    ...     tmp_path / "home" / ".vcspull.yaml",
    ...     cwd=project,
    ...     home=tmp_path / "home",
    ... )
    'user'
    >>> classify_scope(
    ...     tmp_path / "elsewhere.yaml", cwd=project, home=tmp_path / "home"
    ... )
    'external'
    """
    resolved = _real(config_path)
    home = _real(home)
    cwd = _real(cwd)

    if resolved.parent == home and resolved.name in {
        f"{PROJECT_CONFIG_STEM}{suffix}" for suffix in CONFIG_SUFFIXES
    }:
        return "user"

    xdg_config_home = _real(
        pathlib.Path(environ.get("XDG_CONFIG_HOME", home / ".config")),
    )
    if _is_within(resolved, xdg_config_home / "vcspull"):
        return "user"

    xdg_config_dirs = environ.get("XDG_CONFIG_DIRS")
    system_bases = [SYSTEM_CONFIG_DIR]
    if xdg_config_dirs:
        system_bases.extend(
            pathlib.Path(entry) / "vcspull"
            for entry in xdg_config_dirs.split(os.pathsep)
            if entry
        )
    else:
        system_bases.append(pathlib.Path("/etc/xdg/vcspull"))
    for base in system_bases:
        if _is_within(resolved, _real(base)):
            return "system"

    return "project" if _is_within(resolved, cwd) else "external"


def _is_within(path: pathlib.Path, directory: pathlib.Path) -> bool:
    """Return whether *path* is *directory* or lives beneath it.

    Examples
    --------
    >>> _is_within(pathlib.Path("/w/vendor/x"), pathlib.Path("/w"))
    True
    >>> _is_within(pathlib.Path("/w"), pathlib.Path("/w"))
    True
    >>> _is_within(pathlib.Path("/workspace"), pathlib.Path("/w"))
    False
    """
    return path == directory or directory in path.parents
