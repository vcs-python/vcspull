"""``vcspull import codeberg`` subcommand."""

from __future__ import annotations

import argparse

from vcspull._internal.remotes import GiteaImporter

from .._formatter import VcspullHelpFormatter
from ._common import (
    _create_mode_parent,
    _create_shared_parent,
    _create_target_parent,
    _create_token_parent,
    _run_import,
)


def create_codeberg_subparser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Register the ``codeberg`` (alias ``cb``) service subcommand.

    Parameters
    ----------
    subparsers : argparse._SubParsersAction
        The subparsers action from the ``import`` parser.
    """
    subparsers.add_parser(
        "codeberg",
        aliases=["cb"],
        help="import from Codeberg",
        parents=[
            _create_shared_parent(),
            _create_token_parent(),
            _create_mode_parent(),
            _create_target_parent(),
        ],
        formatter_class=VcspullHelpFormatter,
        description="Import repositories from Codeberg.",
    ).set_defaults(import_handler=handle_codeberg)


def handle_codeberg(args: argparse.Namespace) -> int:
    """Handle ``vcspull import codeberg``.

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

    importer = GiteaImporter(
        token=getattr(args, "token", None),
        base_url="https://codeberg.org",
    )
    return _run_import(
        importer,
        service_name="codeberg",
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
    )
