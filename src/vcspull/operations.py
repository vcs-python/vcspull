"""Repository operations API for VCSPull.

This module provides high-level functions for working with repositories,
including synchronizing, detecting, and managing repositories.
"""

from __future__ import annotations

import concurrent.futures
import json
import typing as t
from pathlib import Path

import yaml

from vcspull._internal import logger
from vcspull.config.models import LockedRepository, LockFile, Repository, VCSPullConfig
from vcspull.vcs import get_vcs_handler
from vcspull.vcs.base import get_vcs_handler as get_vcs_interface


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
            # Moved exception handling outside the loop using a function
            _process_single_repo(repo, results, config.settings)

    return results


def _process_single_repo(
    repo: Repository,
    results: dict[str, bool],
    settings: t.Any,
) -> None:
    """Process a single repository for syncing, with exception handling.

    Parameters
    ----------
    repo : Repository
        Repository to sync
    results : dict[str, bool]
        Results dictionary to update
    settings : t.Any
        Settings to use for syncing
    """
    try:
        results[repo.path] = _sync_single_repository(repo, settings)
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error syncing {repo.path}: {error_msg}")
        # Status already set to False by default


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
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Failed to sync repository {repo.path}: {error_msg}")
        return False
    return True


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


def lock_repositories(
    config: VCSPullConfig,
    output_path: str | Path,
    paths: list[str] | None = None,
    parallel: bool = True,
    max_workers: int | None = None,
) -> LockFile:
    """Lock repositories to their current revisions.

    Parameters
    ----------
    config : VCSPullConfig
        The configuration containing repositories to lock
    output_path : str | Path
        Path to save the lock file
    paths : list[str] | None, optional
        List of specific repository paths to lock, by default None (all repositories)
    parallel : bool, optional
        Whether to process repositories in parallel, by default True
    max_workers : int | None, optional
        Maximum number of worker threads when parallel is True, by default None
        (uses default ThreadPoolExecutor behavior)

    Returns
    -------
    LockFile
        The lock file with locked repositories
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

    lock_file = LockFile()

    if parallel and len(repositories) > 1:
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_repo = {
                executor.submit(_lock_single_repository, repo): repo
                for repo in repositories
            }

            for future in concurrent.futures.as_completed(future_to_repo):
                repo = future_to_repo[future]
                try:
                    locked_repo = future.result()
                    if locked_repo:
                        lock_file.repositories.append(locked_repo)
                except Exception as e:
                    error_msg = str(e)
                    logger.error(f"Error locking {repo.path}: {error_msg}")
    else:
        for repo in repositories:
            _process_single_lock(repo, lock_file)

    # Save the lock file
    output_path_obj = Path(output_path).expanduser().resolve()
    output_path_obj.parent.mkdir(parents=True, exist_ok=True)

    with output_path_obj.open("w") as f:
        json.dump(lock_file.model_dump(), f, indent=2, default=str)

    logger.info(f"Saved lock file to {output_path_obj}")
    return lock_file


def _process_single_lock(repo: Repository, lock_file: LockFile) -> None:
    """Process a single repository for locking, with exception handling.

    Parameters
    ----------
    repo : Repository
        Repository to lock
    lock_file : LockFile
        Lock file to update
    """
    try:
        locked_repo = _lock_single_repository(repo)
        if locked_repo:
            lock_file.repositories.append(locked_repo)
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error locking {repo.path}: {error_msg}")


def _lock_single_repository(repo: Repository) -> LockedRepository | None:
    """Lock a single repository to its current revision.

    Parameters
    ----------
    repo : Repository
        The repository to lock

    Returns
    -------
    LockedRepository | None
        The locked repository information, or None if locking failed
    """
    try:
        logger.info(f"Locking repository: {repo.path}")

        # Need to determine repository type if not specified
        vcs_type = repo.vcs
        if vcs_type is None:
            # Try to detect VCS type from directory structure
            path = Path(repo.path)
            for vcs in ["git", "hg", "svn"]:
                if _is_vcs_directory(path, vcs):
                    vcs_type = vcs
                    break

            if vcs_type is None:
                logger.error(f"Could not determine VCS type for {repo.path}")
                return None

        # Get VCS handler for the repository
        handler = get_vcs_interface(repo)

        # Get the current revision
        current_rev = handler.get_revision()

        if not current_rev:
            logger.error(f"Could not determine current revision for {repo.path}")
            return None

        # Create locked repository object
        locked_repo = LockedRepository(
            name=repo.name,
            path=repo.path,
            vcs=vcs_type,
            url=repo.url,
            rev=current_rev,
        )

        logger.info(f"Locked {repo.path} at revision {current_rev}")
    except Exception as e:
        logger.error(f"Error locking repository {repo.path}: {e}")
        return None
    return locked_repo


def apply_lock(
    lock_file_path: str | Path,
    paths: list[str] | None = None,
    parallel: bool = True,
    max_workers: int | None = None,
) -> dict[str, bool]:
    """Apply a lock file to set repositories to specific revisions.

    Parameters
    ----------
    lock_file_path : str | Path
        Path to the lock file
    paths : list[str] | None, optional
        List of specific repository paths to apply lock to,
        by default None (all repositories)
    parallel : bool, optional
        Whether to process repositories in parallel, by default True
    max_workers : int | None, optional
        Maximum number of worker threads when parallel is True, by default None
        (uses default ThreadPoolExecutor behavior)

    Returns
    -------
    dict[str, bool]
        Dictionary mapping repository paths to apply success status
    """
    lock_file_path_obj = Path(lock_file_path).expanduser().resolve()

    if not lock_file_path_obj.exists():
        error_msg = f"Lock file not found: {lock_file_path}"
        raise FileNotFoundError(error_msg)

    # Load the lock file
    with lock_file_path_obj.open("r") as f:
        if lock_file_path_obj.suffix in {".yaml", ".yml"}:
            lock_data = yaml.safe_load(f)
        else:
            lock_data = json.load(f)

    lock_file = LockFile.model_validate(lock_data)
    repositories = lock_file.repositories

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
                executor.submit(_apply_lock_to_repository, repo): repo
                for repo in repositories
            }

            for future in concurrent.futures.as_completed(future_to_repo):
                repo = future_to_repo[future]
                try:
                    results[repo.path] = future.result()
                except Exception as e:
                    error_msg = str(e)
                    logger.error(f"Error applying lock to {repo.path}: {error_msg}")
                    results[repo.path] = False
    else:
        for repo in repositories:
            _process_single_apply_lock(repo, results)

    return results


def _process_single_apply_lock(
    repo: LockedRepository,
    results: dict[str, bool],
) -> None:
    """Process a single repository for applying lock, with exception handling.

    Parameters
    ----------
    repo : LockedRepository
        Repository to apply lock to
    results : dict[str, bool]
        Results dictionary to update
    """
    try:
        results[repo.path] = _apply_lock_to_repository(repo)
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error applying lock to {repo.path}: {error_msg}")
        results[repo.path] = False


def _apply_lock_to_repository(repo: LockedRepository) -> bool:
    """Apply a lock to a single repository.

    Parameters
    ----------
    repo : LockedRepository
        The locked repository to apply

    Returns
    -------
    bool
        Whether the lock was successfully applied
    """
    try:
        logger.info(f"Applying lock to repository: {repo.path} (revision: {repo.rev})")

        # Create a Repository object from the LockedRepository
        repository = Repository(
            name=repo.name,
            path=repo.path,
            vcs=repo.vcs,
            url=repo.url,
        )

        # Get VCS handler for the repository
        handler = get_vcs_interface(repository)

        # Check if directory exists
        path = Path(repo.path)
        if not path.exists():
            logger.error(f"Repository directory does not exist: {repo.path}")
            return False

        # Check if it's the correct VCS type
        if not _is_vcs_directory(path, repo.vcs):
            logger.error(f"Repository at {repo.path} is not a {repo.vcs} repository")
            return False

        # Switch to the specified revision
        success = handler.update_repo(rev=repo.rev)

        if success:
            logger.info(f"Successfully updated {repo.path} to revision {repo.rev}")
        else:
            logger.error(f"Failed to update {repo.path} to revision {repo.rev}")
    except Exception as e:
        logger.error(f"Error applying lock to repository {repo.path}: {e}")
        return False
    return success
