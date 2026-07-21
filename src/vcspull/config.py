"""Configuration functionality for vcspull."""

from __future__ import annotations

import contextlib
import copy
import enum
import fnmatch
import logging
import os
import pathlib
import subprocess
import sys
import tempfile
import typing as t
from collections.abc import Callable, Iterable, Sequence

from libvcs.sync.git import GitRemote

from vcspull.validator import is_valid_config

from . import exc
from ._internal import scopes
from ._internal.config_reader import (
    ConfigReader,
    DuplicateAwareConfigReader,
    config_format_from_path,
)
from ._internal.private_path import PrivatePath
from .types import ConfigDict, RawConfigDict, WorktreeConfigDict
from .util import get_config_dir, update_dict

log = logging.getLogger(__name__)


def expand_dir(
    dir_: pathlib.Path,
    cwd: pathlib.Path | Callable[[], pathlib.Path] = pathlib.Path.cwd,
) -> pathlib.Path:
    """Return path with environmental variables and tilde ~ expanded.

    Parameters
    ----------
    dir_ : pathlib.Path
        Directory path to expand
    cwd : pathlib.Path, optional
        Current working dir (used to resolve relative paths). Defaults to
        :py:meth:`pathlib.Path.cwd`.

    Returns
    -------
    pathlib.Path
        Absolute directory path
    """
    dir_ = pathlib.Path(os.path.expandvars(str(dir_))).expanduser()
    if callable(cwd):
        cwd = cwd()

    if not dir_.is_absolute():
        dir_ = pathlib.Path(os.path.normpath(cwd / dir_))
        assert dir_ == pathlib.Path(cwd, dir_).resolve(strict=False)
    return dir_


def normalize_config_file_path(
    path: pathlib.Path,
    cwd: pathlib.Path | Callable[[], pathlib.Path] = pathlib.Path.cwd,
) -> pathlib.Path:
    """Return absolute config file path without resolving symlinks.

    Symlink entry names are preserved intact so that downstream operations
    (e.g. atomic writes) can resolve them as needed, while the logical path
    is used for display and identity.

    Parameters
    ----------
    path : pathlib.Path
        Config file path to normalize.
    cwd : pathlib.Path, optional
        Current working dir (used to resolve relative paths). Defaults to
        :py:meth:`pathlib.Path.cwd`.

    Returns
    -------
    pathlib.Path
        Absolute config file path with symlink names preserved.

    Examples
    --------
    >>> normalize_config_file_path(pathlib.Path("~/cfg.yaml")).name
    'cfg.yaml'
    >>> normalize_config_file_path(
    ...     pathlib.Path("configs/vcspull.yaml"),
    ...     cwd=pathlib.Path("/tmp/project"),
    ... )  # doctest: +ELLIPSIS
    PosixPath('.../configs/vcspull.yaml')
    """
    path = pathlib.Path(os.path.expandvars(str(path))).expanduser()
    if callable(cwd):
        cwd = cwd()

    if not path.is_absolute():
        path = pathlib.Path(os.path.normpath(cwd / path))
    return path


def _validate_worktrees_config(
    worktrees_raw: t.Any,
    repo_name: str,
) -> list[WorktreeConfigDict]:
    """Validate and normalize worktrees configuration.

    Parameters
    ----------
    worktrees_raw : Any
        Raw worktrees configuration from YAML/JSON.
    repo_name : str
        Name of the parent repository (for error messages).

    Returns
    -------
    list[WorktreeConfigDict]
        Validated list of worktree configurations.

    Raises
    ------
    VCSPullException
        If the worktrees configuration is invalid.

    Examples
    --------
    Valid configuration with a tag:

    >>> from vcspull.config import _validate_worktrees_config
    >>> config = [{"dir": "../v1", "tag": "v1.0.0"}]
    >>> result = _validate_worktrees_config(config, "myrepo")
    >>> len(result)
    1
    >>> result[0]["dir"]
    '../v1'
    >>> result[0]["tag"]
    'v1.0.0'

    Valid configuration with a branch:

    >>> config = [{"dir": "../dev", "branch": "develop"}]
    >>> result = _validate_worktrees_config(config, "myrepo")
    >>> result[0]["branch"]
    'develop'

    Valid configuration with a commit:

    >>> config = [{"dir": "../fix", "commit": "abc123"}]
    >>> result = _validate_worktrees_config(config, "myrepo")
    >>> result[0]["commit"]
    'abc123'

    Error: worktrees must be a list:

    >>> _validate_worktrees_config("not-a-list", "myrepo")
    Traceback (most recent call last):
        ...
    vcspull.exc.VCSPullException: ...worktrees must be a list, got str

    Error: worktree entry must be a dict:

    >>> _validate_worktrees_config(["not-a-dict"], "myrepo")
    Traceback (most recent call last):
        ...
    vcspull.exc.VCSPullException: ...must be a dict, got str

    Error: missing required 'dir' field:

    >>> _validate_worktrees_config([{"tag": "v1.0.0"}], "myrepo")
    Traceback (most recent call last):
        ...
    vcspull.exc.VCSPullException: ...missing required 'dir' field

    Error: no ref type specified:

    >>> _validate_worktrees_config([{"dir": "../wt"}], "myrepo")
    Traceback (most recent call last):
        ...
    vcspull.exc.VCSPullException: ...must specify one of: tag, branch, or commit

    Error: empty ref value:

    >>> _validate_worktrees_config([{"dir": "../wt", "tag": ""}], "myrepo")
    Traceback (most recent call last):
        ...
    vcspull.exc.VCSPullException: ...empty ref value...

    Error: multiple refs specified:

    >>> _validate_worktrees_config(
    ...     [{"dir": "../wt", "tag": "v1", "branch": "main"}], "myrepo"
    ... )
    Traceback (most recent call last):
        ...
    vcspull.exc.VCSPullException: ...cannot specify multiple refs...
    """
    if not isinstance(worktrees_raw, list):
        msg = (
            f"Repository '{repo_name}': worktrees must be a list, "
            f"got {type(worktrees_raw).__name__}"
        )
        raise exc.VCSPullException(msg)

    validated: list[WorktreeConfigDict] = []

    for idx, wt in enumerate(worktrees_raw):
        if not isinstance(wt, dict):
            msg = (
                f"Repository '{repo_name}': worktree entry {idx} must be a dict, "
                f"got {type(wt).__name__}"
            )
            raise exc.VCSPullException(msg)

        # Validate required 'dir' field
        if "dir" not in wt or not wt["dir"]:
            msg = (
                f"Repository '{repo_name}': worktree entry {idx} "
                "missing required 'dir' field"
            )
            raise exc.VCSPullException(msg)

        if not isinstance(wt["dir"], str):
            msg = (
                f"Repository '{repo_name}': worktree entry {idx} "
                f"'dir' must be a string, got {type(wt['dir']).__name__}"
            )
            raise exc.VCSPullException(msg)

        # Validate exactly one ref type
        tag = wt.get("tag")
        branch = wt.get("branch")
        commit = wt.get("commit")

        refs_specified = sum(
            1 for ref in [tag, branch, commit] if ref is not None and ref != ""
        )
        empty_refs = sum(1 for ref in [tag, branch, commit] if ref == "")

        if refs_specified == 0 and empty_refs == 0:
            msg = (
                f"Repository '{repo_name}': worktree entry {idx} "
                "must specify one of: tag, branch, or commit"
            )
            raise exc.VCSPullException(msg)
        if refs_specified == 0 and empty_refs > 0:
            msg = (
                f"Repository '{repo_name}': worktree entry {idx} "
                "has empty ref value (tag, branch, or commit)"
            )
            raise exc.VCSPullException(msg)
        if refs_specified > 1:
            msg = (
                f"Repository '{repo_name}': worktree entry {idx} "
                "cannot specify multiple refs (tag, branch, commit)"
            )
            raise exc.VCSPullException(msg)

        # Validate ref types are strings
        for ref_name, ref_val in [("tag", tag), ("branch", branch), ("commit", commit)]:
            if ref_val is not None and not isinstance(ref_val, str):
                msg = (
                    f"Repository '{repo_name}': worktree entry {idx} "
                    f"'{ref_name}' must be a string, got {type(ref_val).__name__}"
                )
                raise exc.VCSPullException(msg)

        # Build validated worktree config
        wt_config: WorktreeConfigDict = {"dir": wt["dir"]}

        if tag:
            wt_config["tag"] = tag
        if branch:
            wt_config["branch"] = branch
        if commit:
            wt_config["commit"] = commit

        # Optional fields
        if "detach" in wt:
            wt_config["detach"] = wt["detach"]
        if "lock" in wt:
            wt_config["lock"] = wt["lock"]
        if "lock_reason" in wt:
            wt_config["lock_reason"] = wt["lock_reason"]

        validated.append(wt_config)

    return validated


