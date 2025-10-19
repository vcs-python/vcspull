"""Synchronization functionality for vcspull."""

from __future__ import annotations

import logging
import sys
import typing as t
from copy import deepcopy

from libvcs._internal.shortcuts import create_project
from libvcs.url import registry as url_tools

from vcspull import exc
from vcspull.config import filter_repos, find_config_files, load_configs
from vcspull.types import ConfigDict

from ._colors import Colors, get_color_mode
from ._output import OutputFormatter, OutputMode, get_output_mode
from ._workspaces import filter_by_workspace

if t.TYPE_CHECKING:
    import argparse
    import pathlib
    from datetime import datetime

    from libvcs._internal.types import VCSLiteral
    from libvcs.sync.git import GitSync

log = logging.getLogger(__name__)


def clamp(n: int, _min: int, _max: int) -> int:
    """Clamp a number between a min and max value."""
    return max(_min, min(n, _max))


EXIT_ON_ERROR_MSG = "Exiting via error (--exit-on-error passed)"
NO_REPOS_FOR_TERM_MSG = 'No repo found in config(s) for "{name}"'


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
    parser: argparse.ArgumentParser
    | None = None,  # optional so sync can be unit tested
) -> None:
    """Entry point for ``vcspull sync``."""
    if isinstance(repo_patterns, list) and len(repo_patterns) == 0:
        if parser is not None:
            parser.print_help()
        sys.exit(2)

    output_mode = get_output_mode(output_json, output_ndjson)
    formatter = OutputFormatter(output_mode)
    colors = Colors(get_color_mode(color))

    if config:
        configs = load_configs([config])
    else:
        configs = load_configs(find_config_files(include_home=True))
    found_repos: list[ConfigDict] = []

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
            log.info(NO_REPOS_FOR_TERM_MSG.format(name=name))
        found_repos.extend(found)

    if workspace_root:
        found_repos = filter_by_workspace(found_repos, workspace_root)

    if not found_repos:
        formatter.emit(
            {
                "reason": "summary",
                "total": 0,
                "synced": 0,
                "previewed": 0,
                "failed": 0,
            }
        )
        formatter.emit_text(colors.warning("No repositories matched the criteria."))
        formatter.finalize()
        return

    summary = {"total": 0, "synced": 0, "previewed": 0, "failed": 0}

    for repo in found_repos:
        repo_name = repo.get("name", "unknown")
        repo_path = repo.get("path", "unknown")
        workspace_label = repo.get("workspace_root", "")

        summary["total"] += 1

        event: dict[str, t.Any] = {
            "reason": "sync",
            "name": repo_name,
            "path": str(repo_path),
            "workspace_root": str(workspace_label),
        }

        if dry_run:
            summary["previewed"] += 1
            event["status"] = "preview"
            formatter.emit(event)
            log.info(f"Would sync {repo_name} at {repo_path}")
            formatter.emit_text(
                f"{colors.warning('→')} Would sync {colors.info(repo_name)} "
                f"{colors.muted('→')} {repo_path}",
            )
            continue

        try:
            update_repo(repo)
        except Exception as e:
            summary["failed"] += 1
            event["status"] = "error"
            event["error"] = str(e)
            formatter.emit(event)
            log.info(
                f"Failed syncing {repo_name}",
            )
            if log.isEnabledFor(logging.DEBUG):
                import traceback

                traceback.print_exc()
            formatter.emit_text(
                f"{colors.error('✗')} Failed syncing {colors.info(repo_name)}: "
                f"{colors.error(str(e))}",
            )
            if exit_on_error:
                formatter.emit(
                    {
                        "reason": "summary",
                        **summary,
                    }
                )
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
            f"{colors.muted('→')} {repo_path}",
        )

    formatter.emit(
        {
            "reason": "summary",
            **summary,
        }
    )

    if formatter.mode == OutputMode.HUMAN:
        formatter.emit_text(
            f"\n{colors.info('Summary:')} "
            f"{summary['total']} repos, "
            f"{colors.success(str(summary['synced']))} synced, "
            f"{colors.warning(str(summary['previewed']))} previewed, "
            f"{colors.error(str(summary['failed']))} failed",
        )

    formatter.finalize()


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


def update_repo(
    repo_dict: t.Any,
    # repo_dict: Dict[str, Union[str, Dict[str, GitRemote], pathlib.Path]]
) -> GitSync:
    """Synchronize a single repository."""
    repo_dict = deepcopy(repo_dict)
    if "pip_url" not in repo_dict:
        repo_dict["pip_url"] = repo_dict.pop("url")
    if "url" not in repo_dict:
        repo_dict["url"] = repo_dict.pop("pip_url")
    repo_dict["progress_callback"] = progress_cb

    if repo_dict.get("vcs") is None:
        vcs = guess_vcs(url=repo_dict["url"])
        if vcs is None:
            raise CouldNotGuessVCSFromURL(repo_url=repo_dict["url"])

        repo_dict["vcs"] = vcs

    r = create_project(**repo_dict)  # Creates the repo object
    r.update_repo(set_remotes=True)  # Creates repo if not exists and fetches

    # TODO: Fix this
    return r  # type:ignore
