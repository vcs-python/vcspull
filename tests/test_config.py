"""Tests for vcspull configuration format."""

from __future__ import annotations

import dataclasses
import logging
import subprocess
import textwrap
import typing as t

import pytest

from vcspull import config
from vcspull.config import (
    MergeAction,
    _classify_merge_action,
    detect_git_depth,
    detect_legacy_repo_options,
    merge_duplicate_workspace_root_entries,
    migrate_repo_entry,
    resolve_clone_depth,
)
from vcspull.exc import VCSPullException

if t.TYPE_CHECKING:
    import pathlib

    from libvcs.pytest_plugin import CreateRepoFn

    from vcspull.types import ConfigDict, RawConfigDict


class LoadYAMLFn(t.Protocol):
    """Typing for load_yaml pytest fixture."""

    def __call__(
        self,
        content: str,
        path: str = "randomdir",
        filename: str = "randomfilename.yaml",
    ) -> tuple[pathlib.Path, list[t.Any | pathlib.Path], list[ConfigDict]]:
        """Callable function type signature for load_yaml pytest fixture."""
        ...


@pytest.fixture
def load_yaml(tmp_path: pathlib.Path) -> LoadYAMLFn:
    """Return a yaml loading function that uses temporary directory path."""

    def fn(
        content: str,
        path: str = "randomdir",
        filename: str = "randomfilename.yaml",
    ) -> tuple[pathlib.Path, list[pathlib.Path], list[ConfigDict]]:
        """Return vcspull configurations and write out config to temp directory."""
        dir_ = tmp_path / path
        dir_.mkdir()
        config_ = dir_ / filename
        config_.write_text(content, encoding="utf-8")

        configs = config.find_config_files(path=dir_)
        repos = config.load_configs(configs, cwd=dir_)
        return dir_, configs, repos

    return fn


@pytest.mark.parametrize(
    ("entry", "field"),
    [
        ({"git": {"filtre": "blob:none"}}, "git.filtre"),
        ({"git": {"filter": ["blob:none", {"kind": "nope"}]}}, "git.filter[1]"),
        ({"git": {"filter": []}}, "git.filter"),
        ({"git": {"filter": {"kind": "combine", "filters": ["auto"]}}}, "git.filter"),
        ({"git": {"depth": True}}, "git.depth"),
        ({"git": {"tls_verify": "false"}}, "git.tls_verify"),
        ({"git": {"depth": 1.5}}, "git.depth"),
        ({"git": {"depth": 2}, "options": {"depth": False}}, "options.depth"),
        ({"working_copy": {"branch": "main"}, "rev": []}, "rev"),
        ({"git": {"depth": 2}, "git_options": {"depth": False}}, "git_options.depth"),
        ({"url": "git+https://example.com/repo.git", "repo": False}, "repo"),
        ({"metadata": {"nested": {1: "non-string key"}}}, "metadata"),
        ({"metadata": {"number": float("inf")}}, "metadata"),
        ({"git": {"filter": "combine:blob:none+tree:1"}}, "git.filter"),
        ({"hg": {}}, "hg"),
        ({"svn": {"depth": "files"}}, "svn"),
        ({"git_options": {"typo": True}}, "git_options.typo"),
        ({"working_coppy": {"branch": "main"}}, "working_coppy"),
        (
            {"remotes": {"upstream": {"fetch_url": "git+https://example.com/up.git"}}},
            "remotes.upstream.push_url",
        ),
        ({"pin": {"sync": True}}, "pin.sync"),
        (
            {"repo": "hg+https://example.com/repo", "hg": {"ssh": "bad\0value"}},
            "hg.ssh",
        ),
        (
            {"repo": "hg+https://example.com/repo", "hg": {"remote_cmd": "bad\0value"}},
            "hg.remote_cmd",
        ),
        (
            {"repo": "svn+https://example.com/repo", "svn": {"username": "bad\0value"}},
            "svn.username",
        ),
        (
            {"repo": "svn+https://example.com/repo", "svn": {"password": "bad\0value"}},
            "svn.password",
        ),
    ],
)
def test_load_rejects_invalid_backend_entry_at_source(
    tmp_path: pathlib.Path,
    entry: dict[str, t.Any],
    field: str,
) -> None:
    """Malformed options name their file, workspace, repository, and field."""
    path = tmp_path / "config.yaml"
    config.save_config_yaml(
        path,
        {"~/code/": {"project": {"repo": "git+https://example.com/repo.git", **entry}}},
    )

    with pytest.raises(VCSPullException) as error:
        config.load_configs([path])

    for part in (str(path), "~/code/", "project", field):
        assert part in str(error.value)