def extract_repos(
    config: RawConfigDict,
    cwd: pathlib.Path | Callable[[], pathlib.Path] = pathlib.Path.cwd,
) -> list[ConfigDict]:
    """Return expanded configuration.

    end-user configuration permit inline configuration shortcuts, expand to
    identical format for parsing.

    Parameters
    ----------
    config : dict
        the repo config in :py:class:`dict` format.
    cwd : pathlib.Path
        current working dir (for deciphering relative paths)

    Returns
    -------
    list : List of normalized repository information
    """
    configs: list[ConfigDict] = []
    if callable(cwd):
        cwd = cwd()

    for directory, repos in config.items():
        assert isinstance(repos, dict)
        for repo, repo_data in repos.items():
            conf: dict[str, t.Any] = {}

            """
            repo_name: http://myrepo.com/repo.git

            to

            repo_name: { url: 'http://myrepo.com/repo.git' }

            also assures the repo is a :py:class:`dict`.
            """

            if isinstance(repo_data, str):
                conf["url"] = repo_data
            else:
                conf = update_dict(conf, repo_data)

            if "repo" in conf:
                if "url" not in conf:
                    conf["url"] = conf.pop("repo")
                else:
                    conf.pop("repo", None)

            # Sync-tuning keys (rev/shallow/depth) are canonical under
            # ``options:``; lift them onto the flat ConfigDict the sync path
            # reads. A legacy top-level key was already copied above by
            # update_dict, but an ``options:`` value wins when both are set.
            entry_options = conf.get("options")
            if isinstance(entry_options, dict):
                for option_key in LEGACY_REPO_OPTION_KEYS:
                    if option_key in entry_options:
                        conf[option_key] = entry_options[option_key]

            if "name" not in conf:
                conf["name"] = repo

            if "workspace_root" not in conf:
                conf["workspace_root"] = directory

            if "path" not in conf:
                conf["path"] = expand_dir(
                    pathlib.Path(expand_dir(pathlib.Path(directory), cwd=cwd))
                    / conf["name"],
                    cwd,
                )

            if "remotes" in conf:
                assert isinstance(conf["remotes"], dict)
                for remote_name, url in conf["remotes"].items():
                    if isinstance(url, GitRemote):
                        continue
                    if isinstance(url, str):
                        conf["remotes"][remote_name] = GitRemote(
                            name=remote_name,
                            fetch_url=url,
                            push_url=url,
                        )
                    elif isinstance(url, dict):
                        assert "push_url" in url
                        assert "fetch_url" in url
                        conf["remotes"][remote_name] = GitRemote(
                            name=remote_name,
                            **url,
                        )

            # Process worktrees configuration
            if "worktrees" in conf:
                worktrees_raw = conf["worktrees"]
                if worktrees_raw is not None:
                    repo_name_for_error = conf.get("name") or repo
                    validated_worktrees = _validate_worktrees_config(
                        worktrees_raw,
                        repo_name=repo_name_for_error,
                    )
                    conf["worktrees"] = validated_worktrees

            def is_valid_config_dict(val: t.Any) -> t.TypeGuard[ConfigDict]:
                assert isinstance(val, dict)
                return True

            assert is_valid_config_dict(conf)

            configs.append(conf)

    return configs


def find_home_config_files(
    filetype: list[str] | None = None,
) -> list[pathlib.Path]:
    """Return configs of ``.vcspull.{yaml,json}`` in user's home directory.

    The returned path preserves the logical home entry name so callers
    keep the config type implied by ``.yaml`` or ``.json`` even when the
    file is a symlink.

    Parameters
    ----------
    filetype : list of str, optional
        File types to search for (default ``["json", "yaml"]``)

    Returns
    -------
    list of pathlib.Path
        Absolute paths to discovered config files

    Examples
    --------
    >>> find_home_config_files()
    []
    """
    if filetype is None:
        filetype = ["json", "yaml"]
    configs: list[pathlib.Path] = []

    check_yaml = "yaml" in filetype
    check_json = "json" in filetype

    yaml_config = normalize_config_file_path(pathlib.Path("~/.vcspull.yaml"))
    has_yaml_config = check_yaml and yaml_config.exists()
    json_config = normalize_config_file_path(pathlib.Path("~/.vcspull.json"))
    has_json_config = check_json and json_config.exists()

    if not has_yaml_config and not has_json_config:
        log.debug(
            "No config file found. Create a .vcspull.yaml or .vcspull.json"
            " in your $HOME directory. http://vcspull.git-pull.com for a"
            " quickstart.",
        )
    else:
        if sum(filter(None, [has_json_config, has_yaml_config])) > 1:
            raise exc.MultipleConfigWarning
        if has_yaml_config:
            configs.append(yaml_config)
        if has_json_config:
            configs.append(json_config)

    return configs


def find_config_files(
    path: list[pathlib.Path] | pathlib.Path | None = None,
    match: list[str] | str | None = None,
    filetype: t.Literal["json", "yaml", "yml", "*"]
    | list[t.Literal["json", "yaml", "yml", "*"]]
    | None = None,
    include_home: bool = False,
) -> list[pathlib.Path]:
    """Return repos from a directory and match. Not recursive.

    Parameters
    ----------
    path : list
        list of paths to search
    match : list
        list of globs to search against
    filetype: list
        of filetypes to search against
    include_home : bool
        Include home configuration files

    Raises
    ------
    LoadConfigRepoConflict :
        There are two configs that have same path and name with different repo urls.

    Returns
    -------
    list :
        list of absolute paths to config files.
    """
    if filetype is None:
        filetype = ["json", "yaml", "yml"]
    if match is None:
        match = ["*"]
    config_files = []
    if path is None:
        path = get_config_dir()

    if include_home is True:
        config_files.extend(find_home_config_files())

    if isinstance(path, list):
        for p in path:
            config_files.extend(find_config_files(p, match, filetype))
    else:
        path = path.expanduser()
        if isinstance(match, list):
            for m in match:
                config_files.extend(find_config_files(path, m, filetype))
        elif isinstance(filetype, list):
            for f in filetype:
                config_files.extend(find_config_files(path, match, f))
        else:
            match = f"{match}.{filetype}"
            config_files = list(path.glob(match))

    return config_files


