"""Base VCS interface for VCSPull."""

from __future__ import annotations

import typing as t
from abc import ABC, abstractmethod

if t.TYPE_CHECKING:
    from vcspull.config.models import Repository


class VCSInterface(ABC):
    """Base interface for VCS operations."""

    @abstractmethod
    def __init__(self, repo: Repository) -> None:
        """Initialize the VCS interface.

        Parameters
        ----------
        repo : Repository
            Repository configuration
        """
        ...

    @abstractmethod
    def exists(self) -> bool:
        """Check if the repository exists locally.

        Returns
        -------
        bool
            True if the repository exists locally
        """
        ...

    @abstractmethod
    def clone(self) -> bool:
        """Clone the repository.

        Returns
        -------
        bool
            True if the operation was successful
        """
        ...

    @abstractmethod
    def pull(self) -> bool:
        """Pull changes from the remote repository.

        Returns
        -------
        bool
            True if the operation was successful
        """
        ...

    @abstractmethod
    def update(self) -> bool:
        """Update the repository to the specified revision.

        Returns
        -------
        bool
            True if the operation was successful
        """
        ...

    @abstractmethod
    def get_revision(self) -> str | None:
        """Get the current revision of the repository.

        Returns
        -------
        str | None
            The current revision hash or identifier, or None if it couldn't be
            determined
        """
        ...

    @abstractmethod
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
        ...


def get_vcs_handler(
    repo: Repository,
    default_vcs: str | None = None,
) -> VCSInterface:
    """Get the appropriate VCS handler for a repository.

    Parameters
    ----------
    repo : Repository
        Repository configuration
    default_vcs : Optional[str]
        Default VCS type to use if not specified in the repository

    Returns
    -------
    VCSInterface
        VCS handler for the repository

    Raises
    ------
    ValueError
        If the VCS type is not supported or not specified
    """
    vcs_type = repo.vcs

    # Use default_vcs if not specified in the repository
    if vcs_type is None:
        if default_vcs is None:
            # Try to infer from URL
            url = repo.url.lower()
            if any(x in url for x in ["github.com", "gitlab.com", "git@"]):
                vcs_type = "git"
            elif "bitbucket" in url and "/hg/" in url:
                vcs_type = "hg"
            elif "/svn/" in url:
                vcs_type = "svn"
            else:
                msg = (
                    f"Could not determine VCS type for {repo.url}, "
                    f"please specify vcs in the repository configuration"
                )
                raise ValueError(
                    msg,
                )
        else:
            vcs_type = default_vcs

    # Import the appropriate implementation
    if vcs_type == "git":
        from .git import GitInterface

        return GitInterface(repo)
    if vcs_type in {"hg", "mercurial"}:
        from .mercurial import MercurialInterface

        return MercurialInterface(repo)
    if vcs_type in {"svn", "subversion"}:
        from .svn import SubversionInterface

        return SubversionInterface(repo)
    msg = f"Unsupported VCS type: {vcs_type}"
    raise ValueError(msg)
