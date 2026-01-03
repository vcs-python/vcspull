"""Tests for vcspull search command."""

from __future__ import annotations

import json
import re
import typing as t

import pytest

from vcspull.cli._colors import ColorMode, Colors
from vcspull.cli.search import (
    compile_search_patterns,
    highlight_text,
    normalize_fields,
    parse_query_terms,
    search_repos,
)
from vcspull.config import save_config_yaml

if t.TYPE_CHECKING:
    import pathlib


def create_test_config(config_path: pathlib.Path, repos: dict[str, t.Any]) -> None:
    """Create a test config file."""
    save_config_yaml(config_path, repos)


class SearchReposFixture(t.NamedTuple):
    """Fixture for search repos test cases."""

    test_id: str
    query_terms: list[str]
    fields: list[str] | None
    ignore_case: bool
    smart_case: bool
    fixed_strings: bool
    word_regexp: bool
    invert_match: bool
    match_any: bool
    workspace_filter: str | None
    expected_repo_names: list[str]


SEARCH_REPOS_FIXTURES: list[SearchReposFixture] = [
    SearchReposFixture(
        test_id="search-basic-regex",
        query_terms=["django"],
        fields=None,
        ignore_case=False,
        smart_case=False,
        fixed_strings=False,
        word_regexp=False,
        invert_match=False,
        match_any=False,
        workspace_filter=None,
        expected_repo_names=["django"],
    ),
    SearchReposFixture(
        test_id="search-field-url",
        query_terms=["url:pallets"],
        fields=None,
        ignore_case=False,
        smart_case=False,
        fixed_strings=False,
        word_regexp=False,
        invert_match=False,
        match_any=False,
        workspace_filter=None,
        expected_repo_names=["flask"],
    ),
    SearchReposFixture(
        test_id="search-ignore-case",
        query_terms=["name:FLASK"],
        fields=None,
        ignore_case=True,
        smart_case=False,
        fixed_strings=False,
        word_regexp=False,
        invert_match=False,
        match_any=False,
        workspace_filter=None,
        expected_repo_names=["flask"],
    ),
    SearchReposFixture(
        test_id="search-any-term",
        query_terms=["name:django", "url:pallets"],
        fields=None,
        ignore_case=False,
        smart_case=False,
        fixed_strings=False,
        word_regexp=False,
        invert_match=False,
        match_any=True,
        workspace_filter=None,
        expected_repo_names=["django", "flask"],
    ),
    SearchReposFixture(
        test_id="search-invert-match",
        query_terms=["flask"],
        fields=None,
        ignore_case=False,
        smart_case=False,
        fixed_strings=False,
        word_regexp=False,
        invert_match=True,
        match_any=False,
        workspace_filter=None,
        expected_repo_names=["django", "internal-api"],
    ),
    SearchReposFixture(
        test_id="search-workspace-filter",
        query_terms=["internal"],
        fields=None,
        ignore_case=False,
        smart_case=False,
        fixed_strings=False,
        word_regexp=False,
        invert_match=False,
        match_any=False,
        workspace_filter="~/work/",
        expected_repo_names=["internal-api"],
    ),
]


@pytest.mark.parametrize(
    list(SearchReposFixture._fields),
    SEARCH_REPOS_FIXTURES,
    ids=[fixture.test_id for fixture in SEARCH_REPOS_FIXTURES],
)
def test_search_repos(
    test_id: str,
    query_terms: list[str],
    fields: list[str] | None,
    ignore_case: bool,
    smart_case: bool,
    fixed_strings: bool,
    word_regexp: bool,
    invert_match: bool,
    match_any: bool,
    workspace_filter: str | None,
    expected_repo_names: list[str],
    user_path: pathlib.Path,
) -> None:
    """Test searching repositories."""
    config_file = user_path / ".vcspull.yaml"
    config_data = {
        "~/code/": {
            "flask": {"repo": "git+https://github.com/pallets/flask.git"},
            "django": {"repo": "git+https://github.com/django/django.git"},
        },
        "~/work/": {
            "internal-api": {"repo": "git+ssh://git.example.com/internal-api.git"},
        },
    }
    create_test_config(config_file, config_data)

    results = search_repos(
        query_terms=query_terms,
        config_path=config_file,
        workspace_root=workspace_filter,
        output_json=False,
        output_ndjson=False,
        color="never",
        fields=fields,
        ignore_case=ignore_case,
        smart_case=smart_case,
        fixed_strings=fixed_strings,
        word_regexp=word_regexp,
        invert_match=invert_match,
        match_any=match_any,
        emit_output=False,
    )

    repo_names = {item["name"] for item in results}
    assert repo_names == set(expected_repo_names)


