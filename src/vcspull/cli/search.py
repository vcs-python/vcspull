"""Search repositories functionality for vcspull."""

from __future__ import annotations

import argparse
import logging
import pathlib
import re
import typing as t
from dataclasses import dataclass

from vcspull._internal.private_path import PrivatePath
from vcspull.config import find_config_files, load_configs
from vcspull.types import ConfigDict

from ._colors import Colors, get_color_mode
from ._output import OutputFormatter, get_output_mode
from ._workspaces import filter_by_workspace

log = logging.getLogger(__name__)

FIELD_ALIASES = {
    "name": "name",
    "path": "path",
    "url": "url",
    "workspace": "workspace",
    "root": "workspace",
    "ws": "workspace",
}
DEFAULT_FIELDS = ("name", "path", "url", "workspace")


class SearchToken(t.NamedTuple):
    """Parsed query token with optional field restrictions."""

    fields: tuple[str, ...]
    pattern: str


@dataclass(frozen=True)
class SearchPattern:
    """Compiled search pattern tied to repository fields."""

    fields: tuple[str, ...]
    raw: str
    regex: re.Pattern[str]


def normalize_fields(fields: list[str] | None) -> tuple[str, ...]:
    """Normalize and validate search fields.

    Parameters
    ----------
    fields : list[str] | None
        Raw field list, optionally comma-delimited

    Returns
    -------
    tuple[str, ...]
        Normalized field names

    Examples
    --------
    >>> normalize_fields(["name", "url"])
    ('name', 'url')
    >>> normalize_fields(["name,url", "workspace"])
    ('name', 'url', 'workspace')
    >>> normalize_fields(None)
    ('name', 'path', 'url', 'workspace')
    """
    if not fields:
        return DEFAULT_FIELDS

    normalized: list[str] = []
    for entry in fields:
        if not entry:
            continue
        for raw in entry.split(","):
            raw = raw.strip().lower()
            if not raw:
                continue
            field = FIELD_ALIASES.get(raw)
            if field is None:
                message = f"Unknown search field: {raw}"
                raise ValueError(message)
            if field not in normalized:
                normalized.append(field)

    return tuple(normalized or DEFAULT_FIELDS)


def parse_query_terms(
    terms: list[str],
    *,
    default_fields: tuple[str, ...],
) -> list[SearchToken]:
    """Parse raw search terms into field-scoped tokens.

    Parameters
    ----------
    terms : list[str]
        Raw query terms
    default_fields : tuple[str, ...]
        Fields to apply when no field prefix is provided

    Returns
    -------
    list[SearchToken]
        Parsed search tokens

    Examples
    --------
    >>> tokens = parse_query_terms(
    ...     ["name:django", "github"],
    ...     default_fields=("name", "url"),
    ... )
    >>> tokens[0]
    SearchToken(fields=('name',), pattern='django')
    >>> tokens[1]
    SearchToken(fields=('name', 'url'), pattern='github')
    """
    tokens: list[SearchToken] = []
    for term in terms:
        if term is None:
            continue
        prefix, sep, rest = term.partition(":")
        if sep:
            field = FIELD_ALIASES.get(prefix.strip().lower())
            if field is not None:
                if not rest:
                    message = "Search term cannot be empty after field prefix"
                    raise ValueError(message)
                tokens.append(SearchToken(fields=(field,), pattern=rest))
                continue
        tokens.append(SearchToken(fields=default_fields, pattern=term))

    return tokens


def compile_search_patterns(
    tokens: list[SearchToken],
    *,
    ignore_case: bool,
    smart_case: bool,
    fixed_strings: bool,
    word_regexp: bool,
) -> list[SearchPattern]:
    """Compile search tokens into regex patterns.

    Parameters
    ----------
    tokens : list[SearchToken]
        Parsed tokens
    ignore_case : bool
        Force case-insensitive matching
    smart_case : bool
        Enable smart-case matching
    fixed_strings : bool
        Treat patterns as literal strings
    word_regexp : bool
        Match whole words only

    Returns
    -------
    list[SearchPattern]
        Compiled search patterns

    Examples
    --------
    >>> tokens = [SearchToken(fields=("name",), pattern="django")]
    >>> patterns = compile_search_patterns(
    ...     tokens,
    ...     ignore_case=True,
    ...     smart_case=False,
    ...     fixed_strings=False,
    ...     word_regexp=False,
    ... )
    >>> bool(patterns[0].regex.search("Django"))
    True
    """
    if not tokens:
        return []

    use_ignore_case = ignore_case
    if not ignore_case and smart_case:
        has_upper = any(
            any(char.isupper() for char in token.pattern) for token in tokens
        )
        use_ignore_case = not has_upper

    flags = re.IGNORECASE if use_ignore_case else 0
    patterns: list[SearchPattern] = []

    for token in tokens:
        raw = token.pattern
        if raw == "":
            message = "Search pattern cannot be empty"
            raise ValueError(message)

        pattern = re.escape(raw) if fixed_strings else raw
        if word_regexp:
            pattern = rf"\b(?:{pattern})\b"

        try:
            regex = re.compile(pattern, flags)
        except re.error as exc:
            message = f"Invalid search pattern {raw!r}: {exc}"
            raise ValueError(message) from exc

        patterns.append(SearchPattern(fields=token.fields, raw=raw, regex=regex))

    return patterns