def test_load_retains_nullable_shell_hook(tmp_path: pathlib.Path) -> None:
    """An explicitly disabled post-sync hook remains valid entry metadata."""
    path = tmp_path / "config.yaml"
    config.save_config_yaml(
        path,
        {
            "~/code/": {
                "project": {
                    "repo": "git+https://example.com/repo.git",
                    "shell_command_after": None,
                }
            }
        },
    )

    assert config.load_configs([path])[0]["shell_command_after"] is None


def test_load_normalizes_legacy_options_and_warns(
    tmp_path: pathlib.Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The in-memory entry has one canonical options layout with clear warnings."""
    path = tmp_path / "config.yaml"
    config.save_config_yaml(
        path,
        {
            "~/code/": {
                "project": {
                    "repo": "git+https://example.com/repo.git",
                    "options": {"rev": "v1", "shallow": True, "pin": True},
                    "git_options": {"filter": "blob:none"},
                }
            }
        },
    )

    with caplog.at_level(logging.WARNING, logger="vcspull.config"):
        entry = config.load_configs([path])[0]

    assert entry["working_copy"] == {"rev": "v1"}
    assert entry["git"] == {"depth": 1, "filter": "blob:none"}
    assert entry["pin"] is True
    assert "options" not in entry
    assert "rev" not in entry
    assert "shallow" not in entry
    assert any(
        "'~/code/' -> 'project'" in record.getMessage() for record in caplog.records
    )


def test_backend_config_fields_match_libvcs_options() -> None:
    """Every public backend knob has exactly one field in the config type."""
    from libvcs import GitOptions, HgOptions, SvnOptions

    from vcspull.types import GitOptionsDict, HgOptionsDict, SvnOptionsDict

    for option_type, config_type in (
        (GitOptions, GitOptionsDict),
        (HgOptions, HgOptionsDict),
        (SvnOptions, SvnOptionsDict),
    ):
        assert {field.name for field in dataclasses.fields(option_type)} == set(
            t.get_type_hints(config_type)
        )


def test_simple_format(load_yaml: LoadYAMLFn) -> None:
    """Test simple configuration YAML file for vcspull."""
    path, _, repos = load_yaml(
        """
vcspull:
  libvcs: git+https://github.com/vcs-python/libvcs
   """,
    )

    assert len(repos) == 1
    repo = repos[0]

    assert path / "vcspull" == repo["path"].parent
    assert path / "vcspull" / "libvcs" == repo["path"]


def test_relative_dir(load_yaml: LoadYAMLFn) -> None:
    """Test configuration files for vcspull support relative directories."""
    path, _, repos = load_yaml(
        """
./relativedir:
  docutils: svn+http://svn.code.sf.net/p/docutils/code/trunk
   """,
    )

    config_files = config.find_config_files(path=path)
    repos = config.load_configs(config_files, path)

    assert len(repos) == 1
    repo = repos[0]

    assert path / "relativedir" == repo["path"].parent
    assert path / "relativedir" / "docutils" == repo["path"]


class ExtractWorkspaceFixture(t.NamedTuple):
    """Fixture capturing workspace root injection scenarios."""

    test_id: str
    raw_config: dict[str, dict[str, str | dict[str, str]]]
    expected_roots: dict[str, str]


EXTRACT_WORKSPACE_FIXTURES: list[ExtractWorkspaceFixture] = [
    ExtractWorkspaceFixture(
        test_id="tilde-workspace",
        raw_config={
            "~/code/": {
                "alpha": {"repo": "git+https://example.com/alpha.git"},
            },
        },
        expected_roots={"alpha": "~/code/"},
    ),
    ExtractWorkspaceFixture(
        test_id="relative-workspace",
        raw_config={
            "./projects": {
                "beta": "git+https://example.com/beta.git",
            },
        },
        expected_roots={"beta": "./projects"},
    ),
]


@pytest.mark.parametrize(
    list(ExtractWorkspaceFixture._fields),
    EXTRACT_WORKSPACE_FIXTURES,
    ids=[fixture.test_id for fixture in EXTRACT_WORKSPACE_FIXTURES],
)
def test_extract_repos_injects_workspace_root(
    test_id: str,
    raw_config: dict[str, dict[str, str | dict[str, str]]],
    expected_roots: dict[str, str],
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ensure extract_repos assigns workspace_root consistently."""
    import pathlib as pl

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)

    typed_raw_config = t.cast("RawConfigDict", raw_config)
    repos = config.extract_repos(typed_raw_config, cwd=tmp_path)

    assert len(repos) == len(expected_roots)

    for repo in repos:
        name = repo["name"]
        expected_root = expected_roots[name]
        assert repo["workspace_root"] == expected_root
        expected_path = config.expand_dir(pl.Path(expected_root), cwd=tmp_path) / name
        assert repo["path"] == expected_path