def test_search_repos_json_output(
    user_path: pathlib.Path,
    capsys: t.Any,
) -> None:
    """Test JSON output for search command."""
    config_file = user_path / ".vcspull.yaml"
    config_data = {
        "~/code/": {
            "django": {"repo": "git+https://github.com/django/django.git"},
        },
    }
    create_test_config(config_file, config_data)

    search_repos(
        query_terms=["django"],
        config_path=config_file,
        workspace_root=None,
        output_json=True,
        output_ndjson=False,
        color="never",
        fields=None,
        ignore_case=False,
        smart_case=False,
        fixed_strings=False,
        word_regexp=False,
        invert_match=False,
        match_any=False,
    )

    captured = capsys.readouterr()
    output_data = json.loads(captured.out)
    assert isinstance(output_data, list)
    assert output_data[0]["name"] == "django"
    assert "matched_fields" in output_data[0]


def test_search_repos_ndjson_output(
    user_path: pathlib.Path,
    capsys: t.Any,
) -> None:
    """Test NDJSON output for search command."""
    config_file = user_path / ".vcspull.yaml"
    config_data = {
        "~/code/": {
            "django": {"repo": "git+https://github.com/django/django.git"},
        },
    }
    create_test_config(config_file, config_data)

    search_repos(
        query_terms=["django"],
        config_path=config_file,
        workspace_root=None,
        output_json=False,
        output_ndjson=True,
        color="never",
        fields=None,
        ignore_case=False,
        smart_case=False,
        fixed_strings=False,
        word_regexp=False,
        invert_match=False,
        match_any=False,
    )

    captured = capsys.readouterr()
    lines = [line for line in captured.out.strip().split("\n") if line]
    assert lines, "Expected NDJSON output"
    item = json.loads(lines[0])
    assert item["name"] == "django"
    assert "matched_fields" in item


def test_search_repos_no_matches(
    user_path: pathlib.Path,
    capsys: t.Any,
) -> None:
    """Test search output when no repositories match."""
    config_file = user_path / ".vcspull.yaml"
    config_data = {
        "~/code/": {
            "django": {"repo": "git+https://github.com/django/django.git"},
        },
    }
    create_test_config(config_file, config_data)

    search_repos(
        query_terms=["nonexistent"],
        config_path=config_file,
        workspace_root=None,
        output_json=False,
        output_ndjson=False,
        color="never",
        fields=None,
        ignore_case=False,
        smart_case=False,
        fixed_strings=False,
        word_regexp=False,
        invert_match=False,
        match_any=False,
    )

    captured = capsys.readouterr()
    assert "No repositories found" in captured.out


# Unit tests for normalize_fields


class NormalizeFieldsFixture(t.NamedTuple):
    """Fixture for normalize_fields test cases."""

    test_id: str
    fields: list[str] | None
    expected: tuple[str, ...]
    raises: type[Exception] | None


NORMALIZE_FIELDS_FIXTURES: list[NormalizeFieldsFixture] = [
    NormalizeFieldsFixture(
        test_id="none-returns-defaults",
        fields=None,
        expected=("name", "path", "url", "workspace"),
        raises=None,
    ),
    NormalizeFieldsFixture(
        test_id="empty-list-returns-defaults",
        fields=[],
        expected=("name", "path", "url", "workspace"),
        raises=None,
    ),
    NormalizeFieldsFixture(
        test_id="comma-separated-fields",
        fields=["name,url"],
        expected=("name", "url"),
        raises=None,
    ),
    NormalizeFieldsFixture(
        test_id="mixed-comma-and-separate",
        fields=["name,url", "workspace"],
        expected=("name", "url", "workspace"),
        raises=None,
    ),
    NormalizeFieldsFixture(
        test_id="alias-root-to-workspace",
        fields=["root"],
        expected=("workspace",),
        raises=None,
    ),
    NormalizeFieldsFixture(
        test_id="alias-ws-to-workspace",
        fields=["ws"],
        expected=("workspace",),
        raises=None,
    ),
    NormalizeFieldsFixture(
        test_id="duplicates-removed",
        fields=["name", "name", "url"],
        expected=("name", "url"),
        raises=None,
    ),
    NormalizeFieldsFixture(
        test_id="empty-string-entry-skipped",
        fields=["", "name"],
        expected=("name",),
        raises=None,
    ),
    NormalizeFieldsFixture(
        test_id="whitespace-trimmed",
        fields=["  name  ", "  url  "],
        expected=("name", "url"),
        raises=None,
    ),
    NormalizeFieldsFixture(
        test_id="invalid-field-raises",
        fields=["invalid_field"],
        expected=(),
        raises=ValueError,
    ),
]