def evaluate_match(
    fields: dict[str, str],
    patterns: list[SearchPattern],
    *,
    match_any: bool,
) -> tuple[bool, dict[str, list[str]]]:
    """Return match status and matched substrings by field.

    Parameters
    ----------
    fields : dict[str, str]
        Field values to search
    patterns : list[SearchPattern]
        Compiled search patterns
    match_any : bool
        Whether to match any token instead of all tokens

    Returns
    -------
    tuple[bool, dict[str, list[str]]]
        Match status and mapping of matched fields to match strings

    Examples
    --------
    >>> fields = {
    ...     "name": "django",
    ...     "path": "~/code/django",
    ...     "url": "git+https://github.com/django/django.git",
    ...     "workspace": "~/code/",
    ... }
    >>> tokens = parse_query_terms(["name:django"], default_fields=("name", "url"))
    >>> patterns = compile_search_patterns(
    ...     tokens,
    ...     ignore_case=False,
    ...     smart_case=False,
    ...     fixed_strings=False,
    ...     word_regexp=False,
    ... )
    >>> matched, matches = evaluate_match(fields, patterns, match_any=False)
    >>> matched
    True
    >>> matches["name"]
    ['django']
    """
    if not patterns:
        return False, {}

    matches: dict[str, list[str]] = {}
    token_hits: list[bool] = []

    for pattern in patterns:
        token_matched = False
        for field in pattern.fields:
            value = fields.get(field, "")
            if not value:
                continue
            if pattern.regex.search(value):
                token_matched = True
                field_matches = matches.setdefault(field, [])
                for match in pattern.regex.finditer(value):
                    text = match.group(0)
                    if text and text not in field_matches:
                        field_matches.append(text)
        token_hits.append(token_matched)
        if not match_any and not token_matched:
            return False, {}

    if match_any:
        if any(token_hits):
            return True, matches
        return False, {}

    return True, matches


def highlight_text(
    text: str,
    patterns: list[re.Pattern[str]],
    *,
    colors: Colors,
    base_color: str | None = None,
) -> str:
    """Return text with regex matches highlighted.

    Parameters
    ----------
    text : str
        Input text
    patterns : list[re.Pattern[str]]
        Patterns to highlight
    colors : Colors
        Color manager
    base_color : str | None
        Base color code to reapply outside highlights

    Returns
    -------
    str
        Highlighted text

    Examples
    --------
    >>> from vcspull.cli._colors import ColorMode
    >>> colors = Colors(ColorMode.NEVER)
    >>> highlight_text("django", [re.compile("jan")], colors=colors)
    'django'
    """
    if not patterns:
        if base_color:
            return colors.colorize(text, base_color)
        return text

    if not colors._enabled:
        return text

    unique_patterns: list[str] = []
    flags = 0
    for pattern in patterns:
        if pattern.pattern not in unique_patterns:
            unique_patterns.append(pattern.pattern)
        flags |= pattern.flags

    if not unique_patterns:
        if base_color:
            return colors.colorize(text, base_color)
        return text

    combined = re.compile("|".join(f"(?:{pat})" for pat in unique_patterns), flags)

    if base_color:

        def repl_with_base(match: re.Match[str]) -> str:
            return f"{colors.HIGHLIGHT}{match.group(0)}{base_color}"

        return f"{base_color}{combined.sub(repl_with_base, text)}{colors.RESET}"

    def repl_plain(match: re.Match[str]) -> str:
        return f"{colors.HIGHLIGHT}{match.group(0)}{colors.RESET}"

    return combined.sub(repl_plain, text)


