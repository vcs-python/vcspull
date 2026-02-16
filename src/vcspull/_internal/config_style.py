"""Central config output formatting for vcspull.

All commands that *write* configuration entries (``add``, ``discover``,
``import``, ``fmt``) delegate to the functions here so that the output
style (concise / standard / verbose) is controlled in one place.
"""

from __future__ import annotations

import logging
import pathlib
import subprocess
import typing as t

from vcspull.types import ConfigStyle, RawRepoEntry

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _infer_vcs_from_url(url: str) -> str | None:
    """Extract the VCS type from a prefixed URL.

    Parameters
    ----------
    url : str
        Repository URL, optionally prefixed (e.g. ``"git+https://..."``).

    Returns
    -------
    str | None
        ``"git"``, ``"hg"``, ``"svn"``, or ``None`` when no prefix is found.

    Examples
    --------
    >>> _infer_vcs_from_url("git+https://github.com/user/repo.git")
    'git'
    >>> _infer_vcs_from_url("hg+https://hg.example.com/repo")
    'hg'
    >>> _infer_vcs_from_url("https://github.com/user/repo.git") is None
    True
    """
    for prefix in ("git+", "hg+", "svn+"):
        if url.startswith(prefix):
            return prefix[:-1]
    return None


def _strip_vcs_prefix(url: str) -> str:
    """Remove a VCS prefix from a URL.

    Parameters
    ----------
    url : str
        Repository URL, optionally prefixed (e.g. ``"git+https://..."``).

    Returns
    -------
    str
        URL without VCS prefix.

    Examples
    --------
    >>> _strip_vcs_prefix("git+https://github.com/user/repo.git")
    'https://github.com/user/repo.git'
    >>> _strip_vcs_prefix("https://github.com/user/repo.git")
    'https://github.com/user/repo.git'
    """
    for prefix in ("git+", "hg+", "svn+"):
        if url.startswith(prefix):
            return url[len(prefix) :]
    return url


def _read_git_remotes(repo_path: pathlib.Path) -> dict[str, str] | None:
    """Read git remote names and URLs from a local repository.

    Parameters
    ----------
    repo_path : pathlib.Path
        Path to a git working tree.

    Returns
    -------
    dict[str, str] | None
        Mapping of remote name to fetch URL, or ``None`` on failure.

    Examples
    --------
    >>> import pathlib
    >>> _read_git_remotes(pathlib.Path("/nonexistent")) is None
    True
    """
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_path), "remote", "-v"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return None

    remotes: dict[str, str] = {}
    for line in result.stdout.splitlines():
        parts = line.split()
        if len(parts) >= 2 and line.endswith("(fetch)"):
            remotes[parts[0]] = parts[1]
    return remotes or None


def _extract_url(repo_data: RawRepoEntry) -> str:
    """Get the URL from any entry form.

    Parameters
    ----------
    repo_data : str | dict
        Repository entry in any style.

    Returns
    -------
    str
        The repository URL.

    Examples
    --------
    >>> _extract_url("git+https://github.com/user/repo.git")
    'git+https://github.com/user/repo.git'
    >>> _extract_url({"repo": "git+https://github.com/user/repo.git"})
    'git+https://github.com/user/repo.git'
    """
    if isinstance(repo_data, str):
        return repo_data
    return str(repo_data.get("repo") or repo_data.get("url", ""))


def _has_extra_keys(repo_data: RawRepoEntry) -> bool:
    """Check whether a dict entry has keys beyond ``repo`` / ``url``.

    Parameters
    ----------
    repo_data : str | dict
        Repository entry.

    Returns
    -------
    bool
        ``True`` when the entry carries additional metadata.

    Examples
    --------
    >>> _has_extra_keys("git+https://github.com/user/repo.git")
    False
    >>> _has_extra_keys({"repo": "url"})
    False
    >>> _has_extra_keys({"repo": "url", "shell_command_after": "make"})
    True
    """
    if isinstance(repo_data, str):
        return False
    return bool(set(repo_data.keys()) - {"repo", "url"})


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def format_repo_entry(
    url: str,
    *,
    style: ConfigStyle,
    existing_remotes: dict[str, str] | None = None,
    repo_path: pathlib.Path | None = None,
) -> RawRepoEntry:
    """Create a single repository config entry in the requested style.

    Parameters
    ----------
    url : str
        The full repository URL (e.g. ``"git+https://..."``).
    style : ConfigStyle
        Desired output style.
    existing_remotes : dict[str, str] | None
        Pre-fetched remote mapping; skips ``git remote -v`` when provided.
    repo_path : pathlib.Path | None
        Local clone path, used to read remotes for :attr:`ConfigStyle.VERBOSE`.

    Returns
    -------
    str | dict
        ``str`` for concise, ``dict`` for standard / verbose.

    Examples
    --------
    >>> from vcspull.types import ConfigStyle
    >>> format_repo_entry("git+https://github.com/u/r.git", style=ConfigStyle.CONCISE)
    'git+https://github.com/u/r.git'
    >>> entry = format_repo_entry(
    ...     "git+https://github.com/u/r.git", style=ConfigStyle.STANDARD
    ... )
    >>> entry == {"repo": "git+https://github.com/u/r.git"}
    True
    """
    if style is ConfigStyle.CONCISE:
        return url

    if style is ConfigStyle.STANDARD:
        return {"repo": url}

    # VERBOSE
    entry: dict[str, t.Any] = {"repo": url}

    vcs = _infer_vcs_from_url(url)
    if vcs is not None:
        entry["vcs"] = vcs

    remotes = existing_remotes
    if remotes is None and repo_path is not None:
        remotes = _read_git_remotes(repo_path)
    if remotes is None:
        bare_url = _strip_vcs_prefix(url)
        remotes = {"origin": bare_url}

    entry["remotes"] = remotes
    return entry


