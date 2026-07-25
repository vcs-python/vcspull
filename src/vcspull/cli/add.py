"""Add single repository functionality for vcspull."""

from __future__ import annotations

import argparse
import copy
import enum
import logging
import pathlib
import subprocess
import traceback
import typing as t

from colorama import Fore, Style
from libvcs.url.git import GitURL

from vcspull._internal.config_reader import (
    DuplicateAwareConfigReader,
    config_format_from_path,
)
from vcspull._internal.private_path import PrivatePath
from vcspull.config import (
    build_repo_entry,
    canonicalize_workspace_path,
    expand_dir,
    find_home_config_files,
    get_pin_reason,
    is_pinned_for_op,
    merge_duplicate_workspace_roots,
    normalize_config_file_path,
    resolve_clone_depth,
    save_config,
    save_config_json,
    save_config_yaml_with_items,
    workspace_root_label,
)

log = logging.getLogger(__name__)


class AddAction(enum.Enum):
    """Action resolved for a single repo during ``vcspull add``."""

    ADD = "add"
    SKIP_EXISTING = "skip_existing"
    SKIP_PINNED = "skip_pinned"


def _classify_add_action(existing_entry: t.Any) -> AddAction:
    """Classify the add action for a single repository.

    Parameters
    ----------
    existing_entry : Any
        Current config entry for this repo name, or ``None`` if absent.

    Examples
    --------
    Not in config:

    >>> _classify_add_action(None)
    <AddAction.ADD: 'add'>

    Already exists (unpinned):

    >>> _classify_add_action({"repo": "git+ssh://x"})
    <AddAction.SKIP_EXISTING: 'skip_existing'>

    Pinned for add:

    >>> _classify_add_action({"repo": "git+ssh://x", "options": {"pin": True}})
    <AddAction.SKIP_PINNED: 'skip_pinned'>
    >>> entry = {"repo": "git+ssh://x", "options": {"pin": {"add": True}}}
    >>> _classify_add_action(entry)
    <AddAction.SKIP_PINNED: 'skip_pinned'>

    Pinned for import only — not pinned for add:

    >>> entry = {"repo": "git+ssh://x", "options": {"pin": {"import": True}}}
    >>> _classify_add_action(entry)
    <AddAction.SKIP_EXISTING: 'skip_existing'>
    """
    if existing_entry is None:
        return AddAction.ADD
    if is_pinned_for_op(existing_entry, "add"):
        return AddAction.SKIP_PINNED
    return AddAction.SKIP_EXISTING


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
            "Filesystem path to an existing project, or a repository URL to "
            "declare without checking it out. A path's parent directory "
            "becomes the workspace; a URL uses --workspace, else a workspace "
            "root already declared in the config."
        ),
    )
    parser.add_argument(
        "--name",
        dest="override_name",
        help=(
            "Override the repository name detected from the path or URL. "
            "Required when a URL has no path segment to name."
        ),
    )
    parser.add_argument(
        "--url",
        dest="url",
        help=(
            "Repository URL to record for a path (overrides detected remotes). "
            "Omit when the argument is already a URL."
        ),
    )
    parser.add_argument(
        "--pin",
        dest="pin",
        metavar="REF",
        help="Record a fixed commit, tag, or branch as the repository 'rev'",
    )
    parser.add_argument(
        "--shallow",
        dest="shallow",
        action="store_true",
        help=(
            "Record 'options.shallow: true' (clone --depth 1 on sync). A "
            "shallow checkout is detected automatically; this forces it on."
        ),
    )
    parser.add_argument(
        "--depth",
        dest="depth",
        type=int,
        metavar="N",
        help=(
            "Record 'options.depth: N' (clone --depth N on sync). Overrides "
            "--shallow. An existing shallow checkout's depth is detected "
            "automatically."
        ),
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


class ParsedRepoUrl(t.NamedTuple):
    """What ``add`` needs from a repository URL, as libvcs parses it.

    Attributes
    ----------
    name : str | None
        Repository name taken from the URL's path, or ``None`` when the URL
        carries no path segment to name.
    url : str
        The URL without any pip-style ``@rev``, suitable to record as ``repo``.
    rev : str | None
        Revision from a pip-style ``@rev``, to record as ``options.rev``.
    unparsed_rev : str | None
        Revision trailing a URL libvcs does not parse revisions for, which
        would otherwise stay in the recorded URL and fail to clone.
    """

    name: str | None
    url: str
    rev: str | None
    unparsed_rev: str | None


def _parse_repo_url(url: str) -> ParsedRepoUrl:
    """Split a repository URL into a name, a rev-free URL, and a revision.

    ``add`` accepts a URL argument on :meth:`GitURL.is_valid`, so it derives
    the name and revision from that same parse rather than splitting strings
    itself. Two libvcs details shape this:

    - :meth:`GitURL.to_url` re-appends a revision the input already carried, so
      the rev-free URL drops the parsed revision from the tail instead.
    - The pip ``file://`` rule leaves ``.git`` on ``path`` instead of moving it
      to ``suffix``, so the final segment is trimmed unconditionally.

    Only pip-style URLs (``git+…``) carry a revision; libvcs parses ``@rev`` on
    a bare ``https://`` URL as part of the path.

    Parameters
    ----------
    url : str
        Repository URL, already accepted by :meth:`GitURL.is_valid`.

    Returns
    -------
    ParsedRepoUrl
        ``name`` is ``None`` when the URL has no path segment to name.

    Examples
    --------
    >>> _parse_repo_url("https://github.com/pallets/flask.git").name
    'flask'

    A pip-style revision moves out of the URL:

    >>> parsed = _parse_repo_url("git+https://github.com/pallets/flask.git@v1.0")
    >>> parsed.name, parsed.rev
    ('flask', 'v1.0')
    >>> parsed.url
    'git+https://github.com/pallets/flask.git'

    Scp-style remotes, trailing slashes, and a missing ``.git`` all resolve:

    >>> _parse_repo_url("git@github.com:pallets/flask.git").name
    'flask'
    >>> _parse_repo_url("https://github.com/pallets/flask/").name
    'flask'
    >>> _parse_repo_url("git+file:///srv/git/flask.git").name
    'flask'

    A URL with no path segment yields no name:

    >>> _parse_repo_url("https://host/.git").name is None
    True

    A revision on a URL libvcs parses no revision for is reported, not kept:

    >>> _parse_repo_url("https://github.com/pallets/flask.git@v1.0").unparsed_rev
    'v1.0'
    >>> _parse_repo_url("https://user@host/pallets/flask.git").unparsed_rev is None
    True
    """
    cleaned = url.strip()
    parsed = GitURL(url=cleaned)

    rev = parsed.rev or None
    if rev is not None and cleaned.endswith(f"@{rev}"):
        cleaned = cleaned[: -(len(rev) + 1)]

    segment = (parsed.path or "").rstrip("/").rsplit("/", 1)[-1].removesuffix(".git")

    # Only pip-style URLs expose a revision, so on any other shape an ``@rev``
    # stays in the URL and git cannot clone it. Anchor the search on the parsed
    # path rather than scanning for ``@``, which would also match ``user@host``.
    unparsed_rev = None
    if rev is None and parsed.path:
        trailer = cleaned.rsplit(parsed.path, 1)[-1]
        if "@" in trailer:
            unparsed_rev = trailer.rsplit("@", 1)[-1] or None

    return ParsedRepoUrl(
        name=segment or None,
        url=cleaned,
        rev=rev,
        unparsed_rev=unparsed_rev,
    )


class RepoPlacement(t.NamedTuple):
    """Where a repository lands, for the preview and the write to agree on.

    Attributes
    ----------
    workspace_label : str
        Workspace root label the entry is recorded under.
    display_path : str
        Destination path of the working tree, shortened for display.
    """

    workspace_label: str
    display_path: str


def _resolve_placement(
    workspace_root_input: str,
    repo_name: str,
    repo_path: pathlib.Path,
    *,
    url_mode: bool,
    cwd: pathlib.Path,
) -> RepoPlacement:
    """Derive the workspace label and destination path for a workspace root.

    Called once the workspace root is settled — after the prompt, which may
    swap in a different declared root — so the preview cannot announce a
    workspace the entry is not written under.

    Parameters
    ----------
    workspace_root_input : str
        Workspace root as the user, the config, or the prompt supplied it.
    repo_name : str
        Repository name that becomes the config key.
    repo_path : pathlib.Path
        Existing checkout. Unused in URL mode, where nothing is on disk.
    url_mode : bool
        ``True`` when declaring from a URL rather than importing a checkout.
    cwd : pathlib.Path
        Current working directory, for resolving relative roots.

    Returns
    -------
    RepoPlacement
        Label and destination path to preview and to write under.

    Examples
    --------
    In URL mode the destination is the workspace root joined with the name:

    >>> placement = _resolve_placement(
    ...     "~/code/",
    ...     "flask",
    ...     pathlib.Path("/nonexistent"),
    ...     url_mode=True,
    ...     cwd=pathlib.Path.cwd(),
    ... )
    >>> placement.workspace_label
    '~/code/'
    >>> placement.display_path
    '~/code/flask'

    In path mode the destination is the checkout itself:

    >>> checkout = tmp_path / "workspace" / "flask"
    >>> placement = _resolve_placement(
    ...     str(tmp_path / "workspace"),
    ...     "flask",
    ...     checkout,
    ...     url_mode=False,
    ...     cwd=pathlib.Path.cwd(),
    ... )
    >>> placement.display_path == str(checkout)
    True
    """
    workspace_path = expand_dir(pathlib.Path(workspace_root_input), cwd=cwd)
    return RepoPlacement(
        workspace_label=workspace_root_label(
            workspace_path,
            cwd=cwd,
            home=pathlib.Path.home(),
            preserve_cwd_label=workspace_root_input in {".", "./"},
        ),
        display_path=str(
            PrivatePath(workspace_path / repo_name if url_mode else repo_path),
        ),
    )


class ConfigFileResolution(t.NamedTuple):
    """Outcome of deciding which config file ``add`` should write to."""

    path: pathlib.Path | None
    creates_new_default: bool
    ambiguous: bool


def _resolve_config_file(config_file_path_str: str | None) -> ConfigFileResolution:
    """Resolve which config file ``add`` should write to.

    Reports discovery outcomes rather than logging them, so callers that only
    need the path (to read declared workspace roots, say) do not emit the
    discovery messages a second time.

    Parameters
    ----------
    config_file_path_str : str | None
        Value of ``-f/--file``, or ``None`` to discover a default.

    Returns
    -------
    ConfigFileResolution
        ``path`` is ``None`` only when ``ambiguous`` is ``True``.

    Examples
    --------
    An explicit ``-f/--file`` path is taken as given:

    >>> resolution = _resolve_config_file(str(tmp_path / "custom.yaml"))
    >>> resolution.path.name
    'custom.yaml'
    >>> resolution.creates_new_default, resolution.ambiguous
    (False, False)

    With no explicit path and no config in the home directory, ``add`` falls
    back to creating one in the current directory:

    >>> resolution = _resolve_config_file(None)
    >>> resolution.path.name
    '.vcspull.yaml'
    >>> resolution.creates_new_default
    True
    """
    if config_file_path_str:
        return ConfigFileResolution(
            path=normalize_config_file_path(pathlib.Path(config_file_path_str)),
            creates_new_default=False,
            ambiguous=False,
        )

    home_configs = find_home_config_files(filetype=["yaml"])
    if not home_configs:
        return ConfigFileResolution(
            path=pathlib.Path.cwd() / ".vcspull.yaml",
            creates_new_default=True,
            ambiguous=False,
        )
    if len(home_configs) > 1:
        return ConfigFileResolution(
            path=None,
            creates_new_default=False,
            ambiguous=True,
        )
    return ConfigFileResolution(
        path=home_configs[0],
        creates_new_default=False,
        ambiguous=False,
    )


def _declared_workspace_labels(config_file_path: pathlib.Path) -> list[str]:
    r"""Return workspace root labels already declared in a config file.

    Used to offer the workspace roots a user already keeps repositories under
    when adding by URL, where there is no parent directory to infer from.
    Duplicate labels collapse to their first occurrence, preserving file order.

    Parameters
    ----------
    config_file_path : pathlib.Path
        Config file to inspect. A missing or unreadable file yields ``[]``.

    Returns
    -------
    list[str]
        Workspace root labels in the order they appear in the file.

    Examples
    --------
    A missing file has no declared roots:

    >>> _declared_workspace_labels(tmp_path / "absent.yaml")
    []

    Labels come back in file order, without duplicates:

    >>> config_file = tmp_path / "declared.yaml"
    >>> _ = config_file.write_text(
    ...     "~/code/:\n  a: git+https://example.com/a.git\n"
    ...     "~/study/:\n  b: git+https://example.com/b.git\n",
    ...     encoding="utf-8",
    ... )
    >>> _declared_workspace_labels(config_file)
    ['~/code/', '~/study/']
    """
    if not (config_file_path.exists() and config_file_path.is_file()):
        return []

    try:
        (
            raw_config,
            _duplicates,
            top_level_items,
        ) = DuplicateAwareConfigReader.load_with_duplicates(config_file_path)
    except Exception:
        log.debug(
            "Could not read workspace roots from %s",
            PrivatePath(config_file_path),
            exc_info=True,
        )
        return []

    source = top_level_items or list(raw_config.items())
    labels: list[str] = []
    seen: set[str] = set()
    for label, section in source:
        if isinstance(section, dict) and label not in seen:
            seen.add(label)
            labels.append(label)
    return labels


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


def _collapse_ordered_items_to_dict(
    ordered_items: list[dict[str, t.Any]],
) -> dict[str, t.Any]:
    """Collapse ordered items into a flat dict for JSON serialization.

    JSON does not support duplicate keys, so sections with the same
    workspace label are merged at the repo level via ``dict.update()``
    (last occurrence of a repo name wins).

    Examples
    --------
    Distinct labels pass through unchanged:

    >>> _collapse_ordered_items_to_dict([
    ...     {"label": "~/code/", "section": {"repo1": {"repo": "git+x"}}},
    ...     {"label": "~/work/", "section": {"repo2": {"repo": "git+y"}}},
    ... ])
    {'~/code/': {'repo1': {'repo': 'git+x'}}, '~/work/': {'repo2': {'repo': 'git+y'}}}

    Duplicate labels are merged (repos from both sections appear):

    >>> result = _collapse_ordered_items_to_dict([
    ...     {"label": "~/code/", "section": {"repo1": {"repo": "git+a"}}},
    ...     {"label": "~/code/", "section": {"repo2": {"repo": "git+b"}}},
    ... ])
    >>> sorted(result["~/code/"].keys())
    ['repo1', 'repo2']
    """
    result: dict[str, t.Any] = {}
    for entry in ordered_items:
        label = entry["label"]
        section = entry["section"]
        if (
            label in result
            and isinstance(result[label], dict)
            and isinstance(section, dict)
        ):
            result[label].update(section)
        else:
            result[label] = (
                copy.deepcopy(section) if isinstance(section, dict) else section
            )
    return result


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


def _save_ordered_items(
    config_file_path: pathlib.Path,
    ordered_items: list[dict[str, t.Any]],
) -> None:
    """Persist ordered items in the format matching the config file extension.

    Parameters
    ----------
    config_file_path : pathlib.Path
        Path to config file (.yaml or .json).
    ordered_items : list of dict
        Each dict has ``"label"`` and ``"section"`` keys.

    Examples
    --------
    YAML output:

    >>> import pathlib
    >>> config_file = tmp_path / "test.yaml"
    >>> items = [{"label": "~/code/", "section": {"myrepo": "git+https://example.com/r.git"}}]
    >>> _save_ordered_items(config_file, items)
    >>> config_file.read_text().strip()  # doctest: +ELLIPSIS
    '~/code/...'

    JSON output:

    >>> config_file = tmp_path / "test.json"
    >>> _save_ordered_items(config_file, items)
    >>> import json
    >>> data = json.loads(config_file.read_text())
    >>> "~/code/" in data
    True
    """
    if config_format_from_path(config_file_path) == "json":
        save_config_json(
            config_file_path,
            _collapse_ordered_items_to_dict(ordered_items),
        )
    else:
        items = [(entry["label"], entry["section"]) for entry in ordered_items]
        save_config_yaml_with_items(config_file_path, items)


def handle_add_command(args: argparse.Namespace) -> None:
    """Entry point for the ``vcspull add`` CLI command."""
    repo_input = getattr(args, "repo_path", None)
    if repo_input is None:
        log.error("A repository path or URL must be provided.")
        return

    cwd = pathlib.Path.cwd()
    repo_path = expand_dir(pathlib.Path(repo_input), cwd=cwd)
    explicit_url = getattr(args, "url", None)

    # An existing directory always wins, so every path-mode invocation keeps
    # behaving as before; a URL is only considered when nothing is on disk.
    url_mode = not repo_path.exists() and GitURL.is_valid(repo_input)

    if not url_mode:
        if not repo_path.exists():
            log.error("Repository path %s does not exist.", PrivatePath(repo_path))
            return

        if not repo_path.is_dir():
            log.error("Repository path %s is not a directory.", PrivatePath(repo_path))
            return

    resolution = _resolve_config_file(getattr(args, "config", None))
    if resolution.ambiguous or resolution.path is None:
        log.error(
            "Multiple home config files found, please specify one with -f/--file",
        )
        return
    # Discovery messages stay in add_repo, which owns the write, so resolving
    # here to read declared workspace roots does not duplicate them.
    config_file_path = resolution.path

    override_name = getattr(args, "override_name", None)
    pin_rev = getattr(args, "pin", None)
    url_rev: str | None = None

    if url_mode:
        if explicit_url:
            log.error(
                "Cannot combine a repository URL argument with --url; "
                "pass the URL once.",
            )
            return
        parsed_url = _parse_repo_url(repo_input)
        if parsed_url.rev is not None and pin_rev:
            log.error(
                "Cannot combine the revision '@%s' in the URL with "
                "--pin %s; pass the revision once.",
                parsed_url.rev,
                pin_rev,
            )
            return
        if parsed_url.unparsed_rev is not None:
            log.error(
                "Cannot record the revision '@%s' from %s: only pip-style "
                "'git+' URLs carry a revision. Pass the URL without it and "
                "--pin %s instead.",
                parsed_url.unparsed_rev,
                repo_input,
                parsed_url.unparsed_rev,
            )
            return
        derived_name = override_name or parsed_url.name
        if derived_name is None:
            log.error(
                "Could not derive a repository name from %s; pass --name to set one.",
                repo_input,
            )
            return
        url_rev = parsed_url.rev
        repo_name = derived_name
        display_url, config_url = _normalize_detected_url(parsed_url.url)
    else:
        repo_name = override_name or repo_path.name
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
    workspace_candidates: list[str] = []

    if workspace_root_arg is not None:
        workspace_root_input = workspace_root_arg
    elif url_mode:
        # No parent directory to infer from, so offer the roots this config
        # already declares before falling back to the current directory.
        workspace_candidates = _declared_workspace_labels(config_file_path)
        if workspace_candidates:
            workspace_root_input = workspace_candidates[0]
        else:
            workspace_root_input = workspace_root_label(
                cwd,
                cwd=cwd,
                home=pathlib.Path.home(),
                preserve_cwd_label=config_file_path.parent == cwd,
            )
    else:
        workspace_root_input = repo_path.parent.as_posix()

    summary_url = display_url or config_url

    # Offering the choice inline keeps URL mode to a single prompt: confirming
    # accepts the default root, a number picks a different declared one.
    offer_choice = len(workspace_candidates) > 1
    answers = "[y/N]" if not offer_choice else f"[y/N/1-{len(workspace_candidates)}]"
    interactive = not args.dry_run and not getattr(args, "assume_yes", False)
    # Only an answered choice can move the workspace, so anything else is
    # already settled and previews in place.
    workspace_settled = not (offer_choice and interactive)

    def announce_placement() -> None:
        """Log where the entry lands, reading the settled workspace root."""
        placement = _resolve_placement(
            workspace_root_input,
            repo_name,
            repo_path,
            url_mode=url_mode,
            cwd=cwd,
        )
        log.info(
            "  %s•%s workspace: %s%s%s",
            Fore.BLUE,
            Style.RESET_ALL,
            Fore.MAGENTA,
            placement.workspace_label,
            Style.RESET_ALL,
        )
        log.info(
            "  %s↳%s path: %s%s%s",
            Fore.BLUE,
            Style.RESET_ALL,
            Fore.BLUE,
            placement.display_path,
            Style.RESET_ALL,
        )

    explicit_depth = getattr(args, "depth", None)
    if explicit_depth is not None and explicit_depth < 1:
        log.error("--depth must be a positive integer (got %s)", explicit_depth)
        return

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
    if workspace_settled:
        announce_placement()
    effective_rev = pin_rev or url_rev
    if effective_rev:
        log.info(
            "  %s•%s rev: %s%s%s",
            Fore.BLUE,
            Style.RESET_ALL,
            Fore.YELLOW,
            effective_rev,
            Style.RESET_ALL,
        )

    shallow, depth = resolve_clone_depth(
        repo_path,
        explicit_shallow=bool(getattr(args, "shallow", False)),
        explicit_depth=explicit_depth,
    )
    if depth is not None:
        log.info(
            "  %s•%s depth: %s%s%s",
            Fore.BLUE,
            Style.RESET_ALL,
            Fore.YELLOW,
            depth,
            Style.RESET_ALL,
        )
    elif shallow:
        log.info(
            "  %s•%s shallow: %strue%s",
            Fore.BLUE,
            Style.RESET_ALL,
            Fore.YELLOW,
            Style.RESET_ALL,
        )

    if offer_choice:
        log.info(
            "  %s•%s workspace roots in %s%s%s:",
            Fore.BLUE,
            Style.RESET_ALL,
            Fore.BLUE,
            PrivatePath(config_file_path),
            Style.RESET_ALL,
        )
        for index, candidate in enumerate(workspace_candidates, start=1):
            log.info(
                "      %s%d)%s %s%s%s%s",
                Fore.YELLOW,
                index,
                Style.RESET_ALL,
                Fore.MAGENTA,
                candidate,
                Style.RESET_ALL,
                " (default)" if index == 1 else "",
            )

    prompt_text = f"{Fore.CYAN}?{Style.RESET_ALL} Import this repository? {answers}: "

    if args.dry_run:
        log.info(
            "%s?%s Import this repository? %s: %sskipped (dry-run)%s",
            Fore.CYAN,
            Style.RESET_ALL,
            answers,
            Fore.YELLOW,
            Style.RESET_ALL,
        )
    elif getattr(args, "assume_yes", False):
        log.info(
            "%s?%s Import this repository? %s: %sy (auto-confirm)%s",
            Fore.CYAN,
            Style.RESET_ALL,
            answers,
            Fore.GREEN,
            Style.RESET_ALL,
        )
    else:
        try:
            response = input(prompt_text)
        except EOFError:
            response = ""
        answer = response.strip().lower()

        chosen: str | None = None
        if answer in {"y", "yes"}:
            chosen = workspace_root_input
        elif offer_choice and answer.isdecimal():
            # ``isdecimal()`` and not ``isdigit()``: the latter accepts
            # characters such as '²' that ``int()`` then rejects.
            index = int(answer)
            if 1 <= index <= len(workspace_candidates):
                chosen = workspace_candidates[index - 1]

        if chosen is None:
            log.info(
                "Aborted import of '%s' from %s",
                repo_name,
                repo_input if url_mode else PrivatePath(repo_path),
            )
            return
        workspace_root_input = chosen

    if not workspace_settled:
        # The answer above may have swapped in a different declared root, so
        # the placement is only announced once it can no longer change.
        announce_placement()

    add_repo(
        name=repo_name,
        url=config_url,
        config_file_path_str=args.config,
        path=None if url_mode else str(repo_path),
        workspace_root_path=workspace_root_input,
        dry_run=args.dry_run,
        merge_duplicates=args.merge_duplicates,
        rev=effective_rev,
        shallow=shallow,
        depth=depth,
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
    rev: str | None = None,
    shallow: bool = False,
    depth: int | None = None,
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
    rev : str | None
        Commit, tag, or branch to record as ``options.rev``.
    shallow : bool
        If ``True``, record ``options.shallow: true`` for the repository.
    depth : int | None
        If set, record ``options.depth: N`` for the repository.
    """
    # Determine config file
    resolution = _resolve_config_file(config_file_path_str)
    if resolution.ambiguous or resolution.path is None:
        log.error(
            "Multiple home config files found, please specify one with -f/--file",
        )
        return
    config_file_path = resolution.path
    if resolution.creates_new_default:
        log.info(
            "No config specified and no default found, will create at %s",
            PrivatePath(config_file_path),
        )

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

    new_repo_entry = build_repo_entry(url, rev=rev, shallow=shallow, depth=depth)

    def _ensure_workspace_label_for_merge(
        config_data: dict[str, t.Any],
    ) -> tuple[str, bool]:
        workspace_map: dict[pathlib.Path, str] = {}
        for label, section in config_data.items():
            if not isinstance(section, dict):
                continue
            try:
                path_key = canonicalize_workspace_path(label, cwd=cwd)
            except (OSError, ValueError):
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
            except (OSError, ValueError):
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
        add_action = _classify_add_action(existing_config)

        if add_action == AddAction.SKIP_PINNED:
            reason = get_pin_reason(existing_config)
            log.warning(
                "Repository '%s' is pinned%s — skipping",
                name,
                f" ({reason})" if reason else "",
            )
            if (duplicate_merge_changes > 0 or config_was_relabelled) and not dry_run:
                try:
                    save_config(config_file_path, raw_config)
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
        elif add_action == AddAction.SKIP_EXISTING:
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
                "To update, remove and re-add, or edit the config file manually.",
                name,
                workspace_label,
                current_url,
            )

            if (duplicate_merge_changes > 0 or config_was_relabelled) and not dry_run:
                try:
                    save_config(config_file_path, raw_config)
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
            save_config(config_file_path, raw_config)
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
    no_merge_add_action = _classify_add_action(existing_config)

    if no_merge_add_action == AddAction.SKIP_PINNED:
        reason = get_pin_reason(existing_config)
        log.warning(
            "Repository '%s' is pinned%s — skipping",
            name,
            f" ({reason})" if reason else "",
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
                    _save_ordered_items(config_file_path, ordered_items)
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
    elif no_merge_add_action == AddAction.SKIP_EXISTING:
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
            "To update, remove and re-add, or edit the config file manually.",
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
                    _save_ordered_items(config_file_path, ordered_items)
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
        _save_ordered_items(config_file_path, ordered_items)
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
