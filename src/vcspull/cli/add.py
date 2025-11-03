"""Add single repository functionality for vcspull."""

from __future__ import annotations

import copy
import logging
import pathlib
import subprocess
import traceback
import typing as t

from colorama import Fore, Style

from vcspull._internal.config_reader import DuplicateAwareConfigReader
from vcspull.config import (
    canonicalize_workspace_path,
    expand_dir,
    find_home_config_files,
    merge_duplicate_workspace_roots,
    normalize_workspace_roots,
    save_config_yaml,
    save_config_yaml_with_items,
    workspace_root_label,
)
from vcspull.util import contract_user_home

if t.TYPE_CHECKING:
    import argparse

log = logging.getLogger(__name__)


def create_add_subparser(parser: argparse.ArgumentParser) -> None:
    """Create ``vcspull add`` argument subparser.

    Parameters
    ----------
    parser : argparse.ArgumentParser
        The parser to configure
    """
    parser.add_argument(
        "repo_path",
        help=(
            "Filesystem path to an existing project. The parent directory "
            "becomes the workspace unless overridden with --workspace."
        ),
    )
    parser.add_argument(
        "--name",
        dest="override_name",
        help="Override detected repository name when importing from a path",
    )
    parser.add_argument(
        "--url",
        dest="url",
        help="Repository URL to record (overrides detected remotes)",
    )
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
        dest="workspace_root_path",
        metavar="DIR",
        help=(
            "Workspace root directory in config (e.g., '~/projects/'). Defaults "
            "to the parent directory of the repository path."
        ),
    )
    parser.add_argument(
        "--dry-run",
        "-n",
        action="store_true",
        help="Preview changes without writing to config file",
    )
    parser.add_argument(
        "--no-merge",
        dest="merge_duplicates",
        action="store_false",
        help="Skip merging duplicate workspace roots before writing",
    )
    parser.add_argument(
        "-y",
        "--yes",
        dest="assume_yes",
        action="store_true",
        help="Automatically confirm interactive prompts",
    )
    parser.set_defaults(merge_duplicates=True)


def _resolve_workspace_path(
    workspace_root: str | None,
    repo_path_str: str | None,
    *,
    cwd: pathlib.Path,
) -> pathlib.Path:
    """Resolve workspace path from arguments.

    Parameters
    ----------
    workspace_root : str | None
        Workspace root path from user
    repo_path_str : str | None
        Repo path from user
    cwd : pathlib.Path
        Current working directory

    Returns
    -------
    pathlib.Path
        Resolved workspace path
    """
    if workspace_root:
        return canonicalize_workspace_path(workspace_root, cwd=cwd)
    if repo_path_str:
        return expand_dir(pathlib.Path(repo_path_str), cwd)
    return cwd


def _detect_git_remote(repo_path: pathlib.Path) -> str | None:
    """Return the ``origin`` remote URL for a Git repository if available."""
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_path), "remote", "get-url", "origin"],
            check=True,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        log.debug("git executable not found when inspecting %s", repo_path)
        return None
    except subprocess.CalledProcessError:
        log.debug("No git remote 'origin' configured for %s", repo_path)
        return None

    remote = result.stdout.strip()
    return remote or None


def _normalize_detected_url(remote: str | None) -> tuple[str, str]:
    """Return display and config URLs derived from a detected remote."""
    if remote is None:
        return "", ""

    display_url = remote
    config_url = remote

    normalized = remote.strip()

    if normalized and not normalized.startswith("git+"):
        if normalized.startswith(("http://", "https://", "file://")):
            config_url = f"git+{normalized}"
        else:
            config_url = normalized
    elif normalized:
        config_url = normalized

    return display_url, config_url


