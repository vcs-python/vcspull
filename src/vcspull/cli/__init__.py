"""CLI utilities for vcspull."""

from __future__ import annotations

import argparse
import logging
import pathlib
import sys
import textwrap
import typing as t

from libvcs.__about__ import __version__ as libvcs_version

from vcspull import exc
from vcspull.__about__ import __version__
from vcspull.log import setup_logger

from ._formatter import VcspullHelpFormatter
from .add import add_repo, create_add_subparser, handle_add_command
from .config import (
    config_ls,
    create_config_subparser,
    create_trust_subparser,
    trust_command,
)
from .discover import create_discover_subparser, discover_repos
from .fmt import create_fmt_subparser, format_config_file
from .import_cmd import create_import_subparser
from .list import create_list_subparser, list_repos
from .migrate import create_migrate_subparser, migrate_config_file
from .search import create_search_subparser, search_repos
from .status import create_status_subparser, status_repos
from .sync import create_sync_subparser, sync
from .worktree import create_worktree_subparser, handle_worktree_command

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
                "vcspull add ~/code/mylib",
                "vcspull add ~/src/mylib --workspace ~/code",
                (
                    "vcspull add ~/code/mylib "
                    "--url https://github.com/example/mylib.git --dry-run"
                ),
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
                "vcspull add ~/code/mylib",
                "vcspull add ~/src/mylib --workspace ~/code",
                (
                    "vcspull add ~/code/mylib "
                    "--url https://github.com/example/mylib.git --dry-run"
                ),
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

MIGRATE_DESCRIPTION = build_description(
    """
    Migrate configuration files to the options: form.

    Relocates per-repository rev/shallow/depth keys from the entry root into
    the options: block. Without --write it previews changes; with --write it
    rewrites the file(s).
    """,
    (
        (
            None,
            [
                "vcspull migrate",
                "vcspull migrate -f ./myrepos.yaml",
                "vcspull migrate --write",
                "vcspull migrate --all --write",
            ],
        ),
    ),
)

IMPORT_DESCRIPTION = build_description(
    """
    Import repositories from remote services.

    Fetches repository lists from a remote hosting service and adds them to
    the vcspull configuration.  Choose a service subcommand for details:

      github (gh)       GitHub or GitHub Enterprise
      gitlab (gl)       GitLab (gitlab.com or self-hosted)
      codeberg (cb)     Codeberg
      gitea             Self-hosted Gitea instance
      forgejo           Self-hosted Forgejo instance
      codecommit (cc)   AWS CodeCommit
    """,
    (
        (
            None,
            [
                "vcspull import github torvalds -w ~/repos/linux",
                "vcspull import gh django -w ~/study/python --mode org",
                "vcspull import gitlab mygroup -w ~/work --mode org",
                "vcspull import codecommit -w ~/work/aws --region us-east-1",
            ],
        ),
    ),
)

CONFIG_DESCRIPTION = build_description(
    """
    Inspect the configuration scopes in effect.

    'vcspull config ls' prints every configuration file vcspull would load
    from the current directory, weakest first, with its scope, its repository
    count, and whether a nearer file overrode any of its entries.
    """,
    (
        (
            None,
            [
                "vcspull config ls",
                "vcspull --no-project config ls",
            ],
        ),
    ),
)

TRUST_DESCRIPTION = build_description(
    """
    Trust a project directory's configuration.

    A project config that would check a repository out beyond its own
    directory needs your consent before vcspull will act on it. Trust is
    recorded per directory, so a second config in the same project does not
    re-ask.
    """,
    (
        (
            None,
            [
                "vcspull trust",
                "vcspull trust ~/work/api",
                "vcspull trust --untrust ~/work/api",
                "vcspull trust --show",
            ],
        ),
    ),
)

WORKTREE_DESCRIPTION = build_description(
    """
    Manage git worktrees for repositories.

    Worktrees allow checking out multiple branches/tags/commits of a repository
    simultaneously in separate directories.
    """,
    (
        (
            None,
            [
                "vcspull worktree list",
                "vcspull worktree sync",
                "vcspull worktree sync --dry-run",
                "vcspull worktree prune",
            ],
        ),
    ),
)