def find_search_matches(
    repos: list[ConfigDict],
    patterns: list[SearchPattern],
    *,
    match_any: bool,
    invert_match: bool,
) -> list[dict[str, t.Any]]:
    """Return search matches for repositories.

    Parameters
    ----------
    repos : list[ConfigDict]
        Repository configurations to search
    patterns : list[SearchPattern]
        Compiled search patterns
    match_any : bool
        Whether any token match is sufficient
    invert_match : bool
        Whether to return non-matching repositories

    Returns
    -------
    list[dict[str, t.Any]]
        Search results containing matched fields

    Examples
    --------
    >>> repos = [
    ...     {
    ...         "name": "django",
    ...         "path": "/tmp/django",
    ...         "url": "git+https://github.com/django/django.git",
    ...         "workspace_root": "~/code/",
    ...     },
    ... ]
    >>> tokens = parse_query_terms(["django"], default_fields=DEFAULT_FIELDS)
    >>> patterns = compile_search_patterns(
    ...     tokens,
    ...     ignore_case=False,
    ...     smart_case=False,
    ...     fixed_strings=False,
    ...     word_regexp=False,
    ... )
    >>> results = find_search_matches(
    ...     repos,
    ...     patterns,
    ...     match_any=False,
    ...     invert_match=False,
    ... )
    >>> [item["name"] for item in results]
    ['django']
    """
    results: list[dict[str, t.Any]] = []
    field_order = DEFAULT_FIELDS

    for repo in repos:
        name = str(repo.get("name", ""))
        path_value = PrivatePath(pathlib.Path(repo.get("path", "")))
        url = str(repo.get("url", repo.get("pip_url", "")) or "")
        workspace_raw = repo.get("workspace_root")
        if workspace_raw:
            workspace_path = pathlib.Path(str(workspace_raw)).expanduser()
        else:
            workspace_path = pathlib.Path(repo.get("path", ""))
            if workspace_path:
                workspace_path = workspace_path.expanduser().parent
        workspace = str(PrivatePath(workspace_path)) if workspace_path else ""

        field_values = {
            "name": name,
            "path": str(path_value),
            "url": url,
            "workspace": workspace,
        }

        matched, matches_by_field = evaluate_match(
            field_values,
            patterns,
            match_any=match_any,
        )

        if invert_match:
            matched = not matched
            if matched:
                matches_by_field = {}

        if not matched:
            continue

        matched_fields = [field for field in field_order if field in matches_by_field]

        results.append(
            {
                "name": name,
                "path": str(path_value),
                "url": url,
                "workspace_root": workspace,
                "matched_fields": matched_fields,
                "matches": matches_by_field,
            },
        )

    return results


