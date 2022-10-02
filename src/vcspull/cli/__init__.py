"""CLI utilities for vcspull.

vcspull.cli
~~~~~~~~~~~

"""
import argparse
import logging

from libvcs.__about__ import __version__ as libvcs_version

from ..__about__ import __version__
from ..log import setup_logger
from .sync import create_sync_subparser, sync

log = logging.getLogger(__name__)


def create_parser():
    parser = argparse.ArgumentParser(prog="vcspull")
    parser.add_argument(
        "--version",
        "-V",
        action="version",
        version=f"%(prog)s {__version__}, libvcs {libvcs_version}",
    )
    parser.add_argument(
        "--log-level",
        action="store",
        default="INFO",
        help="Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)",
    )
    subparsers = parser.add_subparsers(dest="subparser_name")
    sync_parser = subparsers.add_parser("sync")
    create_sync_subparser(sync_parser)

    return parser


def cli(args=None):
    parser = create_parser()
    args = parser.parse_args(args)

    setup_logger(log=log, level=args.log_level.upper())

    if args.subparser_name is None:
        parser.print_help()
        return
    elif args.subparser_name == "sync":
        sync(
            repo_terms=args.repo_terms,
            config=args.config,
            exit_on_error=args.exit_on_error,
            parser=parser,
        )
