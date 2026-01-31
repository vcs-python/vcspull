"""Synchronization functionality for vcspull."""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import logging
import os
import pathlib
import re
import subprocess
import sys
import typing as t
from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
from io import StringIO
from time import perf_counter

from libvcs._internal.shortcuts import create_project
from libvcs._internal.types import VCSLiteral
from libvcs.sync.git import GitSync
from libvcs.sync.hg import HgSync
from libvcs.sync.svn import SvnSync
from libvcs.url import registry as url_tools

from vcspull import exc
from vcspull._internal.private_path import PrivatePath
from vcspull._internal.worktree_sync import (
    WorktreeAction,
    sync_all_worktrees,
)
from vcspull.config import expand_dir, filter_repos, find_config_files, load_configs
from vcspull.types import ConfigDict

from ._colors import Colors, get_color_mode
from ._output import (
    OutputFormatter,
    OutputMode,
    PlanAction,
    PlanEntry,
    PlanRenderOptions,
    PlanResult,
    PlanSummary,
    get_output_mode,
)
from ._workspaces import filter_by_workspace
from .status import check_repo_status

log = logging.getLogger(__name__)

ProgressCallback = Callable[[str, datetime], None]


PLAN_SYMBOLS: dict[PlanAction, str] = {
    PlanAction.CLONE: "+",
    PlanAction.UPDATE: "~",
    PlanAction.UNCHANGED: "✓",
    PlanAction.BLOCKED: "⚠",
    PlanAction.ERROR: "✗",
}

PLAN_ORDER: dict[PlanAction, int] = {
    PlanAction.ERROR: 0,
    PlanAction.BLOCKED: 1,
    PlanAction.CLONE: 2,
    PlanAction.UPDATE: 3,
    PlanAction.UNCHANGED: 4,
}

PLAN_TIP_MESSAGE = (
    "Tip: run without --dry-run to apply. Use --show-unchanged to include ✓ rows."
)

DEFAULT_PLAN_CONCURRENCY = max(1, min(32, (os.cpu_count() or 4) * 2))
ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*m")


@dataclass
class SyncPlanConfig:
    """Configuration options for building sync plans."""

    fetch: bool
    offline: bool


def _visible_length(text: str) -> int:
    """Return the printable length of string stripped of ANSI codes."""
    return len(ANSI_ESCAPE_RE.sub("", text))


class PlanProgressPrinter:
    """Render incremental plan progress for human-readable dry runs."""

    def __init__(self, total: int, colors: Colors, enabled: bool) -> None:
        self.total = total
        self._colors = colors
        self._enabled = enabled and total > 0
        self._stream = sys.stdout
        self._last_render_len = 0

    def update(self, summary: PlanSummary, processed: int) -> None:
        """Update the progress line with the latest summary counts."""
        if not self._enabled:
            return

        line = " ".join(
            (
                f"Progress: {processed}/{self.total}",
                self._colors.success(f"+:{summary.clone}"),
                self._colors.warning(f"~:{summary.update}"),
                self._colors.muted(f"✓:{summary.unchanged}"),
                self._colors.warning(f"⚠:{summary.blocked}"),
                self._colors.error(f"✗:{summary.errors}"),
            ),
        )
        clean_len = _visible_length(line)
        padding = max(self._last_render_len - clean_len, 0)
        self._stream.write("\r" + line + " " * padding)
        self._stream.flush()
        self._last_render_len = clean_len

    def finish(self) -> None:
        """Ensure the progress line is terminated with a newline."""
        if not self._enabled:
            return
        self._stream.write("\n")
        self._stream.flush()


def _extract_repo_url(repo: ConfigDict) -> str | None:
    """Extract the primary repository URL from a config dictionary."""
    url = repo.get("url")
    if isinstance(url, str):
        return url
    pip_url = repo.get("pip_url")
    if isinstance(pip_url, str):
        return pip_url
    return None


def _get_repo_path(repo: ConfigDict) -> pathlib.Path:
    """Return the resolved filesystem path for a repository entry."""
    raw_path = repo.get("path")
    if raw_path is None:
        return pathlib.Path.cwd()
    return pathlib.Path(str(raw_path)).expanduser()