ConfigGate = Callable[[pathlib.Path, Sequence[ConfigDict]], bool]
"""Decides whether a resolved configuration file may contribute.

Receives the file and the entries it expands to, and returns ``False`` to skip
it. Raising aborts the load.
"""


def load_configs(
    files: list[pathlib.Path],
    cwd: pathlib.Path | Callable[[], pathlib.Path] = pathlib.Path.cwd,
    *,
    merge_duplicates: bool = True,
    warn_legacy_options: bool = False,
    gate: ConfigGate | None = None,
) -> list[ConfigDict]:
    """Return repos from a list of files, nearest file winning.

    *files* are ordered weakest to strongest. Repositories with distinct
    destination paths are unioned; when two files name the same destination the
    later one replaces the earlier entry whole, so a project config that
    repoints a repository never inherits the weaker file's ``options:``.

    Parameters
    ----------
    files : list
        paths to config file, weakest first
    cwd : pathlib.Path
        current path (pass down for :func:`extract_repos`
    warn_legacy_options : bool
        If ``True``, log a deprecation warning for entries that still carry
        top-level ``rev``/``shallow``/``depth`` keys (see
        :func:`detect_legacy_repo_options`).
    gate : ConfigGate, optional
        Consulted with each file and the destinations it resolves to before the
        file contributes. Returning ``False`` skips the file.

    Returns
    -------
    list of dict :
        expanded config dict item
    """
    merged: dict[pathlib.Path, ConfigDict] = {}
    origins: dict[pathlib.Path, pathlib.Path] = {}
    if callable(cwd):
        cwd = cwd()

    for file in files:
        if isinstance(file, str):
            file = pathlib.Path(file)
        assert isinstance(file, pathlib.Path)

        config_content, duplicate_roots, _top_level_items = (
            DuplicateAwareConfigReader.load_with_duplicates(file)
        )

        if merge_duplicates:
            (
                config_content,
                merge_conflicts,
                _merge_change_count,
                merge_details,
            ) = merge_duplicate_workspace_roots(config_content, duplicate_roots)

            for conflict in merge_conflicts:
                log.warning("%s: %s", file, conflict)

            for root_label, occurrence_count in merge_details:
                duplicate_count = max(occurrence_count - 1, 0)
                if duplicate_count == 0:
                    continue
                plural = "entry" if duplicate_count == 1 else "entries"
                log.info(
                    "%s: merged %d duplicate %s for workspace root '%s'",
                    file,
                    duplicate_count,
                    plural,
                    root_label,
                )
        elif duplicate_roots:
            duplicate_list = ", ".join(sorted(duplicate_roots.keys()))
            log.warning(
                "%s: duplicate workspace roots detected (%s); keeping last occurrences",
                file,
                duplicate_list,
            )

        if warn_legacy_options:
            legacy_entries = detect_legacy_repo_options(config_content)
            if legacy_entries:
                affected = ", ".join(f"{label}{name}" for label, name in legacy_entries)
                log.warning(
                    "%s: top-level rev/shallow/depth are deprecated; move them "
                    "under 'options:' (run 'vcspull migrate'). Affected: %s",
                    file,
                    affected,
                    extra={
                        "vcspull_config_path": str(file),
                        "vcspull_legacy_count": len(legacy_entries),
                    },
                )

        assert is_valid_config(config_content)
        repos = extract_repos(config_content, cwd=cwd)

        # Gated on the expanded entries, not the raw keys: an entry may
        # override its destination with ``path:`` and never touch the
        # workspace root the key declares.
        if gate is not None and not gate(file, repos):
            continue

        for repo in repos:
            key = pathlib.Path(repo["path"]).parent / repo["name"]
            displaced = merged.get(key)
            if displaced is not None and _entries_diverge(displaced, repo):
                log.warning(
                    "%s overrides %s for '%s' (url or vcs differs)",
                    PrivatePath(file),
                    PrivatePath(origins[key]),
                    PrivatePath(key),
                )
            merged[key] = repo
            origins[key] = file

    return list(merged.values())


def _entries_diverge(displaced: ConfigDict, winner: ConfigDict) -> bool:
    """Return whether two entries for one destination really disagree.

    Identical duplicates across a user and a project file are the common,
    harmless case, so only a differing URL or VCS is worth a warning.

    Examples
    --------
    >>> entry = {"url": "git+https://x", "vcs": "git"}
    >>> _entries_diverge(entry, dict(entry))
    False
    >>> _entries_diverge(entry, {"url": "git+https://fork", "vcs": "git"})
    True
    """
    return (displaced.get("url"), displaced.get("vcs")) != (
        winner.get("url"),
        winner.get("vcs"),
    )


def load_scoped_configs(
    config_path: pathlib.Path | None = None,
    *,
    cwd: pathlib.Path | None = None,
    include_project: bool = True,
    trust_project: bool = False,
    warn_legacy_options: bool = False,
) -> list[ConfigDict]:
    """Return every repository the configuration scopes in effect define.

    An explicit *config_path* replaces the whole stack. Otherwise the system,
    user, and project scopes are unioned nearest-wins, and each project config
    that would check a repository out beyond its own directory must be trusted
    first.

    Parameters
    ----------
    config_path : pathlib.Path, optional
        Explicit configuration file from ``-f``/``--file``.
    cwd : pathlib.Path, optional
        Working directory the project walk starts from.
    include_project : bool
        Set ``False`` to skip the project scope entirely (``--no-project``).
    trust_project : bool
        Trust escaping project configs without prompting
        (``--trust-project``).
    warn_legacy_options : bool
        Warn about entries still using top-level ``rev``/``shallow``/``depth``.

    Raises
    ------
    exc.VCSPullException
        When an escaping project config cannot be confirmed because there is no
        terminal to ask on.
    """
    cwd = cwd or pathlib.Path.cwd()

    if config_path is not None:
        return load_configs(
            [config_path],
            cwd=cwd,
            warn_legacy_options=warn_legacy_options,
        )

    sources = scopes.resolve_sources(cwd=cwd, include_project=include_project)
    by_path = {source.path: source for source in sources}
    state_file = scopes.trust_state_file()
    trusted = scopes.read_trusted(state_file)

    def gate(path: pathlib.Path, repos: Sequence[ConfigDict]) -> bool:
        source = by_path[path]
        escaping = scopes.requires_trust(
            source,
            repo_destinations(repos),
            cwd=cwd,
            trusted=trusted,
        )
        if not escaping:
            return True
        return _authorize_config(
            source,
            escaping,
            state_file=state_file,
            trust_project=trust_project,
        )

    return load_configs(
        [source.path for source in sources],
        cwd=cwd,
        warn_legacy_options=warn_legacy_options,
        gate=gate,
    )


def repo_destinations(repos: Iterable[ConfigDict]) -> list[pathlib.Path]:
    """Return where each entry would be checked out.

    ``path:`` overrides the workspace root, so this is the only honest answer
    to "where does this configuration write?".

    Examples
    --------
    >>> repo_destinations(
    ...     extract_repos(
    ...         {"./vendor/": {"evil": {"repo": "git+https://e.com/e.git",
    ...                                 "path": "~/.ssh/evil"}}},
    ...         cwd=pathlib.Path("/w"),
    ...     )
    ... )
    [PosixPath('~/.ssh/evil')]
    """
    return [pathlib.Path(repo["path"]) for repo in repos]


