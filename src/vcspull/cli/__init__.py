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

from ._formatter import VcspullHelpFormatter
from .add import add_repo, create_add_subparser, handle_add_command
from .discover import create_discover_subparser, discover_repos
from .fmt import create_fmt_subparser, format_config_file
from .import_repos import create_import_subparser, import_repos
from .list import create_list_subparser, list_repos
from .search import create_search_subparser, search_repos
from .status import create_status_subparser, status_repos
from .sync import create_sync_subparser, sync

log = logging.getLogger(__name__)


def build_description(
    intro: str,
    example_blocks: t.Sequence[tuple[str | None, t.Sequence[str]]],
) -> str:
    """Assemble help text with optional example sections."""
    sections: list[str] = []
    intro_text = textwrap.dedent(intro).strip()
    if intro_text:
        sections.append(intro_text)

    for heading, commands in example_blocks:
        if not commands:
            continue
        title = "examples:" if heading is None else f"{heading} examples:"
        lines = [title]
        lines.extend(f"  {command}" for command in commands)
        sections.append("\n".join(lines))

    return "\n\n".join(sections)


CLI_DESCRIPTION = build_description(
    """
    Manage multiple VCS repositories from a single configuration file.
    """,
    (
        (
            "sync",
            [
                "vcspull sync --all",
                'vcspull sync "django-*"',
                "vcspull sync --dry-run --all",
                "vcspull sync -f ./myrepos.yaml --all",
                "vcspull sync -w ~/code myproject",
            ],
        ),
        (
            "list",
            [
                "vcspull list",
                'vcspull list "django-*"',
                "vcspull list --tree",
                "vcspull list --json",
            ],
        ),
        (
            "search",
            [
                "vcspull search django",
                "vcspull search name:django url:github",
                "vcspull search --fixed-strings 'git+https://github.com/org/repo.git'",
                "vcspull search --ignore-case --any django flask",
            ],
        ),
        (
            "add",
            [
                "vcspull add mylib https://github.com/example/mylib.git",
                "vcspull add mylib URL -w ~/code",
                "vcspull add mylib URL --dry-run",
            ],
        ),
        (
            "discover",
            [
                "vcspull discover ~/code",
                "vcspull discover ~/code --recursive --yes",
                "vcspull discover ~/code -w ~/projects --dry-run",
            ],
        ),
        (
            "fmt",
            [
                "vcspull fmt",
                "vcspull fmt -f ./myrepos.yaml",
                "vcspull fmt --write",
                "vcspull fmt --all",
            ],
        ),
        (
            "import",
            [
                "vcspull import github torvalds -w ~/repos/linux --mode user",
                "vcspull import github django -w ~/study/python --mode org",
                "vcspull import gitlab gitlab-org/ci-cd -w ~/work --mode org",
                "vcspull import codeberg user -w ~/oss --json",
            ],
        ),
    ),
)

SYNC_DESCRIPTION = build_description(
    """
    Synchronize VCS repositories.
    """,
    (
        (
            None,
            [
                "vcspull sync --all",
                'vcspull sync "django-*"',
                "vcspull sync --dry-run --all",
                "vcspull sync -f ./myrepos.yaml --all",
                "vcspull sync -w ~/code myproject",
            ],
        ),
    ),
)

LIST_DESCRIPTION = build_description(
    """
    List configured repositories.
    """,
    (
        (
            None,
            [
                "vcspull list",
                'vcspull list "django-*"',
                "vcspull list --tree",
                "vcspull list --json",
            ],
        ),
    ),
)

SEARCH_DESCRIPTION = build_description(
    """
    Search configured repositories.

    Query terms use regex by default, with optional field prefixes like
    name:, path:, url:, or workspace:.
    """,
    (
        (
            None,
            [
                "vcspull search django",
                "vcspull search name:django url:github",
                "vcspull search --fixed-strings 'git+https://github.com/org/repo.git'",
                "vcspull search --ignore-case --any django flask",
            ],
        ),
    ),
)

STATUS_DESCRIPTION = build_description(
    """
    Check status of repositories.
    """,
    (
        (
            None,
            [
                "vcspull status",
                'vcspull status "django-*"',
                "vcspull status --detailed",
                "vcspull status --json",
            ],
        ),
    ),
)

