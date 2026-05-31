"""Tests for vcspull configuration format."""

from __future__ import annotations

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
    """Fixture for extract_repos lifting sync keys onto the flat ConfigDict."""

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
        expected={"rev": "v3.0.0", "depth": 50},
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
        expected={"rev": "v1.0.0", "shallow": True},
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
        expected={"rev": "canonical", "depth": 99},
    ),
]


@pytest.mark.parametrize(
    list(ExtractOptionsFixture._fields),
    EXTRACT_OPTIONS_FIXTURES,
    ids=[f.test_id for f in EXTRACT_OPTIONS_FIXTURES],
)
def test_extract_repos_lifts_options_sync_keys(
    test_id: str,
    raw_config: dict[str, t.Any],
    expected: dict[str, t.Any],
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """extract_repos surfaces options/legacy sync keys on the flat ConfigDict."""
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
    """Fixture for migrate_repo_entry top-level -> options relocation."""

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
        test_id="no-legacy-keys",
        entry={"repo": "git+ssh://x", "options": {"pin": True}},
        expected_changed=False,
        expected_entry={"repo": "git+ssh://x", "options": {"pin": True}},
    ),
    MigrateEntryFixture(
        test_id="single-legacy-shallow",
        entry={"repo": "git+ssh://x", "shallow": True},
        expected_changed=True,
        expected_entry={"repo": "git+ssh://x", "options": {"shallow": True}},
    ),
    MigrateEntryFixture(
        test_id="depth-wins-over-shallow",
        entry={"repo": "git+ssh://x", "rev": "v1", "shallow": True, "depth": 5},
        expected_changed=True,
        expected_entry={"repo": "git+ssh://x", "options": {"rev": "v1", "depth": 5}},
    ),
    MigrateEntryFixture(
        test_id="options-value-wins",
        entry={"repo": "git+ssh://x", "rev": "legacy", "options": {"rev": "canonical"}},
        expected_changed=True,
        expected_entry={"repo": "git+ssh://x", "options": {"rev": "canonical"}},
    ),
    MigrateEntryFixture(
        test_id="preserves-pin-options",
        entry={"repo": "git+ssh://x", "shallow": True, "options": {"pin": True}},
        expected_changed=True,
        expected_entry={
            "repo": "git+ssh://x",
            "options": {"pin": True, "shallow": True},
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
    """migrate_repo_entry relocates legacy keys under options:, depth wins."""
    changed, result = migrate_repo_entry(entry)
    assert changed is expected_changed
    assert result == expected_entry


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
        raw_config={"~/code/": {"flask": {"repo": "git+x", "options": {"depth": 5}}}},
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
                "django": {"repo": "git+y", "options": {"depth": 5}},
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
    """detect_legacy_repo_options reports only entries with top-level keys."""
    assert detect_legacy_repo_options(raw_config) == expected
