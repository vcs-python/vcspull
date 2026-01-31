"""Worktree management CLI for vcspull."""

from __future__ import annotations

import argparse
import pathlib
import typing as t

from vcspull._internal.private_path import PrivatePath
from vcspull._internal.worktree_sync import (
    WorktreeAction,
    WorktreePlanEntry,
    list_existing_worktrees,
    plan_worktree_sync,
    prune_worktrees,
    sync_all_worktrees,
)
from vcspull.config import expand_dir, filter_repos, find_config_files, load_configs

from ._colors import Colors, get_color_mode
from ._output import OutputFormatter, get_output_mode
from ._workspaces import filter_by_workspace

if t.TYPE_CHECKING:
    from vcspull.types import ConfigDict


WORKTREE_SYMBOLS: dict[WorktreeAction, str] = {
    WorktreeAction.CREATE: "+",
    WorktreeAction.UPDATE: "~",
    WorktreeAction.UNCHANGED: "✓",
    WorktreeAction.BLOCKED: "⚠",
    WorktreeAction.ERROR: "✗",
}


def create_worktree_subparser(parser: argparse.ArgumentParser) -> None:
    """Create ``vcspull worktree`` argument subparser.

    Parameters
    ----------
    parser : argparse.ArgumentParser
        The parser to configure
    """
    subparsers = parser.add_subparsers(dest="worktree_action")

    # List subcommand
    list_parser = subparsers.add_parser(
        "list",
        help="list configured worktrees and their status",
    )
    _add_common_args(list_parser)

    # Sync subcommand
    sync_parser = subparsers.add_parser(
        "sync",
        help="create or update worktrees",
    )
    _add_common_args(sync_parser)
    sync_parser.add_argument(
        "--dry-run",
        "-n",
        action="store_true",
        help="preview what would be synced without making changes",
    )

    # Prune subcommand
    prune_parser = subparsers.add_parser(
        "prune",
        help="remove worktrees not in configuration",
    )
    _add_common_args(prune_parser)
    prune_parser.add_argument(
        "--dry-run",
        "-n",
        action="store_true",
        help="preview what would be pruned without making changes",
    )


def _add_common_args(parser: argparse.ArgumentParser) -> None:
    """Add common arguments to worktree subparsers.

    Parameters
    ----------
    parser : argparse.ArgumentParser
        The subparser to add arguments to.
    """
    parser.add_argument(
        "-f",
        "--file",
        dest="config",
        metavar="FILE",
        help="path to config file (default: ~/.vcspull.yaml or ./.vcspull.yaml)",
    )
    parser.add_argument(
        "-w",
        "--workspace",
        "--workspace-root",
        dest="workspace_root",
        metavar="DIR",
        help="filter by workspace root directory",
    )
    parser.add_argument(
        "repo_patterns",
        metavar="pattern",
        nargs="*",
        help="patterns / terms of repos, accepts globs / fnmatch(3)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="output_json",
        help="output as JSON",
    )
    parser.add_argument(
        "--ndjson",
        action="store_true",
        dest="output_ndjson",
        help="output as NDJSON (one JSON per line)",
    )
    parser.add_argument(
        "--color",
        choices=["auto", "always", "never"],
        default="auto",
        help="when to use colors (default: auto)",
    )


def handle_worktree_command(args: argparse.Namespace) -> None:
    """Handle the vcspull worktree command.

    Parameters
    ----------
    args : argparse.Namespace
        Parsed command line arguments.
    """
    if args.worktree_action is None:
        print("Usage: vcspull worktree {list,sync,prune} [options]")
        return

    # Load configs
    config_path = pathlib.Path(args.config) if args.config else None
    if config_path:
        configs = load_configs([config_path])
    else:
        configs = load_configs(find_config_files(include_home=True))

    # Filter by patterns
    if args.repo_patterns:
        found_repos: list[ConfigDict] = []
        for pattern in args.repo_patterns:
            found_repos.extend(filter_repos(configs, name=pattern))
    else:
        found_repos = configs

    # Filter by workspace root
    if args.workspace_root:
        found_repos = filter_by_workspace(found_repos, args.workspace_root)

    # Filter to only repos with worktrees configured
    repos_with_worktrees = [repo for repo in found_repos if repo.get("worktrees")]

    output_mode = get_output_mode(args.output_json, args.output_ndjson)
    formatter = OutputFormatter(output_mode)
    colors = Colors(get_color_mode(args.color))

    if args.worktree_action == "list":
        _handle_list(repos_with_worktrees, formatter, colors)
    elif args.worktree_action == "sync":
        _handle_sync(
            repos_with_worktrees,
            formatter,
            colors,
            dry_run=args.dry_run,
        )
    elif args.worktree_action == "prune":
        _handle_prune(
            repos_with_worktrees,
            formatter,
            colors,
            dry_run=args.dry_run,
        )

    formatter.finalize()