ADD_DESCRIPTION = build_description(
    """
    Add a single repository to the configuration.
    """,
    (
        (
            None,
            [
                "vcspull add mylib https://github.com/example/mylib.git",
                "vcspull add mylib URL -w ~/code",
                "vcspull add mylib URL --dry-run",
            ],
        ),
    ),
)

DISCOVER_DESCRIPTION = build_description(
    """
    Discover and add repositories from filesystem.

    Scans a directory for git repositories and adds them to the configuration.
    """,
    (
        (
            None,
            [
                "vcspull discover ~/code",
                "vcspull discover ~/code --recursive --yes",
                "vcspull discover ~/code -w ~/projects --dry-run",
            ],
        ),
    ),
)

FMT_DESCRIPTION = build_description(
    """
    Format vcspull configuration files for consistency.

    Normalizes repository entries, sorts sections, and can write changes
    back to disk or format all discovered configuration files.
    """,
    (
        (
            None,
            [
                "vcspull fmt",
                "vcspull fmt -f ./myrepos.yaml",
                "vcspull fmt --write",
                "vcspull fmt --all",
            ],
        ),
    ),
)

IMPORT_DESCRIPTION = build_description(
    """
    Import repositories from remote services.

    Fetches repository lists from GitHub, GitLab, Codeberg/Gitea/Forgejo,
    or AWS CodeCommit and adds them to the vcspull configuration.

    For GitLab, you can specify subgroups using slash notation (e.g., parent/child).
    """,
    (
        (
            None,
            [
                "vcspull import github torvalds -w ~/repos/linux --mode user",
                "vcspull import github django -w ~/study/python --mode org",
                "vcspull import gitlab gitlab-org/ci-cd -w ~/work --mode org",
                "vcspull import gitlab myuser -w ~/work --url https://gitlab.company.com",
                "vcspull import codeberg user -w ~/oss --dry-run",
                "vcspull import codecommit -w ~/work/aws --region us-east-1",
            ],
        ),
    ),
)


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
        formatter_class=VcspullHelpFormatter,
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

    # Sync command
    sync_parser = subparsers.add_parser(
        "sync",
        help="synchronize repositories",
        formatter_class=VcspullHelpFormatter,
        description=SYNC_DESCRIPTION,
    )
    create_sync_subparser(sync_parser)

    # List command
    list_parser = subparsers.add_parser(
        "list",
        help="list configured repositories",
        formatter_class=VcspullHelpFormatter,
        description=LIST_DESCRIPTION,
    )
    create_list_subparser(list_parser)

    # Status command
    status_parser = subparsers.add_parser(
        "status",
        help="check repository status",
        formatter_class=VcspullHelpFormatter,
        description=STATUS_DESCRIPTION,
    )
    create_status_subparser(status_parser)

    # Search command
    search_parser = subparsers.add_parser(
        "search",
        help="search configured repositories",
        formatter_class=VcspullHelpFormatter,
        description=SEARCH_DESCRIPTION,
    )
    create_search_subparser(search_parser)

    # Add command
    add_parser = subparsers.add_parser(
        "add",
        help="add a single repository",
        formatter_class=VcspullHelpFormatter,
        description=ADD_DESCRIPTION,
    )
    create_add_subparser(add_parser)

    # Discover command
    discover_parser = subparsers.add_parser(
        "discover",
        help="discover repositories from filesystem",
        formatter_class=VcspullHelpFormatter,
        description=DISCOVER_DESCRIPTION,
    )
    create_discover_subparser(discover_parser)

    # Fmt command
    fmt_parser = subparsers.add_parser(
        "fmt",
        help="format configuration files",
        formatter_class=VcspullHelpFormatter,
        description=FMT_DESCRIPTION,
    )
    create_fmt_subparser(fmt_parser)

    # Import command
    import_parser = subparsers.add_parser(
        "import",
        help="import repositories from remote services",
        formatter_class=VcspullHelpFormatter,
        description=IMPORT_DESCRIPTION,
    )
    create_import_subparser(import_parser)

    if return_subparsers:
        # Return all parsers needed by cli() function
        return parser, (
            sync_parser,
            list_parser,
            status_parser,
            search_parser,
            add_parser,
            discover_parser,
            fmt_parser,
            import_parser,
        )
    return parser