@pytest.mark.parametrize(
    list(NormalizeFieldsFixture._fields),
    NORMALIZE_FIELDS_FIXTURES,
    ids=[fixture.test_id for fixture in NORMALIZE_FIELDS_FIXTURES],
)
def test_normalize_fields(
    test_id: str,
    fields: list[str] | None,
    expected: tuple[str, ...],
    raises: type[Exception] | None,
) -> None:
    """Test normalize_fields function."""
    if raises:
        with pytest.raises(raises):
            normalize_fields(fields)
    else:
        result = normalize_fields(fields)
        assert result == expected


# Unit tests for parse_query_terms


class ParseQueryTermsFixture(t.NamedTuple):
    """Fixture for parse_query_terms test cases."""

    test_id: str
    terms: list[str]
    expected_patterns: list[str]
    raises: type[Exception] | None


PARSE_QUERY_TERMS_FIXTURES: list[ParseQueryTermsFixture] = [
    ParseQueryTermsFixture(
        test_id="simple-term",
        terms=["django"],
        expected_patterns=["django"],
        raises=None,
    ),
    ParseQueryTermsFixture(
        test_id="field-prefixed-term",
        terms=["name:django"],
        expected_patterns=["django"],
        raises=None,
    ),
    ParseQueryTermsFixture(
        test_id="empty-after-prefix-raises",
        terms=["name:"],
        expected_patterns=[],
        raises=ValueError,
    ),
    ParseQueryTermsFixture(
        test_id="unknown-prefix-treated-as-pattern",
        terms=["unknownfield:value"],
        expected_patterns=["unknownfield:value"],
        raises=None,
    ),
]


@pytest.mark.parametrize(
    list(ParseQueryTermsFixture._fields),
    PARSE_QUERY_TERMS_FIXTURES,
    ids=[fixture.test_id for fixture in PARSE_QUERY_TERMS_FIXTURES],
)
def test_parse_query_terms(
    test_id: str,
    terms: list[str],
    expected_patterns: list[str],
    raises: type[Exception] | None,
) -> None:
    """Test parse_query_terms function."""
    if raises:
        with pytest.raises(raises):
            parse_query_terms(terms, default_fields=("name", "url"))
    else:
        result = parse_query_terms(terms, default_fields=("name", "url"))
        assert [token.pattern for token in result] == expected_patterns


# Unit tests for compile_search_patterns


class CompileSearchPatternsFixture(t.NamedTuple):
    """Fixture for compile_search_patterns test cases."""

    test_id: str
    terms: list[str]
    ignore_case: bool
    smart_case: bool
    fixed_strings: bool
    word_regexp: bool
    test_text: str
    should_match: bool
    raises: type[Exception] | None