def _write_duplicate_config(tmp_path: pathlib.Path) -> pathlib.Path:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        textwrap.dedent(
            """\
            ~/workspace/:
              alpha:
                repo: git+https://example.com/alpha.git
            ~/workspace/:
              beta:
                repo: git+https://example.com/beta.git
            """,
        ),
        encoding="utf-8",
    )
    return config_path


def test_load_configs_merges_duplicate_workspace_roots(
    tmp_path: pathlib.Path,
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Duplicate workspace roots are merged to keep every repository."""
    monkeypatch.setenv("HOME", str(tmp_path))
    caplog.set_level(logging.INFO, logger="vcspull.config")

    config_path = _write_duplicate_config(tmp_path)

    repos = config.load_configs([config_path], cwd=tmp_path)

    repo_names = {repo["name"] for repo in repos}
    assert repo_names == {"alpha", "beta"}

    merged_messages = [message for message in caplog.messages if "merged" in message]
    assert merged_messages, "Expected a merge log entry for duplicate roots"


def test_load_configs_can_skip_merging_duplicates(
    tmp_path: pathlib.Path,
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The merge step can be skipped while still warning about duplicates."""
    monkeypatch.setenv("HOME", str(tmp_path))
    caplog.set_level(logging.WARNING, logger="vcspull.config")

    config_path = _write_duplicate_config(tmp_path)

    repos = config.load_configs(
        [config_path],
        cwd=tmp_path,
        merge_duplicates=False,
    )

    repo_names = {repo["name"] for repo in repos}
    assert repo_names == {"beta"}

    warning_messages = [
        message for message in caplog.messages if "duplicate" in message
    ]
    assert warning_messages, "Expected a warning about duplicate workspace roots"


# ---------------------------------------------------------------------------
# MergeAction classifier unit tests
# ---------------------------------------------------------------------------

_MERGE_HTTPS = "git+https://github.com/testuser/repo1.git"
_MERGE_SSH = "git+git@github.com:testuser/repo1.git"


class MergeActionFixture(t.NamedTuple):
    """Fixture for _classify_merge_action unit tests."""

    test_id: str
    existing_entry: dict[str, t.Any] | str
    incoming_entry: dict[str, t.Any] | str
    expected_action: MergeAction


MERGE_ACTION_FIXTURES: list[MergeActionFixture] = [
    MergeActionFixture(
        "keep-first-no-pins",
        {"repo": _MERGE_HTTPS},
        {"repo": _MERGE_SSH},
        MergeAction.KEEP_EXISTING,
    ),
    MergeActionFixture(
        "keep-pinned-incoming",
        {"repo": _MERGE_HTTPS},
        {"repo": _MERGE_SSH, "options": {"pin": True}},
        MergeAction.KEEP_INCOMING,
    ),
    MergeActionFixture(
        "keep-pinned-existing",
        {"repo": _MERGE_HTTPS, "options": {"pin": True}},
        {"repo": _MERGE_SSH},
        MergeAction.KEEP_EXISTING,
    ),
    MergeActionFixture(
        "both-pinned-keep-first",
        {"repo": _MERGE_HTTPS, "options": {"pin": True}},
        {"repo": _MERGE_SSH, "options": {"pin": True}},
        MergeAction.KEEP_EXISTING,
    ),
    MergeActionFixture(
        "keep-pinned-merge-specific",
        {"repo": _MERGE_HTTPS},
        {"repo": _MERGE_SSH, "options": {"pin": {"merge": True}}},
        MergeAction.KEEP_INCOMING,
    ),
    MergeActionFixture(
        "import-pin-no-effect-on-merge",
        {"repo": _MERGE_HTTPS},
        {"repo": _MERGE_SSH, "options": {"pin": {"import": True}}},
        MergeAction.KEEP_EXISTING,
    ),
]


@pytest.mark.parametrize(
    list(MergeActionFixture._fields),
    MERGE_ACTION_FIXTURES,
    ids=[f.test_id for f in MERGE_ACTION_FIXTURES],
)
def test_classify_merge_action(
    test_id: str,
    existing_entry: dict[str, t.Any] | str,
    incoming_entry: dict[str, t.Any] | str,
    expected_action: MergeAction,
) -> None:
    """Test _classify_merge_action covers all permutations."""
    action = _classify_merge_action(existing_entry, incoming_entry)
    assert action == expected_action


# ---------------------------------------------------------------------------
# merge_duplicate_workspace_root_entries conflict branch tests
# ---------------------------------------------------------------------------


class MergeDuplicateConflictFixture(t.NamedTuple):
    """Fixture for merge_duplicate_workspace_root_entries conflict branches."""

    test_id: str
    label: str
    occurrences: list[dict[str, t.Any]]
    expected_merged_keys: set[str]
    expected_conflict_fragments: list[str]


MERGE_DUPLICATE_CONFLICT_FIXTURES: list[MergeDuplicateConflictFixture] = [
    MergeDuplicateConflictFixture(
        test_id="keep-incoming-pinned",
        label="~/code/",
        occurrences=[
            {"r": {"repo": "git+https://a.com/r.git"}},
            {
                "r": {
                    "repo": "git+https://b.com/r.git",
                    "options": {"pin": True},
                },
            },
        ],
        expected_merged_keys={"r"},
        expected_conflict_fragments=["displaced"],
    ),
    MergeDuplicateConflictFixture(
        test_id="keep-existing-pinned",
        label="~/code/",
        occurrences=[
            {
                "r": {
                    "repo": "git+https://a.com/r.git",
                    "options": {"pin": True},
                },
            },
            {"r": {"repo": "git+https://b.com/r.git"}},
        ],
        expected_merged_keys={"r"},
        expected_conflict_fragments=["keeping"],
    ),
]


@pytest.mark.parametrize(
    list(MergeDuplicateConflictFixture._fields),
    MERGE_DUPLICATE_CONFLICT_FIXTURES,
    ids=[f.test_id for f in MERGE_DUPLICATE_CONFLICT_FIXTURES],
)
def test_merge_duplicate_workspace_root_entries_conflicts(
    test_id: str,
    label: str,
    occurrences: list[dict[str, t.Any]],
    expected_merged_keys: set[str],
    expected_conflict_fragments: list[str],
) -> None:
    """Test merge_duplicate_workspace_root_entries handles pin conflicts."""
    merged, conflicts, change_count = merge_duplicate_workspace_root_entries(
        label,
        occurrences,
    )

    assert set(merged.keys()) == expected_merged_keys
    assert change_count == max(len(occurrences) - 1, 0)

    all_conflict_text = " ".join(conflicts)
    for fragment in expected_conflict_fragments:
        assert fragment in all_conflict_text, (
            f"Expected '{fragment}' in conflicts for {test_id}, "
            f"got: {all_conflict_text}"
        )


# ---------------------------------------------------------------------------
# options: sync-tuning keys (rev/shallow/depth)
# ---------------------------------------------------------------------------


def _seed_commits(repo_path: pathlib.Path, count: int) -> None:
    """Add ``count`` empty commits to a git checkout."""
    for index in range(count):
        subprocess.run(
            [
                "git",
                "-C",
                str(repo_path),
                "commit",
                "-q",
                "--allow-empty",
                "-m",
                f"commit-{index}",
            ],
            check=True,
            capture_output=True,
        )


class ExtractOptionsFixture(t.NamedTuple):
    """Legacy tuning normalizes into backend options and a checkout target."""

    test_id: str
    raw_config: dict[str, t.Any]
    expected: dict[str, t.Any]


EXTRACT_OPTIONS_FIXTURES: list[ExtractOptionsFixture] = [
    ExtractOptionsFixture(
        test_id="options-canonical",
        raw_config={
            "~/code/": {
                "flask": {
                    "repo": "git+https://example.com/flask.git",
                    "options": {"rev": "v3.0.0", "depth": 50},
                },
            },
        },
        expected={"working_copy": {"rev": "v3.0.0"}, "git": {"depth": 50}},
    ),
    ExtractOptionsFixture(
        test_id="legacy-top-level",
        raw_config={
            "~/code/": {
                "flask": {
                    "repo": "git+https://example.com/flask.git",
                    "rev": "v1.0.0",
                    "shallow": True,
                },
            },
        },
        expected={"working_copy": {"rev": "v1.0.0"}, "git": {"depth": 1}},
    ),
    ExtractOptionsFixture(
        test_id="options-wins-over-legacy",
        raw_config={
            "~/code/": {
                "flask": {
                    "repo": "git+https://example.com/flask.git",
                    "rev": "legacy",
                    "depth": 10,
                    "options": {"rev": "canonical", "depth": 99},
                },
            },
        },
        expected={"working_copy": {"rev": "canonical"}, "git": {"depth": 99}},
    ),
]


@pytest.mark.parametrize(
    list(ExtractOptionsFixture._fields),
    EXTRACT_OPTIONS_FIXTURES,
    ids=[f.test_id for f in EXTRACT_OPTIONS_FIXTURES],
)
def test_extract_repos_normalizes_options_sync_keys(
    test_id: str,
    raw_config: dict[str, t.Any],
    expected: dict[str, t.Any],
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Legacy options resolve with the documented canonical precedence."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)

    typed_raw_config = t.cast("RawConfigDict", raw_config)
    repos = config.extract_repos(typed_raw_config, cwd=tmp_path)

    assert len(repos) == 1
    repo = t.cast("dict[str, t.Any]", repos[0])
    for key, value in expected.items():
        assert repo[key] == value


class ResolveDepthFixture(t.NamedTuple):
    """Fixture for resolve_clone_depth explicit-flag precedence."""

    test_id: str
    explicit_shallow: bool
    explicit_depth: int | None
    expected: tuple[bool, int | None]


RESOLVE_DEPTH_FIXTURES: list[ResolveDepthFixture] = [
    ResolveDepthFixture("explicit-depth", False, 5, (False, 5)),
    ResolveDepthFixture("explicit-depth-beats-shallow", True, 5, (False, 5)),
    ResolveDepthFixture("explicit-shallow", True, None, (True, None)),
    ResolveDepthFixture("no-flags-non-git", False, None, (False, None)),
]


@pytest.mark.parametrize(
    list(ResolveDepthFixture._fields),
    RESOLVE_DEPTH_FIXTURES,
    ids=[f.test_id for f in RESOLVE_DEPTH_FIXTURES],
)
def test_resolve_clone_depth_explicit(
    test_id: str,
    explicit_shallow: bool,
    explicit_depth: int | None,
    expected: tuple[bool, int | None],
    tmp_path: pathlib.Path,
) -> None:
    """Explicit flags resolve without inspecting the filesystem."""
    result = resolve_clone_depth(
        tmp_path,
        explicit_shallow=explicit_shallow,
        explicit_depth=explicit_depth,
    )
    assert result == expected


def test_resolve_clone_depth_autodetect(
    tmp_path: pathlib.Path,
    create_git_remote_repo: CreateRepoFn,
) -> None:
    """Hybrid auto-detect: depth-1 -> shallow, depth>1 -> numeric, full -> none."""
    remote = create_git_remote_repo()
    _seed_commits(remote, 4)

    full = tmp_path / "full"
    subprocess.run(
        ["git", "clone", "-q", f"file://{remote}", str(full)],
        check=True,
        capture_output=True,
    )
    assert resolve_clone_depth(full) == (False, None)

    shallow_one = tmp_path / "shallow_one"
    subprocess.run(
        ["git", "clone", "-q", "--depth", "1", f"file://{remote}", str(shallow_one)],
        check=True,
        capture_output=True,
    )
    assert resolve_clone_depth(shallow_one) == (True, None)

    shallow_three = tmp_path / "shallow_three"
    subprocess.run(
        ["git", "clone", "-q", "--depth", "3", f"file://{remote}", str(shallow_three)],
        check=True,
        capture_output=True,
    )
    assert resolve_clone_depth(shallow_three) == (False, 3)


def test_detect_git_depth(
    tmp_path: pathlib.Path,
    create_git_remote_repo: CreateRepoFn,
) -> None:
    """detect_git_depth returns the commit count for shallow checkouts only."""
    assert detect_git_depth(tmp_path) is None  # not a git repo

    remote = create_git_remote_repo()
    _seed_commits(remote, 4)

    full = tmp_path / "full"
    subprocess.run(
        ["git", "clone", "-q", f"file://{remote}", str(full)],
        check=True,
        capture_output=True,
    )
    assert detect_git_depth(full) is None

    shallow = tmp_path / "shallow"
    subprocess.run(
        ["git", "clone", "-q", "--depth", "3", f"file://{remote}", str(shallow)],
        check=True,
        capture_output=True,
    )
    assert detect_git_depth(shallow) == 3


class MigrateEntryFixture(t.NamedTuple):
    """Legacy entries and their canonical checkout/backend settings."""

    test_id: str
    entry: t.Any
    expected_changed: bool
    expected_entry: t.Any


MIGRATE_ENTRY_FIXTURES: list[MigrateEntryFixture] = [
    MigrateEntryFixture(
        test_id="string-passthrough",
        entry="git+ssh://x",
        expected_changed=False,
        expected_entry="git+ssh://x",
    ),
    MigrateEntryFixture(
        test_id="legacy-pin-options",
        entry={"repo": "git+ssh://x", "options": {"pin": True}},
        expected_changed=True,
        expected_entry={"repo": "git+ssh://x", "pin": True},
    ),
    MigrateEntryFixture(
        test_id="single-legacy-shallow",
        entry={"repo": "git+ssh://x", "shallow": True},
        expected_changed=True,
        expected_entry={"repo": "git+ssh://x", "git": {"depth": 1}},
    ),
    MigrateEntryFixture(
        test_id="depth-wins-over-shallow",
        entry={"repo": "git+ssh://x", "rev": "v1", "shallow": True, "depth": 5},
        expected_changed=True,
        expected_entry={
            "repo": "git+ssh://x",
            "working_copy": {"rev": "v1"},
            "git": {"depth": 5},
        },
    ),
    MigrateEntryFixture(
        test_id="options-value-wins",
        entry={"repo": "git+ssh://x", "rev": "legacy", "options": {"rev": "canonical"}},
        expected_changed=True,
        expected_entry={"repo": "git+ssh://x", "working_copy": {"rev": "canonical"}},
    ),
    MigrateEntryFixture(
        test_id="preserves-pin-options",
        entry={"repo": "git+ssh://x", "shallow": True, "options": {"pin": True}},
        expected_changed=True,
        expected_entry={
            "repo": "git+ssh://x",
            "pin": True,
            "git": {"depth": 1},
        },
    ),
    MigrateEntryFixture(
        test_id="null-depth-retains-shallow",
        entry={
            "repo": "git+https://example.com/r.git",
            "options": {"shallow": True, "depth": None},
        },
        expected_changed=True,
        expected_entry={"repo": "git+https://example.com/r.git", "git": {"depth": 1}},
    ),
    MigrateEntryFixture(
        test_id="all-legacy-locations-one-pass",
        entry={
            "repo": "git+ssh://x",
            "depth": 2,
            "options": {
                "rev": "v1",
                "depth": 5,
                "pin": {"import": True},
                "allow_overwrite": False,
                "pin_reason": "local fork",
            },
            "git_options": {"filter": "blob:none", "depth": 8},
        },
        expected_changed=True,
        expected_entry={
            "repo": "git+ssh://x",
            "working_copy": {"rev": "v1"},
            "git": {"depth": 8, "filter": "blob:none"},
            "pin": {"import": True},
            "allow_overwrite": False,
            "pin_reason": "local fork",
        },
    ),
    MigrateEntryFixture(
        test_id="canonical-target-and-options-win",
        entry={
            "repo": "git+ssh://x",
            "options": {"rev": "old", "depth": 5},
            "working_copy": {"branch": "main", "sync": {"dirty": "abort"}},
            "git_options": {"filter": "blob:none", "depth": 8},
            "git": {"depth": 12},
        },
        expected_changed=True,
        expected_entry={
            "repo": "git+ssh://x",
            "working_copy": {"branch": "main", "sync": {"dirty": "abort"}},
            "git": {"depth": 12, "filter": "blob:none"},
        },
    ),
    MigrateEntryFixture(
        test_id="svn-target-and-metadata",
        entry={
            "repo": "svn+https://example.test/trunk",
            "options": {"rev": 42},
            "svn_options": {"depth": "files"},
            "note": "build input",
        },
        expected_changed=True,
        expected_entry={
            "repo": "svn+https://example.test/trunk",
            "working_copy": {"rev": 42},
            "svn": {"depth": "files"},
            "note": "build input",
        },
    ),
]


@pytest.mark.parametrize(
    list(MigrateEntryFixture._fields),
    MIGRATE_ENTRY_FIXTURES,
    ids=[f.test_id for f in MIGRATE_ENTRY_FIXTURES],
)
def test_migrate_repo_entry(
    test_id: str,
    entry: t.Any,
    expected_changed: bool,
    expected_entry: t.Any,
) -> None:
    """Migration preserves values and reaches a fixed point in one pass."""
    changed, result = migrate_repo_entry(entry)
    assert changed is expected_changed
    assert result == expected_entry
    assert migrate_repo_entry(result) == (False, result)


def test_migrate_rejects_unknown_legacy_options() -> None:
    """An unrecognized legacy option cannot disappear during migration."""
    with pytest.raises(ValueError, match=r"options\.deph"):
        migrate_repo_entry({"repo": "git+ssh://x", "options": {"deph": 5}})


@pytest.mark.parametrize("shallow", ["false", {"value": False}, [], 1])
def test_migrate_rejects_malformed_shallow(shallow: t.Any) -> None:
    """Migration cannot turn an invalid shallow value into a valid clone policy."""
    with pytest.raises(ValueError, match="shallow"):
        migrate_repo_entry({"repo": "git+x", "options": {"shallow": shallow}})


class LegacyOptionsFixture(t.NamedTuple):
    """Fixture for detect_legacy_repo_options scanning."""

    test_id: str
    raw_config: t.Any
    expected: list[tuple[str, str]]


LEGACY_OPTIONS_FIXTURES: list[LegacyOptionsFixture] = [
    LegacyOptionsFixture(
        test_id="legacy-shallow-flagged",
        raw_config={"~/code/": {"flask": {"repo": "git+x", "shallow": True}}},
        expected=[("~/code/", "flask")],
    ),
    LegacyOptionsFixture(
        test_id="canonical-not-flagged",
        raw_config={"~/code/": {"flask": {"repo": "git+x", "git": {"depth": 5}}}},
        expected=[],
    ),
    LegacyOptionsFixture(
        test_id="string-entry-not-flagged",
        raw_config={"~/code/": {"flask": "git+x"}},
        expected=[],
    ),
    LegacyOptionsFixture(
        test_id="mixed-only-legacy-flagged",
        raw_config={
            "~/code/": {
                "flask": {"repo": "git+x", "rev": "v1"},
                "django": {"repo": "git+y", "git": {"depth": 5}},
            },
        },
        expected=[("~/code/", "flask")],
    ),
    LegacyOptionsFixture(
        test_id="non-dict-input",
        raw_config="not-a-dict",
        expected=[],
    ),
]


@pytest.mark.parametrize(
    list(LegacyOptionsFixture._fields),
    LEGACY_OPTIONS_FIXTURES,
    ids=[f.test_id for f in LEGACY_OPTIONS_FIXTURES],
)
def test_detect_legacy_repo_options(
    test_id: str,
    raw_config: t.Any,
    expected: list[tuple[str, str]],
) -> None:
    """Legacy locations warn while backend blocks and shorthand stay quiet."""
    assert detect_legacy_repo_options(raw_config) == expected


@pytest.mark.parametrize(
    ("url", "kwargs", "field"),
    [
        ("svn+https://example.com/repo", {"shallow": True}, "git"),
        ("git+https://example.com/repo.git", {"depth": -1}, "depth"),
        ("git+https://example.com/repo.git", {"rev": "-invalid"}, "rev"),
    ],
)
def test_build_repo_entry_rejects_invalid_settings(
    url: str, kwargs: dict[str, t.Any], field: str
) -> None:
    """Writers reject settings that the canonical loader would reject."""
    from vcspull.config import build_repo_entry
    from vcspull.exc import VCSPullException

    with pytest.raises(VCSPullException, match=field):
        build_repo_entry(url, **kwargs)


def test_load_normalizes_integral_config_numbers(tmp_path: pathlib.Path) -> None:
    """JSON integer values normalize before strict libvcs construction."""
    path = tmp_path / "config.yaml"
    config.save_config_yaml(
        path,
        {
            "./": {
                "project": {
                    "repo": "git+https://example.com/repo.git",
                    "options": {"depth": 2.0, "rev": 4.0},
                    "git": {
                        "filter": [
                            {"kind": "tree", "depth": 3.0},
                            {"kind": "blob:limit", "limit": 1024.0},
                        ]
                    },
                }
            }
        },
    )
    entry = config.load_configs([path])[0]
    assert type(entry["git"]["depth"]) is int
    assert entry["working_copy"]["rev"] == 4
    assert type(entry["working_copy"]["rev"]) is int
    filters = entry["git"]["filter"]
    assert filters == [
        {"kind": "tree", "depth": 3},
        {"kind": "blob:limit", "limit": 1024},
    ]
    assert isinstance(filters, list)
    assert isinstance(filters[0], dict)
    assert type(filters[0]["depth"]) is int


def test_migrate_native_combines_to_structured_config() -> None:
    """Migration removes percent encoding without changing filter semantics."""
    from libvcs.cmd.git_filter import coerce_filter

    original = "combine:combine:sparse:oid=a%25%32%42b+blob:none"
    entry: dict[str, t.Any] = {
        "repo": "git+https://example.com/r.git",
        "git": {"filter": original},
    }
    changed, migrated = migrate_repo_entry(entry)
    assert changed
    assert migrated["git"]["filter"] == {
        "kind": "combine",
        "filters": [{"kind": "combine", "filters": ["sparse:oid=a+b"]}, "blob:none"],
    }
    assert coerce_filter(migrated["git"]["filter"]) == coerce_filter(original)
    assert migrate_repo_entry(migrated) == (False, migrated)
    assert entry["git"]["filter"] == original


@pytest.mark.parametrize("container", ["list", "mapping"])
def test_load_rejects_recursive_metadata(
    tmp_path: pathlib.Path, container: str
) -> None:
    """Recursive YAML metadata raises a source-specific config error."""
    metadata: dict[str, t.Any] = {}
    metadata["loop"] = [metadata] if container == "list" else metadata
    path = tmp_path / "recursive.yaml"
    config.save_config_yaml(
        path,
        {
            "./": {
                "project": {
                    "repo": "git+https://example.com/r.git",
                    "metadata": metadata,
                }
            }
        },
    )
    with pytest.raises(VCSPullException, match="metadata") as error:
        if container == "list":
            config.load_configs([path])
        else:
            config.extract_repos(
                t.cast(
                    "RawConfigDict",
                    {
                        "./": {
                            "project": {
                                "repo": "git+https://example.com/r.git",
                                "metadata": metadata,
                            }
                        }
                    },
                )
            )
    if container == "list":
        assert str(path) in str(error.value)
    assert "project" in str(error.value)
    with pytest.raises(ValueError, match="metadata"):
        migrate_repo_entry(
            {"repo": "git+https://example.com/r.git", "metadata": metadata}
        )
