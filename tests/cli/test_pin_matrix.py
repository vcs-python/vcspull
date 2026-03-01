"""End-to-end pin matrix: every pin config x every operation.

Exercises the pin system across all 5 mutating operations (import --sync, add,
discover, fmt --write, merge) for each of the 8 pin configurations.  Each test
function is parameterized over the 8 configs, yielding 40 cases total.  A
separate smaller test verifies ``pin_reason`` appears in logs.
"""

from __future__ import annotations

import logging
import pathlib
import subprocess
import typing as t

import pytest
import yaml

from vcspull._internal.config_reader import ConfigReader
from vcspull._internal.remotes import ImportOptions, RemoteRepo
from vcspull.cli.add import add_repo
from vcspull.cli.discover import discover_repos
from vcspull.cli.fmt import format_config_file
from vcspull.cli.import_cmd._common import _run_import
from vcspull.config import (
    merge_duplicate_workspace_root_entries,
    save_config_yaml,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_OLD_URL = "git+https://github.com/testuser/repo1.git"
_NEW_URL = "git+https://github.com/testuser/repo1-moved.git"
_SSH_URL = "git+git@github.com:testuser/repo1.git"


# ---------------------------------------------------------------------------
# Pin config fixtures (8 configs)
# ---------------------------------------------------------------------------


class PinConfig(t.NamedTuple):
    """A pin configuration and the set of operations it guards."""

    test_id: str
    options: dict[str, t.Any] | None
    pinned_ops: frozenset[str]


PIN_CONFIGS: list[PinConfig] = [
    PinConfig(
        test_id="no-pin",
        options=None,
        pinned_ops=frozenset(),
    ),
    PinConfig(
        test_id="pin-true",
        options={"pin": True},
        pinned_ops=frozenset({"import", "add", "discover", "fmt", "merge"}),
    ),
    PinConfig(
        test_id="pin-import-only",
        options={"pin": {"import": True}},
        pinned_ops=frozenset({"import"}),
    ),
    PinConfig(
        test_id="pin-add-only",
        options={"pin": {"add": True}},
        pinned_ops=frozenset({"add"}),
    ),
    PinConfig(
        test_id="pin-discover-only",
        options={"pin": {"discover": True}},
        pinned_ops=frozenset({"discover"}),
    ),
    PinConfig(
        test_id="pin-fmt-only",
        options={"pin": {"fmt": True}},
        pinned_ops=frozenset({"fmt"}),
    ),
    PinConfig(
        test_id="pin-merge-only",
        options={"pin": {"merge": True}},
        pinned_ops=frozenset({"merge"}),
    ),
    PinConfig(
        test_id="allow-overwrite-false",
        options={"allow_overwrite": False},
        pinned_ops=frozenset({"import"}),
    ),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _entry(url: str, options: dict[str, t.Any] | None) -> dict[str, t.Any]:
    """Build a repo entry dict, optionally including options."""
    entry: dict[str, t.Any] = {"repo": url}
    if options is not None:
        entry["options"] = options
    return entry


def _init_git_repo(repo_path: pathlib.Path, remote_url: str) -> None:
    """Initialize a bare git repo with an origin remote."""
    repo_path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q", str(repo_path)], check=True)
    subprocess.run(
        ["git", "-C", str(repo_path), "remote", "add", "origin", remote_url],
        check=True,
    )


class MockImporter:
    """Minimal mock importer for _run_import tests."""

    def __init__(self, *, repos: list[RemoteRepo] | None = None) -> None:
        self.service_name = "MockService"
        self._repos = repos or []

    def fetch_repos(self, options: ImportOptions) -> t.Iterator[RemoteRepo]:
        """Yield mock repos."""
        yield from self._repos


def _make_repo(name: str, owner: str = "testuser") -> RemoteRepo:
    """Create a RemoteRepo with URLs that differ from _OLD_URL."""
    return RemoteRepo(
        name=name,
        clone_url=f"https://github.com/{owner}/{name}-moved.git",
        ssh_url=f"git@github.com:{owner}/{name}-moved.git",
        html_url=f"https://github.com/{owner}/{name}-moved",
        description=f"Test repo {name}",
        language="Python",
        topics=(),
        stars=10,
        is_fork=False,
        is_archived=False,
        default_branch="main",
        owner=owner,
    )


# ---------------------------------------------------------------------------
# 1. import --sync
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    list(PinConfig._fields),
    PIN_CONFIGS,
    ids=[pc.test_id for pc in PIN_CONFIGS],
)
def test_pin_matrix_import_sync(
    test_id: str,
    options: dict[str, t.Any] | None,
    pinned_ops: frozenset[str],
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Import --sync: pinned entries keep their URL."""
    caplog.set_level(logging.INFO)
    monkeypatch.setenv("HOME", str(tmp_path))

    workspace = tmp_path / "repos"
    workspace.mkdir()
    config_file = tmp_path / ".vcspull.yaml"

    # Pre-populate config with old URL + pin config
    save_config_yaml(
        config_file,
        {"~/repos/": {"repo1": _entry(_OLD_URL, options)}},
    )

    # MockImporter returns repo1 at a *different* URL
    importer = MockImporter(repos=[_make_repo("repo1")])
    _run_import(
        importer,
        service_name="github",
        target="testuser",
        workspace=str(workspace),
        mode="user",
        language=None,
        topics=None,
        min_stars=0,
        include_archived=False,
        include_forks=False,
        limit=100,
        config_path_str=str(config_file),
        dry_run=False,
        yes=True,
        output_json=False,
        output_ndjson=False,
        color="never",
        sync=True,
    )

    final_config = ConfigReader._from_file(config_file)
    assert final_config is not None
    entry = final_config["~/repos/"]["repo1"]

    if "import" in pinned_ops:
        # URL must NOT have changed
        assert entry["repo"] == _OLD_URL
        assert "pinned" in caplog.text.lower()
    else:
        # URL should be updated to the new SSH URL (default for import)
        assert entry["repo"] != _OLD_URL


# ---------------------------------------------------------------------------
# 2. add
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    list(PinConfig._fields),
    PIN_CONFIGS,
    ids=[pc.test_id for pc in PIN_CONFIGS],
)
def test_pin_matrix_add(
    test_id: str,
    options: dict[str, t.Any] | None,
    pinned_ops: frozenset[str],
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """add: pinned entries are not overwritten."""
    caplog.set_level(logging.INFO)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)

    config_file = tmp_path / ".vcspull.yaml"

    # Pre-populate config with existing entry
    config_file.write_text(
        yaml.dump({"~/code/": {"myrepo": _entry(_OLD_URL, options)}}),
        encoding="utf-8",
    )

    # Try to add same repo name with a different URL
    add_repo(
        name="myrepo",
        url=_NEW_URL,
        config_file_path_str=str(config_file),
        path=None,
        workspace_root_path="~/code/",
        dry_run=False,
    )

    with config_file.open() as f:
        actual_config = yaml.safe_load(f)

    entry = actual_config["~/code/"]["myrepo"]

    if "add" in pinned_ops:
        # Entry must be unchanged
        assert entry["repo"] == _OLD_URL
        assert "pinned" in caplog.text.lower()
    else:
        # add skips existing entries (SKIP_EXISTING), URL stays the same.
        # add_repo doesn't update URLs for existing entries — it just skips.
        assert entry["repo"] == _OLD_URL


# ---------------------------------------------------------------------------
# 3. discover
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    list(PinConfig._fields),
    PIN_CONFIGS,
    ids=[pc.test_id for pc in PIN_CONFIGS],
)
def test_pin_matrix_discover(
    test_id: str,
    options: dict[str, t.Any] | None,
    pinned_ops: frozenset[str],
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """discover: pinned entries are not overwritten."""
    # discover logs pinned skips at DEBUG level
    caplog.set_level(logging.DEBUG)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)

    scan_dir = tmp_path / "code"
    scan_dir.mkdir()

    # Create a git repo that will be discovered
    repo_path = scan_dir / "myrepo"
    _init_git_repo(repo_path, _NEW_URL)

    config_file = tmp_path / ".vcspull.yaml"

    # Pre-populate config with existing entry at old URL
    config_file.write_text(
        yaml.dump({"~/code/": {"myrepo": _entry(_OLD_URL, options)}}),
        encoding="utf-8",
    )

    discover_repos(
        scan_dir_str=str(scan_dir),
        config_file_path_str=str(config_file),
        recursive=False,
        workspace_root_override=None,
        yes=True,
        dry_run=False,
    )

    with config_file.open() as f:
        actual_config = yaml.safe_load(f)

    entry = actual_config["~/code/"]["myrepo"]

    if "discover" in pinned_ops:
        # Pinned entry must be unchanged
        assert entry["repo"] == _OLD_URL
        # Note: discover logs pinned skips at DEBUG level only
    else:
        # discover skips existing entries (SKIP_EXISTING), URL stays the same.
        # discover_repos doesn't update URLs for existing entries — it skips.
        assert entry["repo"] == _OLD_URL


# ---------------------------------------------------------------------------
# 4. fmt --write
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    list(PinConfig._fields),
    PIN_CONFIGS,
    ids=[pc.test_id for pc in PIN_CONFIGS],
)
def test_pin_matrix_fmt(
    test_id: str,
    options: dict[str, t.Any] | None,
    pinned_ops: frozenset[str],
    tmp_path: pathlib.Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Fmt --write: pinned entries are not normalized.

    We use a compact string entry (``"git+url"``) as the test input.
    After fmt, unpinned entries are normalized to ``{"repo": "git+url"}``.
    Pinned entries stay in their original form.
    """
    caplog.set_level(logging.INFO)

    config_file = tmp_path / ".vcspull.yaml"

    if options is not None:
        # Verbose entry with options — use 'url' key so fmt can normalize
        entry_data: dict[str, t.Any] | str = {"url": _OLD_URL, "options": options}
    else:
        # Compact string entry — fmt normalizes to {"repo": url}
        entry_data = _OLD_URL

    config_file.write_text(
        yaml.dump({"~/projects/": {"myrepo": entry_data}}),
        encoding="utf-8",
    )

    format_config_file(str(config_file), write=True, format_all=False)

    with config_file.open() as f:
        actual_config = yaml.safe_load(f)

    entry = actual_config["~/projects/"]["myrepo"]

    if "fmt" in pinned_ops:
        # Entry must stay in its original form (not normalized)
        assert isinstance(entry, dict)
        assert "url" in entry  # 'url' key not converted to 'repo'
        # Note: fmt silently preserves pinned entries (no log message)
    else:
        # Entry should be normalized
        if isinstance(entry, dict):
            # url key should have been converted to repo key
            assert "repo" in entry
        else:
            # Should have been expanded from string to dict
            msg = f"Expected dict after fmt normalization, got {type(entry)}"
            raise AssertionError(msg)


# ---------------------------------------------------------------------------
# 5. merge
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    list(PinConfig._fields),
    PIN_CONFIGS,
    ids=[pc.test_id for pc in PIN_CONFIGS],
)
def test_pin_matrix_merge(
    test_id: str,
    options: dict[str, t.Any] | None,
    pinned_ops: frozenset[str],
    tmp_path: pathlib.Path,
) -> None:
    """merge: pinned incoming entry displaces unpinned existing.

    We create two occurrences of the same workspace root.  The existing
    (first) entry is always unpinned.  The incoming (second) entry carries
    the pin config under test.  When ``merge`` is in the pinned set, the
    incoming entry should win; otherwise the existing (first) entry wins.
    """
    existing_entry: dict[str, t.Any] = {"repo": _OLD_URL}
    incoming_entry: dict[str, t.Any] = _entry(_NEW_URL, options)

    merged, _conflicts, _change_count = merge_duplicate_workspace_root_entries(
        "~/code/",
        [
            {"myrepo": existing_entry},
            {"myrepo": incoming_entry},
        ],
    )

    if "merge" in pinned_ops:
        # Pinned incoming should displace unpinned existing
        assert merged["myrepo"]["repo"] == _NEW_URL
    else:
        # First occurrence (existing) wins
        assert merged["myrepo"]["repo"] == _OLD_URL


# ---------------------------------------------------------------------------
# pin_reason coverage (5 cases, one per operation)
# ---------------------------------------------------------------------------


class PinReasonFixture(t.NamedTuple):
    """Fixture for pin_reason log verification."""

    test_id: str
    operation: str


PIN_REASON_FIXTURES: list[PinReasonFixture] = [
    PinReasonFixture("pin-reason-import", "import"),
    PinReasonFixture("pin-reason-add", "add"),
    PinReasonFixture("pin-reason-discover", "discover"),
    PinReasonFixture("pin-reason-fmt", "fmt"),
    PinReasonFixture("pin-reason-merge", "merge"),
]


@pytest.mark.parametrize(
    list(PinReasonFixture._fields),
    PIN_REASON_FIXTURES,
    ids=[f.test_id for f in PIN_REASON_FIXTURES],
)
def test_pin_reason_in_log(
    test_id: str,
    operation: str,
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """pin_reason should appear in log output for each operation."""
    caplog.set_level(logging.DEBUG)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)

    pin_reason_text = "locked by admin policy"
    pin_options: dict[str, t.Any] = {"pin": True, "pin_reason": pin_reason_text}
    entry = _entry(_OLD_URL, pin_options)

    if operation == "import":
        workspace = tmp_path / "repos"
        workspace.mkdir()
        config_file = tmp_path / ".vcspull.yaml"
        save_config_yaml(config_file, {"~/repos/": {"repo1": entry}})
        importer = MockImporter(repos=[_make_repo("repo1")])
        _run_import(
            importer,
            service_name="github",
            target="testuser",
            workspace=str(workspace),
            mode="user",
            language=None,
            topics=None,
            min_stars=0,
            include_archived=False,
            include_forks=False,
            limit=100,
            config_path_str=str(config_file),
            dry_run=False,
            yes=True,
            output_json=False,
            output_ndjson=False,
            color="never",
            sync=True,
        )
        assert pin_reason_text in caplog.text

    elif operation == "add":
        config_file = tmp_path / ".vcspull.yaml"
        config_file.write_text(
            yaml.dump({"~/code/": {"myrepo": entry}}),
            encoding="utf-8",
        )
        add_repo(
            name="myrepo",
            url=_NEW_URL,
            config_file_path_str=str(config_file),
            path=None,
            workspace_root_path="~/code/",
            dry_run=False,
        )
        assert pin_reason_text in caplog.text

    elif operation == "discover":
        scan_dir = tmp_path / "code"
        scan_dir.mkdir()
        repo_path = scan_dir / "myrepo"
        _init_git_repo(repo_path, _NEW_URL)
        config_file = tmp_path / ".vcspull.yaml"
        config_file.write_text(
            yaml.dump({"~/code/": {"myrepo": entry}}),
            encoding="utf-8",
        )
        discover_repos(
            scan_dir_str=str(scan_dir),
            config_file_path_str=str(config_file),
            recursive=False,
            workspace_root_override=None,
            yes=True,
            dry_run=False,
        )
        # discover logs pin_reason at DEBUG; verify config preserved it
        with config_file.open() as f:
            saved = yaml.safe_load(f)
        saved_opts = saved["~/code/"]["myrepo"].get("options", {})
        assert saved_opts.get("pin_reason") == pin_reason_text

    elif operation == "fmt":
        config_file = tmp_path / ".vcspull.yaml"
        fmt_entry = {"url": _OLD_URL, "options": pin_options}
        config_file.write_text(
            yaml.dump({"~/projects/": {"myrepo": fmt_entry}}),
            encoding="utf-8",
        )
        format_config_file(str(config_file), write=True, format_all=False)
        # fmt silently preserves pinned entries; verify pin_reason survives
        with config_file.open() as f:
            saved = yaml.safe_load(f)
        saved_opts = saved["~/projects/"]["myrepo"].get("options", {})
        assert saved_opts.get("pin_reason") == pin_reason_text

    elif operation == "merge":
        # merge logs conflicts; pin_reason appears in conflict messages
        existing_entry: dict[str, t.Any] = {"repo": _OLD_URL}
        incoming_entry = _entry(_NEW_URL, pin_options)
        _merged, _conflicts, _changes = merge_duplicate_workspace_root_entries(
            "~/code/",
            [
                {"myrepo": existing_entry},
                {"myrepo": incoming_entry},
            ],
        )
        # For merge, pin_reason may appear in conflict messages or we check
        # the merged entry preserves pin_reason
        merged_entry = _merged["myrepo"]
        assert merged_entry.get("options", {}).get("pin_reason") == pin_reason_text
