"""Tests for vcspull._internal.config_style."""

from __future__ import annotations

import typing as t

import pytest

from vcspull._internal.config_style import (
    _extract_url,
    _has_extra_keys,
    _infer_vcs_from_url,
    _read_git_remotes,
    _strip_vcs_prefix,
    apply_config_style,
    format_repo_entry,
    restyle_repo_entry,
)
from vcspull.types import ConfigStyle, RawRepoEntry

if t.TYPE_CHECKING:
    from syrupy.assertion import SnapshotAssertion


# ---------------------------------------------------------------------------
# _infer_vcs_from_url
# ---------------------------------------------------------------------------


class InferVcsFixture(t.NamedTuple):
    """Fixture for VCS inference from URL prefix."""

    test_id: str
    url: str
    expected: str | None


INFER_VCS_FIXTURES: list[InferVcsFixture] = [
    InferVcsFixture("git-https", "git+https://github.com/u/r.git", "git"),
    InferVcsFixture("git-ssh", "git+ssh://git@github.com/u/r.git", "git"),
    InferVcsFixture("hg-https", "hg+https://hg.example.com/repo", "hg"),
    InferVcsFixture("svn-https", "svn+https://svn.example.com/repo", "svn"),
    InferVcsFixture("no-prefix-https", "https://github.com/u/r.git", None),
    InferVcsFixture("no-prefix-ssh", "git@github.com:u/r.git", None),
    InferVcsFixture("empty", "", None),
]


@pytest.mark.parametrize(
    list(InferVcsFixture._fields),
    INFER_VCS_FIXTURES,
    ids=[f.test_id for f in INFER_VCS_FIXTURES],
)
def test_infer_vcs_from_url(test_id: str, url: str, expected: str | None) -> None:
    """VCS type should be correctly inferred from URL prefix."""
    del test_id
    assert _infer_vcs_from_url(url) == expected


# ---------------------------------------------------------------------------
# _strip_vcs_prefix
# ---------------------------------------------------------------------------


class StripPrefixFixture(t.NamedTuple):
    """Fixture for VCS prefix stripping."""

    test_id: str
    url: str
    expected: str


STRIP_PREFIX_FIXTURES: list[StripPrefixFixture] = [
    StripPrefixFixture(
        "git-prefix", "git+https://github.com/u/r.git", "https://github.com/u/r.git"
    ),
    StripPrefixFixture(
        "hg-prefix", "hg+https://hg.example.com/repo", "https://hg.example.com/repo"
    ),
    StripPrefixFixture(
        "no-prefix", "https://github.com/u/r.git", "https://github.com/u/r.git"
    ),
]


@pytest.mark.parametrize(
    list(StripPrefixFixture._fields),
    STRIP_PREFIX_FIXTURES,
    ids=[f.test_id for f in STRIP_PREFIX_FIXTURES],
)
def test_strip_vcs_prefix(test_id: str, url: str, expected: str) -> None:
    """VCS prefix should be stripped correctly."""
    del test_id
    assert _strip_vcs_prefix(url) == expected


# ---------------------------------------------------------------------------
# _extract_url / _has_extra_keys
# ---------------------------------------------------------------------------


def test_extract_url_from_string() -> None:
    """URL extraction from a string entry returns the string itself."""
    assert (
        _extract_url("git+https://github.com/u/r.git")
        == "git+https://github.com/u/r.git"
    )


def test_extract_url_from_repo_dict() -> None:
    """URL extraction from a dict entry with 'repo' key."""
    assert (
        _extract_url({"repo": "git+https://github.com/u/r.git"})
        == "git+https://github.com/u/r.git"
    )


def test_extract_url_from_url_dict() -> None:
    """URL extraction from a dict entry with 'url' key."""
    assert (
        _extract_url({"url": "git+https://github.com/u/r.git"})
        == "git+https://github.com/u/r.git"
    )


def test_has_extra_keys_string() -> None:
    """String entries never have extra keys."""
    assert _has_extra_keys("git+https://github.com/u/r.git") is False


def test_has_extra_keys_standard() -> None:
    """Standard dict entry with only 'repo' has no extra keys."""
    assert _has_extra_keys({"repo": "url"}) is False


def test_has_extra_keys_with_remotes() -> None:
    """Dict entry with remotes has extra keys."""
    assert _has_extra_keys({"repo": "url", "remotes": {"origin": "url"}}) is True


def test_has_extra_keys_with_shell_command() -> None:
    """Dict entry with shell_command_after has extra keys."""
    assert _has_extra_keys({"repo": "url", "shell_command_after": "make"}) is True


# ---------------------------------------------------------------------------
# _read_git_remotes
# ---------------------------------------------------------------------------


