"""Tests for vcspull search command."""

from __future__ import annotations

import json
import typing as t

import pytest

from vcspull.cli.search import search_repos
from vcspull.config import save_config_yaml

if t.TYPE_CHECKING:
    import pathlib

    from _pytest.monkeypatch import MonkeyPatch


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
    tmp_path: pathlib.Path,
    monkeypatch: MonkeyPatch,
) -> None:
    """Test searching repositories."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)

    config_file = tmp_path / ".vcspull.yaml"
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
    tmp_path: pathlib.Path,
    monkeypatch: MonkeyPatch,
    capsys: t.Any,
) -> None:
    """Test JSON output for search command."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)

    config_file = tmp_path / ".vcspull.yaml"
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
    tmp_path: pathlib.Path,
    monkeypatch: MonkeyPatch,
    capsys: t.Any,
) -> None:
    """Test NDJSON output for search command."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)

    config_file = tmp_path / ".vcspull.yaml"
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
    tmp_path: pathlib.Path,
    monkeypatch: MonkeyPatch,
    capsys: t.Any,
) -> None:
    """Test search output when no repositories match."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)

    config_file = tmp_path / ".vcspull.yaml"
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
