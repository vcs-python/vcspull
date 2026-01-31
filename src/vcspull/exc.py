"""Exceptions for vcspull."""

from __future__ import annotations


class VCSPullException(Exception):
    """Standard exception raised by vcspull."""


class MultipleConfigWarning(VCSPullException):
    """Multiple eligible config files found at the same time."""

    message = "Multiple configs found in home directory use only one. .yaml, .json."


class WorktreeError(VCSPullException):
    """Base exception for worktree operations."""


class WorktreeExistsError(WorktreeError):
    """Worktree already exists at the specified path."""

    def __init__(self, path: str, *args: object, **kwargs: object) -> None:
        super().__init__(f"Worktree already exists at path: {path}")
        self.path = path


class WorktreeRefNotFoundError(WorktreeError):
    """Reference (tag, branch, or commit) not found in repository."""

    def __init__(
        self,
        ref: str,
        ref_type: str,
        repo_path: str,
        *args: object,
        **kwargs: object,
    ) -> None:
        super().__init__(
            f"{ref_type.capitalize()} '{ref}' not found in repository at {repo_path}"
        )
        self.ref = ref
        self.ref_type = ref_type
        self.repo_path = repo_path


class WorktreeConfigError(WorktreeError):
    """Invalid worktree configuration."""

    def __init__(self, message: str, *args: object, **kwargs: object) -> None:
        super().__init__(message)


class WorktreeDirtyError(WorktreeError):
    """Worktree has uncommitted changes and cannot be modified."""

    def __init__(self, path: str, *args: object, **kwargs: object) -> None:
        super().__init__(f"Worktree at {path} has uncommitted changes")
        self.path = path
