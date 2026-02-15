"""``vcspull import`` subcommand package.

Each supported service (GitHub, GitLab, Codeberg, Gitea, Forgejo,
CodeCommit) is registered as a proper argparse subcommand so that
``vcspull import <service> --help`` shows only the flags relevant to
that service.
"""

from __future__ import annotations

import argparse

from .codeberg import create_codeberg_subparser
from .codecommit import create_codecommit_subparser
from .forgejo import create_forgejo_subparser
from .gitea import create_gitea_subparser
from .github import create_github_subparser
from .gitlab import create_gitlab_subparser

__all__ = ["create_import_subparser"]


def create_import_subparser(parser: argparse.ArgumentParser) -> None:
    """Wire per-service subparsers into the ``vcspull import`` parser.

    Parameters
    ----------
    parser : argparse.ArgumentParser
        The ``import`` parser to attach service subcommands to.
    """
    service_subparsers = parser.add_subparsers(dest="import_service")

    create_github_subparser(service_subparsers)
    create_gitlab_subparser(service_subparsers)
    create_codeberg_subparser(service_subparsers)
    create_gitea_subparser(service_subparsers)
    create_forgejo_subparser(service_subparsers)
    create_codecommit_subparser(service_subparsers)
