"""``vcspull import codecommit`` subcommand."""

from __future__ import annotations

import argparse
import logging

from vcspull._internal.remotes import CodeCommitImporter, DependencyError

from .._colors import Colors, get_color_mode
from .._formatter import VcspullHelpFormatter
from ._common import _create_shared_parent, _run_import

log = logging.getLogger(__name__)


def create_codecommit_subparser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Register the ``codecommit`` (aliases ``cc``, ``aws``) service subcommand.

    Parameters
    ----------
    subparsers : argparse._SubParsersAction
        The subparsers action from the ``import`` parser.
    """
    parser = subparsers.add_parser(
        "codecommit",
        aliases=["cc", "aws"],
        help="import from AWS CodeCommit",
        parents=[_create_shared_parent()],
        formatter_class=VcspullHelpFormatter,
        description="Import repositories from AWS CodeCommit.",
    )
    parser.add_argument(
        "target",
        metavar="TARGET",
        nargs="?",
        default="",
        help="Optional substring filter for repository names",
    )
    parser.add_argument(
        "--region",
        dest="region",
        metavar="REGION",
        help="AWS region for CodeCommit",
    )
    parser.add_argument(
        "--profile",
        dest="profile",
        metavar="PROFILE",
        help="AWS profile for CodeCommit",
    )
    parser.set_defaults(import_handler=handle_codecommit)


def handle_codecommit(args: argparse.Namespace) -> int:
    """Handle ``vcspull import codecommit``.

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

    colors = Colors(get_color_mode(getattr(args, "color", "auto")))

    try:
        importer = CodeCommitImporter(
            region=getattr(args, "region", None),
            profile=getattr(args, "profile", None),
        )
    except DependencyError as exc:
        log.error("%s %s", colors.error("\u2717"), exc)  # noqa: TRY400
        return 1

    return _run_import(
        importer,
        service_name="codecommit",
        target=getattr(args, "target", "") or "",
        workspace=args.workspace,
        mode="user",
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