def _trust_parser() -> argparse.ArgumentParser:
    """Return the shared parent parser carrying ``--trust-project``.

    Every command that may act on a project ``.vcspull.*`` accepts the trust
    bypass, and the root parser inherits it too, so both
    ``vcspull --trust-project sync`` and ``vcspull sync --trust-project``
    parse. ``SUPPRESS`` keeps the subcommand from clobbering a value the root
    already set.
    """
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument(
        "--trust-project",
        action="store_true",
        default=argparse.SUPPRESS,
        help=(
            "load project configs that check repositories out beyond their "
            "own directory (also VCSPULL_YES=1)"
        ),
    )
    return parser


def _scope_parser(trust: argparse.ArgumentParser) -> argparse.ArgumentParser:
    """Return the shared parent parser for commands that resolve the stack."""
    parser = argparse.ArgumentParser(add_help=False, parents=[trust])
    parser.add_argument(
        "--no-project",
        action="store_true",
        default=argparse.SUPPRESS,
        help="skip .vcspull.* files found above the working directory",
    )
    return parser


@t.overload
def create_parser(
    return_subparsers: t.Literal[True],
) -> tuple[argparse.ArgumentParser, t.Any]: ...


@t.overload
def create_parser(return_subparsers: t.Literal[False]) -> argparse.ArgumentParser: ...


def create_parser(
    return_subparsers: bool = False,
) -> argparse.ArgumentParser | tuple[argparse.ArgumentParser, t.Any]:
    """Create CLI argument parser for vcspull."""
    trust_parent = _trust_parser()
    scope_parent = _scope_parser(trust_parent)

    parser = argparse.ArgumentParser(
        prog="vcspull",
        formatter_class=VcspullHelpFormatter,
        description=CLI_DESCRIPTION,
        parents=[scope_parent],
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
        parents=[scope_parent],
    )
    create_sync_subparser(sync_parser)

    # List command
    list_parser = subparsers.add_parser(
        "list",
        help="list configured repositories",
        formatter_class=VcspullHelpFormatter,
        description=LIST_DESCRIPTION,
        parents=[scope_parent],
    )
    create_list_subparser(list_parser)

    # Status command
    status_parser = subparsers.add_parser(
        "status",
        help="check repository status",
        formatter_class=VcspullHelpFormatter,
        description=STATUS_DESCRIPTION,
        parents=[scope_parent],
    )
    create_status_subparser(status_parser)

    # Search command
    search_parser = subparsers.add_parser(
        "search",
        help="search configured repositories",
        formatter_class=VcspullHelpFormatter,
        description=SEARCH_DESCRIPTION,
        parents=[scope_parent],
    )
    create_search_subparser(search_parser)

    # Add command
    add_parser = subparsers.add_parser(
        "add",
        help="add a single repository",
        formatter_class=VcspullHelpFormatter,
        description=ADD_DESCRIPTION,
        parents=[trust_parent],
    )
    create_add_subparser(add_parser)

    # Discover command
    discover_parser = subparsers.add_parser(
        "discover",
        help="discover repositories from filesystem",
        formatter_class=VcspullHelpFormatter,
        description=DISCOVER_DESCRIPTION,
        parents=[trust_parent],
    )
    create_discover_subparser(discover_parser)

    # Fmt command
    fmt_parser = subparsers.add_parser(
        "fmt",
        help="format configuration files",
        formatter_class=VcspullHelpFormatter,
        description=FMT_DESCRIPTION,
        parents=[scope_parent],
    )
    create_fmt_subparser(fmt_parser)

    # Migrate command
    migrate_parser = subparsers.add_parser(
        "migrate",
        help="migrate configuration files to the options: form",
        formatter_class=VcspullHelpFormatter,
        description=MIGRATE_DESCRIPTION,
        parents=[scope_parent],
    )
    create_migrate_subparser(migrate_parser)

    # Import command
    import_parser = subparsers.add_parser(
        "import",
        help="import repositories from remote services",
        formatter_class=VcspullHelpFormatter,
        description=IMPORT_DESCRIPTION,
    )
    create_import_subparser(import_parser)

    # Config command
    config_parser = subparsers.add_parser(
        "config",
        help="inspect the configuration scopes in effect",
        formatter_class=VcspullHelpFormatter,
        description=CONFIG_DESCRIPTION,
        parents=[scope_parent],
    )
    create_config_subparser(config_parser, scope_parent)

    # Trust command
    trust_parser = subparsers.add_parser(
        "trust",
        help="trust a project directory's configuration",
        formatter_class=VcspullHelpFormatter,
        description=TRUST_DESCRIPTION,
    )
    create_trust_subparser(trust_parser)

    # Worktree command
    worktree_parser = subparsers.add_parser(
        "worktree",
        help="manage git worktrees",
        formatter_class=VcspullHelpFormatter,
        description=WORKTREE_DESCRIPTION,
        parents=[scope_parent],
    )
    create_worktree_subparser(worktree_parser)

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
            migrate_parser,
            import_parser,
            worktree_parser,
            config_parser,
        )
    return parser


