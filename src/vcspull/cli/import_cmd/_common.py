"""Shared infrastructure for the ``vcspull import`` subcommand tree.

Provides parent argparse parsers (for flag composition via ``parents=[]``)
and the ``_run_import()`` function that all per-service handlers delegate to.
"""

from __future__ import annotations

import argparse
import logging
import pathlib
import sys
import typing as t

from vcspull._internal.private_path import PrivatePath
from vcspull._internal.remotes import (
    AuthenticationError,
    ConfigurationError,
    ImportMode,
    ImportOptions,
    NotFoundError,
    RateLimitError,
    RemoteImportError,
    RemoteRepo,
    ServiceUnavailableError,
)
from vcspull.config import (
    find_home_config_files,
    save_config_json,
    save_config_yaml,
    workspace_root_label,
)
from vcspull.exc import MultipleConfigWarning

from .._colors import Colors, get_color_mode
from .._output import OutputFormatter, get_output_mode

log = logging.getLogger(__name__)


class Importer(t.Protocol):
    """Structural type for any remote service importer."""

    service_name: str

    def fetch_repos(self, options: ImportOptions) -> t.Iterator[RemoteRepo]:
        """Yield repositories matching *options*."""
        ...


# ---------------------------------------------------------------------------
# Parent parser factories
# ---------------------------------------------------------------------------


def _create_shared_parent() -> argparse.ArgumentParser:
    """Create parent parser with workspace, filtering, and output flags.

    Returns
    -------
    argparse.ArgumentParser
        Parent parser (``add_help=False``) carrying flags shared by all
        import service subcommands.
    """
    parent = argparse.ArgumentParser(add_help=False)
    parent.add_argument(
        "-w",
        "--workspace",
        dest="workspace",
        metavar="DIR",
        default=None,
        help="Workspace root directory (REQUIRED)",
    )

    # Filtering options
    filter_group = parent.add_argument_group("filtering")
    filter_group.add_argument(
        "-l",
        "--language",
        dest="language",
        metavar="LANG",
        help="Filter by programming language",
    )
    filter_group.add_argument(
        "--topics",
        dest="topics",
        metavar="TOPICS",
        help="Filter by topics (comma-separated)",
    )
    filter_group.add_argument(
        "--min-stars",
        dest="min_stars",
        type=int,
        default=0,
        metavar="N",
        help="Minimum stars (for search mode)",
    )
    filter_group.add_argument(
        "--archived",
        dest="include_archived",
        action="store_true",
        help="Include archived repositories",
    )
    filter_group.add_argument(
        "--forks",
        dest="include_forks",
        action="store_true",
        help="Include forked repositories",
    )
    filter_group.add_argument(
        "--limit",
        dest="limit",
        type=int,
        default=100,
        metavar="N",
        help="Maximum repositories to fetch (default: 100)",
    )

    # Output options
    output_group = parent.add_argument_group("output")
    output_group.add_argument(
        "-f",
        "--file",
        dest="config",
        metavar="FILE",
        help="Config file to write to (default: ~/.vcspull.yaml)",
    )
    output_group.add_argument(
        "--dry-run",
        "-n",
        action="store_true",
        help="Preview without writing to config file",
    )
    output_group.add_argument(
        "--yes",
        "-y",
        action="store_true",
        help="Skip confirmation prompt",
    )
    output_group.add_argument(
        "--json",
        action="store_true",
        dest="output_json",
        help="Output as JSON",
    )
    output_group.add_argument(
        "--ndjson",
        action="store_true",
        dest="output_ndjson",
        help="Output as NDJSON (one JSON per line)",
    )
    output_group.add_argument(
        "--https",
        action="store_true",
        dest="use_https",
        help="Use HTTPS clone URLs instead of SSH (default: SSH)",
    )
    output_group.add_argument(
        "--color",
        choices=["auto", "always", "never"],
        default="auto",
        help="When to use colors (default: auto)",
    )
    return parent


def _create_token_parent() -> argparse.ArgumentParser:
    """Create parent parser with the ``--token`` flag.

    Returns
    -------
    argparse.ArgumentParser
        Parent parser carrying ``--token``.
    """
    parent = argparse.ArgumentParser(add_help=False)
    parent.add_argument(
        "--token",
        dest="token",
        metavar="TOKEN",
        help="API token (overrides env var; prefer env var for security)",
    )
    return parent