def _handle_list(
    repos: list[ConfigDict],
    formatter: OutputFormatter,
    colors: Colors,
) -> None:
    """Handle the worktree list subcommand.

    Parameters
    ----------
    repos : list[ConfigDict]
        List of repository configurations with worktrees.
    formatter : OutputFormatter
        Output formatter for JSON/NDJSON/human output.
    colors : Colors
        Color manager for terminal output.

    Notes
    -----
    See tests/test_worktree.py for integration tests.
    """
    if not repos:
        formatter.emit_text(
            colors.warning("No repositories with worktrees configured.")
        )
        return

    for repo in repos:
        repo_name = repo.get("name", "unknown")
        repo_path = pathlib.Path(str(repo.get("path", ".")))
        workspace_root = str(repo.get("workspace_root", "."))
        worktrees_config = repo.get("worktrees", [])

        if not worktrees_config:
            continue

        workspace_path = expand_dir(pathlib.Path(workspace_root))
        entries = plan_worktree_sync(repo_path, worktrees_config, workspace_path)

        # Human output: repo header
        formatter.emit_text(
            f"\n{colors.highlight(repo_name)} ({PrivatePath(repo_path)})"
        )

        for entry in entries:
            _emit_worktree_entry(entry, formatter, colors)


def _emit_worktree_entry(
    entry: WorktreePlanEntry,
    formatter: OutputFormatter,
    colors: Colors,
) -> None:
    """Emit a single worktree entry to both JSON and human output.

    Parameters
    ----------
    entry : WorktreePlanEntry
        The worktree plan entry to emit.
    formatter : OutputFormatter
        Output formatter for JSON/NDJSON/human output.
    colors : Colors
        Color manager for terminal output.
    """
    symbol = WORKTREE_SYMBOLS.get(entry.action, "?")

    color_fn: t.Callable[[str], str]
    if entry.action == WorktreeAction.CREATE:
        color_fn = colors.success
    elif entry.action == WorktreeAction.UPDATE:
        color_fn = colors.warning
    elif entry.action == WorktreeAction.UNCHANGED:
        color_fn = colors.muted
    elif entry.action == WorktreeAction.BLOCKED:
        color_fn = colors.warning
    else:
        color_fn = colors.error

    ref_display = f"{entry.ref_type}:{entry.ref_value}"
    status = "exists" if entry.exists else "missing"

    # JSON output
    formatter.emit(
        {
            "worktree_path": str(PrivatePath(entry.worktree_path)),
            "ref_type": entry.ref_type,
            "ref_value": entry.ref_value,
            "action": entry.action.value,
            "exists": entry.exists,
            "is_dirty": entry.is_dirty,
            "detail": entry.detail,
            "error": entry.error,
        }
    )

    # Human output
    detail_text = entry.detail or entry.error or status
    formatter.emit_text(
        f"  {color_fn(symbol)} {colors.info(ref_display):20s} "
        f"{colors.muted(str(PrivatePath(entry.worktree_path)))} "
        f"({color_fn(detail_text)})"
    )


