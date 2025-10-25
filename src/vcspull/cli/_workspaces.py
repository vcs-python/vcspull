"""Workspace filtering helpers for vcspull CLI."""

from __future__ import annotations

import fnmatch
import pathlib
import typing as t

from vcspull.config import canonicalize_workspace_path, workspace_root_label

if t.TYPE_CHECKING:
    from vcspull.types import ConfigDict


def _normalize_workspace_label(
    workspace_root: str,
    *,
    cwd: pathlib.Path,
    home: pathlib.Path,
) -> str:
    canonical_path = canonicalize_workspace_path(workspace_root, cwd=cwd)
    return workspace_root_label(canonical_path, cwd=cwd, home=home)


def _repo_workspace_label(
    repo: ConfigDict,
    *,
    cwd: pathlib.Path,
    home: pathlib.Path,
) -> str:
    raw_label = repo.get("workspace_root")
    if raw_label:
        return _normalize_workspace_label(str(raw_label), cwd=cwd, home=home)

    repo_path = pathlib.Path(repo["path"]).expanduser()
    return workspace_root_label(repo_path.parent, cwd=cwd, home=home)


def filter_by_workspace(
    repos: list[ConfigDict],
    workspace_root: str | None,
    *,
    cwd: pathlib.Path | None = None,
    home: pathlib.Path | None = None,
) -> list[ConfigDict]:
    """Filter repositories by workspace root pattern."""
    if not workspace_root:
        return repos

    cwd = cwd or pathlib.Path.cwd()
    home = home or pathlib.Path.home()

    normalized_filter = _normalize_workspace_label(
        workspace_root,
        cwd=cwd,
        home=home,
    )
    has_glob = any(char in workspace_root for char in "*?[]")

    filtered: list[ConfigDict] = []
    for repo in repos:
        repo_label = _repo_workspace_label(repo, cwd=cwd, home=home)
        if has_glob:
            if fnmatch.fnmatch(repo_label, workspace_root) or fnmatch.fnmatch(
                repo_label,
                normalized_filter,
            ):
                filtered.append(repo)
        elif repo_label == normalized_filter:
            filtered.append(repo)
    return filtered