def create_search_subparser(parser: argparse.ArgumentParser) -> None:
    """Create ``vcspull search`` argument subparser.

    Parameters
    ----------
    parser : argparse.ArgumentParser
        The parser to configure

    Examples
    --------
    >>> import argparse
    >>> parser = argparse.ArgumentParser()
    >>> create_search_subparser(parser)
    >>> parsed = parser.parse_args(["django"])
    >>> parsed.query_terms
    ['django']
    """
    parser.add_argument(
        "query_terms",
        metavar="query",
        nargs="*",
        help=(
            "search query terms (regex by default). Use field prefixes like "
            "name:, path:, url:, workspace:."
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
        dest="workspace_root",
        metavar="DIR",
        help="filter by workspace root directory",
    )
    parser.add_argument(
        "--field",
        dest="fields",
        action="append",
        metavar="NAME",
        help=(
            "limit unscoped queries to specific fields "
            "(name, path, url, workspace). Repeatable or comma-separated."
        ),
    )
    parser.add_argument(
        "-i",
        "--ignore-case",
        action="store_true",
        help="case-insensitive matching",
    )
    parser.add_argument(
        "-S",
        "--smart-case",
        action="store_true",
        help="smart case matching (ignore case unless pattern has capitals)",
    )
    parser.add_argument(
        "-F",
        "--fixed-strings",
        action="store_true",
        help="treat search terms as literal strings",
    )
    parser.add_argument(
        "--word-regexp",
        action="store_true",
        help="match only whole words",
    )
    parser.add_argument(
        "-v",
        "--invert-match",
        action="store_true",
        help="show non-matching repositories",
    )
    parser.add_argument(
        "--any",
        dest="match_any",
        action="store_true",
        help="match if any term matches (default: all terms)",
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
        "--include-worktrees",
        action="store_true",
        dest="include_worktrees",
        help="include configured worktrees in search results",
    )


def search_repos(
    query_terms: list[str],
    config_path: pathlib.Path | None,
    workspace_root: str | None,
    output_json: bool,
    output_ndjson: bool,
    color: str,
    *,
    fields: list[str] | None,
    ignore_case: bool,
    smart_case: bool,
    fixed_strings: bool,
    word_regexp: bool,
    invert_match: bool,
    match_any: bool,
    emit_output: bool = True,
) -> list[dict[str, t.Any]]:
    """Search configured repositories.

    Parameters
    ----------
    query_terms : list[str]
        Search query terms
    config_path : pathlib.Path | None
        Path to config file, or None to auto-discover
    workspace_root : str | None
        Filter by workspace root
    output_json : bool
        Output as JSON
    output_ndjson : bool
        Output as NDJSON
    color : str
        Color mode (auto, always, never)
    fields : list[str] | None
        Field list for unscoped queries
    ignore_case : bool
        Force case-insensitive matching
    smart_case : bool
        Enable smart-case matching
    fixed_strings : bool
        Treat terms as literal strings
    word_regexp : bool
        Match whole words only
    invert_match : bool
        Return non-matching repositories
    match_any : bool
        Match if any term matches
    emit_output : bool
        Whether to emit human/JSON output

    Returns
    -------
    list[dict[str, t.Any]]
        Search results

    Examples
    --------
    >>> from vcspull.config import save_config_yaml
    >>> config_file = tmp_path / ".vcspull.yaml"
    >>> save_config_yaml(
    ...     config_file,
    ...     {"~/code/": {"django": {"repo": "git+https://github.com/django/django.git"}}},
    ... )
    >>> results = search_repos(
    ...     ["django"],
    ...     config_path=config_file,
    ...     workspace_root=None,
    ...     output_json=False,
    ...     output_ndjson=False,
    ...     color="never",
    ...     fields=None,
    ...     ignore_case=False,
    ...     smart_case=False,
    ...     fixed_strings=False,
    ...     word_regexp=False,
    ...     invert_match=False,
    ...     match_any=False,
    ...     emit_output=False,
    ... )
    >>> [item["name"] for item in results]
    ['django']
    """
    if config_path:
        configs = load_configs([config_path])
    else:
        configs = load_configs(find_config_files(include_home=True))

    if workspace_root:
        configs = filter_by_workspace(configs, workspace_root)

    try:
        normalized_fields = normalize_fields(fields)
        tokens = parse_query_terms(query_terms, default_fields=normalized_fields)
        patterns = compile_search_patterns(
            tokens,
            ignore_case=ignore_case,
            smart_case=smart_case,
            fixed_strings=fixed_strings,
            word_regexp=word_regexp,
        )
    except ValueError:
        log.exception("Search query parsing failed")
        return []

    results = find_search_matches(
        configs,
        patterns,
        match_any=match_any,
        invert_match=invert_match,
    )

    if not emit_output:
        return results

    output_mode = get_output_mode(output_json, output_ndjson)
    formatter = OutputFormatter(output_mode)
    colors = Colors(get_color_mode(color))

    if not results:
        formatter.emit_text(colors.warning("No repositories found."))
        formatter.finalize()
        return results

    patterns_by_field: dict[str, list[re.Pattern[str]]] = {
        field: [] for field in DEFAULT_FIELDS
    }
    for pattern in patterns:
        for field in pattern.fields:
            patterns_by_field.setdefault(field, []).append(pattern.regex)

    for result in results:
        formatter.emit(
            {
                "name": result["name"],
                "url": result["url"],
                "path": result["path"],
                "workspace_root": result["workspace_root"],
                "matched_fields": result["matched_fields"],
            },
        )

        name_display = highlight_text(
            result["name"],
            patterns_by_field.get("name", []),
            colors=colors,
            base_color=colors.INFO,
        )
        path_display = highlight_text(
            result["path"],
            patterns_by_field.get("path", []),
            colors=colors,
        )
        formatter.emit_text(
            f"{colors.muted('•')} {name_display} {colors.muted('→')} {path_display}",
        )

        matched_fields = set(result.get("matched_fields", []))
        if "url" in matched_fields:
            url_display = highlight_text(
                result["url"],
                patterns_by_field.get("url", []),
                colors=colors,
            )
            formatter.emit_text(f"  {colors.muted('url:')} {url_display}")
        if "workspace" in matched_fields:
            workspace_display = highlight_text(
                result["workspace_root"],
                patterns_by_field.get("workspace", []),
                colors=colors,
            )
            formatter.emit_text(
                f"  {colors.muted('workspace:')} {workspace_display}",
            )

    formatter.finalize()
    return results