def source_escapes(
    source: scopes.ConfigSource,
    *,
    cwd: pathlib.Path,
) -> tuple[pathlib.Path, ...]:
    """Return the destinations *source* declares that need consent, if any.

    Never prompts and never raises, so a reporting command can ask the same
    question the loader does without changing anything.

    Parameters
    ----------
    source : scopes.ConfigSource
        Resolved configuration file.
    cwd : pathlib.Path
        Working directory, used to resolve relative destinations.
    """
    try:
        content, _duplicates, _items = DuplicateAwareConfigReader.load_with_duplicates(
            source.path,
        )
        destinations = repo_destinations(
            extract_repos(t.cast("RawConfigDict", content), cwd=cwd),
        )
    except Exception:
        # An unreadable config declares no destinations, so it cannot escape.
        # Let the caller's own load report the real parse error.
        return ()
    return scopes.requires_trust(
        source,
        destinations,
        cwd=cwd,
        trusted=scopes.read_trusted(scopes.trust_state_file()),
    )


def ensure_config_trusted(
    config_path: pathlib.Path,
    *,
    cwd: pathlib.Path | None = None,
    trust_project: bool = False,
    explicit: bool = False,
) -> bool:
    """Return whether a write command may target *config_path*.

    A repository that ships a configuration redirecting your writes deserves
    the same gate as one that redirects your clones, so ``add``, ``discover``,
    ``fmt``, and ``migrate`` ask this before touching a project file vcspull
    found on its own. Files that do not exist yet, and files outside the
    project scope, are always allowed.

    Naming a file with ``--file`` is consent, and *explicit* says so. The read
    path does not gate ``--file`` either — it replaces the stack rather than
    joining the project tier — and gating a reformat of a file you named while
    ``vcspull sync --file`` clones from it freely would be incoherent.

    Parameters
    ----------
    config_path : pathlib.Path
        File the command is about to read or rewrite.
    cwd : pathlib.Path, optional
        Working directory. Defaults to :meth:`pathlib.Path.cwd`.
    trust_project : bool
        Trust an escaping config without prompting (``--trust-project``).
    explicit : bool
        The caller named this file with ``--file``.

    Examples
    --------
    A file that does not exist yet is not a project config anybody shipped:

    >>> ensure_config_trusted(tmp_path / "brand-new.yaml", cwd=tmp_path)
    True
    """
    cwd = cwd or pathlib.Path.cwd()
    if explicit or not config_path.is_file():
        return True

    scope = scopes.classify_scope(
        config_path,
        cwd=cwd,
        home=pathlib.Path.home(),
    )
    if scope != "project":
        return True

    source = scopes.ConfigSource("project", config_path, config_path.parent)
    escaping = source_escapes(source, cwd=cwd)
    if not escaping:
        return True
    return _authorize_config(
        source,
        escaping,
        state_file=scopes.trust_state_file(),
        trust_project=trust_project,
    )


def _authorize_config(
    source: scopes.ConfigSource,
    escaping: Sequence[pathlib.Path],
    *,
    state_file: pathlib.Path,
    trust_project: bool,
) -> bool:
    """Ask whether an escaping project config may act, and remember ``always``.

    Raises
    ------
    exc.VCSPullException
        When there is no terminal to prompt on. A sync must never block on a
        hidden prompt, so this is a hard error rather than a silent skip.
    """
    config = PrivatePath(source.path)
    directory = PrivatePath(os.path.realpath(source.trust_root))

    if trust_project or scopes.env_flag("VCSPULL_YES"):
        log.debug("trusting %s without prompting", config)
        return True

    if not sys.stdin.isatty():
        listed = ", ".join(str(PrivatePath(path)) for path in escaping)
        msg = (
            f"{config} would check repositories out outside its directory "
            f"({listed}) and there is no terminal to confirm on. "
            f"Run 'vcspull trust {directory}' to allow it, pass "
            "--trust-project, or use --no-project to skip project configs."
        )
        raise exc.VCSPullException(msg)

    print(
        f"! {config} would check repositories out outside its directory:",
        file=sys.stderr,
    )
    for path in escaping:
        print(f"    {PrivatePath(path)}", file=sys.stderr)
    answer = input("  Trust this config? [y/N/always] ").strip().lower()

    if answer == "always":
        scopes.trust_directory(state_file, source.trust_root)
        return True
    if answer in {"y", "yes"}:
        return True

    log.warning("skipping untrusted config %s", config)
    return False


def detect_duplicate_repos(
    config1: list[ConfigDict],
    config2: list[ConfigDict],
) -> list[tuple[ConfigDict, ConfigDict]]:
    """Return duplicate repos dict if repo_dir same and vcs different.

    Parameters
    ----------
    config1 : list[ConfigDict]

    config2 : list[ConfigDict]

    Returns
    -------
    list[tuple[ConfigDict, ConfigDict]]
        List of duplicate tuples
    """
    if not config1:
        return []

    dupes: list[tuple[ConfigDict, ConfigDict]] = []

    repo_dirs = {
        pathlib.Path(repo["path"]).parent / repo["name"]: repo for repo in config1
    }
    repo_dirs_2 = {
        pathlib.Path(repo["path"]).parent / repo["name"]: repo for repo in config2
    }

    for repo_dir, repo in repo_dirs.items():
        if repo_dir in repo_dirs_2:
            dupes.append((repo, repo_dirs_2[repo_dir]))

    return dupes


def in_dir(
    config_dir: pathlib.Path | None = None,
    extensions: list[str] | None = None,
) -> list[str]:
    """Return a list of configs in ``config_dir``.

    Parameters
    ----------
    config_dir : str
        directory to search
    extensions : list
        filetypes to check (e.g. ``['.yaml', '.json']``).

    Returns
    -------
    list
    """
    if extensions is None:
        extensions = [".yml", ".yaml", ".json"]
    if config_dir is None:
        config_dir = get_config_dir()

    return [
        path.name
        for path in config_dir.iterdir()
        if is_config_file(path.name, extensions) and not path.name.startswith(".")
    ]


def filter_repos(
    config: list[ConfigDict],
    path: pathlib.Path | t.Literal["*"] | str | None = None,
    vcs_url: str | None = None,
    name: str | None = None,
) -> list[ConfigDict]:
    """Return a :py:obj:`list` list of repos from (expanded) config file.

    path, vcs_url and name all support fnmatch.

    Parameters
    ----------
    config : dict
        the expanded repo config in :py:class:`dict` format.
    path : str, Optional
        directory of checkout location, fnmatch pattern supported
    vcs_url : str, Optional
        url of vcs remote, fn match pattern supported
    name : str, Optional
        project name, fnmatch pattern supported

    Returns
    -------
    list :
        Repos
    """
    repo_list: list[ConfigDict] = []

    if path:
        repo_list.extend(
            [
                r
                for r in config
                if fnmatch.fnmatch(str(pathlib.Path(r["path"]).parent), str(path))
            ],
        )

    if vcs_url:
        repo_list.extend(
            r
            for r in config
            if fnmatch.fnmatch(str(r.get("url", r.get("repo"))), vcs_url)
        )

    if name:
        repo_list.extend(
            [r for r in config if fnmatch.fnmatch(str(r.get("name")), name)],
        )

    return repo_list