def cli(_args: list[str] | None = None) -> None:
    """CLI entry point for vcspull."""
    parser, subparsers = create_parser(return_subparsers=True)
    (
        sync_parser,
        _list_parser,
        _status_parser,
        search_parser,
        add_parser,
        discover_parser,
        _fmt_parser,
        _import_parser,
    ) = subparsers
    args = parser.parse_args(_args)

    setup_logger(log=log, level=args.log_level.upper())

    if args.subparser_name is None:
        parser.print_help()
        return

    if args.subparser_name == "sync":
        sync(
            repo_patterns=args.repo_patterns,
            config=pathlib.Path(args.config) if args.config else None,
            workspace_root=getattr(args, "workspace_root", None),
            dry_run=getattr(args, "dry_run", False),
            output_json=getattr(args, "output_json", False),
            output_ndjson=getattr(args, "output_ndjson", False),
            color=getattr(args, "color", "auto"),
            exit_on_error=args.exit_on_error,
            show_unchanged=getattr(args, "show_unchanged", False),
            summary_only=getattr(args, "summary_only", False),
            long_view=getattr(args, "long_view", False),
            relative_paths=getattr(args, "relative_paths", False),
            fetch=getattr(args, "fetch", False),
            offline=getattr(args, "offline", False),
            verbosity=getattr(args, "verbosity", 0),
            sync_all=getattr(args, "sync_all", False),
            parser=sync_parser,
        )
    elif args.subparser_name == "list":
        list_repos(
            repo_patterns=args.repo_patterns,
            config_path=pathlib.Path(args.config) if args.config else None,
            workspace_root=getattr(args, "workspace_root", None),
            tree=args.tree,
            output_json=args.output_json,
            output_ndjson=args.output_ndjson,
            color=args.color,
        )
    elif args.subparser_name == "status":
        status_repos(
            repo_patterns=args.repo_patterns,
            config_path=pathlib.Path(args.config) if args.config else None,
            workspace_root=getattr(args, "workspace_root", None),
            detailed=args.detailed,
            output_json=args.output_json,
            output_ndjson=args.output_ndjson,
            color=args.color,
            concurrent=not getattr(args, "no_concurrent", False),
            max_concurrent=getattr(args, "max_concurrent", None),
        )
    elif args.subparser_name == "search":
        if not args.query_terms:
            search_parser.print_help()
            return
        search_repos(
            query_terms=args.query_terms,
            config_path=pathlib.Path(args.config) if args.config else None,
            workspace_root=getattr(args, "workspace_root", None),
            output_json=args.output_json,
            output_ndjson=args.output_ndjson,
            color=args.color,
            fields=getattr(args, "fields", None),
            ignore_case=getattr(args, "ignore_case", False),
            smart_case=getattr(args, "smart_case", False),
            fixed_strings=getattr(args, "fixed_strings", False),
            word_regexp=getattr(args, "word_regexp", False),
            invert_match=getattr(args, "invert_match", False),
            match_any=getattr(args, "match_any", False),
        )
    elif args.subparser_name == "add":
        if not args.repo_path:
            add_parser.print_help()
            return
        handle_add_command(args)
    elif args.subparser_name == "discover":
        if not args.scan_dir:
            discover_parser.print_help()
            return
        discover_repos(
            scan_dir_str=args.scan_dir,
            config_file_path_str=args.config,
            recursive=args.recursive,
            workspace_root_override=args.workspace_root_path,
            yes=args.yes,
            dry_run=args.dry_run,
            merge_duplicates=args.merge_duplicates,
        )
    elif args.subparser_name == "fmt":
        format_config_file(
            args.config,
            args.write,
            args.all,
            merge_roots=args.merge_roots,
        )
    elif args.subparser_name == "import":
        import_repos(
            service=args.service,
            target=args.target,
            workspace=args.workspace,
            mode=args.mode,
            base_url=getattr(args, "base_url", None),
            token=getattr(args, "token", None),
            region=getattr(args, "region", None),
            profile=getattr(args, "profile", None),
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
        )
