"""Repository operations API for VCSPull.

This module provides high-level functions for working with repositories,
including synchronizing, detecting, and managing repositories.
"""

from __future__ import annotations

import concurrent.futures
import typing as t
from pathlib import Path

from vcspull._internal import logger
from vcspull.config.models import Repository, VCSPullConfig
from vcspull.vcs import get_vcs_handler


def sync_repositories(
    config: VCSPullConfig,
    paths: list[str] | None = None,
    parallel: bool = True,
    max_workers: int | None = None,
) -> dict[str, bool]:
    """Synchronize repositories based on configuration.

    Parameters
    ----------
    config : VCSPullConfig
        The configuration containing repositories to sync
    paths : list[str] | None, optional
        List of specific repository paths to sync, by default None (all repositories)
    parallel : bool, optional
        Whether to sync repositories in parallel, by default True
    max_workers : int | None, optional
        Maximum number of worker threads when parallel is True, by default None
        (uses default ThreadPoolExecutor behavior)

    Returns
    -------
    dict[str, bool]
        Dictionary mapping repository paths to sync success status
    """
    repositories = config.repositories

    # Filter repositories if paths are specified
    if paths:
        # Convert path strings to Path objects for samefile comparison
        path_objects = [Path(p).expanduser().resolve() for p in paths]
        filtered_repos = []

        for repo in repositories:
            repo_path = Path(repo.path)
            for path in path_objects:
                try:
                    if repo_path.samefile(path):
                        filtered_repos.append(repo)
                        break
                except FileNotFoundError:
                    # Skip if either path doesn't exist
                    continue

        repositories = filtered_repos

    results: dict[str, bool] = {}

    if parallel and len(repositories) > 1:
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_repo = {
                executor.submit(_sync_single_repository, repo, config.settings): repo
                for repo in repositories
            }

            for future in concurrent.futures.as_completed(future_to_repo):
                repo = future_to_repo[future]
                try:
                    results[repo.path] = future.result()
                except Exception as e:
                    error_msg = str(e)
                    logger.error(f"Error syncing {repo.path}: {error_msg}")
                    results[repo.path] = False
    else:
        # Sequential sync - handle exceptions outside the loop to avoid PERF203
        for repo in repositories:
            results[repo.path] = False  # Default status

        for repo in repositories:
            try:
                results[repo.path] = _sync_single_repository(repo, config.settings)
            except Exception as e:
                error_msg = str(e)
                logger.error(f"Error syncing {repo.path}: {error_msg}")
                # Status already set to False by default

    return results


def _sync_single_repository(
    repo: Repository,
    settings: t.Any,
) -> bool:
    """Synchronize a single repository.

    Parameters
    ----------
    repo : Repository
        Repository to synchronize
    settings : t.Any
        Global settings to use

    Returns
    -------
    bool
        Success status of the sync operation
    """
    repo_path = Path(repo.path)
    vcs_type = repo.vcs or settings.default_vcs

    if vcs_type is None:
        logger.error(f"No VCS type specified for repository: {repo.path}")
        return False

    try:
        handler = get_vcs_handler(vcs_type, repo_path, repo.url)

        # Determine if repository exists
        if repo_path.exists() and handler.is_repo():
            logger.info(f"Updating existing repository: {repo.path}")
            handler.update()

            # Handle remotes if any
            if settings.sync_remotes and repo.remotes:
                for remote_name, remote_url in repo.remotes.items():
                    handler.set_remote(remote_name, remote_url)
                    handler.update_remote(remote_name)

            # Update to specified revision if provided
            if repo.rev:
                handler.update_to_rev(repo.rev)

            return True
        # Repository doesn't exist, create it
        logger.info(f"Obtaining new repository: {repo.path}")
        handler.obtain(depth=settings.depth)

        # Add remotes
        if repo.remotes:
            for remote_name, remote_url in repo.remotes.items():
                handler.set_remote(remote_name, remote_url)

        # Update to specified revision if provided
        if repo.rev:
            handler.update_to_rev(repo.rev)

        return True
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Failed to sync repository {repo.path}: {error_msg}")
        return False


def detect_repositories(
    directories: list[str | Path],
    recursive: bool = False,
    depth: int = 2,
) -> list[Repository]:
    """Detect VCS repositories in the specified directories.

    Parameters
    ----------
    directories : list[str | Path]
        Directories to search for repositories
    recursive : bool, optional
        Whether to search recursively, by default False
    depth : int, optional
        Maximum directory depth to search when recursive is True, by default 2

    Returns
    -------
    list[Repository]
        List of detected repositories
    """
    detected_repos: list[Repository] = []

    for directory in directories:
        directory_path = Path(directory).expanduser().resolve()

        if not directory_path.exists() or not directory_path.is_dir():
            logger.warning(f"Directory does not exist: {directory}")
            continue

        _detect_repositories_in_dir(
            directory_path,
            detected_repos,
            recursive=recursive,
            current_depth=1,
            max_depth=depth,
        )

    return detected_repos


def _detect_repositories_in_dir(
    directory: Path,
    result_list: list[Repository],
    recursive: bool = False,
    current_depth: int = 1,
    max_depth: int = 2,
) -> None:
    """Search for repositories in a directory.

    Parameters
    ----------
    directory : Path
        Directory to search
    result_list : list[Repository]
        List to store found repositories
    recursive : bool, optional
        Whether to search recursively, by default False
    current_depth : int, optional
        Current recursion depth, by default 1
    max_depth : int, optional
        Maximum recursion depth, by default 2
    """
    # Check if the current directory is a repository
    for vcs_type in ["git", "hg", "svn"]:
        if _is_vcs_directory(directory, vcs_type):
            # Found a repository
            try:
                remote_url = _get_remote_url(directory, vcs_type)
                repo = Repository(
                    name=directory.name,
                    url=remote_url or "",
                    path=str(directory),
                    vcs=vcs_type,
                )
                result_list.append(repo)
            except Exception as e:
                error_msg = str(e)
                logger.warning(
                    f"Error detecting repository in {directory}: {error_msg}",
                )

            # Don't search subdirectories of a repository
            return

    # Recursively search subdirectories if requested
    if recursive and current_depth <= max_depth:
        for subdir in directory.iterdir():
            if subdir.is_dir() and not subdir.name.startswith("."):
                _detect_repositories_in_dir(
                    subdir,
                    result_list,
                    recursive=recursive,
                    current_depth=current_depth + 1,
                    max_depth=max_depth,
                )


def _is_vcs_directory(directory: Path, vcs_type: str) -> bool:
    """Check if a directory is a VCS repository.

    Parameters
    ----------
    directory : Path
        Directory to check
    vcs_type : str
        VCS type to check for

    Returns
    -------
    bool
        True if the directory is a repository of the specified type
    """
    if vcs_type == "git":
        return (directory / ".git").exists()
    if vcs_type == "hg":
        return (directory / ".hg").exists()
    if vcs_type == "svn":
        return (directory / ".svn").exists()
    return False


def _get_remote_url(directory: Path, vcs_type: str) -> str | None:
    """Get the remote URL for a repository.

    Parameters
    ----------
    directory : Path
        Repository directory
    vcs_type : str
        VCS type of the repository

    Returns
    -------
    str | None
        Remote URL if found, None otherwise
    """
    try:
        handler = get_vcs_handler(vcs_type, directory, "")
        return handler.get_remote_url()
    except Exception:
        return None