def handle_add_command(args: argparse.Namespace) -> None:
    """Entry point for the ``vcspull add`` CLI command."""
    repo_input = getattr(args, "repo_path", None)
    if repo_input is None:
        log.error("A repository path must be provided.")
        return

    cwd = pathlib.Path.cwd()
    repo_path = expand_dir(pathlib.Path(repo_input), cwd=cwd)

    if not repo_path.exists():
        log.error("Repository path %s does not exist.", repo_path)
        return

    if not repo_path.is_dir():
        log.error("Repository path %s is not a directory.", repo_path)
        return

    override_name = getattr(args, "override_name", None)
    repo_name = override_name or repo_path.name

    explicit_url = getattr(args, "url", None)
    if explicit_url:
        display_url, config_url = _normalize_detected_url(explicit_url)
    else:
        detected_remote = _detect_git_remote(repo_path)
        display_url, config_url = _normalize_detected_url(detected_remote)

    if not config_url:
        display_url = contract_user_home(repo_path)
        config_url = str(repo_path)
        log.warning(
            "Unable to determine git remote for %s; using local path in config.",
            repo_path,
        )

    workspace_root_arg = getattr(args, "workspace_root_path", None)
    workspace_root_input = (
        workspace_root_arg
        if workspace_root_arg is not None
        else repo_path.parent.as_posix()
    )

    workspace_path = expand_dir(pathlib.Path(workspace_root_input), cwd=cwd)
    workspace_label = workspace_root_label(
        workspace_path,
        cwd=cwd,
        home=pathlib.Path.home(),
        preserve_cwd_label=workspace_root_arg in {".", "./"},
    )

    summary_url = display_url or config_url

    display_path = contract_user_home(repo_path)

    log.info("%sFound new repository to import:%s", Fore.GREEN, Style.RESET_ALL)
    log.info(
        "  %s+%s %s%s%s (%s%s%s)",
        Fore.GREEN,
        Style.RESET_ALL,
        Fore.CYAN,
        repo_name,
        Style.RESET_ALL,
        Fore.YELLOW,
        summary_url,
        Style.RESET_ALL,
    )
    log.info(
        "  %s•%s workspace: %s%s%s",
        Fore.BLUE,
        Style.RESET_ALL,
        Fore.MAGENTA,
        workspace_label,
        Style.RESET_ALL,
    )
    log.info(
        "  %s↳%s path: %s%s%s",
        Fore.BLUE,
        Style.RESET_ALL,
        Fore.BLUE,
        display_path,
        Style.RESET_ALL,
    )

    prompt_text = f"{Fore.CYAN}?{Style.RESET_ALL} Import this repository? [y/N]: "

    proceed = True
    if args.dry_run:
        log.info(
            "%s?%s Import this repository? [y/N]: %sskipped (dry-run)%s",
            Fore.CYAN,
            Style.RESET_ALL,
            Fore.YELLOW,
            Style.RESET_ALL,
        )
    elif getattr(args, "assume_yes", False):
        log.info(
            "%s?%s Import this repository? [y/N]: %sy (auto-confirm)%s",
            Fore.CYAN,
            Style.RESET_ALL,
            Fore.GREEN,
            Style.RESET_ALL,
        )
    else:
        try:
            response = input(prompt_text)
        except EOFError:
            response = ""
        proceed = response.strip().lower() in {"y", "yes"}
        if not proceed:
            log.info("Aborted import of '%s' from %s", repo_name, repo_path)
            return

    add_repo(
        name=repo_name,
        url=config_url,
        config_file_path_str=args.config,
        path=str(repo_path),
        workspace_root_path=workspace_root_input,
        dry_run=args.dry_run,
        merge_duplicates=args.merge_duplicates,
    )


