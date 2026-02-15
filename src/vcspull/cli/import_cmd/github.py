"""``vcspull import github`` subcommand."""

from __future__ import annotations

import argparse

from vcspull._internal.remotes import GitHubImporter

from .._formatter import VcspullHelpFormatter
from ._common import (
    _create_mode_parent,
    _create_shared_parent,
    _create_target_parent,
    _create_token_parent,
    _run_import,
)


def create_github_subparser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Register the ``github`` (alias ``gh``) service subcommand.

    Parameters
    ----------
    subparsers : argparse._SubParsersAction
        The subparsers action from the ``import`` parser.
    """
    parser = subparsers.add_parser(
        "github",
        aliases=["gh"],
        help="import from GitHub",
        parents=[
            _create_shared_parent(),
            _create_token_parent(),
            _create_mode_parent(),
            _create_target_parent(),
        ],
        formatter_class=VcspullHelpFormatter,
        description=(
            "Import repositories from GitHub (github.com or GitHub Enterprise)."
        ),
    )
    parser.add_argument(
        "--url",
        dest="base_url",
        metavar="URL",
        help="Base URL for GitHub Enterprise (optional)",
    )
    parser.set_defaults(import_handler=handle_github)


def handle_github(args: argparse.Namespace) -> int:
    """Handle ``vcspull import github``.

    Parameters
    ----------
    args : argparse.Namespace
        Parsed CLI arguments.

    Returns
    -------
    int
        Exit code (0 = success).
    """
    if args.workspace is None:
        msg = "-w/--workspace is required"
        raise SystemExit(msg)

    importer = GitHubImporter(
        token=getattr(args, "token", None),
        base_url=getattr(args, "base_url", None),
    )
    return _run_import(
        importer,
        service_name="github",
        target=args.target,
        workspace=args.workspace,
        mode=args.mode,
        language=getattr(args, "language", None),
        topics=getattr(args, "topics", None),
        min_stars=getattr(args, "min_stars", 0),
        include_archived=getattr(args, "include_archived", False),
        include_forks=getattr(args, "include_forks", False),
        limit=getattr(args, "limit", 100),
        config_path_str=getattr(args, "config", None),
        dry_run=getattr(args, "dry_run", False),
        yes=getattr(args, "yes", False),
        output_json=getattr(args, "output_json", False),
        output_ndjson=getattr(args, "output_ndjson", False),
        color=getattr(args, "color", "auto"),
        use_https=getattr(args, "use_https", False),
        style=getattr(args, "style", None),
    )
