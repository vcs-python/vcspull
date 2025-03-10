"""Subversion VCS interface for VCSPull."""

from __future__ import annotations

import subprocess
import typing as t
from pathlib import Path

from vcspull._internal import logger

from .base import VCSInterface

if t.TYPE_CHECKING:
    from vcspull.config.models import Repository


class SubversionInterface(VCSInterface):
    """Subversion repository interface."""

    def __init__(self, repo: Repository) -> None:
        """Initialize the Subversion interface.

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
        return (self.path / ".svn").exists()

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
            cmd = ["svn", "checkout", self.repo.url, str(self.path)]
            subprocess.run(cmd, check=True, capture_output=True, text=True)
            logger.info(f"Checked out repository: {self.path}")
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to checkout repository: {e.stderr}")
            return False
        return True

    def pull(self) -> bool:
        """Update the repository from the remote.

        Returns
        -------
        bool
            True if successful, False otherwise
        """
        if not self.exists():
            logger.error(f"Repository does not exist: {self.path}")
            return False

        try:
            cmd = ["svn", "update", str(self.path)]
            subprocess.run(cmd, check=True, capture_output=True, text=True)
            logger.info(f"Updated repository: {self.path}")
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to update repository: {e.stderr}")
            return False
        return True

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

    def get_revision(self) -> str | None:
        """Get the current revision of the repository.

        Returns
        -------
        str | None
            The current revision number, or None if it couldn't be determined
        """
        if not self.exists():
            logger.error(f"Repository does not exist: {self.path}")
            return None

        try:
            cmd = ["svn", "info", "--show-item", "revision", str(self.path)]
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to get revision: {e.stderr}")
            return None

    def update_repo(self, rev: str | None = None) -> bool:
        """Update the repository to a specific revision.

        Parameters
        ----------
        rev : str | None
            The revision to update to, or None to update to the latest

        Returns
        -------
        bool
            True if the operation was successful
        """
        if not self.exists():
            logger.error(f"Repository does not exist: {self.path}")
            return False

        try:
            if rev:
                cmd = ["svn", "update", "-r", rev, str(self.path)]
                subprocess.run(cmd, check=True, capture_output=True, text=True)
                logger.info(f"Updated to revision {rev} in {self.path}")
            else:
                # Update to the latest revision
                cmd = ["svn", "update", str(self.path)]
                subprocess.run(cmd, check=True, capture_output=True, text=True)
                logger.info(f"Updated to latest revision in {self.path}")
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to update repository to revision {rev}: {e.stderr}")
            return False
        return True


class SubversionRepo:
    """Subversion repository adapter for the new API."""

    def __init__(self, repo_path: str | Path, url: str, **kwargs: t.Any) -> None:
        """Initialize the Subversion repository adapter.

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

        # Create a Repository object for the SubversionInterface
        self.repo = Repository(
            path=str(self.repo_path),
            url=self.url,
            vcs="svn",
        )

        # Create the interface
        self.interface = SubversionInterface(self.repo)

    def is_repo(self) -> bool:
        """Check if the directory is a Subversion repository.

        Returns
        -------
        bool
            True if the directory is a Subversion repository, False otherwise
        """
        return self.interface.exists()

    def obtain(self, depth: int | None = None) -> bool:
        """Checkout the repository.

        Parameters
        ----------
        depth : int | None, optional
            Checkout depth, by default None (ignored for SVN)

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
            Name of the remote (ignored for SVN)
        url : str
            URL of the remote (ignored for SVN)

        Returns
        -------
        bool
            Always returns False as SVN doesn't support multiple remotes
        """
        # SVN doesn't support multiple remotes in the same way as Git/Mercurial
        return False

    def update_remote(self, name: str) -> bool:
        """Update from a remote.

        Parameters
        ----------
        name : str
            Name of the remote (ignored for SVN)

        Returns
        -------
        bool
            True if successful, False otherwise
        """
        # SVN doesn't have named remotes, so just update
        return self.update()

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
            cmd = ["svn", "update", "-r", rev, str(self.repo_path)]
            subprocess.run(cmd, check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError:
            return False
        return True

    def get_remote_url(self) -> str | None:
        """Get the URL of the repository.

        Returns
        -------
        str | None
            URL of the repository, or None if not found
        """
        if not self.is_repo():
            return None

        try:
            cmd = ["svn", "info", "--show-item", "url", str(self.repo_path)]
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            return result.stdout.strip()
        except subprocess.CalledProcessError:
            return None