def cli(_args: list[str] | None = None) -> None:
    """CLI entry point for vcspull.

    A :exc:`vcspull.exc.VCSPullException` is the tool telling you something
    actionable — an untrusted project config, an unreadable file — so it is
    reported as one line rather than a traceback. Run with
    ``--log-level debug`` to see the stack.
    """
    try:
        _run(_args)
    except exc.VCSPullException as error:
        log.debug("vcspull command failed", exc_info=True)
        print(f"vcspull: {error}", file=sys.stderr)
        raise SystemExit(1) from error


def _run(_args: list[str] | None) -> None:
    """Parse arguments and dispatch to the selected subcommand."""
    parser, subparsers = create_parser(return_subparsers=True)
    (
        sync_parser,
        _list_parser,
        _status_parser,
        search_parser,
        add_parser,
        discover_parser,
        _fmt_parser,
        _migrate_parser,
        _import_parser,
        _worktree_parser,
        config_parser,
    ) = subparsers
    args = parser.parse_args(_args)

    # ``args.verbosity`` is only set by the sync subcommand; default 0
    # everywhere else. The sync ``-v`` ladder (0 → libvcs WARNING; 1 → INFO;
    # 2+ → DEBUG) is documented in :func:`vcspull.log.setup_logger`.
    setup_logger(
        log=log,
        level=args.log_level.upper(),
        verbosity=getattr(args, "verbosity", 0),
    )

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
            include_worktrees=getattr(args, "include_worktrees", False),
            timeout=getattr(args, "timeout", None),
            log_file=getattr(args, "log_file", None),
            no_log_file=getattr(args, "no_log_file", False),
            panel_lines=getattr(args, "panel_lines", None),
            include_project=not getattr(args, "no_project", False),
            trust_project=getattr(args, "trust_project", False),
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
            include_worktrees=getattr(args, "include_worktrees", False),
            include_project=not getattr(args, "no_project", False),
            trust_project=getattr(args, "trust_project", False),
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
            include_project=not getattr(args, "no_project", False),
            trust_project=getattr(args, "trust_project", False),
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
            include_project=not getattr(args, "no_project", False),
            trust_project=getattr(args, "trust_project", False),
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
            trust_project=getattr(args, "trust_project", False),
            dry_run=args.dry_run,
            merge_duplicates=args.merge_duplicates,
            include_worktrees=getattr(args, "include_worktrees", False),
            rev=getattr(args, "pin", None),
            shallow=getattr(args, "shallow", False),
            depth=getattr(args, "depth", None),
        )
    elif args.subparser_name == "fmt":
        format_config_file(
            args.config,
            args.write,
            args.all,
            merge_roots=args.merge_roots,
            trust_project=getattr(args, "trust_project", False),
        )
    elif args.subparser_name == "migrate":
        migrate_config_file(
            args.config,
            args.write,
            args.all,
            trust_project=getattr(args, "trust_project", False),
        )
    elif args.subparser_name == "import":
        handler = getattr(args, "import_handler", None)
        if handler is None:
            _import_parser.print_help()
            return
        result = handler(args)
        if result:
            raise SystemExit(result)
    elif args.subparser_name == "config":
        if args.config_command != "ls":
            config_parser.print_help()
            return
        config_ls(
            include_project=not getattr(args, "no_project", False),
            trust_project=getattr(args, "trust_project", False),
        )
    elif args.subparser_name == "trust":
        trust_command(
            args.directory,
            untrust=args.untrust,
            show=args.show,
        )
    elif args.subparser_name == "worktree":
        handle_worktree_command(args)