def _handle_sync(
    repos: list[ConfigDict],
    formatter: OutputFormatter,
    colors: Colors,
    *,
    dry_run: bool = False,
) -> None:
    """Handle the worktree sync subcommand.

    Parameters
    ----------
    repos : list[ConfigDict]
        List of repository configurations with worktrees.
    formatter : OutputFormatter
        Output formatter for JSON/NDJSON/human output.
    colors : Colors
        Color manager for terminal output.
    dry_run : bool
        If True, only preview what would be synced.

    Notes
    -----
    See tests/test_worktree.py for integration tests.
    """
    if not repos:
        formatter.emit_text(
            colors.warning("No repositories with worktrees configured.")
        )
        return

    total_created = 0
    total_updated = 0
    total_unchanged = 0
    total_blocked = 0
    total_errors = 0

    for repo in repos:
        repo_name = repo.get("name", "unknown")
        repo_path = pathlib.Path(str(repo.get("path", ".")))
        workspace_root = str(repo.get("workspace_root", "."))
        worktrees_config = repo.get("worktrees", [])

        if not worktrees_config:
            continue

        workspace_path = expand_dir(pathlib.Path(workspace_root))

        formatter.emit_text(
            f"\n{colors.highlight(repo_name)} ({PrivatePath(repo_path)})"
        )

        result = sync_all_worktrees(
            repo_path,
            worktrees_config,
            workspace_path,
            dry_run=dry_run,
        )

        for entry in result.entries:
            _emit_worktree_entry(entry, formatter, colors)

        total_created += result.created
        total_updated += result.updated
        total_unchanged += result.unchanged
        total_blocked += result.blocked
        total_errors += result.errors

    # Summary
    action_word = "Would sync" if dry_run else "Synced"
    formatter.emit_text(
        f"\n{colors.info('Summary:')} {action_word} worktrees: "
        f"{colors.success(f'+{total_created}')} created, "
        f"{colors.warning(f'~{total_updated}')} updated, "
        f"{colors.muted(f'✓{total_unchanged}')} unchanged, "
        f"{colors.warning(f'⚠{total_blocked}')} blocked, "
        f"{colors.error(f'✗{total_errors}')} errors"
    )

    if dry_run:
        formatter.emit_text(
            colors.muted("Tip: run without --dry-run to apply changes.")
        )


def _handle_prune(
    repos: list[ConfigDict],
    formatter: OutputFormatter,
    colors: Colors,
    *,
    dry_run: bool = False,
) -> None:
    """Handle the worktree prune subcommand.

    Parameters
    ----------
    repos : list[ConfigDict]
        List of repository configurations with worktrees.
    formatter : OutputFormatter
        Output formatter for JSON/NDJSON/human output.
    colors : Colors
        Color manager for terminal output.
    dry_run : bool
        If True, only preview what would be pruned.

    Notes
    -----
    See tests/test_worktree.py for integration tests.
    """
    if not repos:
        formatter.emit_text(
            colors.warning("No repositories with worktrees configured.")
        )
        return

    total_pruned = 0

    for repo in repos:
        repo_name = repo.get("name", "unknown")
        repo_path = pathlib.Path(str(repo.get("path", ".")))
        workspace_root = str(repo.get("workspace_root", "."))
        worktrees_config = repo.get("worktrees", [])

        workspace_path = expand_dir(pathlib.Path(workspace_root))

        # Get existing worktrees
        existing = list_existing_worktrees(repo_path)
        if not existing:
            continue

        pruned = prune_worktrees(
            repo_path,
            worktrees_config or [],
            workspace_path,
            dry_run=dry_run,
        )

        if pruned:
            formatter.emit_text(
                f"\n{colors.highlight(repo_name)} ({PrivatePath(repo_path)})"
            )
            for wt_path in pruned:
                action_word = "Would prune" if dry_run else "Pruned"
                formatter.emit_text(
                    f"  {colors.warning('-')} {action_word}: "
                    f"{colors.muted(str(PrivatePath(wt_path)))}"
                )
                formatter.emit(
                    {
                        "action": "prune",
                        "worktree_path": str(PrivatePath(wt_path)),
                        "dry_run": dry_run,
                    }
                )
                total_pruned += 1

    if total_pruned == 0:
        formatter.emit_text(colors.muted("No orphaned worktrees to prune."))
    else:
        action_word = "Would prune" if dry_run else "Pruned"
        formatter.emit_text(
            f"\n{colors.info('Summary:')} {action_word} {total_pruned} worktree(s)"
        )

    if dry_run and total_pruned > 0:
        formatter.emit_text(
            colors.muted("Tip: run without --dry-run to apply changes.")
        )
