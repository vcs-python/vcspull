"""Mercurial VCS interface for VCSPull."""

from __future__ import annotations

import subprocess
import typing as t
from pathlib import Path

from vcspull._internal import logger

from .base import VCSInterface

if t.TYPE_CHECKING:
    from vcspull.config.models import Repository


class MercurialInterface(VCSInterface):
    """Mercurial repository interface."""

    def __init__(self, repo: Repository) -> None:
        """Initialize the Mercurial interface.

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
        return (self.path / ".hg").exists()

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
            cmd = ["hg", "clone", self.repo.url, str(self.path)]
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
            cmd = ["hg", "--cwd", str(self.path), "pull"]
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

        # Pull changes
        if not self.pull():
            return False

        # Update working copy
        try:
            cmd = ["hg", "--cwd", str(self.path), "update"]
            subprocess.run(cmd, check=True, capture_output=True, text=True)
            logger.info(f"Updated repository: {self.path}")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to update repository: {e.stderr}")
            return False


class MercurialRepo:
    """Mercurial repository adapter for the new API."""

    def __init__(self, repo_path: str | Path, url: str, **kwargs: t.Any) -> None:
        """Initialize the Mercurial repository adapter.

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

        # Create a Repository object for the MercurialInterface
        self.repo = Repository(
            path=str(self.repo_path),
            url=self.url,
            vcs="hg",
        )

        # Create the interface
        self.interface = MercurialInterface(self.repo)

    def is_repo(self) -> bool:
        """Check if the directory is a Mercurial repository.

        Returns
        -------
        bool
            True if the directory is a Mercurial repository, False otherwise
        """
        return self.interface.exists()

    def obtain(self, depth: int | None = None) -> bool:
        """Clone the repository.

        Parameters
        ----------
        depth : int | None, optional
            Clone depth, by default None (ignored for Mercurial)

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
            # Mercurial uses paths in .hg/hgrc
            with (self.repo_path / ".hg" / "hgrc").open("a") as f:
                f.write(f"\n[paths]\n{name} = {url}\n")
            return True
        except Exception:
            return False

    def update_remote(self, name: str) -> bool:
        """Pull from a remote.

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
            cmd = ["hg", "--cwd", str(self.repo_path), "pull", "-R", name]
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
            cmd = ["hg", "--cwd", str(self.repo_path), "update", rev]
            subprocess.run(cmd, check=True, capture_output=True, text=True)
            return True
        except subprocess.CalledProcessError:
            return False

    def get_remote_url(self) -> str | None:
        """Get the URL of the default remote.

        Returns
        -------
        str | None
            URL of the default remote, or None if not found
        """
        if not self.is_repo():
            return None

        try:
            cmd = ["hg", "--cwd", str(self.repo_path), "paths", "default"]
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            return result.stdout.strip()
        except subprocess.CalledProcessError:
            return None
