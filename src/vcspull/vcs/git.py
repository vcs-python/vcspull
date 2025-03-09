"""Git VCS interface for VCSPull."""

from __future__ import annotations

import subprocess
import typing as t
from pathlib import Path

from vcspull._internal import logger

from .base import VCSInterface

if t.TYPE_CHECKING:
    from vcspull.config.models import Repository


class GitInterface(VCSInterface):
    """Git repository interface."""

    def __init__(self, repo: Repository) -> None:
        """Initialize the Git interface.

        Parameters
        ----------
        repo : Repository
            Repository configuration
        """
        self.repo = repo
        self.path = Path(repo.path).expanduser().resolve()

    def exists(self) -> bool:
        """Check if the repository exists.

        Returns
        -------
        bool
            True if the repository exists, False otherwise
        """
        return (self.path / ".git").exists()

    def clone(self) -> bool:
        """Clone the repository.

        Returns
        -------
        bool
            True if successful, False otherwise
        """
        if self.exists():
            logger.info(f"Repository already exists: {self.path}")
            return True

        # Create parent directory if it doesn't exist
        self.path.parent.mkdir(parents=True, exist_ok=True)

        try:
            cmd = ["git", "clone", self.repo.url, str(self.path)]
            subprocess.run(cmd, check=True, capture_output=True, text=True)
            logger.info(f"Cloned repository: {self.path}")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to clone repository: {e.stderr}")
            return False

    def pull(self) -> bool:
        """Pull changes from the remote repository.

        Returns
        -------
        bool
            True if successful, False otherwise
        """
        if not self.exists():
            logger.error(f"Repository does not exist: {self.path}")
            return False

        try:
            cmd = ["git", "-C", str(self.path), "pull"]
            subprocess.run(cmd, check=True, capture_output=True, text=True)
            logger.info(f"Pulled changes for repository: {self.path}")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to pull repository: {e.stderr}")
            return False

    def update(self) -> bool:
        """Update the repository.

        Returns
        -------
        bool
            True if successful, False otherwise
        """
        if not self.exists():
            return self.clone()
        return self.pull()


class GitRepo:
    """Git repository adapter for the new API."""

    def __init__(self, repo_path: str | Path, url: str, **kwargs: t.Any) -> None:
        """Initialize the Git repository adapter.

        Parameters
        ----------
        repo_path : str | Path
            Path to the repository
        url : str
            URL of the repository
        **kwargs : t.Any
            Additional keyword arguments
        """
        from vcspull.config.models import Repository

        self.repo_path = Path(repo_path).expanduser().resolve()
        self.url = url
        self.kwargs = kwargs

        # Create a Repository object for the GitInterface
        self.repo = Repository(
            path=str(self.repo_path),
            url=self.url,
            vcs="git",
        )

        # Create the interface
        self.interface = GitInterface(self.repo)

    def is_repo(self) -> bool:
        """Check if the directory is a Git repository.

        Returns
        -------
        bool
            True if the directory is a Git repository, False otherwise
        """
        return self.interface.exists()

    def obtain(self, depth: int | None = None) -> bool:
        """Clone the repository.

        Parameters
        ----------
        depth : int | None, optional
            Clone depth, by default None

        Returns
        -------
        bool
            True if successful, False otherwise
        """
        return self.interface.clone()

    def update(self) -> bool:
        """Update the repository.

        Returns
        -------
        bool
            True if successful, False otherwise
        """
        return self.interface.update()

    def set_remote(self, name: str, url: str) -> bool:
        """Set a remote for the repository.

        Parameters
        ----------
        name : str
            Name of the remote
        url : str
            URL of the remote

        Returns
        -------
        bool
            True if successful, False otherwise
        """
        if not self.is_repo():
            return False

        try:
            # Check if remote exists
            cmd = ["git", "-C", str(self.repo_path), "remote"]
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            remotes = result.stdout.strip().split("\n")

            if name in remotes:
                # Update existing remote
                cmd = ["git", "-C", str(self.repo_path), "remote", "set-url", name, url]
            else:
                # Add new remote
                cmd = ["git", "-C", str(self.repo_path), "remote", "add", name, url]

            subprocess.run(cmd, check=True, capture_output=True, text=True)
            return True
        except subprocess.CalledProcessError:
            return False

    def update_remote(self, name: str) -> bool:
        """Fetch from a remote.

        Parameters
        ----------
        name : str
            Name of the remote

        Returns
        -------
        bool
            True if successful, False otherwise
        """
        if not self.is_repo():
            return False

        try:
            cmd = ["git", "-C", str(self.repo_path), "fetch", name]
            subprocess.run(cmd, check=True, capture_output=True, text=True)
            return True
        except subprocess.CalledProcessError:
            return False

    def update_to_rev(self, rev: str) -> bool:
        """Update to a specific revision.

        Parameters
        ----------
        rev : str
            Revision to update to

        Returns
        -------
        bool
            True if successful, False otherwise
        """
        if not self.is_repo():
            return False

        try:
            cmd = ["git", "-C", str(self.repo_path), "checkout", rev]
            subprocess.run(cmd, check=True, capture_output=True, text=True)
            return True
        except subprocess.CalledProcessError:
            return False

    def get_remote_url(self) -> str | None:
        """Get the URL of the origin remote.

        Returns
        -------
        str | None
            URL of the origin remote, or None if not found
        """
        if not self.is_repo():
            return None

        try:
            cmd = ["git", "-C", str(self.repo_path), "remote", "get-url", "origin"]
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            return result.stdout.strip()
        except subprocess.CalledProcessError:
            return None