def restyle_repo_entry(
    repo_name: str,
    repo_data: RawRepoEntry,
    *,
    style: ConfigStyle,
    repo_path: pathlib.Path | None = None,
) -> tuple[RawRepoEntry, list[str]]:
    """Convert an existing entry to a different style.

    Parameters
    ----------
    repo_name : str
        Name of the repository (for warning messages).
    repo_data : str | dict
        Current entry value.
    style : ConfigStyle
        Target output style.
    repo_path : pathlib.Path | None
        Local clone path, used for verbose remote reading.

    Returns
    -------
    tuple[str | dict, list[str]]
        The restyled entry and a list of warning messages (may be empty).

    Examples
    --------
    >>> from vcspull.types import ConfigStyle
    >>> entry, warns = restyle_repo_entry(
    ...     "myrepo", {"repo": "git+https://github.com/u/r.git"},
    ...     style=ConfigStyle.CONCISE,
    ... )
    >>> entry
    'git+https://github.com/u/r.git'
    >>> warns
    []
    """
    warnings: list[str] = []
    url = _extract_url(repo_data)

    if style is ConfigStyle.CONCISE:
        if _has_extra_keys(repo_data):
            warnings.append(
                f"'{repo_name}' has extra keys that would be lost in concise "
                f"style; keeping original entry"
            )
            return repo_data, warnings
        return url, warnings

    if style is ConfigStyle.STANDARD:
        if isinstance(repo_data, dict) and _has_extra_keys(repo_data):
            normalized = dict(repo_data)
            if "url" in normalized and "repo" not in normalized:
                normalized["repo"] = normalized.pop("url")
            return normalized, warnings
        return {"repo": url}, warnings

    # VERBOSE
    existing_remotes: dict[str, str] | None = None
    if isinstance(repo_data, dict) and "remotes" in repo_data:
        raw_remotes = repo_data["remotes"]
        if isinstance(raw_remotes, dict):
            existing_remotes = {
                k: v for k, v in raw_remotes.items() if isinstance(v, str)
            }

    entry = format_repo_entry(
        url,
        style=ConfigStyle.VERBOSE,
        existing_remotes=existing_remotes,
        repo_path=repo_path,
    )

    if isinstance(repo_data, dict) and isinstance(entry, dict):
        for key, value in repo_data.items():
            if key not in entry:
                entry[key] = value

    return entry, warnings


def apply_config_style(
    config_data: dict[str, t.Any],
    *,
    style: ConfigStyle,
    base_dirs: dict[str, pathlib.Path] | None = None,
) -> tuple[dict[str, t.Any], int, list[str]]:
    """Restyle all entries in a full config dict.

    Parameters
    ----------
    config_data : dict
        Full vcspull configuration mapping.
    style : ConfigStyle
        Target output style.
    base_dirs : dict[str, pathlib.Path] | None
        Optional mapping of workspace labels to resolved filesystem paths,
        used to locate repo clones for verbose remote reading.

    Returns
    -------
    tuple[dict, int, list[str]]
        The restyled configuration, count of changed entries, and warnings.

    Examples
    --------
    >>> from vcspull.types import ConfigStyle
    >>> cfg = {"~/code/": {"flask": "git+https://github.com/pallets/flask.git"}}
    >>> styled, count, warns = apply_config_style(cfg, style=ConfigStyle.STANDARD)
    >>> styled["~/code/"]["flask"]
    {'repo': 'git+https://github.com/pallets/flask.git'}
    >>> count
    1
    """
    result: dict[str, t.Any] = {}
    change_count = 0
    all_warnings: list[str] = []

    for workspace_label, repos in config_data.items():
        if not isinstance(repos, dict):
            result[workspace_label] = repos
            continue

        result_section: dict[str, t.Any] = {}
        for repo_name, repo_data in repos.items():
            repo_path: pathlib.Path | None = None
            if base_dirs and workspace_label in base_dirs:
                repo_path = base_dirs[workspace_label] / repo_name

            new_entry, warnings = restyle_repo_entry(
                repo_name,
                repo_data,
                style=style,
                repo_path=repo_path,
            )
            all_warnings.extend(warnings)

            if new_entry != repo_data:
                change_count += 1

            result_section[repo_name] = new_entry

        result[workspace_label] = result_section

    return result, change_count, all_warnings
