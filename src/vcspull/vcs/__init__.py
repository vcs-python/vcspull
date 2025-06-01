"""Version Control System handlers for VCSPull."""

from __future__ import annotations

import typing as t

from .git import GitRepo
from .mercurial import MercurialRepo
from .svn import SubversionRepo

if t.TYPE_CHECKING:
    from pathlib import Path


def get_vcs_handler(
    vcs_type: str,
    repo_path: str | Path,
    url: str,
    **kwargs: t.Any,
) -> GitRepo | MercurialRepo | SubversionRepo:
    """Get a VCS handler for the specified repository type.

    Parameters
    ----------
    vcs_type : str
        Type of VCS (git, hg, svn)
    repo_path : str | Path
        Path to the repository
    url : str
        URL of the repository
    **kwargs : t.Any
        Additional keyword arguments for the VCS handler

    Returns
    -------
    t.Union[GitRepo, MercurialRepo, SubversionRepo]
        VCS handler instance

    Raises
    ------
    ValueError
        If the VCS type is not supported
    """
    if vcs_type == "git":
        return GitRepo(repo_path, url, **kwargs)
    if vcs_type in {"hg", "mercurial"}:
        return MercurialRepo(repo_path, url, **kwargs)
    if vcs_type in {"svn", "subversion"}:
        return SubversionRepo(repo_path, url, **kwargs)
    error_msg = f"Unsupported VCS type: {vcs_type}"
    raise ValueError(error_msg)
