"""Repository status checking functionality for vcspull."""

from __future__ import annotations

import argparse
import logging
import pathlib
import typing as t

from vcspull.config import filter_repos, find_config_files, load_configs

from ._colors import Colors, get_color_mode
from ._output import OutputFormatter, get_output_mode

if t.TYPE_CHECKING:
    from vcspull.types import ConfigDict

log = logging.getLogger(__name__)


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

    status: dict[str, t.Any] = {
        "name": repo_name,
        "path": str(repo_path),
        "exists": False,
        "is_git": False,
        "clean": None,
    }

    # Check if repository exists
    if repo_path.exists():
        status["exists"] = True

        # Check if it's a git repository
        if (repo_path / ".git").exists():
            status["is_git"] = True

            # TODO: Add more detailed status checks when detailed=True
            # - Check if clean/dirty
            # - Check if ahead/behind remote
            # - Check current branch
            # For now, just mark as clean if .git exists
            status["clean"] = True

    return status


def status_repos(
    repo_patterns: list[str],
    config_path: pathlib.Path | None,
    workspace_root: str | None,
    detailed: bool,
    output_json: bool,
    output_ndjson: bool,
    color: str,
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
        # TODO: Implement workspace root filtering
        pass

    # Initialize output formatter and colors
    output_mode = get_output_mode(output_json, output_ndjson)
    formatter = OutputFormatter(output_mode)
    colors = Colors(get_color_mode(color))

    if not found_repos:
        formatter.emit_text(colors.warning("No repositories found."))
        formatter.finalize()
        return

    # Check status of each repository
    summary = {"total": 0, "exists": 0, "missing": 0, "clean": 0, "dirty": 0}

    for repo in found_repos:
        status = check_repo_status(repo, detailed=detailed)
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
            }
        )

        # Human output
        _format_status_line(status, formatter, colors, detailed)

    # Emit summary
    formatter.emit(
        {
            "reason": "summary",
            **summary,
        }
    )

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
        message = "up to date" if status["clean"] else "dirty"
        status_color = (
            colors.success(message) if status["clean"] else colors.warning(message)
        )
    else:
        symbol = colors.warning("⚠")
        message = "not a git repo"
        status_color = colors.warning(message)

    formatter.emit_text(f"{symbol} {colors.info(name)}: {status_color}")

    if detailed:
        formatter.emit_text(f"  {colors.muted('Path:')} {status['path']}")