def add_repo(
    name: str,
    url: str,
    config_file_path_str: str | None,
    path: str | None,
    workspace_root_path: str | None,
    dry_run: bool,
    *,
    merge_duplicates: bool = True,
) -> None:
    """Add a repository to the vcspull configuration.

    Parameters
    ----------
    name : str
        Repository name for the config
    url : str
        Repository URL
    config_file_path_str : str | None
        Path to config file, or None to use default
    path : str | None
        Local path where repo will be cloned
    workspace_root_path : str | None
        Workspace root to use in config
    dry_run : bool
        If True, preview changes without writing
    """
    # Determine config file
    config_file_path: pathlib.Path
    if config_file_path_str:
        config_file_path = pathlib.Path(config_file_path_str).expanduser().resolve()
    else:
        home_configs = find_home_config_files(filetype=["yaml"])
        if not home_configs:
            config_file_path = pathlib.Path.cwd() / ".vcspull.yaml"
            log.info(
                "No config specified and no default found, will create at %s",
                contract_user_home(config_file_path),
            )
        elif len(home_configs) > 1:
            log.error(
                "Multiple home config files found, please specify one with -f/--file",
            )
            return
        else:
            config_file_path = home_configs[0]

    # Load existing config
    raw_config: dict[str, t.Any]
    duplicate_root_occurrences: dict[str, list[t.Any]]
    top_level_items: list[tuple[str, t.Any]]
    display_config_path = contract_user_home(config_file_path)

    if config_file_path.exists() and config_file_path.is_file():
        try:
            (
                raw_config,
                duplicate_root_occurrences,
                top_level_items,
            ) = DuplicateAwareConfigReader.load_with_duplicates(config_file_path)
        except TypeError:
            log.exception(
                "Config file %s is not a valid YAML dictionary.",
                config_file_path,
            )
            return
        except Exception:
            log.exception("Error loading YAML from %s. Aborting.", config_file_path)
            if log.isEnabledFor(logging.DEBUG):
                traceback.print_exc()
            return
    else:
        raw_config = {}
        duplicate_root_occurrences = {}
        top_level_items = []
        log.info(
            "Config file %s not found. A new one will be created.",
            display_config_path,
        )

    config_items: list[tuple[str, t.Any]] = (
        [(label, copy.deepcopy(section)) for label, section in top_level_items]
        if top_level_items
        else [(label, copy.deepcopy(section)) for label, section in raw_config.items()]
    )

    def _aggregate_items(items: list[tuple[str, t.Any]]) -> dict[str, t.Any]:
        aggregated: dict[str, t.Any] = {}
        for label, section in items:
            if isinstance(section, dict):
                workspace_section = aggregated.setdefault(label, {})
                for repo_name, repo_config in section.items():
                    workspace_section[repo_name] = copy.deepcopy(repo_config)
            else:
                aggregated[label] = copy.deepcopy(section)
        return aggregated

    if not merge_duplicates:
        raw_config = _aggregate_items(config_items)

    duplicate_merge_conflicts: list[str] = []
    duplicate_merge_changes = 0
    duplicate_merge_details: list[tuple[str, int]] = []

    if merge_duplicates:
        (
            raw_config,
            duplicate_merge_conflicts,
            duplicate_merge_changes,
            duplicate_merge_details,
        ) = merge_duplicate_workspace_roots(raw_config, duplicate_root_occurrences)
        for message in duplicate_merge_conflicts:
            log.warning(message)

        if duplicate_merge_changes and duplicate_merge_details:
            for label, occurrence_count in duplicate_merge_details:
                log.info(
                    "%s•%s Merged %s%d%s duplicate entr%s for workspace root %s%s%s",
                    Fore.BLUE,
                    Style.RESET_ALL,
                    Fore.YELLOW,
                    occurrence_count,
                    Style.RESET_ALL,
                    "y" if occurrence_count == 1 else "ies",
                    Fore.MAGENTA,
                    label,
                    Style.RESET_ALL,
                )
    else:
        if duplicate_root_occurrences:
            duplicate_merge_details = [
                (label, len(values))
                for label, values in duplicate_root_occurrences.items()
            ]
            for label, occurrence_count in duplicate_merge_details:
                log.warning(
                    "%s•%s Duplicate workspace root %s%s%s appears %s%d%s time%s; "
                    "skipping merge because --no-merge was provided.",
                    Fore.BLUE,
                    Style.RESET_ALL,
                    Fore.MAGENTA,
                    label,
                    Style.RESET_ALL,
                    Fore.YELLOW,
                    occurrence_count,
                    Style.RESET_ALL,
                    "" if occurrence_count == 1 else "s",
                )

        duplicate_merge_conflicts = []

    cwd = pathlib.Path.cwd()
    home = pathlib.Path.home()

    aggregated_config = (
        raw_config if merge_duplicates else _aggregate_items(config_items)
    )

    if merge_duplicates:
        (
            raw_config,
            workspace_map,
            merge_conflicts,
            merge_changes,
        ) = normalize_workspace_roots(
            aggregated_config,
            cwd=cwd,
            home=home,
        )
        config_was_normalized = (merge_changes + duplicate_merge_changes) > 0
    else:
        (
            _normalized_preview,
            workspace_map,
            merge_conflicts,
            _merge_changes,
        ) = normalize_workspace_roots(
            aggregated_config,
            cwd=cwd,
            home=home,
        )
        config_was_normalized = False

    for message in merge_conflicts:
        log.warning(message)

    workspace_path = _resolve_workspace_path(
        workspace_root_path,
        path,
        cwd=cwd,
    )
    workspace_label = workspace_map.get(workspace_path)

    if workspace_root_path is None:
        preserve_workspace_label = path is None
    else:
        preserve_workspace_label = workspace_root_path in {".", "./"}

    if workspace_label is None:
        workspace_label = workspace_root_label(
            workspace_path,
            cwd=cwd,
            home=home,
            preserve_cwd_label=preserve_workspace_label,
        )
        workspace_map[workspace_path] = workspace_label
        raw_config.setdefault(workspace_label, {})
        if not merge_duplicates:
            config_items.append((workspace_label, {}))

    if workspace_label not in raw_config:
        raw_config[workspace_label] = {}
        if not merge_duplicates:
            config_items.append((workspace_label, {}))
    elif not isinstance(raw_config[workspace_label], dict):
        log.error(
            "Workspace root '%s' in configuration is not a dictionary. Aborting.",
            workspace_label,
        )
        return
    workspace_sections: list[tuple[int, dict[str, t.Any]]] = [
        (idx, section)
        for idx, (label, section) in enumerate(config_items)
        if label == workspace_label and isinstance(section, dict)
    ]

    # Check if repo already exists
    if name in raw_config[workspace_label]:
        existing_config = raw_config[workspace_label][name]
        # Handle both string and dict formats
        current_url: str
        if isinstance(existing_config, str):
            current_url = existing_config
        elif isinstance(existing_config, dict):
            repo_value = existing_config.get("repo")
            url_value = existing_config.get("url")
            current_url = repo_value or url_value or "unknown"
        else:
            current_url = str(existing_config)

        log.warning(
            "Repository '%s' already exists under '%s'. Current URL: %s. "
            "To update, remove and re-add, or edit the YAML file manually.",
            name,
            workspace_label,
            current_url,
        )
        if config_was_normalized:
            if dry_run:
                log.info(
                    "%s→%s Would save normalized workspace roots to %s%s%s.",
                    Fore.YELLOW,
                    Style.RESET_ALL,
                    Fore.BLUE,
                    display_config_path,
                    Style.RESET_ALL,
                )
            else:
                try:
                    save_config_yaml(config_file_path, raw_config)
                    log.info(
                        "%s✓%s Normalized workspace roots saved to %s%s%s.",
                        Fore.GREEN,
                        Style.RESET_ALL,
                        Fore.BLUE,
                        display_config_path,
                        Style.RESET_ALL,
                    )
                except Exception:
                    log.exception("Error saving config to %s", config_file_path)
                    if log.isEnabledFor(logging.DEBUG):
                        traceback.print_exc()
        return

    # Add the repository in verbose format
    new_repo_entry = {"repo": url}
    if merge_duplicates:
        raw_config[workspace_label][name] = new_repo_entry
    else:
        target_section: dict[str, t.Any]
        if workspace_sections:
            _, target_section = workspace_sections[-1]
        else:
            target_section = {}
            config_items.append((workspace_label, target_section))
        target_section[name] = copy.deepcopy(new_repo_entry)
        raw_config[workspace_label][name] = copy.deepcopy(new_repo_entry)

    # Save or preview config
    if dry_run:
        log.info(
            "%s→%s Would add %s'%s'%s (%s%s%s) to %s%s%s under '%s%s%s'.",
            Fore.YELLOW,
            Style.RESET_ALL,
            Fore.CYAN,
            name,
            Style.RESET_ALL,
            Fore.YELLOW,
            url,
            Style.RESET_ALL,
            Fore.BLUE,
            display_config_path,
            Style.RESET_ALL,
            Fore.MAGENTA,
            workspace_label,
            Style.RESET_ALL,
        )
    else:
        try:
            if merge_duplicates:
                save_config_yaml(config_file_path, raw_config)
            else:
                save_config_yaml_with_items(config_file_path, config_items)
            log.info(
                "%s✓%s Successfully added %s'%s'%s (%s%s%s) to %s%s%s under '%s%s%s'.",
                Fore.GREEN,
                Style.RESET_ALL,
                Fore.CYAN,
                name,
                Style.RESET_ALL,
                Fore.YELLOW,
                url,
                Style.RESET_ALL,
                Fore.BLUE,
                display_config_path,
                Style.RESET_ALL,
                Fore.MAGENTA,
                workspace_label,
                Style.RESET_ALL,
            )
        except Exception:
            log.exception("Error saving config to %s", config_file_path)
            if log.isEnabledFor(logging.DEBUG):
                traceback.print_exc()
            return