COMPILE_SEARCH_PATTERNS_FIXTURES: list[CompileSearchPatternsFixture] = [
    CompileSearchPatternsFixture(
        test_id="smart-case-lowercase-ignores-case",
        terms=["django"],
        ignore_case=False,
        smart_case=True,
        fixed_strings=False,
        word_regexp=False,
        test_text="Django",
        should_match=True,
        raises=None,
    ),
    CompileSearchPatternsFixture(
        test_id="smart-case-uppercase-is-case-sensitive",
        terms=["Django"],
        ignore_case=False,
        smart_case=True,
        fixed_strings=False,
        word_regexp=False,
        test_text="django",
        should_match=False,
        raises=None,
    ),
    CompileSearchPatternsFixture(
        test_id="word-regexp-matches-whole-word",
        terms=["test"],
        ignore_case=False,
        smart_case=False,
        fixed_strings=False,
        word_regexp=True,
        test_text="test",
        should_match=True,
        raises=None,
    ),
    CompileSearchPatternsFixture(
        test_id="word-regexp-no-partial-match",
        terms=["test"],
        ignore_case=False,
        smart_case=False,
        fixed_strings=False,
        word_regexp=True,
        test_text="testing",
        should_match=False,
        raises=None,
    ),
    CompileSearchPatternsFixture(
        test_id="fixed-strings-escapes-regex",
        terms=["a.b"],
        ignore_case=False,
        smart_case=False,
        fixed_strings=True,
        word_regexp=False,
        test_text="a.b",
        should_match=True,
        raises=None,
    ),
    CompileSearchPatternsFixture(
        test_id="fixed-strings-no-regex-match",
        terms=["a.b"],
        ignore_case=False,
        smart_case=False,
        fixed_strings=True,
        word_regexp=False,
        test_text="aXb",
        should_match=False,
        raises=None,
    ),
    CompileSearchPatternsFixture(
        test_id="invalid-regex-raises",
        terms=["[invalid"],
        ignore_case=False,
        smart_case=False,
        fixed_strings=False,
        word_regexp=False,
        test_text="",
        should_match=False,
        raises=ValueError,
    ),
]


@pytest.mark.parametrize(
    list(CompileSearchPatternsFixture._fields),
    COMPILE_SEARCH_PATTERNS_FIXTURES,
    ids=[fixture.test_id for fixture in COMPILE_SEARCH_PATTERNS_FIXTURES],
)
def test_compile_search_patterns(
    test_id: str,
    terms: list[str],
    ignore_case: bool,
    smart_case: bool,
    fixed_strings: bool,
    word_regexp: bool,
    test_text: str,
    should_match: bool,
    raises: type[Exception] | None,
) -> None:
    """Test compile_search_patterns function."""
    tokens = parse_query_terms(terms, default_fields=("name",))
    if raises:
        with pytest.raises(raises):
            compile_search_patterns(
                tokens,
                ignore_case=ignore_case,
                smart_case=smart_case,
                fixed_strings=fixed_strings,
                word_regexp=word_regexp,
            )
    else:
        patterns = compile_search_patterns(
            tokens,
            ignore_case=ignore_case,
            smart_case=smart_case,
            fixed_strings=fixed_strings,
            word_regexp=word_regexp,
        )
        assert len(patterns) == 1
        match = patterns[0].regex.search(test_text)
        assert (match is not None) == should_match


def test_compile_search_patterns_empty_tokens() -> None:
    """Test compile_search_patterns with empty token list."""
    patterns = compile_search_patterns(
        [],
        ignore_case=False,
        smart_case=False,
        fixed_strings=False,
        word_regexp=False,
    )
    assert patterns == []


# Unit tests for highlight_text


def test_highlight_text_no_patterns() -> None:
    """Test highlight_text with no patterns returns original text."""
    colors = Colors(ColorMode.NEVER)
    result = highlight_text("django", [], colors=colors)
    assert result == "django"


def test_highlight_text_no_patterns_with_base_color() -> None:
    """Test highlight_text with base_color but no patterns."""
    colors = Colors(ColorMode.ALWAYS)
    result = highlight_text("django", [], colors=colors, base_color=colors.INFO)
    assert "django" in result


def test_highlight_text_with_color_enabled() -> None:
    """Test highlight_text with colors enabled."""
    colors = Colors(ColorMode.ALWAYS)
    pattern = re.compile("jan", re.IGNORECASE)
    result = highlight_text("django", [pattern], colors=colors)
    # Should contain ANSI codes for highlighting
    assert colors.HIGHLIGHT in result or "jan" in result


def test_highlight_text_with_base_color_and_pattern() -> None:
    """Test highlight_text with both base_color and pattern."""
    colors = Colors(ColorMode.ALWAYS)
    pattern = re.compile("jan", re.IGNORECASE)
    result = highlight_text("django", [pattern], colors=colors, base_color=colors.INFO)
    assert "jan" in result


# Tests for search_repos with matched fields output