def test_read_git_remotes_nonexistent_path() -> None:
    """Reading remotes from a non-existent path returns None."""
    import pathlib

    assert _read_git_remotes(pathlib.Path("/nonexistent/path/unlikely")) is None


# ---------------------------------------------------------------------------
# format_repo_entry
# ---------------------------------------------------------------------------


class FormatRepoEntryFixture(t.NamedTuple):
    """Fixture for format_repo_entry."""

    test_id: str
    url: str
    style: ConfigStyle
    expected: RawRepoEntry


FORMAT_REPO_ENTRY_FIXTURES: list[FormatRepoEntryFixture] = [
    FormatRepoEntryFixture(
        "concise-git-https",
        "git+https://github.com/u/r.git",
        ConfigStyle.CONCISE,
        "git+https://github.com/u/r.git",
    ),
    FormatRepoEntryFixture(
        "standard-git-https",
        "git+https://github.com/u/r.git",
        ConfigStyle.STANDARD,
        {"repo": "git+https://github.com/u/r.git"},
    ),
    FormatRepoEntryFixture(
        "verbose-git-https",
        "git+https://github.com/u/r.git",
        ConfigStyle.VERBOSE,
        {
            "repo": "git+https://github.com/u/r.git",
            "vcs": "git",
            "remotes": {"origin": "https://github.com/u/r.git"},
        },
    ),
    FormatRepoEntryFixture(
        "verbose-hg",
        "hg+https://hg.example.com/repo",
        ConfigStyle.VERBOSE,
        {
            "repo": "hg+https://hg.example.com/repo",
            "vcs": "hg",
            "remotes": {"origin": "https://hg.example.com/repo"},
        },
    ),
    FormatRepoEntryFixture(
        "verbose-svn",
        "svn+https://svn.example.com/repo",
        ConfigStyle.VERBOSE,
        {
            "repo": "svn+https://svn.example.com/repo",
            "vcs": "svn",
            "remotes": {"origin": "https://svn.example.com/repo"},
        },
    ),
    FormatRepoEntryFixture(
        "concise-ssh",
        "git@github.com:u/r.git",
        ConfigStyle.CONCISE,
        "git@github.com:u/r.git",
    ),
    FormatRepoEntryFixture(
        "standard-ssh",
        "git@github.com:u/r.git",
        ConfigStyle.STANDARD,
        {"repo": "git@github.com:u/r.git"},
    ),
    FormatRepoEntryFixture(
        "verbose-no-vcs-prefix",
        "https://github.com/u/r.git",
        ConfigStyle.VERBOSE,
        {
            "repo": "https://github.com/u/r.git",
            "remotes": {"origin": "https://github.com/u/r.git"},
        },
    ),
]


@pytest.mark.parametrize(
    list(FormatRepoEntryFixture._fields),
    FORMAT_REPO_ENTRY_FIXTURES,
    ids=[f.test_id for f in FORMAT_REPO_ENTRY_FIXTURES],
)
def test_format_repo_entry(
    test_id: str,
    url: str,
    style: ConfigStyle,
    expected: RawRepoEntry,
) -> None:
    """format_repo_entry should produce the correct entry for each style."""
    del test_id
    result = format_repo_entry(url, style=style)
    assert result == expected


# ---------------------------------------------------------------------------
# restyle_repo_entry
# ---------------------------------------------------------------------------


class RestyleRepoEntryFixture(t.NamedTuple):
    """Fixture for restyle_repo_entry."""

    test_id: str
    repo_data: RawRepoEntry
    style: ConfigStyle
    expected_entry: RawRepoEntry
    expect_warnings: bool


RESTYLE_FIXTURES: list[RestyleRepoEntryFixture] = [
    RestyleRepoEntryFixture(
        "concise-to-standard",
        "git+https://github.com/u/r.git",
        ConfigStyle.STANDARD,
        {"repo": "git+https://github.com/u/r.git"},
        False,
    ),
    RestyleRepoEntryFixture(
        "standard-to-concise",
        {"repo": "git+https://github.com/u/r.git"},
        ConfigStyle.CONCISE,
        "git+https://github.com/u/r.git",
        False,
    ),
    RestyleRepoEntryFixture(
        "standard-to-verbose",
        {"repo": "git+https://github.com/u/r.git"},
        ConfigStyle.VERBOSE,
        {
            "repo": "git+https://github.com/u/r.git",
            "vcs": "git",
            "remotes": {"origin": "https://github.com/u/r.git"},
        },
        False,
    ),
    RestyleRepoEntryFixture(
        "verbose-to-concise-with-extras-warns",
        {
            "repo": "git+https://github.com/u/r.git",
            "remotes": {"origin": "https://github.com/u/r.git"},
            "shell_command_after": "make install",
        },
        ConfigStyle.CONCISE,
        {
            "repo": "git+https://github.com/u/r.git",
            "remotes": {"origin": "https://github.com/u/r.git"},
            "shell_command_after": "make install",
        },
        True,
    ),
    RestyleRepoEntryFixture(
        "verbose-to-standard-preserves-extras",
        {
            "repo": "git+https://github.com/u/r.git",
            "remotes": {"origin": "url"},
            "shell_command_after": "make",
        },
        ConfigStyle.STANDARD,
        {
            "repo": "git+https://github.com/u/r.git",
            "remotes": {"origin": "url"},
            "shell_command_after": "make",
        },
        False,
    ),
    RestyleRepoEntryFixture(
        "concise-to-verbose",
        "git+https://github.com/u/r.git",
        ConfigStyle.VERBOSE,
        {
            "repo": "git+https://github.com/u/r.git",
            "vcs": "git",
            "remotes": {"origin": "https://github.com/u/r.git"},
        },
        False,
    ),
    RestyleRepoEntryFixture(
        "url-key-to-standard",
        {"url": "git+https://github.com/u/r.git"},
        ConfigStyle.STANDARD,
        {"repo": "git+https://github.com/u/r.git"},
        False,
    ),
]


