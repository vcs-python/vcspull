"""Repository status checking functionality for vcspull."""

from __future__ import annotations

import asyncio
import logging
import os
import pathlib
import re
import subprocess
import sys
import typing as t
from dataclasses import dataclass
from time import perf_counter

from vcspull._internal.private_path import PrivatePath
from vcspull.config import filter_repos, find_config_files, load_configs

from ._colors import Colors, get_color_mode
from ._output import OutputFormatter, get_output_mode
from ._workspaces import filter_by_workspace

if t.TYPE_CHECKING:
    import argparse

    from vcspull.types import ConfigDict

log = logging.getLogger(__name__)

DEFAULT_STATUS_CONCURRENCY = max(1, min(32, (os.cpu_count() or 4) * 2))
ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*m")


@dataclass
class StatusCheckConfig:
    """Configuration options for status checking."""

    max_concurrent: int
    detailed: bool


def _visible_length(text: str) -> int:
    """Return the printable length of string stripped of ANSI codes."""
    return len(ANSI_ESCAPE_RE.sub("", text))


class StatusProgressPrinter:
    """Render incremental status check progress for TTY output."""

    def __init__(self, total: int, colors: Colors, enabled: bool) -> None:
        """Initialize the progress printer.

        Parameters
        ----------
        total : int
            Total number of repositories to check
        colors : Colors
            Color formatter instance
        enabled : bool
            Whether progress output is enabled
        """
        self.total = total
        self._colors = colors
        self._enabled = enabled and total > 0
        self._stream = sys.stdout
        self._last_render_len = 0

    def update(self, processed: int, exists: int, missing: int) -> None:
        """Update the progress line with the latest counts.

        Parameters
        ----------
        processed : int
            Number of repositories processed so far
        exists : int
            Number of repositories that exist
        missing : int
            Number of repositories that are missing
        """
        if not self._enabled:
            return

        line = " ".join(
            (
                f"Progress: {processed}/{self.total}",
                self._colors.success(f"✓:{exists}"),
                self._colors.error(f"✗:{missing}"),
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


def create_status_subparser(parser: argparse.ArgumentParser) -> None:
    """Create ``vcspull status`` argument subparser.

    Parameters
    ----------
    parser : argparse.ArgumentParser
        The parser to configure
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
        help="filter repositories by name pattern (supports fnmatch)",
    )
    parser.add_argument(
        "--detailed",
        "-d",
        action="store_true",
        help="show detailed status information",
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
        "--no-concurrent",
        "--sequential",
        action="store_true",
        dest="no_concurrent",
        help="check repositories sequentially instead of concurrently",
    )
    parser.add_argument(
        "--max-concurrent",
        type=int,
        metavar="N",
        dest="max_concurrent",
        help=(
            f"maximum concurrent status checks (default: {DEFAULT_STATUS_CONCURRENCY})"
        ),
    )


async def _check_repos_status_async(
    repos: list[ConfigDict],
    *,
    config: StatusCheckConfig,
    progress: StatusProgressPrinter | None,
) -> list[dict[str, t.Any]]:
    """Check repository status concurrently using asyncio.

    Parameters
    ----------
    repos : list[ConfigDict]
        List of repository configurations to check
    config : StatusCheckConfig
        Configuration for status checking
    progress : StatusProgressPrinter | None
        Optional progress printer for live updates

    Returns
    -------
    list[dict[str, t.Any]]
        List of status dictionaries in completion order
    """
    if not repos:
        return []

    semaphore = asyncio.Semaphore(min(config.max_concurrent, len(repos)))
    results: list[dict[str, t.Any]] = []
    exists_count = 0
    missing_count = 0

    async def check_with_limit(repo: ConfigDict) -> dict[str, t.Any]:
        async with semaphore:
            return await asyncio.to_thread(
                check_repo_status,
                repo,
                detailed=config.detailed,
            )

    tasks = [asyncio.create_task(check_with_limit(repo)) for repo in repos]

    for index, task in enumerate(asyncio.as_completed(tasks), start=1):
        status = await task
        results.append(status)

        # Update counts for progress
        if status.get("exists"):
            exists_count += 1
        else:
            missing_count += 1

        if progress is not None:
            progress.update(index, exists_count, missing_count)

    return results


def _run_git_command(
    repo_path: pathlib.Path,
    *args: str,
) -> subprocess.CompletedProcess[str] | None:
    """Execute a git command and return the completed process."""
    try:
        return subprocess.run(
            ["git", *args],
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def check_repo_status(repo: ConfigDict, detailed: bool = False) -> dict[str, t.Any]:
    """Check the status of a single repository.

    Parameters
    ----------
    repo : ConfigDict
        Repository configuration
    detailed : bool
        Whether to include detailed status information

    Returns
    -------
    dict
        Repository status information
    """
    repo_path = pathlib.Path(str(repo.get("path", "")))
    repo_name = repo.get("name", "unknown")
    workspace_root = repo.get("workspace_root", "")

    status: dict[str, t.Any] = {
        "name": repo_name,
        "path": str(PrivatePath(repo_path)),
        "workspace_root": workspace_root,
        "exists": False,
        "is_git": False,
        "clean": None,
        "branch": None,
        "ahead": None,
        "behind": None,
    }

    # Check if repository exists
    if repo_path.exists():
        status["exists"] = True

        # Check if it's a git repository
        if (repo_path / ".git").exists():
            status["is_git"] = True

            porcelain_result = _run_git_command(repo_path, "status", "--porcelain")
            if porcelain_result is not None:
                status["clean"] = porcelain_result.stdout.strip() == ""
            else:
                status["clean"] = True

            if detailed:
                branch_result = _run_git_command(
                    repo_path,
                    "rev-parse",
                    "--abbrev-ref",
                    "HEAD",
                )
                if branch_result is not None:
                    status["branch"] = branch_result.stdout.strip()

                ahead = 0
                behind = 0
                upstream_available = _run_git_command(
                    repo_path,
                    "rev-parse",
                    "--abbrev-ref",
                    "@{upstream}",
                )
                if upstream_available is not None:
                    counts = _run_git_command(
                        repo_path,
                        "rev-list",
                        "--left-right",
                        "--count",
                        "@{upstream}...HEAD",
                    )
                    if counts is not None:
                        parts = counts.stdout.strip().split()
                        if len(parts) == 2:
                            behind, ahead = (int(parts[0]), int(parts[1]))
                status["ahead"] = ahead
                status["behind"] = behind

                # Maintain clean flag if porcelain failed
                if status["clean"] is None:
                    status["clean"] = True
            else:
                status["branch"] = None
                status["ahead"] = None
                status["behind"] = None

    return status


def status_repos(
    repo_patterns: list[str],
    config_path: pathlib.Path | None,
    workspace_root: str | None,
    detailed: bool,
    output_json: bool,
    output_ndjson: bool,
    color: str,
    concurrent: bool = True,
    max_concurrent: int | None = None,
) -> None:
    """Check status of configured repositories.

    Parameters
    ----------
    repo_patterns : list[str]
        Patterns to filter repositories (fnmatch)
    config_path : pathlib.Path | None
        Path to config file, or None to auto-discover
    workspace_root : str | None
        Filter by workspace root
    detailed : bool
        Show detailed status information
    output_json : bool
        Output as JSON
    output_ndjson : bool
        Output as NDJSON
    color : str
        Color mode (auto, always, never)
    concurrent : bool
        Whether to check repositories concurrently (default: True)
    max_concurrent : int | None
        Maximum concurrent status checks (default: based on CPU count)
    """
    # Load configs
    if config_path:
        configs = load_configs([config_path])
    else:
        configs = load_configs(find_config_files(include_home=True))

    # Filter by patterns if provided
    if repo_patterns:
        found_repos: list[ConfigDict] = []
        for pattern in repo_patterns:
            found_repos.extend(filter_repos(configs, name=pattern))
    else:
        # No patterns = all repos
        found_repos = configs

    # Further filter by workspace root if specified
    if workspace_root:
        found_repos = filter_by_workspace(found_repos, workspace_root)

    # Initialize output formatter and colors
    output_mode = get_output_mode(output_json, output_ndjson)
    formatter = OutputFormatter(output_mode)
    colors = Colors(get_color_mode(color))

    if not found_repos:
        formatter.emit_text(colors.warning("No repositories found."))
        formatter.finalize()
        return

    # Check status of repositories (concurrent or sequential)
    if concurrent:
        # Concurrent mode using asyncio
        actual_max_concurrent = (
            max_concurrent if max_concurrent is not None else DEFAULT_STATUS_CONCURRENCY
        )
        check_config = StatusCheckConfig(
            max_concurrent=actual_max_concurrent,
            detailed=detailed,
        )

        # Enable progress for TTY human output
        from ._output import OutputMode

        progress_enabled = formatter.mode == OutputMode.HUMAN and sys.stdout.isatty()
        progress_printer = StatusProgressPrinter(
            len(found_repos),
            colors,
            progress_enabled,
        )

        start_time = perf_counter()
        status_results = asyncio.run(
            _check_repos_status_async(
                found_repos,
                config=check_config,
                progress=progress_printer if progress_enabled else None,
            ),
        )
        duration_ms = int((perf_counter() - start_time) * 1000)

        if progress_enabled:
            progress_printer.finish()
    else:
        # Sequential mode (original behavior)
        status_results = []
        for repo in found_repos:
            status = check_repo_status(repo, detailed=detailed)
            status_results.append(status)
        duration_ms = None

    # Process results
    summary = {"total": 0, "exists": 0, "missing": 0, "clean": 0, "dirty": 0}

    for status in status_results:
        summary["total"] += 1

        if status["exists"]:
            summary["exists"] += 1
            if status["clean"]:
                summary["clean"] += 1
            else:
                summary["dirty"] += 1
        else:
            summary["missing"] += 1

        # Emit status
        formatter.emit(
            {
                "reason": "status",
                **status,
            },
        )

        # Human output
        _format_status_line(status, formatter, colors, detailed)

    # Emit summary
    summary_data: dict[str, t.Any] = {
        "reason": "summary",
        **summary,
    }
    if duration_ms is not None:
        summary_data["duration_ms"] = duration_ms

    formatter.emit(summary_data)

    # Human summary
    formatter.emit_text(
        f"\n{colors.info('Summary:')} {summary['total']} repositories, "
        f"{colors.success(str(summary['exists']))} exist, "
        f"{colors.error(str(summary['missing']))} missing",
    )

    formatter.finalize()


def _format_status_line(
    status: dict[str, t.Any],
    formatter: OutputFormatter,
    colors: Colors,
    detailed: bool,
) -> None:
    """Format a single repository status line for human output.

    Parameters
    ----------
    status : dict
        Repository status information
    formatter : OutputFormatter
        Output formatter
    colors : Colors
        Color manager
    detailed : bool
        Whether to show detailed information
    """
    name = status["name"]

    if not status["exists"]:
        symbol = colors.error("✗")
        message = "missing"
        status_color = colors.error(message)
    elif status["is_git"]:
        symbol = colors.success("✓")
        clean_state = status["clean"]
        ahead = status.get("ahead")
        behind = status.get("behind")
        if clean_state is False:
            message = "dirty"
            status_color = colors.warning(message)
        elif isinstance(ahead, int) and isinstance(behind, int):
            if ahead > 0 and behind > 0:
                message = f"diverged (ahead {ahead}, behind {behind})"
                status_color = colors.warning(message)
            elif ahead > 0:
                message = f"ahead by {ahead}"
                status_color = colors.info(message)
            elif behind > 0:
                message = f"behind by {behind}"
                status_color = colors.warning(message)
            else:
                message = "up to date"
                status_color = colors.success(message)
        else:
            message = "up to date" if clean_state else "dirty"
            status_color = (
                colors.success(message)
                if clean_state in {True, None}
                else colors.warning(message)
            )
    else:
        symbol = colors.warning("⚠")
        message = "not a git repo"
        status_color = colors.warning(message)

    formatter.emit_text(f"{symbol} {colors.info(name)}: {status_color}")

    if detailed:
        formatter.emit_text(
            f"  {colors.muted('Path:')} {PrivatePath(status['path'])}",
        )
        branch = status.get("branch")
        if branch:
            formatter.emit_text(f"  {colors.muted('Branch:')} {branch}")
        ahead = status.get("ahead")
        behind = status.get("behind")
        if isinstance(ahead, int) and isinstance(behind, int):
            formatter.emit_text(f"  {colors.muted('Ahead/Behind:')} {ahead}/{behind}")
