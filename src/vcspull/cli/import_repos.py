"""Import repositories from remote services for vcspull."""

from __future__ import annotations

import argparse
import logging
import pathlib
import sys
import typing as t

from vcspull._internal.private_path import PrivatePath
from vcspull._internal.remotes import (
    AuthenticationError,
    CodeCommitImporter,
    ConfigurationError,
    DependencyError,
    GiteaImporter,
    GitHubImporter,
    GitLabImporter,
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
    save_config_yaml,
    workspace_root_label,
)
from vcspull.exc import MultipleConfigWarning

from ._colors import Colors, get_color_mode
from ._output import OutputFormatter, get_output_mode

log = logging.getLogger(__name__)

SERVICE_ALIASES: dict[str, str] = {
    "github": "github",
    "gh": "github",
    "gitlab": "gitlab",
    "gl": "gitlab",
    "codeberg": "codeberg",
    "cb": "codeberg",
    "gitea": "gitea",
    "forgejo": "forgejo",
    "codecommit": "codecommit",
    "cc": "codecommit",
    "aws": "codecommit",
}


def create_import_subparser(parser: argparse.ArgumentParser) -> None:
    """Create ``vcspull import`` argument subparser.

    Parameters
    ----------
    parser : argparse.ArgumentParser
        The parser to configure
    """
    parser.add_argument(
        "service",
        metavar="SERVICE",
        nargs="?",
        default=None,
        help="Remote service: github, gitlab, codeberg, gitea, forgejo, codecommit",
    )
    parser.add_argument(
        "target",
        metavar="TARGET",
        nargs="?",
        default="",
        help=(
            "User, org name, or search query (optional for codecommit). "
            "For GitLab, supports subgroups with slash notation (e.g., parent/child)."
        ),
    )
    parser.add_argument(
        "-w",
        "--workspace",
        dest="workspace",
        metavar="DIR",
        default=None,
        help="Workspace root directory (REQUIRED)",
    )
    parser.add_argument(
        "-m",
        "--mode",
        dest="mode",
        choices=["user", "org", "search"],
        default="user",
        help="Import mode: user (default), org, or search",
    )
    parser.add_argument(
        "--url",
        dest="base_url",
        metavar="URL",
        help="Base URL for self-hosted instances (required for gitea/forgejo)",
    )
    parser.add_argument(
        "--token",
        dest="token",
        metavar="TOKEN",
        help="API token (overrides env var; prefer env var for security)",
    )
    parser.add_argument(
        "--region",
        dest="region",
        metavar="REGION",
        help="AWS region for CodeCommit",
    )
    parser.add_argument(
        "--profile",
        dest="profile",
        metavar="PROFILE",
        help="AWS profile for CodeCommit",
    )

    # Filtering options
    filter_group = parser.add_argument_group("filtering")
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
    output_group = parser.add_argument_group("output")
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
        "--flatten-groups",
        action="store_true",
        dest="flatten_groups",
        help=(
            "For GitLab --mode org, flatten subgroup repositories into the base "
            "workspace instead of preserving subgroup paths"
        ),
    )
    output_group.add_argument(
        "--color",
        choices=["auto", "always", "never"],
        default="auto",
        help="When to use colors (default: auto)",
    )


def _get_importer(
    service: str,
    *,
    token: str | None,
    base_url: str | None,
    region: str | None,
    profile: str | None,
) -> GitHubImporter | GitLabImporter | GiteaImporter | CodeCommitImporter:
    """Create the appropriate importer for the service.

    Parameters
    ----------
    service : str
        Service name
    token : str | None
        API token
    base_url : str | None
        Base URL for self-hosted instances
    region : str | None
        AWS region (for CodeCommit)
    profile : str | None
        AWS profile (for CodeCommit)

    Returns
    -------
    Importer instance

    Raises
    ------
    ValueError
        When service is unknown or missing required arguments
    """
    normalized = SERVICE_ALIASES.get(service.lower())
    if normalized is None:
        msg = f"Unknown service: {service}"
        raise ValueError(msg)

    if normalized == "github":
        return GitHubImporter(token=token, base_url=base_url)

    if normalized == "gitlab":
        return GitLabImporter(token=token, base_url=base_url)

    if normalized == "codeberg":
        return GiteaImporter(token=token, base_url=base_url or "https://codeberg.org")

    if normalized in ("gitea", "forgejo"):
        if not base_url:
            msg = f"--url is required for {normalized}"
            raise ValueError(msg)
        return GiteaImporter(token=token, base_url=base_url)

    if normalized == "codecommit":
        return CodeCommitImporter(region=region, profile=profile)

    msg = f"Unknown service: {service}"
    raise ValueError(msg)


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
        if path.suffix.lower() not in {".yaml", ".yml"}:
            msg = f"Only YAML config files are supported, got: {path.suffix}"
            raise ValueError(msg)
        return path

    home_configs = find_home_config_files(filetype=["yaml"])
    if home_configs:
        return home_configs[0]

    return pathlib.Path.home() / ".vcspull.yaml"