def clamp(n: int, _min: int, _max: int) -> int:
    """Clamp a number between a min and max value."""
    return max(_min, min(n, _max))


EXIT_ON_ERROR_MSG = "Exiting via error (--exit-on-error passed)"
NO_REPOS_FOR_TERM_MSG = 'No repo found in config(s) for "{name}"'


def _maybe_fetch(
    repo_path: pathlib.Path,
    *,
    config: SyncPlanConfig,
) -> tuple[bool, str | None]:
    """Optionally fetch remote refs to provide accurate status."""
    if config.offline or not config.fetch:
        return True, None
    if not (repo_path / ".git").exists():
        return True, None

    try:
        result = subprocess.run(
            ["git", "fetch", "--prune"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return False, "git executable not found"
    except OSError as exc:
        return False, str(exc)

    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip()
        if not message:
            message = f"git fetch failed with exit code {result.returncode}"
        return False, message

    return True, None


def _determine_plan_action(
    status: dict[str, t.Any],
    *,
    config: SyncPlanConfig,
) -> tuple[PlanAction, str | None]:
    """Decide which plan action applies to a repository."""
    if not status.get("exists"):
        return PlanAction.CLONE, "missing"

    if not status.get("is_git"):
        return PlanAction.UPDATE, "non-git VCS (detailed plan not available)"

    clean_state = status.get("clean")
    if clean_state is False:
        return PlanAction.BLOCKED, "working tree has local changes"

    ahead = status.get("ahead")
    behind = status.get("behind")

    if isinstance(ahead, int) and isinstance(behind, int):
        if ahead > 0 and behind > 0:
            return PlanAction.BLOCKED, f"diverged (ahead {ahead}, behind {behind})"
        if behind > 0:
            return PlanAction.UPDATE, f"behind {behind}"
        if ahead > 0:
            return PlanAction.BLOCKED, f"ahead by {ahead}"
        return PlanAction.UNCHANGED, "up to date"

    if config.offline:
        return PlanAction.UPDATE, "remote state unknown (offline)"

    return PlanAction.UPDATE, "remote state unknown; use --fetch"


def _update_summary(summary: PlanSummary, action: PlanAction) -> None:
    """Update summary counters for the given plan action."""
    if action is PlanAction.CLONE:
        summary.clone += 1
    elif action is PlanAction.UPDATE:
        summary.update += 1
    elif action is PlanAction.UNCHANGED:
        summary.unchanged += 1
    elif action is PlanAction.BLOCKED:
        summary.blocked += 1
    elif action is PlanAction.ERROR:
        summary.errors += 1


def _build_plan_entry(
    repo: ConfigDict,
    *,
    config: SyncPlanConfig,
) -> PlanEntry:
    """Construct a plan entry for a repository configuration."""
    repo_path = _get_repo_path(repo)
    workspace_root = str(repo.get("workspace_root", ""))

    fetch_ok = True
    fetch_error: str | None = None
    if repo_path.exists() and (repo_path / ".git").exists():
        fetch_ok, fetch_error = _maybe_fetch(repo_path, config=config)

    status = check_repo_status(repo, detailed=True)

    action: PlanAction
    detail: str | None
    if not fetch_ok:
        action = PlanAction.ERROR
        detail = fetch_error or "failed to refresh remotes"
    else:
        action, detail = _determine_plan_action(status, config=config)

    return PlanEntry(
        name=str(repo.get("name", "unknown")),
        path=str(PrivatePath(repo_path)),
        workspace_root=workspace_root,
        action=action,
        detail=detail,
        url=_extract_repo_url(repo),
        branch=status.get("branch"),
        remote_branch=None,
        current_rev=None,
        target_rev=None,
        ahead=status.get("ahead"),
        behind=status.get("behind"),
        dirty=status.get("clean") is False if status.get("clean") is not None else None,
        error=fetch_error if not fetch_ok else None,
    )


async def _build_plan_result_async(
    repos: list[ConfigDict],
    *,
    config: SyncPlanConfig,
    progress: PlanProgressPrinter | None,
) -> PlanResult:
    """Build a plan asynchronously while updating progress output."""
    if not repos:
        return PlanResult(entries=[], summary=PlanSummary())

    semaphore = asyncio.Semaphore(min(DEFAULT_PLAN_CONCURRENCY, len(repos)))
    entries: list[PlanEntry] = []
    summary = PlanSummary()

    async def evaluate(repo: ConfigDict) -> PlanEntry:
        async with semaphore:
            return await asyncio.to_thread(_build_plan_entry, repo=repo, config=config)

    tasks = [asyncio.create_task(evaluate(repo)) for repo in repos]

    for index, task in enumerate(asyncio.as_completed(tasks), start=1):
        entry = await task
        entries.append(entry)
        _update_summary(summary, entry.action)
        if progress is not None:
            progress.update(summary, index)

    return PlanResult(entries=entries, summary=summary)


def _filter_entries_for_display(
    entries: list[PlanEntry],
    *,
    show_unchanged: bool,
) -> list[PlanEntry]:
    """Filter entries based on whether unchanged repos should be rendered."""
    if show_unchanged:
        return list(entries)
    return [entry for entry in entries if entry.action is not PlanAction.UNCHANGED]


def _format_detail_text(
    entry: PlanEntry,
    *,
    colors: Colors,
    include_extras: bool,
) -> str:
    """Generate the detail text for a plan entry."""
    detail = entry.detail or ""
    extra_bits: list[str] = []

    if include_extras:
        if entry.action is PlanAction.UPDATE and entry.behind:
            extra_bits.append(f"behind {entry.behind}")
        if entry.action is PlanAction.CLONE and entry.url:
            extra_bits.append(entry.url)
        if entry.action is PlanAction.BLOCKED and entry.error:
            extra_bits.append(entry.error)

    if extra_bits:
        detail = f"{detail} {'; '.join(extra_bits)}".strip()

    color_map: dict[PlanAction, t.Callable[[str], str]] = {
        PlanAction.CLONE: colors.success,
        PlanAction.UPDATE: colors.warning,
        PlanAction.UNCHANGED: colors.muted,
        PlanAction.BLOCKED: colors.warning,
        PlanAction.ERROR: colors.error,
    }

    formatter = color_map.get(entry.action, colors.info)
    return formatter(detail) if detail else ""


def _render_plan(
    formatter: OutputFormatter,
    colors: Colors,
    plan: PlanResult,
    render_options: PlanRenderOptions,
    *,
    dry_run: bool,
    total_repos: int,
) -> None:
    """Render the plan in human-readable format."""
    summary = plan.summary
    summary_line = (
        f"Plan: "
        f"{colors.success(str(summary.clone))} to clone (+), "
        f"{colors.warning(str(summary.update))} to update (~), "
        f"{colors.muted(str(summary.unchanged))} unchanged (✓), "
        f"{colors.warning(str(summary.blocked))} blocked (⚠), "
        f"{colors.error(str(summary.errors))} errors (✗)"
    )
    formatter.emit_text(summary_line)

    if total_repos == 0:
        formatter.emit_text(colors.warning("No repositories matched the criteria."))
        return

    if render_options.summary_only:
        if dry_run:
            formatter.emit_text(colors.muted(PLAN_TIP_MESSAGE))
        return

    display_entries = _filter_entries_for_display(
        sorted(
            plan.entries,
            key=lambda entry: (
                PLAN_ORDER.get(entry.action, 99),
                entry.workspace_root or "",
                entry.name.lower(),
            ),
        ),
        show_unchanged=render_options.show_unchanged,
    )

    if not display_entries:
        formatter.emit_text(colors.muted("All repositories are up to date."))
        if dry_run:
            formatter.emit_text(colors.muted(PLAN_TIP_MESSAGE))
        return

    formatter.emit_text("")

    grouped: dict[str, list[PlanEntry]] = {}
    for entry in display_entries:
        key = entry.workspace_root or "(no workspace)"
        grouped.setdefault(key, []).append(entry)

    for idx, (workspace, group_entries) in enumerate(grouped.items()):
        if idx > 0:
            formatter.emit_text("")
        formatter.emit_text(colors.highlight(workspace))
        name_width = max(len(entry.name) for entry in group_entries)

        for entry in group_entries:
            symbol = PLAN_SYMBOLS.get(entry.action, "?")
            color_map: dict[PlanAction, t.Callable[[str], str]] = {
                PlanAction.CLONE: colors.success,
                PlanAction.UPDATE: colors.warning,
                PlanAction.UNCHANGED: colors.muted,
                PlanAction.BLOCKED: colors.warning,
                PlanAction.ERROR: colors.error,
            }
            symbol_text = color_map.get(entry.action, colors.info)(symbol)

            display_path = entry.path
            if render_options.relative_paths and entry.workspace_root:
                workspace_path = pathlib.Path(entry.workspace_root).expanduser()
                try:
                    rel_path = pathlib.Path(entry.path).relative_to(workspace_path)
                    display_path = str(rel_path)
                except ValueError:
                    display_path = entry.path
            else:
                # Contract home directory for privacy/brevity in human output
                display_path = str(PrivatePath(display_path))

            detail_text = _format_detail_text(
                entry,
                colors=colors,
                include_extras=render_options.verbosity > 0 or render_options.long,
            )

            line = (
                f"  {symbol_text} {colors.info(entry.name.ljust(name_width))}  "
                f"{colors.muted(display_path)}"
            )
            if detail_text:
                line = f"{line}  {detail_text}"
            formatter.emit_text(line.rstrip())

            if render_options.long or render_options.verbosity > 1:
                extra_lines: list[str] = []
                if entry.url:
                    extra_lines.append(f"url: {entry.url}")
                if entry.ahead is not None or entry.behind is not None:
                    extra_lines.append(
                        f"ahead/behind: {entry.ahead or 0}/{entry.behind or 0}",
                    )
                if entry.error:
                    extra_lines.append(f"error: {entry.error}")
                for msg in extra_lines:
                    formatter.emit_text(f"    {colors.muted(msg)}")

    if dry_run:
        formatter.emit_text(colors.muted(PLAN_TIP_MESSAGE))


def _emit_plan_output(
    formatter: OutputFormatter,
    colors: Colors,
    plan: PlanResult,
    render_options: PlanRenderOptions,
    *,
    dry_run: bool,
    total_repos: int,
) -> None:
    """Emit plan output for the requested format."""
    if formatter.mode == OutputMode.HUMAN:
        _render_plan(
            formatter=formatter,
            colors=colors,
            plan=plan,
            render_options=render_options,
            dry_run=dry_run,
            total_repos=total_repos,
        )
        return

    display_entries = _filter_entries_for_display(
        plan.entries,
        show_unchanged=render_options.show_unchanged,
    )

    for entry in display_entries:
        formatter.emit(entry)
    formatter.emit(plan.summary)


def create_sync_subparser(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    """Create ``vcspull sync`` argument subparser."""
    config_file = parser.add_argument(
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
        "--dry-run",
        "-n",
        action="store_true",
        help="preview what would be synced without making changes",
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
    parser.add_argument(
        "--exit-on-error",
        "-x",
        action="store_true",
        dest="exit_on_error",
        help="exit immediately encountering error (when syncing multiple repos)",
    )
    parser.add_argument(
        "--show-unchanged",
        action="store_true",
        help="include repositories that are already up to date",
    )
    parser.add_argument(
        "--summary-only",
        action="store_true",
        dest="summary_only",
        help="print only the plan summary line",
    )
    parser.add_argument(
        "--long",
        action="store_true",
        dest="long_view",
        help="show extended details for each repository",
    )
    parser.add_argument(
        "--relative-paths",
        action="store_true",
        dest="relative_paths",
        help="display repository paths relative to the workspace root",
    )
    parser.add_argument(
        "--fetch",
        action="store_true",
        help="refresh remote tracking information before planning",
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="skip network access while planning (overrides --fetch)",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        dest="verbosity",
        default=0,
        help="increase plan verbosity (-vv for maximum detail)",
    )
    parser.add_argument(
        "--all",
        "-a",
        action="store_true",
        dest="sync_all",
        help="sync all configured repositories",
    )
    parser.add_argument(
        "--include-worktrees",
        action="store_true",
        dest="include_worktrees",
        help="also sync configured worktrees for each repository",
    )

    try:
        import shtab

        config_file.complete = shtab.FILE  # type: ignore
    except ImportError:
        pass
    return parser


def sync(
    repo_patterns: list[str],
    config: pathlib.Path | None,
    workspace_root: str | None,
    dry_run: bool,
    output_json: bool,
    output_ndjson: bool,
    color: str,
    exit_on_error: bool,
    show_unchanged: bool,
    summary_only: bool,
    long_view: bool,
    relative_paths: bool,
    fetch: bool,
    offline: bool,
    verbosity: int,
    sync_all: bool = False,
    parser: argparse.ArgumentParser
    | None = None,  # optional so sync can be unit tested
    include_worktrees: bool = False,
) -> None:
    """Entry point for ``vcspull sync``."""
    # Show help if no patterns and --all not specified
    if not repo_patterns and not sync_all:
        if parser is not None:
            parser.print_help()
        else:
            log.warning(
                "sync() called with no repo patterns and no --all flag; nothing to do",
            )
        return

    output_mode = get_output_mode(output_json, output_ndjson)
    formatter = OutputFormatter(output_mode)
    colors = Colors(get_color_mode(color))

    verbosity_level = clamp(verbosity, 0, 2)
    render_options = PlanRenderOptions(
        show_unchanged=show_unchanged,
        summary_only=summary_only,
        long=long_view,
        verbosity=verbosity_level,
        relative_paths=relative_paths,
    )
    plan_config = SyncPlanConfig(fetch=bool(fetch and not offline), offline=offline)

    if config:
        configs = load_configs([config])
    else:
        configs = load_configs(find_config_files(include_home=True))
    found_repos: list[ConfigDict] = []
    unmatched_count = 0

    if sync_all:
        if repo_patterns:
            msg = "--all cannot be combined with positional patterns"
            if parser is not None:
                parser.error(msg)
            else:
                raise SystemExit(msg)
        # Load all repos when --all is specified
        found_repos = list(configs)
    else:
        for repo_pattern in repo_patterns:
            path, vcs_url, name = None, None, None
            if any(repo_pattern.startswith(n) for n in ["./", "/", "~", "$HOME"]):
                path = repo_pattern
            elif any(repo_pattern.startswith(n) for n in ["http", "git", "svn", "hg"]):
                vcs_url = repo_pattern
            else:
                name = repo_pattern

            found = filter_repos(configs, path=path, vcs_url=vcs_url, name=name)
            if not found:
                search_term = name or path or vcs_url or repo_pattern
                log.debug(NO_REPOS_FOR_TERM_MSG.format(name=search_term))
                if not summary_only:
                    formatter.emit_text(
                        f"{colors.error('✗')} "
                        f"{NO_REPOS_FOR_TERM_MSG.format(name=search_term)}",
                    )
                unmatched_count += 1
            found_repos.extend(found)

        # Deduplicate repos matched by multiple patterns
        seen_paths: set[str] = set()
        deduped: list[ConfigDict] = []
        for repo in found_repos:
            key = str(repo.get("path", ""))
            if key not in seen_paths:
                seen_paths.add(key)
                deduped.append(repo)
        found_repos = deduped

    if workspace_root:
        found_repos = filter_by_workspace(found_repos, workspace_root)

    total_repos = len(found_repos)

    if dry_run:
        progress_enabled = formatter.mode == OutputMode.HUMAN and sys.stdout.isatty()
        progress_printer = PlanProgressPrinter(total_repos, colors, progress_enabled)
        start_time = perf_counter()
        plan_result = asyncio.run(
            _build_plan_result_async(
                found_repos,
                config=plan_config,
                progress=progress_printer if progress_enabled else None,
            ),
        )
        plan_result.summary.duration_ms = int((perf_counter() - start_time) * 1000)
        if progress_enabled:
            progress_printer.finish()
        _emit_plan_output(
            formatter=formatter,
            colors=colors,
            plan=plan_result,
            render_options=render_options,
            dry_run=True,
            total_repos=total_repos,
        )
        formatter.finalize()
        return

    if total_repos == 0:
        if unmatched_count > 0:
            summary = {
                "total": 0,
                "synced": 0,
                "previewed": 0,
                "failed": 0,
                "unmatched": unmatched_count,
            }
            _emit_summary(formatter, colors, summary)
            if exit_on_error:
                formatter.finalize()
                if parser is not None:
                    parser.exit(status=1, message=EXIT_ON_ERROR_MSG)
                raise SystemExit(EXIT_ON_ERROR_MSG)
        else:
            formatter.emit_text(
                colors.warning("No repositories matched the criteria."),
            )
        formatter.finalize()
        return

    is_human = formatter.mode == OutputMode.HUMAN

    summary = {
        "total": 0,
        "synced": 0,
        "previewed": 0,
        "failed": 0,
        "unmatched": unmatched_count,
    }

    progress_callback: ProgressCallback
    if is_human:
        progress_callback = progress_cb
    else:

        def silent_progress(output: str, timestamp: datetime) -> None:
            """Suppress progress for machine-readable output."""
            return

        progress_callback = silent_progress

    for repo in found_repos:
        repo_name = repo.get("name", "unknown")
        repo_path = repo.get("path", "unknown")
        workspace_label = repo.get("workspace_root", "")
        display_repo_path = str(PrivatePath(repo_path))

        summary["total"] += 1

        event: dict[str, t.Any] = {
            "reason": "sync",
            "name": repo_name,
            "path": display_repo_path,
            "workspace_root": str(workspace_label),
        }

        buffer: StringIO | None = None
        captured_output: str | None = None
        try:
            if is_human:
                update_repo(repo, progress_callback=progress_callback)
            else:
                buffer = StringIO()
                with (
                    contextlib.redirect_stdout(buffer),
                    contextlib.redirect_stderr(
                        buffer,
                    ),
                ):
                    update_repo(repo, progress_callback=progress_callback)
                captured_output = buffer.getvalue()
        except Exception as e:
            summary["failed"] += 1
            event["status"] = "error"
            event["error"] = str(e)
            if not is_human and buffer is not None and not captured_output:
                captured_output = buffer.getvalue()
            if captured_output:
                event["details"] = captured_output.strip()
            formatter.emit(event)
            if is_human:
                log.debug(
                    "Failed syncing %s",
                    repo_name,
                )
            if log.isEnabledFor(logging.DEBUG):
                import traceback

                traceback.print_exc()
            formatter.emit_text(
                f"{colors.error('✗')} Failed syncing {colors.info(repo_name)}: "
                f"{colors.error(str(e))}",
            )
            if exit_on_error:
                _emit_summary(formatter, colors, summary)
                formatter.finalize()
                if parser is not None:
                    parser.exit(status=1, message=EXIT_ON_ERROR_MSG)
                raise SystemExit(EXIT_ON_ERROR_MSG) from e
            continue

        summary["synced"] += 1
        event["status"] = "synced"
        formatter.emit(event)
        formatter.emit_text(
            f"{colors.success('✓')} Synced {colors.info(repo_name)} "
            f"{colors.muted('→')} {display_repo_path}",
        )

        # Sync worktrees if enabled and configured
        worktrees_config = repo.get("worktrees")
        if include_worktrees and worktrees_config:
            workspace_path = expand_dir(pathlib.Path(str(workspace_label)))
            repo_path_obj = pathlib.Path(str(repo_path))

            wt_result = sync_all_worktrees(
                repo_path_obj,
                worktrees_config,
                workspace_path,
                dry_run=dry_run,
            )

            for entry in wt_result.entries:
                ref_display = f"{entry.ref_type}:{entry.ref_value}"
                wt_path_display = str(PrivatePath(entry.worktree_path))

                if entry.action == WorktreeAction.CREATE:
                    sym = colors.success("+")
                    ref = colors.info(ref_display)
                    arrow = colors.muted("→")
                    formatter.emit_text(
                        f"    {sym} worktree {ref} {arrow} {wt_path_display}",
                    )
                elif entry.action == WorktreeAction.UPDATE:
                    sym = colors.warning("~")
                    ref = colors.info(ref_display)
                    arrow = colors.muted("→")
                    formatter.emit_text(
                        f"    {sym} worktree {ref} {arrow} {wt_path_display}",
                    )
                elif entry.action == WorktreeAction.BLOCKED:
                    sym = colors.warning("⚠")
                    ref = colors.info(ref_display)
                    formatter.emit_text(
                        f"    {sym} worktree {ref} blocked: {entry.detail}",
                    )
                elif entry.action == WorktreeAction.ERROR:
                    formatter.emit_text(
                        f"    {colors.error('✗')} worktree {colors.info(ref_display)} "
                        f"error: {entry.error}",
                    )

    _emit_summary(formatter, colors, summary)

    if exit_on_error and unmatched_count > 0:
        formatter.finalize()
        if parser is not None:
            parser.exit(status=1, message=EXIT_ON_ERROR_MSG)
        raise SystemExit(EXIT_ON_ERROR_MSG)

    formatter.finalize()


def _emit_summary(
    formatter: OutputFormatter,
    colors: Colors,
    summary: dict[str, int],
) -> None:
    """Emit the structured summary event and optional human-readable text."""
    formatter.emit({"reason": "summary", **summary})
    if formatter.mode == OutputMode.HUMAN:
        previewed = summary.get("previewed", 0)
        unmatched = summary.get("unmatched", 0)
        parts = [
            f"\n{colors.info('Summary:')} "
            f"{colors.info(str(summary['total']))} repos, "
            f"{colors.success(str(summary['synced']))} synced, "
            f"{colors.error(str(summary['failed']))} failed",
        ]
        if previewed > 0:
            parts.append(
                f", {colors.warning(str(previewed))} previewed",
            )
        if unmatched > 0:
            parts.append(
                f", {colors.warning(str(unmatched))} unmatched",
            )
        formatter.emit_text("".join(parts))


def progress_cb(output: str, timestamp: datetime) -> None:
    """CLI Progress callback for command."""
    sys.stdout.write(output)
    sys.stdout.flush()


def guess_vcs(url: str) -> VCSLiteral | None:
    """Guess the VCS from a URL."""
    vcs_matches = url_tools.registry.match(url=url, is_explicit=True)

    if len(vcs_matches) == 0:
        log.warning("No vcs found for %s", url)
        return None
    if len(vcs_matches) > 1:
        log.warning("No exact matches for %s", url)
        return None

    return t.cast("VCSLiteral", vcs_matches[0].vcs)


class CouldNotGuessVCSFromURL(exc.VCSPullException):
    """Raised when no VCS could be guessed from a URL."""

    def __init__(self, repo_url: str, *args: object, **kwargs: object) -> None:
        return super().__init__(f"Could not automatically determine VCS for {repo_url}")


class SyncFailedError(exc.VCSPullException):
    """Raised when a sync operation completes but with errors."""

    def __init__(
        self,
        repo_name: str,
        errors: str,
        *args: object,
        **kwargs: object,
    ) -> None:
        self.repo_name = repo_name
        self.errors = errors
        message = f"Sync failed for {repo_name}"
        if errors:
            message = f"{message}: {errors}"
        super().__init__(message)


def update_repo(
    repo_dict: t.Any,
    progress_callback: ProgressCallback | None = None,
    # repo_dict: Dict[str, Union[str, Dict[str, GitRemote], pathlib.Path]]
) -> GitSync | HgSync | SvnSync:
    """Synchronize a single repository."""
    repo_dict = deepcopy(repo_dict)
    if "pip_url" not in repo_dict:
        repo_dict["pip_url"] = repo_dict.pop("url")
    if "url" not in repo_dict:
        repo_dict["url"] = repo_dict.pop("pip_url")

    repo_dict["progress_callback"] = progress_callback or progress_cb

    if repo_dict.get("vcs") is None:
        vcs = guess_vcs(url=repo_dict["url"])
        if vcs is None:
            raise CouldNotGuessVCSFromURL(repo_url=repo_dict["url"])

        repo_dict["vcs"] = vcs

    r: GitSync | HgSync | SvnSync = create_project(**repo_dict)
    if repo_dict.get("vcs") == "git":
        result = r.update_repo(set_remotes=True)
    else:
        result = r.update_repo()

    if result is not None and not result.ok:
        error_messages = "; ".join(e.message for e in result.errors)
        repo_name = str(repo_dict.get("name", repo_dict.get("url", "unknown")))
        raise SyncFailedError(repo_name=repo_name, errors=error_messages)

    return r