def _create_mode_parent() -> argparse.ArgumentParser:
    """Create parent parser with the ``-m/--mode`` flag.

    Returns
    -------
    argparse.ArgumentParser
        Parent parser carrying ``-m/--mode``.
    """
    parent = argparse.ArgumentParser(add_help=False)
    parent.add_argument(
        "-m",
        "--mode",
        dest="mode",
        choices=["user", "org", "search"],
        default="user",
        help="Import mode: user (default), org, or search",
    )
    return parent


def _create_target_parent() -> argparse.ArgumentParser:
    """Create parent parser with the required ``target`` positional.

    Returns
    -------
    argparse.ArgumentParser
        Parent parser carrying the ``target`` positional argument.
    """
    parent = argparse.ArgumentParser(add_help=False)
    parent.add_argument(
        "target",
        metavar="TARGET",
        help=(
            "User, org name, or search query. "
            "For GitLab, supports subgroups with slash notation (e.g., parent/child)."
        ),
    )
    return parent


# ---------------------------------------------------------------------------
# Config resolution
# ---------------------------------------------------------------------------


def _resolve_config_file(config_path_str: str | None) -> pathlib.Path:
    """Resolve the config file path.

    Parameters
    ----------
    config_path_str : str | None
        Config file path from user, or None for default

    Returns
    -------
    pathlib.Path
        Resolved config file path
    """
    if config_path_str:
        path = pathlib.Path(config_path_str).expanduser().resolve()
        if path.suffix.lower() not in {".yaml", ".yml", ".json"}:
            msg = f"Unsupported config file type: {path.suffix}"
            raise ValueError(msg)
        return path

    home_configs = find_home_config_files(filetype=["yaml", "json"])
    if home_configs:
        return home_configs[0]

    return pathlib.Path.home() / ".vcspull.yaml"


# ---------------------------------------------------------------------------
# Core import logic
# ---------------------------------------------------------------------------


