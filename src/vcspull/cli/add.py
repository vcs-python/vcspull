"""Add single repository functionality for vcspull."""

from __future__ import annotations

import argparse
import copy
import logging
import pathlib
import subprocess
import traceback
import typing as t

from colorama import Fore, Style

from vcspull._internal.config_reader import DuplicateAwareConfigReader
from vcspull._internal.config_style import format_repo_entry
from vcspull._internal.private_path import PrivatePath
from vcspull._internal.settings import resolve_style
from vcspull.config import (
    canonicalize_workspace_path,
    expand_dir,
    find_home_config_files,
    merge_duplicate_workspace_roots,
    save_config_yaml,
    save_config_yaml_with_items,
    workspace_root_label,
)

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
        nargs="?",
        default=None,
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
    parser.add_argument(
        "--style",
        dest="style",
        choices=["concise", "standard", "verbose"],
        default=None,
        help="Config entry style (concise, standard, verbose)",
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
        repo_path = expand_dir(pathlib.Path(repo_path_str), cwd)
        return repo_path.parent
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


def _build_ordered_items(
    top_level_items: list[tuple[str, t.Any]] | None,
    raw_config: dict[str, t.Any],
) -> list[dict[str, t.Any]]:
    """Return deep-copied top-level items preserving original ordering."""
    source: list[tuple[str, t.Any]] = top_level_items or list(raw_config.items())

    ordered: list[dict[str, t.Any]] = []
    for label, section in source:
        ordered.append({"label": label, "section": copy.deepcopy(section)})
    return ordered


def _aggregate_from_ordered_items(
    items: list[dict[str, t.Any]],
) -> dict[str, t.Any]:
    """Collapse ordered top-level items into a mapping grouped by label."""
    aggregated: dict[str, t.Any] = {}
    for entry in items:
        label = entry["label"]
        section = entry["section"]
        if isinstance(section, dict):
            workspace_section = aggregated.setdefault(label, {})
            for repo_name, repo_config in section.items():
                workspace_section[repo_name] = copy.deepcopy(repo_config)
        else:
            aggregated[label] = copy.deepcopy(section)
    return aggregated


def _collect_duplicate_sections(
    items: list[dict[str, t.Any]],
) -> dict[str, list[t.Any]]:
    """Return mapping of labels to their repeated sections (>= 2 occurrences)."""
    occurrences: dict[str, list[t.Any]] = {}
    for entry in items:
        label = entry["label"]
        occurrences.setdefault(label, []).append(copy.deepcopy(entry["section"]))

    return {
        label: sections for label, sections in occurrences.items() if len(sections) > 1
    }


def handle_add_command(args: argparse.Namespace) -> None:
    """Entry point for the ``vcspull add`` CLI command."""
    repo_input = getattr(args, "repo_path", None)
    if repo_input is None:
        log.error("A repository path must be provided.")
        return

    cwd = pathlib.Path.cwd()
    repo_path = expand_dir(pathlib.Path(repo_input), cwd=cwd)

    if not repo_path.exists():
        log.error("Repository path %s does not exist.", PrivatePath(repo_path))
        return

    if not repo_path.is_dir():
        log.error("Repository path %s is not a directory.", PrivatePath(repo_path))
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
        display_url = str(PrivatePath(repo_path))
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

    display_path = str(PrivatePath(repo_path))

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
            log.info(
                "Aborted import of '%s' from %s",
                repo_name,
                PrivatePath(repo_path),
            )
            return

    add_repo(
        name=repo_name,
        url=config_url,
        config_file_path_str=args.config,
        path=str(repo_path),
        workspace_root_path=workspace_root_input,
        dry_run=args.dry_run,
        merge_duplicates=args.merge_duplicates,
        style=getattr(args, "style", None),
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
    style: str | None = None,
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
    style : str | None
        Config entry style (concise, standard, verbose).
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
                PrivatePath(config_file_path),
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
    display_config_path = str(PrivatePath(config_file_path))

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
                display_config_path,
            )
            return
        except Exception:
            log.exception(
                "Error loading YAML from %s. Aborting.",
                PrivatePath(config_file_path),
            )
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

    cwd = pathlib.Path.cwd()
    home = pathlib.Path.home()

    workspace_path = _resolve_workspace_path(
        workspace_root_path,
        path,
        cwd=cwd,
    )

    explicit_dot = workspace_root_path in {".", "./"}

    preferred_label = workspace_root_label(
        workspace_path,
        cwd=cwd,
        home=home,
        preserve_cwd_label=explicit_dot,
    )

    resolved_style = resolve_style(style)
    repo_path_obj = pathlib.Path(path) if path else None
    new_repo_entry = format_repo_entry(
        url, style=resolved_style, repo_path=repo_path_obj
    )

    def _ensure_workspace_label_for_merge(
        config_data: dict[str, t.Any],
    ) -> tuple[str, bool]:
        workspace_map: dict[pathlib.Path, str] = {}
        for label, section in config_data.items():
            if not isinstance(section, dict):
                continue
            try:
                path_key = canonicalize_workspace_path(label, cwd=cwd)
            except Exception:
                continue
            workspace_map[path_key] = label

        existing_label = workspace_map.get(workspace_path)
        relabelled = False

        if explicit_dot:
            workspace_label = "./"
            if existing_label and existing_label != "./":
                config_data["./"] = config_data.pop(existing_label)
                relabelled = True
            else:
                config_data.setdefault("./", {})
        elif existing_label is None:
            workspace_label = preferred_label
            config_data.setdefault(workspace_label, {})
        else:
            workspace_label = existing_label

        if workspace_label not in config_data:
            config_data[workspace_label] = {}

        return workspace_label, relabelled

    def _prepare_no_merge_items(
        items: list[dict[str, t.Any]],
    ) -> tuple[str, int, bool]:
        matching_indexes: list[int] = []
        for idx, entry in enumerate(items):
            section = entry["section"]
            if not isinstance(section, dict):
                continue
            try:
                path_key = canonicalize_workspace_path(entry["label"], cwd=cwd)
            except Exception:
                continue
            if path_key == workspace_path:
                matching_indexes.append(idx)

        relabelled = False

        if explicit_dot:
            if matching_indexes:
                for idx in matching_indexes:
                    if items[idx]["label"] != "./":
                        items[idx]["label"] = "./"
                        relabelled = True
                target_index = matching_indexes[-1]
            else:
                items.append({"label": "./", "section": {}})
                target_index = len(items) - 1
            workspace_label = items[target_index]["label"]
            return workspace_label, target_index, relabelled

        if not matching_indexes:
            workspace_label = preferred_label
            items.append({"label": workspace_label, "section": {}})
            target_index = len(items) - 1
            return workspace_label, target_index, relabelled

        target_index = matching_indexes[-1]
        workspace_label = items[target_index]["label"]
        return workspace_label, target_index, relabelled

    config_was_relabelled = False
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

        workspace_label, relabelled = _ensure_workspace_label_for_merge(raw_config)
        config_was_relabelled = relabelled
        workspace_section = raw_config.get(workspace_label)
        if not isinstance(workspace_section, dict):
            log.error(
                "Workspace root '%s' in configuration is not a dictionary. Aborting.",
                workspace_label,
            )
            return

        existing_config = workspace_section.get(name)
        if existing_config is not None:
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

            if (duplicate_merge_changes > 0 or config_was_relabelled) and not dry_run:
                try:
                    save_config_yaml(config_file_path, raw_config)
                    log.info(
                        "%s✓%s Workspace label adjustments saved to %s%s%s.",
                        Fore.GREEN,
                        Style.RESET_ALL,
                        Fore.BLUE,
                        display_config_path,
                        Style.RESET_ALL,
                    )
                except Exception:
                    log.exception(
                        "Error saving config to %s",
                        PrivatePath(config_file_path),
                    )
                    if log.isEnabledFor(logging.DEBUG):
                        traceback.print_exc()
            elif (duplicate_merge_changes > 0 or config_was_relabelled) and dry_run:
                log.info(
                    "%s→%s Would save workspace label adjustments to %s%s%s.",
                    Fore.YELLOW,
                    Style.RESET_ALL,
                    Fore.BLUE,
                    display_config_path,
                    Style.RESET_ALL,
                )
            return

        workspace_section[name] = copy.deepcopy(new_repo_entry)

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
            return

        try:
            save_config_yaml(config_file_path, raw_config)
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
            log.exception(
                "Error saving config to %s",
                PrivatePath(config_file_path),
            )
            if log.isEnabledFor(logging.DEBUG):
                traceback.print_exc()
        return

    ordered_items = _build_ordered_items(top_level_items, raw_config)

    workspace_label, target_index, relabelled = _prepare_no_merge_items(ordered_items)
    config_was_relabelled = relabelled

    duplicate_sections = _collect_duplicate_sections(ordered_items)
    for label, sections in duplicate_sections.items():
        occurrence_count = len(sections)
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

    raw_config_view = _aggregate_from_ordered_items(ordered_items)
    workspace_section_view = raw_config_view.get(workspace_label)
    if workspace_section_view is None:
        workspace_section_view = {}
        raw_config_view[workspace_label] = workspace_section_view

    if not isinstance(workspace_section_view, dict):
        log.error(
            "Workspace root '%s' in configuration is not a dictionary. Aborting.",
            workspace_label,
        )
        return

    existing_config = workspace_section_view.get(name)
    if existing_config is not None:
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

        if config_was_relabelled:
            if dry_run:
                log.info(
                    "%s→%s Would save workspace label adjustments to %s%s%s.",
                    Fore.YELLOW,
                    Style.RESET_ALL,
                    Fore.BLUE,
                    display_config_path,
                    Style.RESET_ALL,
                )
            else:
                try:
                    save_config_yaml_with_items(
                        config_file_path,
                        [(entry["label"], entry["section"]) for entry in ordered_items],
                    )
                    log.info(
                        "%s✓%s Workspace label adjustments saved to %s%s%s.",
                        Fore.GREEN,
                        Style.RESET_ALL,
                        Fore.BLUE,
                        display_config_path,
                        Style.RESET_ALL,
                    )
                except Exception:
                    log.exception(
                        "Error saving config to %s",
                        PrivatePath(config_file_path),
                    )
                    if log.isEnabledFor(logging.DEBUG):
                        traceback.print_exc()
        return

    target_section = ordered_items[target_index]["section"]
    if not isinstance(target_section, dict):
        log.error(
            "Workspace root '%s' in configuration is not a dictionary. Aborting.",
            ordered_items[target_index]["label"],
        )
        return

    target_section[name] = copy.deepcopy(new_repo_entry)
    workspace_section_view[name] = copy.deepcopy(new_repo_entry)

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
        return

    try:
        save_config_yaml_with_items(
            config_file_path,
            [(entry["label"], entry["section"]) for entry in ordered_items],
        )
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
        log.exception(
            "Error saving config to %s",
            PrivatePath(config_file_path),
        )
        if log.isEnabledFor(logging.DEBUG):
            traceback.print_exc()
