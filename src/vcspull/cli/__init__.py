"""CLI utilities for vcspull."""
import argparse
import logging
import textwrap
import typing as t
from typing import overload

from libvcs.__about__ import __version__ as libvcs_version

from ..__about__ import __version__
from ..log import setup_logger
from .sync import create_sync_subparser, sync

log = logging.getLogger(__name__)

SYNC_DESCRIPTION = textwrap.dedent(
    """
    sync vcs repos

    examples:
      vcspull sync "*"
      vcspull sync "django-*"
      vcspull sync "django-*" flask
      vcspull sync -c ./myrepos.yaml "*"
      vcspull sync -c ./myrepos.yaml myproject
"""
).strip()


@overload
def create_parser(
    return_subparsers: t.Literal[True],
) -> tuple[argparse.ArgumentParser, t.Any]:
    ...


@overload
def create_parser(return_subparsers: t.Literal[False]) -> argparse.ArgumentParser:
    ...


def create_parser(
    return_subparsers: bool = False,
) -> t.Union[argparse.ArgumentParser, tuple[argparse.ArgumentParser, t.Any]]:
    """Create CLI argument parser for vcspull."""
    parser = argparse.ArgumentParser(
        prog="vcspull",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=SYNC_DESCRIPTION,
    )
    parser.add_argument(
        "--version",
        "-V",
        action="version",
        version=f"%(prog)s {__version__}, libvcs {libvcs_version}",
    )
    parser.add_argument(
        "--log-level",
        metavar="level",
        action="store",
        default="INFO",
        help="log level (debug, info, warning, error, critical)",
    )

    subparsers = parser.add_subparsers(dest="subparser_name")
    sync_parser = subparsers.add_parser(
        "sync",
        help="synchronize repos",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=SYNC_DESCRIPTION,
    )
    create_sync_subparser(sync_parser)

    if return_subparsers:
        return parser, sync_parser
    return parser


def cli(_args: t.Optional[list[str]] = None) -> None:
    """CLI entry point for vcspull."""
    parser, sync_parser = create_parser(return_subparsers=True)
    args = parser.parse_args(_args)

    setup_logger(log=log, level=args.log_level.upper())

    if args.subparser_name is None:
        parser.print_help()
        return
    elif args.subparser_name == "sync":
        sync(
            repo_patterns=args.repo_patterns,
            config=args.config,
            exit_on_error=args.exit_on_error,
            parser=sync_parser,
        )