def is_config_file(
    filename: str,
    extensions: list[str] | str | None = None,
) -> bool:
    """Return True if file has a valid config file type.

    Parameters
    ----------
    filename : str
        filename to check (e.g. ``mysession.json``).
    extensions : list or str
        filetypes to check (e.g. ``['.yaml', '.json']``).

    Returns
    -------
    bool : True if is a valid config file type
    """
    if extensions is None:
        extensions = [".yml", ".yaml", ".json"]
    extensions = [extensions] if isinstance(extensions, str) else extensions
    return any(filename.endswith(e) for e in extensions)


def _atomic_write(target: pathlib.Path, content: str) -> None:
    """Write content to a file atomically via temp-file-then-rename.

    If *target* is a symbolic link the write goes through the symlink:
    the temporary file is created next to the resolved destination and
    the rename replaces the resolved path, leaving the symlink intact.

    Parameters
    ----------
    target : pathlib.Path
        Destination file path (may be a symlink)
    content : str
        Content to write

    Examples
    --------
    >>> import pathlib, tempfile
    >>> with tempfile.TemporaryDirectory() as tmp:
    ...     p = pathlib.Path(tmp) / "test.txt"
    ...     _atomic_write(p, "hello")
    ...     p.read_text(encoding="utf-8")
    'hello'

    Symlinks are preserved — the real target is updated:

    >>> with tempfile.TemporaryDirectory() as tmp:
    ...     real = pathlib.Path(tmp) / "real.txt"
    ...     _ = real.write_text("old", encoding="utf-8")
    ...     link = pathlib.Path(tmp) / "link.txt"
    ...     link.symlink_to(real)
    ...     _atomic_write(link, "new")
    ...     link.is_symlink(), link.read_text(encoding="utf-8")
    (True, 'new')
    """
    # Resolve symlinks so the temp file lives next to the real
    # destination and the rename replaces the real file, not the symlink.
    resolved = target.resolve()

    original_mode: int | None = None
    if resolved.exists():
        original_mode = resolved.stat().st_mode

    fd, tmp_path = tempfile.mkstemp(
        dir=resolved.parent,
        prefix=f".{resolved.name}.",
        suffix=".tmp",
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        if original_mode is not None:
            pathlib.Path(tmp_path).chmod(original_mode)
        pathlib.Path(tmp_path).replace(resolved)
    except BaseException:
        # Clean up the temp file on any failure
        with contextlib.suppress(OSError):
            pathlib.Path(tmp_path).unlink()
        raise


def save_config_yaml(config_file_path: pathlib.Path, data: dict[t.Any, t.Any]) -> None:
    """Save configuration data to a YAML file.

    Parameters
    ----------
    config_file_path : pathlib.Path
        Path to the configuration file to write
    data : dict
        Configuration data to save

    Examples
    --------
    >>> import pathlib, tempfile
    >>> with tempfile.TemporaryDirectory() as tmp:
    ...     p = pathlib.Path(tmp) / "cfg.yaml"
    ...     save_config_yaml(p, {"~/code/": {"myrepo": "git+https://example.com/repo.git"}})
    ...     "myrepo" in p.read_text(encoding="utf-8")
    True
    """
    yaml_content = ConfigReader._dump(
        fmt="yaml",
        content=data,
        indent=2,
    )
    _atomic_write(config_file_path, yaml_content)


def save_config_json(config_file_path: pathlib.Path, data: dict[t.Any, t.Any]) -> None:
    """Save configuration data to a JSON file.

    Parameters
    ----------
    config_file_path : pathlib.Path
        Path to the configuration file to write
    data : dict
        Configuration data to save

    Examples
    --------
    >>> import json, pathlib, tempfile
    >>> with tempfile.TemporaryDirectory() as tmp:
    ...     p = pathlib.Path(tmp) / "cfg.json"
    ...     save_config_json(p, {"~/code/": {"myrepo": "git+https://example.com/repo.git"}})
    ...     loaded = json.loads(p.read_text(encoding="utf-8"))
    ...     "~/code/" in loaded
    True
    """
    json_content = ConfigReader._dump(
        fmt="json",
        content=data,
        indent=2,
    )
    _atomic_write(config_file_path, json_content)


def detect_git_shallow(repo_path: pathlib.Path) -> bool:
    """Return whether a local git checkout is shallow.

    Uses ``git rev-parse --is-shallow-repository`` (git 2.15+), falling back to
    the presence of ``.git/shallow``. Any error (missing binary, non-git path)
    is treated as "not shallow".

    Parameters
    ----------
    repo_path : pathlib.Path
        Path to the local git repository.

    Returns
    -------
    bool
        ``True`` if the checkout is shallow, else ``False``.

    Examples
    --------
    A full clone is not shallow:

    >>> remote = create_git_remote_repo()
    >>> full = tmp_path / "full"
    >>> _ = subprocess.run(
    ...     ["git", "clone", f"file://{remote}", str(full)],
    ...     check=True, capture_output=True,
    ... )
    >>> detect_git_shallow(full)
    False

    A ``--depth 1`` clone is shallow:

    >>> shallow = tmp_path / "shallow"
    >>> _ = subprocess.run(
    ...     ["git", "clone", "--depth", "1", f"file://{remote}", str(shallow)],
    ...     check=True, capture_output=True,
    ... )
    >>> detect_git_shallow(shallow)
    True
    """
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_path), "rev-parse", "--is-shallow-repository"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return (repo_path / ".git" / "shallow").exists()

    return result.stdout.strip() == "true"


