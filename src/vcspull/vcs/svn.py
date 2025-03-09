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
        self.path = Path(repo.path)

    def exists(self) -> bool:
        """Check if the repository exists locally.

        Returns
        -------
        bool
            True if the repository exists locally
        """
        svn_dir = self.path / ".svn"
        return svn_dir.exists() and svn_dir.is_dir()

    def clone(self) -> bool:
        """Clone the repository.

        Returns
        -------
        bool
            True if the operation was successful
        """
        if self.exists():
            logger.info(f"Repository already exists at {self.path}")
            return True

        # Create parent directory if it doesn't exist
        if not self.path.parent.exists():
            self.path.parent.mkdir(parents=True, exist_ok=True)

        try:
            logger.info(f"Checking out {self.repo.url} to {self.path}")
            result = subprocess.run(
                ["svn", "checkout", self.repo.url, str(self.path)],
                check=True,
                capture_output=True,
                text=True,
            )
            logger.debug(result.stdout)
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to checkout repository: {e}")
            logger.error(e.stderr)
            return False
        else:
            return True

    def pull(self) -> bool:
        """Pull changes from the remote repository.

        Returns
        -------
        bool
            True if the operation was successful
        """
        if not self.exists():
            logger.warning(f"Repository does not exist at {self.path}")
            return False

        try:
            logger.info(f"Updating {self.path}")
            result = subprocess.run(
                ["svn", "update"],
                check=True,
                cwd=str(self.path),
                capture_output=True,
                text=True,
            )
            logger.debug(result.stdout)
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to update repository: {e}")
            logger.error(e.stderr)
            return False
        else:
            return True

    def update(self) -> bool:
        """Update the repository to the specified revision.

        Returns
        -------
        bool
            True if the operation was successful
        """
        if not self.exists():
            logger.warning(f"Repository does not exist at {self.path}")
            return False

        # If no revision is specified, just update
        if not self.repo.rev:
            return self.pull()

        try:
            logger.info(f"Updating to revision {self.repo.rev} in {self.path}")
            result = subprocess.run(
                ["svn", "update", "-r", self.repo.rev],
                check=True,
                cwd=str(self.path),
                capture_output=True,
                text=True,
            )
            logger.debug(result.stdout)
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to update to revision: {e}")
            logger.error(e.stderr)
            return False
        else:
            return True
