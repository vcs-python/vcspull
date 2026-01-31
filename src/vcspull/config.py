"""Configuration functionality for vcspull."""

from __future__ import annotations

import contextlib
import copy
import fnmatch
import logging
import os
import pathlib
import tempfile
import typing as t
from collections.abc import Callable

from libvcs.sync.git import GitRemote

from vcspull.validator import is_valid_config

from . import exc
from ._internal.config_reader import ConfigReader, DuplicateAwareConfigReader
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

        # Validate exactly one ref type
        tag = wt.get("tag")
        branch = wt.get("branch")
        commit = wt.get("commit")

        refs_specified = sum(1 for ref in [tag, branch, commit] if ref is not None)

        if refs_specified == 0:
            msg = (
                f"Repository '{repo_name}': worktree entry {idx} "
                "must specify one of: tag, branch, or commit"
            )
            raise exc.VCSPullException(msg)
        if refs_specified > 1:
            msg = (
                f"Repository '{repo_name}': worktree entry {idx} "
                "cannot specify multiple refs (tag, branch, commit)"
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
    """Return configs of ``.vcspull.{yaml,json}`` in user's home directory."""
    if filetype is None:
        filetype = ["json", "yaml"]
    configs: list[pathlib.Path] = []

    check_yaml = "yaml" in filetype
    check_json = "json" in filetype

    yaml_config = pathlib.Path("~/.vcspull.yaml").expanduser()
    has_yaml_config = check_yaml and yaml_config.exists()
    json_config = pathlib.Path("~/.vcspull.json").expanduser()
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
    filetype: t.Literal["json", "yaml", "*"]
    | list[t.Literal["json", "yaml", "*"]]
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
        filetype = ["json", "yaml"]
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
            return config_files
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


def load_configs(
    files: list[pathlib.Path],
    cwd: pathlib.Path | Callable[[], pathlib.Path] = pathlib.Path.cwd,
    *,
    merge_duplicates: bool = True,
) -> list[ConfigDict]:
    """Return repos from a list of files.

    Parameters
    ----------
    files : list
        paths to config file
    cwd : pathlib.Path
        current path (pass down for :func:`extract_repos`

    Returns
    -------
    list of dict :
        expanded config dict item

    Todo
    ----
    Validate scheme, check for duplicate destinations, VCS urls
    """
    repos: list[ConfigDict] = []
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

        assert is_valid_config(config_content)
        newrepos = extract_repos(config_content, cwd=cwd)

        if not repos:
            repos.extend(newrepos)
            continue

        dupes = detect_duplicate_repos(repos, newrepos)

        if len(dupes) > 0:
            msg = ("repos with same path + different VCS detected!", dupes)
            raise exc.VCSPullException(msg)
        repos.extend(newrepos)

    return repos


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

    Parameters
    ----------
    target : pathlib.Path
        Destination file path
    content : str
        Content to write
    """
    original_mode: int | None = None
    if target.exists():
        original_mode = target.stat().st_mode

    fd, tmp_path = tempfile.mkstemp(
        dir=target.parent,
        prefix=f".{target.name}.",
        suffix=".tmp",
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        if original_mode is not None:
            pathlib.Path(tmp_path).chmod(original_mode)
        pathlib.Path(tmp_path).replace(target)
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
    """
    json_content = ConfigReader._dump(
        fmt="json",
        content=data,
        indent=2,
    )
    _atomic_write(config_file_path, json_content)


def save_config_yaml_with_items(
    config_file_path: pathlib.Path,
    items: list[tuple[str, t.Any]],
) -> None:
    """Persist configuration data while preserving duplicate top-level sections."""
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
                conflicts.append(
                    (
                        f"Workspace root '{label}' contains conflicting definitions "
                        f"for repository '{repo_name}'. Keeping the existing entry."
                    ),
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