def import_repos(
    service: str,
    target: str,
    workspace: str,
    mode: str,
    base_url: str | None,
    token: str | None,
    region: str | None,
    profile: str | None,
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
) -> None:
    """Import repositories from a remote service.

    Parameters
    ----------
    service : str
        Remote service name
    target : str
        User, org, or search query
    workspace : str
        Workspace root directory
    mode : str
        Import mode (user, org, search)
    base_url : str | None
        Base URL for self-hosted instances
    token : str | None
        API token
    region : str | None
        AWS region (for CodeCommit)
    profile : str | None
        AWS profile (for CodeCommit)
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
    """
    output_mode = get_output_mode(output_json, output_ndjson)
    formatter = OutputFormatter(output_mode)
    colors = Colors(get_color_mode(color))

    # Validate service and create importer
    try:
        importer = _get_importer(
            service,
            token=token,
            base_url=base_url,
            region=region,
            profile=profile,
        )
    except ValueError as exc:
        log.error("%s %s", colors.error("✗"), exc)  # noqa: TRY400
        return
    except DependencyError as exc:
        log.error("%s %s", colors.error("✗"), exc)  # noqa: TRY400
        return

    # Validate target for non-CodeCommit services
    normalized_service = SERVICE_ALIASES.get(service.lower(), service.lower())
    if normalized_service != "codecommit" and not target:
        log.error(
            "%s TARGET is required for %s",
            colors.error("✗"),
            service,
        )
        return

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
            base_url=base_url,
            token=token,
            include_forks=include_forks,
            include_archived=include_archived,
            language=language,
            topics=topic_list,
            min_stars=min_stars,
            limit=limit,
        )
    except ValueError as exc_:
        log.error("%s %s", colors.error("✗"), exc_)  # noqa: TRY400
        return

    # Warn if --language is used with services that don't return language info
    if options.language and normalized_service in ("gitlab", "codecommit"):
        log.warning(
            "%s %s does not return language metadata; "
            "--language filter may exclude all results",
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
        return
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
        return
    except RateLimitError as exc:
        log.error(  # noqa: TRY400
            "%s Rate limit exceeded: %s", colors.error("✗"), exc
        )
        formatter.finalize()
        return
    except NotFoundError as exc:
        log.error("%s Not found: %s", colors.error("✗"), exc)  # noqa: TRY400
        formatter.finalize()
        return
    except ServiceUnavailableError as exc:
        log.error(  # noqa: TRY400
            "%s Service unavailable: %s", colors.error("✗"), exc
        )
        formatter.finalize()
        return
    except ConfigurationError as exc:
        log.error(  # noqa: TRY400
            "%s Configuration error: %s", colors.error("✗"), exc
        )
        formatter.finalize()
        return
    except RemoteImportError as exc:
        log.error("%s Error: %s", colors.error("✗"), exc)  # noqa: TRY400
        formatter.finalize()
        return

    if not repos:
        if output_mode.value == "human":
            log.info(
                "%s No repositories found matching criteria.",
                colors.warning("!"),
            )
        formatter.finalize()
        return

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
        return

    # Confirm with user
    if not yes and output_mode.value == "human":
        if not sys.stdin.isatty():
            log.info(
                "%s Non-interactive mode: use --yes to skip confirmation.",
                colors.error("✗"),
            )
            return
        try:
            confirm = input(
                f"\n{colors.info('Import')} {len(repos)} repositories to "
                f"{display_config_path}? [y/N]: ",
            ).lower()
        except EOFError:
            confirm = ""
        if confirm not in {"y", "yes"}:
            log.info("%s Aborted by user.", colors.error("✗"))
            return

    # Load existing config or create new
    raw_config: dict[str, t.Any]
    if config_file_path.exists():
        import yaml

        try:
            with config_file_path.open() as f:
                raw_config = yaml.safe_load(f) or {}
        except (yaml.YAMLError, OSError):
            log.exception("Error loading config file")
            return

        if not isinstance(raw_config, dict):
            log.error(
                "%s Config file is not a valid YAML mapping: %s",
                colors.error("✗"),
                display_config_path,
            )
            return
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
            normalized_service == "gitlab"
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
        return

    # Save config
    try:
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
