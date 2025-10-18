"""CLI utilities for vcspull."""

from __future__ import annotations

import argparse
import logging
import pathlib
import textwrap
import typing as t
from typing import overload

from libvcs.__about__ import __version__ as libvcs_version

from vcspull.__about__ import __version__
from vcspull.log import setup_logger

from ._import import (
    create_import_subparser,
    import_from_filesystem,
    import_repo,
)
from .fmt import create_fmt_subparser, format_config_file
from .sync import create_sync_subparser, sync

log = logging.getLogger(__name__)

CLI_DESCRIPTION = textwrap.dedent(
    """
    Manage multiple VCS repositories from a single configuration file.

    sync examples:
      vcspull sync "*"
      vcspull sync "django-*"
      vcspull sync "django-*" flask
      vcspull sync -c ./myrepos.yaml "*"
      vcspull sync -c ./myrepos.yaml myproject

    import examples:
      vcspull import mylib https://github.com/example/mylib.git
      vcspull import -c ./myrepos.yaml mylib git@github.com:example/mylib.git
      vcspull import --scan ~/code
      vcspull import --scan ~/code --recursive --workspace-root ~/code --yes

    fmt examples:
      vcspull fmt
      vcspull fmt -c ./myrepos.yaml
      vcspull fmt --write
      vcspull fmt --all
""",
).strip()

SYNC_DESCRIPTION = textwrap.dedent(
    """
    sync vcs repos

    examples:
      vcspull sync "*"
      vcspull sync "django-*"
      vcspull sync "django-*" flask
      vcspull sync -c ./myrepos.yaml "*"
      vcspull sync -c ./myrepos.yaml myproject
""",
).strip()

IMPORT_DESCRIPTION = textwrap.dedent(
    """
    Import repositories into a vcspull configuration file.

    Provide NAME and URL to add a single repository, or use --scan to
    discover existing git repositories within a directory.

    examples:
      vcspull import mylib https://github.com/example/mylib.git
      vcspull import -c ./myrepos.yaml mylib git@github.com:example/mylib.git
      vcspull import --scan ~/code
      vcspull import --scan ~/code --recursive --workspace-root ~/code --yes
""",
).strip()

FMT_DESCRIPTION = textwrap.dedent(
    """
    Format vcspull configuration files for consistency.

    Normalizes repository entries, sorts sections, and can write changes
    back to disk or format all discovered configuration files.

    examples:
      vcspull fmt
      vcspull fmt -c ./myrepos.yaml
      vcspull fmt --write
      vcspull fmt --all
""",
).strip()


@overload
def create_parser(
    return_subparsers: t.Literal[True],
) -> tuple[argparse.ArgumentParser, t.Any]: ...


@overload
def create_parser(return_subparsers: t.Literal[False]) -> argparse.ArgumentParser: ...


def create_parser(
    return_subparsers: bool = False,
) -> argparse.ArgumentParser | tuple[argparse.ArgumentParser, t.Any]:
    """Create CLI argument parser for vcspull."""
    parser = argparse.ArgumentParser(
        prog="vcspull",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=CLI_DESCRIPTION,
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

    import_parser = subparsers.add_parser(
        "import",
        help="import repository or scan filesystem for repositories",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=IMPORT_DESCRIPTION,
    )
    create_import_subparser(import_parser)

    fmt_parser = subparsers.add_parser(
        "fmt",
        help="format vcspull configuration files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=FMT_DESCRIPTION,
    )
    create_fmt_subparser(fmt_parser)

    if return_subparsers:
        # Return all parsers needed by cli() function
        return parser, (sync_parser, import_parser, fmt_parser)
    return parser


def cli(_args: list[str] | None = None) -> None:
    """CLI entry point for vcspull."""
    parser, subparsers = create_parser(return_subparsers=True)
    sync_parser, _import_parser, _fmt_parser = subparsers
    args = parser.parse_args(_args)

    setup_logger(log=log, level=args.log_level.upper())

    if args.subparser_name is None:
        parser.print_help()
        return
    if args.subparser_name == "sync":
        sync(
            repo_patterns=args.repo_patterns,
            config=pathlib.Path(args.config) if args.config else None,
            exit_on_error=args.exit_on_error,
            parser=sync_parser,
        )
    elif args.subparser_name == "import":
        # Unified import command
        if args.scan_dir:
            # Filesystem scan mode
            import_from_filesystem(
                scan_dir_str=args.scan_dir,
                config_file_path_str=args.config,
                recursive=args.recursive,
                workspace_root_override=args.workspace_root_path,
                yes=args.yes,
            )
        elif args.name and args.url:
            # Manual import mode
            import_repo(
                name=args.name,
                url=args.url,
                config_file_path_str=args.config,
                path=args.path,
                workspace_root_path=args.workspace_root_path,
            )
        else:
            # Error: need either name+url or --scan
            log.error("Either provide NAME and URL, or use --scan DIR")
            parser.exit(status=2)
    elif args.subparser_name == "fmt":
        format_config_file(args.config, args.write, args.all)