def _run_import(
    importer: Importer,
    *,
    service_name: str,
    target: str,
    workspace: str,
    mode: str,
    language: str | None,
    topics: str | None,
    min_stars: int,
    include_archived: bool,
    include_forks: bool,
    limit: int,
    config_path_str: str | None,
    dry_run: bool,
    yes: bool,
    output_json: bool,
    output_ndjson: bool,
    color: str,
    use_https: bool = False,
    flatten_groups: bool = False,
) -> int:
    """Run the import workflow for a single service.

    This is the core fetch / preview / confirm / write logic shared by every
    per-service handler.  The caller is responsible for constructing the
    *importer* instance; this function only orchestrates the import flow.

    Parameters
    ----------
    importer : Importer
        Already-constructed importer instance (any object satisfying
        the :class:`Importer` protocol)
    service_name : str
        Canonical service name (e.g. ``"github"``, ``"gitlab"``, ``"codecommit"``)
    target : str
        User, org, or search query
    workspace : str
        Workspace root directory
    mode : str
        Import mode (user, org, search)
    language : str | None
        Language filter
    topics : str | None
        Topics filter (comma-separated)
    min_stars : int
        Minimum stars filter
    include_archived : bool
        Include archived repositories
    include_forks : bool
        Include forked repositories
    limit : int
        Maximum repositories to fetch
    config_path_str : str | None
        Config file path
    dry_run : bool
        Preview without writing
    yes : bool
        Skip confirmation
    output_json : bool
        Output as JSON
    output_ndjson : bool
        Output as NDJSON
    color : str
        Color mode
    use_https : bool
        Use HTTPS clone URLs instead of SSH (default: False, i.e., SSH)
    flatten_groups : bool
        For GitLab org imports, flatten subgroup paths into base workspace

    Returns
    -------
    int
        0 on success, 1 on error
    """
    output_mode = get_output_mode(output_json, output_ndjson)
    formatter = OutputFormatter(output_mode)
    colors = Colors(get_color_mode(color))

    # Build import options
    import_mode = ImportMode(mode)
    topic_list = (
        [topic.strip() for topic in topics.split(",") if topic.strip()]
        if topics
        else []
    )

    try:
        options = ImportOptions(
            mode=import_mode,
            target=target,
            include_forks=include_forks,
            include_archived=include_archived,
            language=language,
            topics=topic_list,
            min_stars=min_stars,
            limit=limit,
        )
    except ValueError as exc_:
        log.error("%s %s", colors.error("✗"), exc_)  # noqa: TRY400
        return 1

    # Warn if --language is used with services that don't return language info
    if options.language and service_name in ("gitlab", "codecommit"):
        log.warning(
            "%s %s does not return language metadata; "
            "--language filter may exclude all results",
            colors.warning("!"),
            importer.service_name,
        )
    if options.topics and service_name == "codecommit":
        log.warning(
            "%s %s does not support topic filtering; "
            "--topics filter may exclude all results",
            colors.warning("!"),
            importer.service_name,
        )
    if options.min_stars > 0 and service_name == "codecommit":
        log.warning(
            "%s %s does not track star counts; "
            "--min-stars filter may exclude all results",
            colors.warning("!"),
            importer.service_name,
        )

    # Resolve workspace path
    workspace_path = pathlib.Path(workspace).expanduser().resolve()
    cwd = pathlib.Path.cwd()
    home = pathlib.Path.home()

    # Resolve config file
    try:
        config_file_path = _resolve_config_file(config_path_str)
    except (ValueError, MultipleConfigWarning) as exc_:
        log.error("%s %s", colors.error("✗"), exc_)  # noqa: TRY400
        return 1
    display_config_path = str(PrivatePath(config_file_path))

    # Fetch repositories
    if output_mode.value == "human":
        log.info(
            "%s Fetching repositories from %s...",
            colors.info("→"),
            colors.highlight(importer.service_name),
        )

    repos: list[RemoteRepo] = []
    try:
        for repo in importer.fetch_repos(options):
            repos.append(repo)

            # Emit for JSON/NDJSON output
            formatter.emit(repo.to_dict())

            # Log progress for human output
            if output_mode.value == "human" and len(repos) % 10 == 0:
                log.info(
                    "%s Fetched %s repositories...",
                    colors.muted("•"),
                    colors.info(str(len(repos))),
                )

    except AuthenticationError as exc:
        log.error(  # noqa: TRY400
            "%s Authentication error: %s", colors.error("✗"), exc
        )
        formatter.finalize()
        return 1
    except RateLimitError as exc:
        log.error(  # noqa: TRY400
            "%s Rate limit exceeded: %s", colors.error("✗"), exc
        )
        formatter.finalize()
        return 1
    except NotFoundError as exc:
        log.error("%s Not found: %s", colors.error("✗"), exc)  # noqa: TRY400
        formatter.finalize()
        return 1
    except ServiceUnavailableError as exc:
        log.error(  # noqa: TRY400
            "%s Service unavailable: %s", colors.error("✗"), exc
        )
        formatter.finalize()
        return 1
    except ConfigurationError as exc:
        log.error(  # noqa: TRY400
            "%s Configuration error: %s", colors.error("✗"), exc
        )
        formatter.finalize()
        return 1
    except RemoteImportError as exc:
        log.error("%s Error: %s", colors.error("✗"), exc)  # noqa: TRY400
        formatter.finalize()
        return 1

    if not repos:
        if output_mode.value == "human":
            log.info(
                "%s No repositories found matching criteria.",
                colors.warning("!"),
            )
        formatter.finalize()
        return 0

    if output_mode.value == "human":
        log.info(
            "\n%s Found %s repositories",
            colors.success("✓"),
            colors.info(str(len(repos))),
        )

    # Show preview in human mode
    if output_mode.value == "human":
        for repo in repos[:10]:  # Show first 10
            stars_str = f" ★{repo.stars}" if repo.stars > 0 else ""
            lang_str = f" [{repo.language}]" if repo.language else ""
            log.info(
                "  %s %s%s%s",
                colors.success("+"),
                colors.info(repo.name),
                colors.muted(lang_str),
                colors.muted(stars_str),
            )
        if len(repos) > 10:
            log.info(
                "  %s and %s more",
                colors.muted("..."),
                colors.info(str(len(repos) - 10)),
            )

    formatter.finalize()

    # Handle dry-run
    if dry_run:
        log.info(
            "\n%s Dry run complete. Would write to %s",
            colors.warning("→"),
            colors.muted(display_config_path),
        )
        return 0

    # Confirm with user
    if not yes and output_mode.value == "human":
        if not sys.stdin.isatty():
            log.info(
                "%s Non-interactive mode: use --yes to skip confirmation.",
                colors.error("✗"),
            )
            return 0
        try:
            confirm = input(
                f"\n{colors.info('Import')} {len(repos)} repositories to "
                f"{display_config_path}? [y/N]: ",
            ).lower()
        except EOFError:
            confirm = ""
        if confirm not in {"y", "yes"}:
            log.info("%s Aborted by user.", colors.error("✗"))
            return 0

    # Load existing config or create new
    raw_config: dict[str, t.Any]
    if config_file_path.exists():
        import yaml

        try:
            with config_file_path.open() as f:
                raw_config = yaml.safe_load(f) or {}
        except (yaml.YAMLError, OSError):
            log.exception("Error loading config file")
            return 1

        if not isinstance(raw_config, dict):
            log.error(
                "%s Config file is not a valid mapping: %s",
                colors.error("✗"),
                display_config_path,
            )
            return 1
    else:
        raw_config = {}

    # Add repositories to config
    checked_labels: set[str] = set()
    added_count = 0
    skipped_count = 0

    for repo in repos:
        # Determine workspace for this repo
        repo_workspace_path = workspace_path

        preserve_group_structure = (
            service_name == "gitlab"
            and options.mode == ImportMode.ORG
            and not flatten_groups
        )
        if preserve_group_structure and repo.owner.startswith(options.target):
            # Check if it is a subdirectory
            if repo.owner == options.target:
                subpath = ""
            elif repo.owner.startswith(options.target + "/"):
                subpath = repo.owner[len(options.target) + 1 :]
            else:
                subpath = ""

            if subpath:
                candidate = (workspace_path / subpath).resolve()
                if not candidate.is_relative_to(workspace_path.resolve()):
                    log.warning(
                        "%s Ignoring subgroup path that escapes workspace: %s",
                        colors.warning("⚠"),
                        repo.owner,
                    )
                    subpath = ""
                else:
                    repo_workspace_path = workspace_path / subpath

        repo_workspace_label = workspace_root_label(
            repo_workspace_path, cwd=cwd, home=home
        )

        if repo_workspace_label not in checked_labels:
            if repo_workspace_label in raw_config and not isinstance(
                raw_config[repo_workspace_label], dict
            ):
                log.error(
                    "%s Workspace section '%s' is not a mapping in config",
                    colors.error("✗"),
                    repo_workspace_label,
                )
            checked_labels.add(repo_workspace_label)

        if repo_workspace_label in raw_config and not isinstance(
            raw_config[repo_workspace_label], dict
        ):
            continue

        if repo_workspace_label not in raw_config:
            raw_config[repo_workspace_label] = {}

        if repo.name in raw_config[repo_workspace_label]:
            skipped_count += 1
            continue

        raw_config[repo_workspace_label][repo.name] = {
            "repo": repo.to_vcspull_url(use_ssh=not use_https),
        }
        added_count += 1

    if added_count == 0:
        log.info(
            "%s All repositories already exist in config. Nothing to add.",
            colors.success("✓"),
        )
        return 0

    # Save config
    try:
        if config_file_path.suffix.lower() == ".json":
            save_config_json(config_file_path, raw_config)
        else:
            save_config_yaml(config_file_path, raw_config)
        log.info(
            "%s Added %s repositories to %s",
            colors.success("✓"),
            colors.info(str(added_count)),
            colors.muted(display_config_path),
        )
        if skipped_count > 0:
            log.info(
                "%s Skipped %s existing repositories",
                colors.warning("!"),
                colors.info(str(skipped_count)),
            )
    except OSError:
        log.exception("Error saving config to %s", display_config_path)
        return 1

    return 0