def test_search_repos_url_field_matched(
    user_path: pathlib.Path,
    capsys: t.Any,
) -> None:
    """Test search output when URL field is matched."""
    config_file = user_path / ".vcspull.yaml"
    config_data = {
        "~/code/": {
            "django": {"repo": "git+https://github.com/django/django.git"},
        },
    }
    create_test_config(config_file, config_data)

    search_repos(
        query_terms=["url:github"],
        config_path=config_file,
        workspace_root=None,
        output_json=False,
        output_ndjson=False,
        color="never",
        fields=None,
        ignore_case=False,
        smart_case=False,
        fixed_strings=False,
        word_regexp=False,
        invert_match=False,
        match_any=False,
    )

    captured = capsys.readouterr()
    assert "url:" in captured.out
    assert "github" in captured.out


def test_search_repos_workspace_field_matched(
    user_path: pathlib.Path,
    capsys: t.Any,
) -> None:
    """Test search output when workspace field is matched."""
    config_file = user_path / ".vcspull.yaml"
    config_data = {
        "~/code/": {
            "django": {"repo": "git+https://github.com/django/django.git"},
        },
    }
    create_test_config(config_file, config_data)

    search_repos(
        query_terms=["workspace:code"],
        config_path=config_file,
        workspace_root=None,
        output_json=False,
        output_ndjson=False,
        color="never",
        fields=None,
        ignore_case=False,
        smart_case=False,
        fixed_strings=False,
        word_regexp=False,
        invert_match=False,
        match_any=False,
    )

    captured = capsys.readouterr()
    assert "workspace:" in captured.out
    assert "code" in captured.out


def test_search_repos_invalid_field_error(
    user_path: pathlib.Path,
) -> None:
    """Test search_repos handles invalid field gracefully."""
    config_file = user_path / ".vcspull.yaml"
    config_data = {
        "~/code/": {
            "django": {"repo": "git+https://github.com/django/django.git"},
        },
    }
    create_test_config(config_file, config_data)

    # Invalid field should trigger ValueError which is caught and logged
    results = search_repos(
        query_terms=["django"],
        config_path=config_file,
        workspace_root=None,
        output_json=False,
        output_ndjson=False,
        color="never",
        fields=["invalid_field"],
        ignore_case=False,
        smart_case=False,
        fixed_strings=False,
        word_regexp=False,
        invert_match=False,
        match_any=False,
        emit_output=False,
    )
    assert results == []


def test_search_repos_invalid_regex_error(
    user_path: pathlib.Path,
) -> None:
    """Test search_repos handles invalid regex gracefully."""
    config_file = user_path / ".vcspull.yaml"
    config_data = {
        "~/code/": {
            "django": {"repo": "git+https://github.com/django/django.git"},
        },
    }
    create_test_config(config_file, config_data)

    # Invalid regex should trigger ValueError which is caught and logged
    results = search_repos(
        query_terms=["[invalid"],
        config_path=config_file,
        workspace_root=None,
        output_json=False,
        output_ndjson=False,
        color="never",
        fields=None,
        ignore_case=False,
        smart_case=False,
        fixed_strings=False,
        word_regexp=False,
        invert_match=False,
        match_any=False,
        emit_output=False,
    )
    assert results == []


def test_search_repos_auto_discover_config(
    user_path: pathlib.Path,
) -> None:
    """Test search_repos with config_path=None to trigger auto-discovery."""
    config_file = user_path / ".vcspull.yaml"
    config_data = {
        "~/code/": {
            "django": {"repo": "git+https://github.com/django/django.git"},
        },
    }
    create_test_config(config_file, config_data)

    # config_path=None triggers find_config_files auto-discovery
    results = search_repos(
        query_terms=["django"],
        config_path=None,
        workspace_root=None,
        output_json=False,
        output_ndjson=False,
        color="never",
        fields=None,
        ignore_case=False,
        smart_case=False,
        fixed_strings=False,
        word_regexp=False,
        invert_match=False,
        match_any=False,
        emit_output=False,
    )
    assert len(results) == 1
    assert results[0]["name"] == "django"


def test_normalize_fields_empty_after_comma() -> None:
    """Test normalize_fields with empty string after comma."""
    result = normalize_fields(["name,", ",url"])
    assert result == ("name", "url")