def detect_git_depth(repo_path: pathlib.Path) -> int | None:
    """Return the clone depth of a shallow git checkout, else ``None``.

    A full (non-shallow) checkout returns ``None``. A shallow checkout returns
    the number of commits reachable from ``HEAD`` (``git rev-list --count
    HEAD``), which equals the ``--depth`` used to clone a linear history. Any
    error (missing binary, non-git path, unparsable output) is treated as
    "cannot determine" and returns ``None``.

    Parameters
    ----------
    repo_path : pathlib.Path
        Path to the local git repository.

    Returns
    -------
    int | None
        Commit count of a shallow checkout, or ``None`` when full or unknown.

    Examples
    --------
    Seed a remote with enough history that a ``--depth 2`` clone is shallow:

    >>> remote = create_git_remote_repo()
    >>> for message in ("two", "three"):
    ...     _ = subprocess.run(
    ...         ["git", "-C", str(remote), "commit", "-q", "--allow-empty",
    ...          "-m", message],
    ...         check=True, capture_output=True,
    ...     )

    A full clone has no depth:

    >>> full = tmp_path / "full"
    >>> _ = subprocess.run(
    ...     ["git", "clone", f"file://{remote}", str(full)],
    ...     check=True, capture_output=True,
    ... )
    >>> detect_git_depth(full) is None
    True

    A ``--depth 2`` clone reports its depth:

    >>> shallow = tmp_path / "shallow"
    >>> _ = subprocess.run(
    ...     ["git", "clone", "--depth", "2", f"file://{remote}", str(shallow)],
    ...     check=True, capture_output=True,
    ... )
    >>> detect_git_depth(shallow)
    2
    """
    if not detect_git_shallow(repo_path):
        return None

    try:
        result = subprocess.run(
            ["git", "-C", str(repo_path), "rev-list", "--count", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None

    try:
        return int(result.stdout.strip())
    except ValueError:
        return None


def resolve_clone_depth(
    repo_path: pathlib.Path,
    *,
    explicit_shallow: bool = False,
    explicit_depth: int | None = None,
) -> tuple[bool, int | None]:
    """Resolve the ``(shallow, depth)`` to record for a checkout.

    Centralizes the precedence shared by ``add`` and ``discover`` so the two
    subcommands stay consistent. Precedence, highest first:

    1. ``explicit_depth`` (from ``--depth N``) → ``(False, explicit_depth)``.
    2. ``explicit_shallow`` (from ``--shallow``) → ``(True, None)``.
    3. Auto-detected depth (hybrid): a depth-1 checkout records ``shallow:
       true`` (the common case), depth > 1 records ``depth: N``, and a full
       checkout records neither.

    Parameters
    ----------
    repo_path : pathlib.Path
        Path to the local git checkout to inspect when auto-detecting.
    explicit_shallow : bool
        Whether ``--shallow`` was passed.
    explicit_depth : int | None
        Value of ``--depth N``, or ``None`` when not passed.

    Returns
    -------
    tuple[bool, int | None]
        ``(shallow, depth)`` to hand to :func:`build_repo_entry`.

    Examples
    --------
    Explicit flags win and never touch the filesystem:

    >>> resolve_clone_depth(tmp_path, explicit_depth=5)
    (False, 5)
    >>> resolve_clone_depth(tmp_path, explicit_shallow=True)
    (True, None)

    A path that is not a shallow checkout records neither:

    >>> resolve_clone_depth(tmp_path)
    (False, None)
    """
    if explicit_depth is not None:
        return False, explicit_depth
    if explicit_shallow:
        return True, None

    detected = detect_git_depth(repo_path)
    if detected is None:
        return False, None
    if detected <= 1:
        return True, None
    return False, detected


def build_repo_entry(
    url: str,
    *,
    rev: str | None = None,
    shallow: bool = False,
    depth: int | None = None,
) -> dict[str, t.Any]:
    """Build a raw per-repository config entry for ``add``/``discover``.

    Centralizes the entry shape written by both subcommands so the recorded
    keys stay consistent. Sync-tuning keys are nested under ``options:``;
    ``depth`` wins over ``shallow`` when both are supplied.

    Parameters
    ----------
    url : str
        VCS URL in vcspull format, e.g. ``git+https://github.com/u/r.git``.
    rev : str | None
        Commit, tag, or branch to pin via ``options.rev``. Omitted when falsy.
    shallow : bool
        If ``True``, record ``options.shallow: true`` (clone ``--depth 1``).
    depth : int | None
        If set, record ``options.depth: N`` (clone ``--depth N``).

    Returns
    -------
    dict
        Mapping ready to store under a workspace root in the config.

    Examples
    --------
    >>> build_repo_entry("git+https://github.com/u/r.git")
    {'repo': 'git+https://github.com/u/r.git'}

    >>> build_repo_entry("git+https://github.com/u/r.git", rev="v1.0.0")
    {'repo': 'git+https://github.com/u/r.git', 'options': {'rev': 'v1.0.0'}}

    >>> build_repo_entry("git+https://github.com/u/r.git", shallow=True)
    {'repo': 'git+https://github.com/u/r.git', 'options': {'shallow': True}}

    >>> build_repo_entry("git+https://github.com/u/r.git", depth=50)
    {'repo': 'git+https://github.com/u/r.git', 'options': {'depth': 50}}

    ``depth`` wins over ``shallow``:

    >>> build_repo_entry("git+https://github.com/u/r.git", shallow=True, depth=50)
    {'repo': 'git+https://github.com/u/r.git', 'options': {'depth': 50}}
    """
    entry: dict[str, t.Any] = {"repo": url}
    options: dict[str, t.Any] = {}
    if rev:
        options["rev"] = rev
    if depth:
        options["depth"] = depth
    elif shallow:
        options["shallow"] = True
    if options:
        entry["options"] = options
    return entry


#: Per-repository sync-tuning keys whose canonical home is the ``options:``
#: block. They were accepted at the entry root in v1.61.0; that form is now
#: deprecated and migrated by :func:`migrate_repo_entry`.
LEGACY_REPO_OPTION_KEYS = ("rev", "shallow", "depth")


def migrate_repo_entry(entry: t.Any) -> tuple[bool, t.Any]:
    """Relocate legacy top-level sync keys under ``options:``.

    Moves any top-level ``rev``/``shallow``/``depth`` into the entry's
    ``options:`` block. A value already present under ``options:`` wins, so the
    redundant top-level copy is simply dropped. When both ``shallow`` and a
    truthy ``depth`` end up under ``options:``, ``depth`` wins and ``shallow``
    is removed (matching how sync resolves precedence).

    Parameters
    ----------
    entry : Any
        A raw repository entry (string shorthand or mapping).

    Returns
    -------
    tuple[bool, Any]
        ``(changed, entry)``. ``changed`` is ``False`` (and the entry returned
        unchanged) for string shorthands and mappings with no legacy keys.

    Examples
    --------
    String shorthands and already-migrated entries are untouched:

    >>> migrate_repo_entry("git+ssh://x")
    (False, 'git+ssh://x')
    >>> migrate_repo_entry({"repo": "git+ssh://x"})
    (False, {'repo': 'git+ssh://x'})

    A legacy top-level key is relocated:

    >>> migrate_repo_entry({"repo": "git+ssh://x", "shallow": True})
    (True, {'repo': 'git+ssh://x', 'options': {'shallow': True}})

    ``depth`` wins over ``shallow`` in the migrated entry:

    >>> migrate_repo_entry(
    ...     {"repo": "git+ssh://x", "rev": "v1", "shallow": True, "depth": 5}
    ... )
    (True, {'repo': 'git+ssh://x', 'options': {'rev': 'v1', 'depth': 5}})
    """
    if not isinstance(entry, dict):
        return False, entry

    if not any(key in entry for key in LEGACY_REPO_OPTION_KEYS):
        return False, entry

    new_entry = copy.deepcopy(entry)
    options: dict[str, t.Any] = dict(new_entry.get("options") or {})
    for key in LEGACY_REPO_OPTION_KEYS:
        if key not in new_entry:
            continue
        value = new_entry.pop(key)
        options.setdefault(key, value)

    if options.get("depth"):
        options.pop("shallow", None)

    new_entry["options"] = options
    return True, new_entry


def detect_legacy_repo_options(raw_config: t.Any) -> list[tuple[str, str]]:
    """Return ``(workspace_label, repo_name)`` pairs using legacy top-level keys.

    Scans a raw (unexpanded) config mapping for repository entries that still
    carry top-level ``rev``/``shallow``/``depth`` instead of nesting them under
    ``options:``. Callers use the result to warn users to run ``vcspull
    migrate``.

    Parameters
    ----------
    raw_config : Any
        Raw config mapping (workspace root → repo name → entry).

    Returns
    -------
    list[tuple[str, str]]
        One ``(workspace_label, repo_name)`` pair per legacy entry.

    Examples
    --------
    >>> detect_legacy_repo_options(
    ...     {"~/code/": {"flask": {"repo": "git+x", "shallow": True}}}
    ... )
    [('~/code/', 'flask')]

    The canonical ``options:`` form is not flagged:

    >>> detect_legacy_repo_options(
    ...     {"~/code/": {"flask": {"repo": "git+x", "options": {"shallow": True}}}}
    ... )
    []
    """
    legacy: list[tuple[str, str]] = []
    if not isinstance(raw_config, dict):
        return legacy

    for workspace_label, repos in raw_config.items():
        if not isinstance(repos, dict):
            continue
        for repo_name, entry in repos.items():
            if isinstance(entry, dict) and any(
                key in entry for key in LEGACY_REPO_OPTION_KEYS
            ):
                legacy.append((str(workspace_label), str(repo_name)))

    return legacy


def save_config(config_file_path: pathlib.Path, data: dict[t.Any, t.Any]) -> None:
    """Save configuration data, dispatching by file extension.

    Parameters
    ----------
    config_file_path : pathlib.Path
        Path to the configuration file to write
    data : dict
        Configuration data to save

    Examples
    --------
    >>> import pathlib, tempfile, json
    >>> with tempfile.TemporaryDirectory() as tmp:
    ...     p = pathlib.Path(tmp) / "test.json"
    ...     save_config(p, {"~/code/": {"repo": {"repo": "git+https://x"}}})
    ...     loaded = json.loads(p.read_text(encoding="utf-8"))
    ...     loaded["~/code/"]["repo"]["repo"]
    'git+https://x'

    >>> with tempfile.TemporaryDirectory() as tmp:
    ...     p = pathlib.Path(tmp) / "test.yaml"
    ...     save_config(p, {"~/code/": {"repo": {"repo": "git+https://x"}}})
    ...     "repo" in p.read_text(encoding="utf-8")
    True
    """
    if config_format_from_path(config_file_path) == "json":
        save_config_json(config_file_path, data)
    else:
        save_config_yaml(config_file_path, data)


def save_config_yaml_with_items(
    config_file_path: pathlib.Path,
    items: list[tuple[str, t.Any]],
) -> None:
    """Persist configuration data while preserving duplicate top-level sections.

    Unlike :func:`save_config_yaml`, which loses duplicate keys when given a
    plain ``dict``, this function accepts ordered ``(label, data)`` pairs so
    that two workspace-root entries with the same key are each serialised as a
    separate YAML block.

    Parameters
    ----------
    config_file_path : pathlib.Path
        Destination config file (may be a symlink; the real target is updated).
    items : list of tuple[str, Any]
        Ordered ``(section_label, section_data)`` pairs. Each pair becomes one
        YAML document block in the output.

    Examples
    --------
    >>> import pathlib, tempfile
    >>> with tempfile.TemporaryDirectory() as tmp:
    ...     p = pathlib.Path(tmp) / "cfg.yaml"
    ...     save_config_yaml_with_items(p, [
    ...         ("~/code/", {"flask": "git+https://github.com/pallets/flask.git"}),
    ...         ("~/code/", {"django": "git+https://github.com/django/django.git"}),
    ...     ])
    ...     content = p.read_text(encoding="utf-8")
    ...     "flask" in content and "django" in content
    True
    """
    documents: list[str] = []

    for label, section in items:
        dumped = ConfigReader._dump(
            fmt="yaml",
            content={label: section},
            indent=2,
        ).rstrip()
        if dumped:
            documents.append(dumped)

    yaml_content = "\n".join(documents)
    if yaml_content:
        yaml_content += "\n"

    _atomic_write(config_file_path, yaml_content)


_VALID_OPS: frozenset[str] = frozenset({"import", "add", "discover", "fmt", "merge"})
"""Valid operation names for pin checking."""


def is_pinned_for_op(entry: t.Any, op: str) -> bool:
    """Return ``True`` if the repo config entry is pinned for *op*.

    Parameters
    ----------
    entry : Any
        Raw repo config value (string, dict, or ``None``).
    op : str
        Operation name: ``"import"``, ``"add"``, ``"discover"``,
        ``"fmt"``, or ``"merge"``.

    Examples
    --------
    Global pin applies to all ops:

    >>> is_pinned_for_op({"repo": "git+x", "options": {"pin": True}}, "import")
    True
    >>> is_pinned_for_op({"repo": "git+x", "options": {"pin": True}}, "fmt")
    True

    Per-op pin is scoped:

    >>> entry = {"repo": "git+x", "options": {"pin": {"import": True}}}
    >>> is_pinned_for_op(entry, "import")
    True
    >>> is_pinned_for_op(entry, "fmt")
    False

    ``allow_overwrite: false`` is shorthand for ``pin: {import: true}``
    (guards against ``--sync``):

    >>> entry2 = {"repo": "git+x", "options": {"allow_overwrite": False}}
    >>> is_pinned_for_op(entry2, "import")
    True
    >>> is_pinned_for_op(entry2, "add")
    False

    Plain string entries and entries without options are never pinned:

    >>> is_pinned_for_op("git+x", "import")
    False
    >>> is_pinned_for_op({"repo": "git+x"}, "import")
    False

    Explicit false is not pinned:

    >>> is_pinned_for_op({"repo": "git+x", "options": {"pin": False}}, "import")
    False

    String values for pin (not bool) are ignored — not pinned:

    >>> is_pinned_for_op({"repo": "git+x", "options": {"pin": "true"}}, "import")
    False

    Invalid op raises ValueError:

    >>> is_pinned_for_op(  # doctest: +IGNORE_EXCEPTION_DETAIL
    ...     {"repo": "git+x"}, "bogus"
    ... )
    Traceback (most recent call last):
        ...
    ValueError: Unknown op: 'bogus'
    """
    if op not in _VALID_OPS:
        msg = f"Unknown op: {op!r}"
        raise ValueError(msg)
    if not isinstance(entry, dict):
        return False
    opts = entry.get("options")
    if not isinstance(opts, dict):
        return False
    pin = opts.get("pin")
    if pin is True:
        return True
    if isinstance(pin, dict) and pin.get(op, False) is True:
        return True
    return op == "import" and opts.get("allow_overwrite", True) is False


def get_pin_reason(entry: t.Any) -> str | None:
    """Return the human-readable pin reason from a repo config entry.

    Non-string values are coerced to :func:`str` so callers can safely
    interpolate the result into log messages.

    Examples
    --------
    >>> entry = {"repo": "git+x", "options": {"pin": True, "pin_reason": "pinned"}}
    >>> get_pin_reason(entry)
    'pinned'
    >>> get_pin_reason({"repo": "git+x"}) is None
    True
    >>> get_pin_reason("git+x") is None
    True

    Non-string pin_reason is coerced:

    >>> get_pin_reason({"repo": "git+x", "options": {"pin_reason": 42}})
    '42'
    """
    if not isinstance(entry, dict):
        return None
    opts = entry.get("options")
    if not isinstance(opts, dict):
        return None
    reason = opts.get("pin_reason")
    if reason is None:
        return None
    return str(reason)


class MergeAction(enum.Enum):
    """Action for resolving a duplicate workspace-root repo conflict."""

    KEEP_EXISTING = "keep_existing"
    """First occurrence wins (standard behavior)."""

    KEEP_INCOMING = "keep_incoming"
    """Incoming pinned entry displaces unpinned existing entry."""


def _classify_merge_action(
    existing_entry: t.Any,
    incoming_entry: t.Any,
) -> MergeAction:
    """Classify the merge conflict resolution action.

    Parameters
    ----------
    existing_entry : Any
        The entry already stored (first occurrence).
    incoming_entry : Any
        The duplicate entry being merged in.

    Examples
    --------
    Neither pinned — keep existing (first-occurrence-wins):

    >>> _classify_merge_action({"repo": "git+a"}, {"repo": "git+b"})
    <MergeAction.KEEP_EXISTING: 'keep_existing'>

    Incoming is pinned — incoming wins:

    >>> _classify_merge_action(
    ...     {"repo": "git+a"},
    ...     {"repo": "git+b", "options": {"pin": True}},
    ... )
    <MergeAction.KEEP_INCOMING: 'keep_incoming'>

    Existing is pinned — existing wins regardless:

    >>> _classify_merge_action(
    ...     {"repo": "git+a", "options": {"pin": True}},
    ...     {"repo": "git+b"},
    ... )
    <MergeAction.KEEP_EXISTING: 'keep_existing'>

    Both pinned — first-occurrence-wins:

    >>> _classify_merge_action(
    ...     {"repo": "git+a", "options": {"pin": True}},
    ...     {"repo": "git+b", "options": {"pin": True}},
    ... )
    <MergeAction.KEEP_EXISTING: 'keep_existing'>
    """
    existing_pinned = is_pinned_for_op(existing_entry, "merge")
    incoming_pinned = is_pinned_for_op(incoming_entry, "merge")
    if incoming_pinned and not existing_pinned:
        return MergeAction.KEEP_INCOMING
    return MergeAction.KEEP_EXISTING


def merge_duplicate_workspace_root_entries(
    label: str,
    occurrences: list[t.Any],
) -> tuple[t.Any, list[str], int]:
    """Merge duplicate entries for a single workspace root."""
    conflicts: list[str] = []
    change_count = max(len(occurrences) - 1, 0)

    if not occurrences:
        return {}, conflicts, change_count

    if not all(isinstance(entry, dict) for entry in occurrences):
        conflicts.append(
            (
                f"Workspace root '{label}' contains duplicate entries that are not "
                "mappings. Keeping the last occurrence."
            ),
        )
        return occurrences[-1], conflicts, change_count

    merged: dict[str, t.Any] = {}

    for entry in occurrences:
        assert isinstance(entry, dict)
        for repo_name, repo_config in entry.items():
            if repo_name not in merged:
                merged[repo_name] = copy.deepcopy(repo_config)
            elif merged[repo_name] != repo_config:
                action = _classify_merge_action(merged[repo_name], repo_config)
                if action == MergeAction.KEEP_INCOMING:
                    merged[repo_name] = copy.deepcopy(repo_config)
                    reason = get_pin_reason(repo_config)
                    suffix = f" ({reason})" if reason else ""
                    conflicts.append(
                        f"'{label}': pinned entry for '{repo_name}'"
                        f" displaced earlier definition{suffix}"
                    )
                else:  # KEEP_EXISTING
                    reason = get_pin_reason(merged[repo_name])
                    qualifier = (
                        "pinned "
                        if is_pinned_for_op(merged[repo_name], "merge")
                        else ""
                    )
                    suffix = f" ({reason})" if reason else ""
                    conflicts.append(
                        f"'{label}': keeping {qualifier}entry for '{repo_name}'{suffix}"
                    )

    return merged, conflicts, change_count


def merge_duplicate_workspace_roots(
    config_data: dict[str, t.Any],
    duplicate_roots: dict[str, list[t.Any]],
) -> tuple[dict[str, t.Any], list[str], int, list[tuple[str, int]]]:
    """Merge duplicate workspace root sections captured during load."""
    if not duplicate_roots:
        return copy.deepcopy(config_data), [], 0, []

    merged_config = copy.deepcopy(config_data)
    conflicts: list[str] = []
    change_count = 0
    details: list[tuple[str, int]] = []

    for label, occurrences in duplicate_roots.items():
        (
            merged_value,
            entry_conflicts,
            entry_changes,
        ) = merge_duplicate_workspace_root_entries(
            label,
            occurrences,
        )
        merged_config[label] = merged_value
        conflicts.extend(entry_conflicts)
        change_count += entry_changes
        details.append((label, len(occurrences)))

    return merged_config, conflicts, change_count, details


def canonicalize_workspace_path(
    label: str,
    *,
    cwd: pathlib.Path | None = None,
) -> pathlib.Path:
    """Convert a workspace root label to an absolute canonical path."""
    cwd = cwd or pathlib.Path.cwd()
    label_path = pathlib.Path(label)
    return expand_dir(label_path, cwd=cwd)


def workspace_root_label(
    workspace_path: pathlib.Path,
    *,
    cwd: pathlib.Path | None = None,
    home: pathlib.Path | None = None,
    preserve_cwd_label: bool = True,
) -> str:
    """Create a normalized label for a workspace root path."""
    cwd = cwd or pathlib.Path.cwd()
    home = home or pathlib.Path.home()

    if preserve_cwd_label and workspace_path == cwd:
        return "./"

    if workspace_path == home:
        return "~/"

    try:
        relative_to_home = workspace_path.relative_to(home)
        label = f"~/{relative_to_home.as_posix()}"
    except ValueError:
        label = workspace_path.as_posix()

    if label != "./" and not label.endswith("/"):
        label += "/"

    return label


def normalize_workspace_roots(
    config_data: dict[str, t.Any],
    *,
    cwd: pathlib.Path | None = None,
    home: pathlib.Path | None = None,
    preserve_cwd_label: bool = True,
) -> tuple[dict[str, t.Any], dict[pathlib.Path, str], list[str], int]:
    """Normalize workspace root labels and merge duplicate sections."""
    cwd = cwd or pathlib.Path.cwd()
    home = home or pathlib.Path.home()

    normalized: dict[str, t.Any] = {}
    path_to_label: dict[pathlib.Path, str] = {}
    conflicts: list[str] = []
    change_count = 0

    for label, value in config_data.items():
        canonical_path = canonicalize_workspace_path(label, cwd=cwd)
        normalized_label = path_to_label.get(canonical_path)

        if normalized_label is None:
            normalized_label = workspace_root_label(
                canonical_path,
                cwd=cwd,
                home=home,
                preserve_cwd_label=preserve_cwd_label,
            )
            path_to_label[canonical_path] = normalized_label

            if isinstance(value, dict):
                normalized[normalized_label] = copy.deepcopy(value)
            else:
                normalized[normalized_label] = value

            if normalized_label != label:
                change_count += 1
        else:
            change_count += 1
            existing_value = normalized.get(normalized_label)

            if isinstance(existing_value, dict) and isinstance(value, dict):
                for repo_name, repo_config in value.items():
                    if repo_name not in existing_value:
                        existing_value[repo_name] = copy.deepcopy(repo_config)
                        change_count += 1
                    elif existing_value[repo_name] != repo_config:
                        conflict_message = (
                            f"Workspace root '{label}' contains conflicting "
                            "definitions for repository '{repo}'. Keeping the existing "
                            "entry."
                        )
                        conflicts.append(
                            conflict_message.format(
                                label=normalized_label,
                                repo=repo_name,
                            ),
                        )
            elif existing_value != value:
                conflict_message = (
                    f"Workspace root '{label}' contains conflicting non-dictionary "
                    "values. Keeping the existing entry."
                )
                conflicts.append(conflict_message.format(label=normalized_label))

    return normalized, path_to_label, conflicts, change_count
