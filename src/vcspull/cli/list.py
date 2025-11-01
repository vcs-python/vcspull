"""List repositories functionality for vcspull."""

from __future__ import annotations

import logging
import typing as t

from vcspull.config import filter_repos, find_config_files, load_configs
from vcspull.util import contract_user_home

from ._colors import Colors, get_color_mode
from ._output import OutputFormatter, get_output_mode
from ._workspaces import filter_by_workspace

if t.TYPE_CHECKING:
    import argparse
    import pathlib

    from vcspull.types import ConfigDict

log = logging.getLogger(__name__)


def create_list_subparser(parser: argparse.ArgumentParser) -> None:
    """Create ``vcspull list`` argument subparser.

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
        "--tree",
        action="store_true",
        help="display repositories grouped by workspace root",
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


def list_repos(
    repo_patterns: list[str],
    config_path: pathlib.Path | None,
    workspace_root: str | None,
    tree: bool,
    output_json: bool,
    output_ndjson: bool,
    color: str,
) -> None:
    """List configured repositories.

    Parameters
    ----------
    repo_patterns : list[str]
        Patterns to filter repositories (fnmatch)
    config_path : pathlib.Path | None
        Path to config file, or None to auto-discover
    workspace_root : str | None
        Filter by workspace root
    tree : bool
        Group by workspace root in tree view
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
        found_repos = filter_by_workspace(found_repos, workspace_root)

    # Initialize output formatter and colors
    output_mode = get_output_mode(output_json, output_ndjson)
    formatter = OutputFormatter(output_mode)
    colors = Colors(get_color_mode(color))

    if not found_repos:
        formatter.emit_text(colors.warning("No repositories found."))
        formatter.finalize()
        return

    # Output based on mode
    if tree:
        _output_tree(found_repos, formatter, colors)
    else:
        _output_flat(found_repos, formatter, colors)

    formatter.finalize()


def _output_flat(
    repos: list[ConfigDict],
    formatter: OutputFormatter,
    colors: Colors,
) -> None:
    """Output repositories in flat list format.

    Parameters
    ----------
    repos : list[ConfigDict]
        Repositories to display
    formatter : OutputFormatter
        Output formatter
    colors : Colors
        Color manager
    """
    for repo in repos:
        repo_name = repo.get("name", "unknown")
        repo_url = repo.get("url", repo.get("pip_url", "unknown"))
        repo_path = repo.get("path", "unknown")

        # JSON/NDJSON output (contract home for privacy/portability)
        formatter.emit(
            {
                "name": repo_name,
                "url": str(repo_url),
                "path": contract_user_home(repo_path),
                "workspace_root": str(repo.get("workspace_root", "")),
            },
        )

        # Human output (contract home directory for privacy/brevity)
        formatter.emit_text(
            f"{colors.muted('•')} {colors.info(repo_name)} "
            f"{colors.muted('→')} {contract_user_home(repo_path)}",
        )


def _output_tree(
    repos: list[ConfigDict],
    formatter: OutputFormatter,
    colors: Colors,
) -> None:
    """Output repositories grouped by workspace root (tree view).

    Parameters
    ----------
    repos : list[ConfigDict]
        Repositories to display
    formatter : OutputFormatter
        Output formatter
    colors : Colors
        Color manager
    """
    # Group by workspace root
    by_workspace: dict[str, list[ConfigDict]] = {}
    for repo in repos:
        workspace = str(repo.get("workspace_root", "unknown"))
        by_workspace.setdefault(workspace, []).append(repo)

    # Output grouped
    for workspace in sorted(by_workspace.keys()):
        workspace_repos = by_workspace[workspace]

        # Human output: workspace header
        formatter.emit_text(f"\n{colors.highlight(workspace)}")

        for repo in workspace_repos:
            repo_name = repo.get("name", "unknown")
            repo_url = repo.get("url", repo.get("pip_url", "unknown"))
            repo_path = repo.get("path", "unknown")

            # JSON/NDJSON output (contract home for privacy/portability)
            formatter.emit(
                {
                    "name": repo_name,
                    "url": str(repo_url),
                    "path": contract_user_home(repo_path),
                    "workspace_root": workspace,
                },
            )

            # Human output: indented repo (contract home directory for privacy/brevity)
            formatter.emit_text(
                f"  {colors.muted('•')} {colors.info(repo_name)} "
                f"{colors.muted('→')} {contract_user_home(repo_path)}",
            )
