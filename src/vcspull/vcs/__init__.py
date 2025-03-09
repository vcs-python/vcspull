"""Version control system interfaces for VCSPull."""

from __future__ import annotations

from .base import VCSInterface, get_vcs_handler

__all__ = ["VCSInterface", "get_vcs_handler"]