@pytest.mark.parametrize(
    list(RestyleRepoEntryFixture._fields),
    RESTYLE_FIXTURES,
    ids=[f.test_id for f in RESTYLE_FIXTURES],
)
def test_restyle_repo_entry(
    test_id: str,
    repo_data: RawRepoEntry,
    style: ConfigStyle,
    expected_entry: RawRepoEntry,
    expect_warnings: bool,
) -> None:
    """Restyle converts entries correctly and warns on lossy conversions."""
    del test_id
    entry, warnings = restyle_repo_entry("testrepo", repo_data, style=style)
    assert entry == expected_entry
    if expect_warnings:
        assert len(warnings) > 0
    else:
        assert warnings == []


# ---------------------------------------------------------------------------
# apply_config_style
# ---------------------------------------------------------------------------


def test_apply_config_style_to_standard(snapshot_json: SnapshotAssertion) -> None:
    """apply_config_style should convert concise entries to standard."""
    config = {
        "~/code/": {
            "flask": "git+https://github.com/pallets/flask.git",
            "django": "git+https://github.com/django/django.git",
        },
    }
    styled, count, warnings = apply_config_style(config, style=ConfigStyle.STANDARD)
    assert count == 2
    assert warnings == []
    assert styled == snapshot_json


def test_apply_config_style_to_concise(snapshot_json: SnapshotAssertion) -> None:
    """apply_config_style should convert standard entries to concise."""
    config = {
        "~/code/": {
            "flask": {"repo": "git+https://github.com/pallets/flask.git"},
            "django": {"repo": "git+https://github.com/django/django.git"},
        },
    }
    styled, count, warnings = apply_config_style(config, style=ConfigStyle.CONCISE)
    assert count == 2
    assert warnings == []
    assert styled == snapshot_json


def test_apply_config_style_to_verbose(snapshot_json: SnapshotAssertion) -> None:
    """apply_config_style should convert standard entries to verbose."""
    config = {
        "~/code/": {
            "flask": {"repo": "git+https://github.com/pallets/flask.git"},
        },
    }
    styled, count, warnings = apply_config_style(config, style=ConfigStyle.VERBOSE)
    assert count == 1
    assert warnings == []
    assert styled == snapshot_json


def test_apply_config_style_warns_on_lossy_concise() -> None:
    """apply_config_style should warn when converting verbose→concise with extras."""
    config = {
        "~/code/": {
            "flask": {
                "repo": "git+https://github.com/pallets/flask.git",
                "shell_command_after": "pip install -e .",
            },
        },
    }
    styled, count, warnings = apply_config_style(config, style=ConfigStyle.CONCISE)
    assert count == 0  # Entry unchanged due to warning
    assert len(warnings) == 1
    assert "extra keys" in warnings[0]
    # Original entry preserved
    assert isinstance(styled["~/code/"]["flask"], dict)


def test_apply_config_style_no_changes_when_already_styled() -> None:
    """No changes should be reported when config is already in target style."""
    config = {
        "~/code/": {
            "flask": {"repo": "git+https://github.com/pallets/flask.git"},
        },
    }
    _styled, count, warnings = apply_config_style(config, style=ConfigStyle.STANDARD)
    assert count == 0
    assert warnings == []


def test_apply_config_style_non_dict_section_passthrough() -> None:
    """Non-dict workspace sections should pass through unchanged."""
    config: dict[str, t.Any] = {
        "~/code/": {
            "flask": {"repo": "url"},
        },
        "metadata": "some-value",
    }
    styled, count, _warnings = apply_config_style(config, style=ConfigStyle.CONCISE)
    assert styled["metadata"] == "some-value"
    assert count == 1  # Only flask changed
