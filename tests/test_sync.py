"""Tests for sync functionality of vcspull."""

from __future__ import annotations

import json
import logging
import subprocess
import textwrap
import typing as t

import pytest
from libvcs._internal.shortcuts import create_project
from libvcs.pytest_plugin import (
    git_remote_repo_single_commit_post_init,
    hg_remote_repo_single_commit_post_init,
    skip_if_hg_missing,
    skip_if_svn_missing,
    svn_remote_repo_single_commit_post_init,
)
from libvcs.sync.git import GitRemote, GitSync
from libvcs.sync.hg import HgSync
from libvcs.sync.svn import SvnSync

from vcspull._internal.config_reader import ConfigReader
from vcspull.cli.sync import _looks_like_branch_error, sync, update_repo
from vcspull.config import (
    detect_git_depth,
    detect_git_shallow,
    extract_repos,
    filter_repos,
    load_configs,
    save_config_yaml,
)
from vcspull.validator import is_valid_config

from .helpers import write_config

if t.TYPE_CHECKING:
    import pathlib

    from libvcs.pytest_plugin import CreateRepoFn

    from vcspull.types import ConfigDict


def test_makes_recursive(
    tmp_path: pathlib.Path,
    git_remote_repo: pathlib.Path,
) -> None:
    """Ensure that syncing creates directories recursively."""
    conf = ConfigReader._load(
        fmt="yaml",
        content=textwrap.dedent(
            f"""
        {tmp_path}/study/myrepo:
            my_url: git+file://{git_remote_repo}
    """,
        ),
    )
    if is_valid_config(conf):
        repos = extract_repos(config=conf)
        assert len(repos) > 0

        filtered_repos = filter_repos(repos, path="*")
        assert len(filtered_repos) > 0

        for r in filtered_repos:
            assert isinstance(r, dict)
            repo = create_project(**r)  # type: ignore
            repo.obtain()

            assert repo.path.exists()


def write_config_remote(
    config_path: pathlib.Path,
    tmp_path: pathlib.Path,
    config_tpl: str,
    path: pathlib.Path,
    clone_name: str,
) -> pathlib.Path:
    """Write vcspull configuration with git remote."""
    return write_config(
        config_path=config_path,
        content=config_tpl.format(
            tmp_path=str(tmp_path.parent),
            path=path,
            CLONE_NAME=clone_name,
        ),
    )


class ConfigVariationTest(t.NamedTuple):
    """pytest fixture for testing vcspull configuration."""

    # pytest (internal), used for naming tests
    test_id: str

    # fixture params
    config_tpl: str
    remote_list: list[str]


CONFIG_VARIATION_FIXTURES: list[ConfigVariationTest] = [
    ConfigVariationTest(
        test_id="default",
        config_tpl="""
        {tmp_path}/study/myrepo:
            {CLONE_NAME}: git+file://{path}
        """,
        remote_list=["origin"],
    ),
    ConfigVariationTest(
        test_id="expanded_repo_style",
        config_tpl="""
        {tmp_path}/study/myrepo:
            {CLONE_NAME}:
               repo: git+file://{path}
        """,
        remote_list=["repo"],
    ),
    ConfigVariationTest(
        test_id="expanded_repo_style_with_remote",
        config_tpl="""
        {tmp_path}/study/myrepo:
            {CLONE_NAME}:
                repo: git+file://{path}
                remotes:
                  secondremote: git+file://{path}
        """,
        remote_list=["secondremote"],
    ),
    ConfigVariationTest(
        test_id="expanded_repo_style_with_unprefixed_remote",
        config_tpl="""
        {tmp_path}/study/myrepo:
            {CLONE_NAME}:
                repo: git+file://{path}
                remotes:
                  git_scheme_repo: git@codeberg.org:tmux-python/tmuxp.git
        """,
        remote_list=["git_scheme_repo"],
    ),
    ConfigVariationTest(
        test_id="expanded_repo_style_with_unprefixed_remote_2",
        config_tpl="""
        {tmp_path}/study/myrepo:
            {CLONE_NAME}:
                repo: git+file://{path}
                remotes:
                  git_scheme_repo: git@github.com:tony/vcspull.git
        """,
        remote_list=["git_scheme_repo"],
    ),
]


@pytest.mark.parametrize(
    list(ConfigVariationTest._fields),
    CONFIG_VARIATION_FIXTURES,
    ids=[test.test_id for test in CONFIG_VARIATION_FIXTURES],
)
def test_config_variations(
    tmp_path: pathlib.Path,
    capsys: pytest.CaptureFixture[str],
    create_git_remote_repo: CreateRepoFn,
    test_id: str,
    config_tpl: str,
    remote_list: list[str],
) -> None:
    """Test vcspull sync'ing across a variety of configurations."""
    dummy_repo = create_git_remote_repo(
        remote_repo_post_init=git_remote_repo_single_commit_post_init,
    )

    config_file = write_config_remote(
        config_path=tmp_path / "myrepos.yaml",
        tmp_path=tmp_path,
        config_tpl=config_tpl,
        path=dummy_repo,
        clone_name="myclone",
    )
    configs = load_configs([config_file])

    # TODO: Merge repos
    repos = filter_repos(configs, path="*")
    assert len(repos) == 1

    for repo_dict in repos:
        repo = update_repo(repo_dict)
        assert isinstance(repo, GitSync)
        remotes = repo.remotes() or {}
        remote_names = set(remotes.keys())
        assert set(remote_list).issubset(remote_names) or {"origin"}.issubset(
            remote_names,
        )

        for remote_name in remotes:
            current_remote = repo.remote(remote_name)
            assert current_remote is not None
            assert repo_dict is not None
            assert isinstance(remote_name, str)
            if (
                "remotes" in repo_dict
                and isinstance(repo_dict["remotes"], dict)
                and remote_name in repo_dict["remotes"]
            ):
                if repo_dict["remotes"][remote_name].fetch_url.startswith(
                    "git+file://",
                ):
                    assert current_remote.fetch_url == repo_dict["remotes"][
                        remote_name
                    ].fetch_url.replace(
                        "git+",
                        "",
                    ), "Final git remote should chop git+ prefix"
                else:
                    assert (
                        current_remote.fetch_url
                        == repo_dict["remotes"][remote_name].fetch_url
                    )


class UpdatingRemoteFixture(t.NamedTuple):
    """pytest fixture for vcspull configuration with a git remote."""

    # pytest (internal), used for naming tests
    test_id: str

    # fixture params
    config_tpl: str
    has_extra_remotes: bool


UPDATING_REMOTE_FIXTURES: list[UpdatingRemoteFixture] = [
    UpdatingRemoteFixture(
        test_id="no_remotes",
        config_tpl="""
        {tmp_path}/study/myrepo:
            {CLONE_NAME}: git+file://{path}
        """,
        has_extra_remotes=False,
    ),
    UpdatingRemoteFixture(
        test_id="no_remotes_expanded_repo_style",
        config_tpl="""
        {tmp_path}/study/myrepo:
            {CLONE_NAME}:
               repo: git+file://{path}
        """,
        has_extra_remotes=False,
    ),
    UpdatingRemoteFixture(
        test_id="has_remotes_expanded_repo_style",
        config_tpl="""
        {tmp_path}/study/myrepo:
            {CLONE_NAME}:
                repo: git+file://{path}
                remotes:
                  mirror_repo: git+file://{path}
        """,
        has_extra_remotes=True,
    ),
]


@pytest.mark.parametrize(
    list(UpdatingRemoteFixture._fields),
    UPDATING_REMOTE_FIXTURES,
    ids=[test.test_id for test in UPDATING_REMOTE_FIXTURES],
)
def test_updating_remote(
    tmp_path: pathlib.Path,
    create_git_remote_repo: CreateRepoFn,
    test_id: str,
    config_tpl: str,
    has_extra_remotes: bool,
) -> None:
    """Verify yaml configuration state is applied and reflected to local VCS clone."""
    dummy_repo = create_git_remote_repo(
        remote_repo_post_init=git_remote_repo_single_commit_post_init,
    )

    mirror_name = "mirror_repo"
    mirror_repo = create_git_remote_repo(
        remote_repo_post_init=git_remote_repo_single_commit_post_init,
    )

    repo_parent = tmp_path / "study" / "myrepo"
    repo_parent.mkdir(parents=True)

    initial_config: ConfigDict = {
        "vcs": "git",
        "name": "myclone",
        "path": tmp_path / "study/myrepo/myclone",
        "url": f"git+file://{dummy_repo}",
        "workspace_root": str(tmp_path / "study/myrepo/"),
        "remotes": {
            mirror_name: GitRemote(
                name=mirror_name,
                fetch_url=f"git+file://{dummy_repo}",
                push_url=f"git+file://{dummy_repo}",
            ),
        },
    }

    for repo_dict in filter_repos(
        [initial_config],
    ):
        synced = update_repo(repo_dict)
        assert isinstance(synced, GitSync)
        local_git_remotes = synced.remotes()
        assert "origin" in local_git_remotes

    expected_remote_url = f"git+file://{mirror_repo}"

    expected_config: ConfigDict = initial_config.copy()
    assert isinstance(expected_config["remotes"], dict)
    expected_config["remotes"][mirror_name] = GitRemote(
        name=mirror_name,
        fetch_url=expected_remote_url,
        push_url=expected_remote_url,
    )

    repo_dict = filter_repos([expected_config], name="myclone")[0]
    assert isinstance(repo_dict, dict)
    repo = update_repo(repo_dict)
    assert isinstance(repo, GitSync)
    for remote_name in repo.remotes():
        remote = repo.remote(remote_name)
        if remote is not None:
            current_remote_url = remote.fetch_url.replace("git+", "")
            if remote_name in expected_config["remotes"]:
                assert (
                    expected_config["remotes"][remote_name].fetch_url.replace(
                        "git+",
                        "",
                    )
                    == current_remote_url
                )

            elif remote_name == "origin" and remote_name in expected_config["remotes"]:
                assert (
                    expected_config["remotes"]["origin"].fetch_url.replace("git+", "")
                    == current_remote_url
                )


def test_sync_deduplicates_repos_matched_by_multiple_patterns(
    tmp_path: pathlib.Path,
    capsys: pytest.CaptureFixture[str],
    create_git_remote_repo: CreateRepoFn,
) -> None:
    """Repos matched by multiple patterns should only sync once."""
    dummy_repo = create_git_remote_repo(
        remote_repo_post_init=git_remote_repo_single_commit_post_init,
    )

    config_file = write_config(
        config_path=tmp_path / "myrepos.yaml",
        content=textwrap.dedent(
            f"""\
            {tmp_path}/code/:
                myclone: git+file://{dummy_repo}
            """,
        ),
    )

    configs = load_configs([config_file])
    assert len(configs) == 1

    # Two patterns that both match the same repo
    sync(
        repo_patterns=["myclone", "*"],
        config=config_file,
        workspace_root=None,
        dry_run=False,
        output_json=True,
        output_ndjson=False,
        color="never",
        exit_on_error=False,
        show_unchanged=False,
        summary_only=False,
        long_view=False,
        relative_paths=False,
        fetch=False,
        offline=False,
        verbosity=0,
    )

    captured = capsys.readouterr()
    output_data = json.loads(captured.out)

    # Count sync events (not summary)
    sync_events = [item for item in output_data if item.get("reason") == "sync"]
    assert len(sync_events) == 1, (
        f"Expected exactly 1 sync event, got {len(sync_events)}"
    )


@skip_if_svn_missing
def test_update_repo_svn(
    tmp_path: pathlib.Path,
    create_svn_remote_repo: CreateRepoFn,
) -> None:
    """update_repo should handle SVN repositories and return SvnSync."""
    svn_remote = create_svn_remote_repo(
        remote_repo_post_init=svn_remote_repo_single_commit_post_init,
    )
    # Use bare file:// URL with explicit vcs since svn binary doesn't understand
    # the svn+ prefix that vcspull uses for VCS detection.
    repo_dict: ConfigDict = {
        "vcs": "svn",
        "name": "my_svn_repo",
        "path": tmp_path / "checkout" / "my_svn_repo",
        "url": f"file://{svn_remote}",
        "workspace_root": str(tmp_path / "checkout/"),
    }

    result = update_repo(repo_dict)
    assert isinstance(result, SvnSync)


@skip_if_hg_missing
def test_update_repo_hg(
    tmp_path: pathlib.Path,
    create_hg_remote_repo: CreateRepoFn,
) -> None:
    """update_repo should handle Mercurial repositories and return HgSync."""
    hg_remote = create_hg_remote_repo(
        remote_repo_post_init=hg_remote_repo_single_commit_post_init,
    )
    # Use bare file:// URL with explicit vcs since hg binary doesn't understand
    # the hg+ prefix that vcspull uses for VCS detection.
    repo_dict: ConfigDict = {
        "vcs": "hg",
        "name": "my_hg_repo",
        "path": tmp_path / "checkout" / "my_hg_repo",
        "url": f"file://{hg_remote}",
        "workspace_root": str(tmp_path / "checkout/"),
    }

    result = update_repo(repo_dict)
    assert isinstance(result, HgSync)


def test_update_repo_git_shallow(
    tmp_path: pathlib.Path,
    create_git_remote_repo: CreateRepoFn,
) -> None:
    """A ``shallow: true`` config entry clones with ``--depth 1`` on sync."""
    dummy_repo = create_git_remote_repo(
        remote_repo_post_init=git_remote_repo_single_commit_post_init,
    )
    # A --depth 1 clone is only meaningfully shallow when the remote carries
    # more history than the requested depth, so add a second commit.
    subprocess.run(
        ["git", "-C", str(dummy_repo), "commit", "-q", "--allow-empty", "-m", "second"],
        check=True,
    )

    repo_dict: ConfigDict = {
        "vcs": "git",
        "name": "shallowclone",
        "path": tmp_path / "checkout" / "shallowclone",
        "url": f"git+file://{dummy_repo}",
        "workspace_root": str(tmp_path / "checkout/"),
        "shallow": True,
    }

    # update_repo must not raise (regression guard: ``git_shallow`` is applied
    # as an attribute post-construction, not forwarded as a GitSync kwarg).
    result = update_repo(repo_dict)
    assert isinstance(result, GitSync)
    assert detect_git_shallow(result.path) is True


def test_update_repo_git_rev(
    tmp_path: pathlib.Path,
    create_git_remote_repo: CreateRepoFn,
) -> None:
    """A ``rev`` config entry checks out that ref on sync, not the branch tip."""
    dummy_repo = create_git_remote_repo(
        remote_repo_post_init=git_remote_repo_single_commit_post_init,
    )
    # Tag the first commit, then advance the branch so the tag != HEAD.
    subprocess.run(["git", "-C", str(dummy_repo), "tag", "v1.0.0"], check=True)
    subprocess.run(
        ["git", "-C", str(dummy_repo), "commit", "-q", "--allow-empty", "-m", "second"],
        check=True,
    )
    tag_sha = subprocess.run(
        ["git", "-C", str(dummy_repo), "rev-parse", "v1.0.0"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()

    repo_dict: ConfigDict = {
        "vcs": "git",
        "name": "revclone",
        "path": tmp_path / "checkout" / "revclone",
        "url": f"git+file://{dummy_repo}",
        "workspace_root": str(tmp_path / "checkout/"),
        "rev": "v1.0.0",
    }

    result = update_repo(repo_dict)
    assert isinstance(result, GitSync)
    assert result.get_revision() == tag_sha


def test_update_repo_git_depth(
    tmp_path: pathlib.Path,
    create_git_remote_repo: CreateRepoFn,
) -> None:
    """A ``depth`` config entry clones with ``--depth N`` on sync."""
    dummy_repo = create_git_remote_repo(
        remote_repo_post_init=git_remote_repo_single_commit_post_init,
    )
    # A --depth N clone is only meaningfully shallow when the remote carries
    # more history than the requested depth, so add commits past depth 2.
    for message in ("second", "third", "fourth"):
        subprocess.run(
            [
                "git",
                "-C",
                str(dummy_repo),
                "commit",
                "-q",
                "--allow-empty",
                "-m",
                message,
            ],
            check=True,
        )

    repo_dict: ConfigDict = {
        "vcs": "git",
        "name": "depthclone",
        "path": tmp_path / "checkout" / "depthclone",
        "url": f"git+file://{dummy_repo}",
        "workspace_root": str(tmp_path / "checkout/"),
        "depth": 2,
    }

    result = update_repo(repo_dict)
    assert isinstance(result, GitSync)
    assert detect_git_depth(result.path) == 2


class LegacyWarningFixture(t.NamedTuple):
    """Fixture for the legacy top-level-keys deprecation warning."""

    test_id: str
    config: dict[str, t.Any]
    expect_warning: bool
    affected_count: int


_REPO = "git+https://github.com/pallets/flask.git"

LEGACY_WARNING_FIXTURES: list[LegacyWarningFixture] = [
    LegacyWarningFixture(
        test_id="legacy-rev",
        config={"~/code/": {"flask": {"repo": _REPO, "rev": "v1"}}},
        expect_warning=True,
        affected_count=1,
    ),
    LegacyWarningFixture(
        test_id="legacy-shallow",
        config={"~/code/": {"flask": {"repo": _REPO, "shallow": True}}},
        expect_warning=True,
        affected_count=1,
    ),
    LegacyWarningFixture(
        test_id="legacy-depth",
        config={"~/code/": {"flask": {"repo": _REPO, "depth": 3}}},
        expect_warning=True,
        affected_count=1,
    ),
    LegacyWarningFixture(
        test_id="legacy-combo",
        config={
            "~/code/": {
                "flask": {"repo": _REPO, "rev": "v1", "shallow": True, "depth": 3}
            }
        },
        expect_warning=True,
        affected_count=1,
    ),
    LegacyWarningFixture(
        test_id="multiple-legacy",
        config={
            "~/code/": {
                "a": {"repo": _REPO, "rev": "v1"},
                "b": {"repo": _REPO, "shallow": True},
            },
        },
        expect_warning=True,
        affected_count=2,
    ),
    LegacyWarningFixture(
        test_id="mixed",
        config={
            "~/code/": {
                "a": {"repo": _REPO, "rev": "v1"},
                "b": {"repo": _REPO, "options": {"shallow": True}},
            },
        },
        expect_warning=True,
        affected_count=1,
    ),
    LegacyWarningFixture(
        test_id="canonical-options",
        config={"~/code/": {"flask": {"repo": _REPO, "options": {"shallow": True}}}},
        expect_warning=False,
        affected_count=0,
    ),
    LegacyWarningFixture(
        test_id="string-shorthand",
        config={"~/code/": {"flask": _REPO}},
        expect_warning=False,
        affected_count=0,
    ),
]


@pytest.mark.parametrize(
    list(LegacyWarningFixture._fields),
    LEGACY_WARNING_FIXTURES,
    ids=[fixture.test_id for fixture in LEGACY_WARNING_FIXTURES],
)
def test_load_configs_warns_on_legacy_options(
    test_id: str,
    config: dict[str, t.Any],
    expect_warning: bool,
    affected_count: int,
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """load_configs(warn_legacy_options=True) warns only on top-level sync keys."""
    monkeypatch.setenv("HOME", str(tmp_path))
    config_file = tmp_path / ".vcspull.yaml"
    save_config_yaml(config_file, config)

    with caplog.at_level(logging.WARNING, logger="vcspull.config"):
        load_configs([config_file], warn_legacy_options=True)

    legacy_records = [
        record
        for record in caplog.records
        if hasattr(record, "vcspull_config_path")
        and hasattr(record, "vcspull_legacy_count")
    ]

    if not expect_warning:
        assert legacy_records == []
        return

    # The warning is emitted once per file, naming every affected entry.
    assert len(legacy_records) == 1
    record = legacy_records[0]
    assert record.levelno == logging.WARNING
    assert "vcspull migrate" in record.getMessage()
    assert record.vcspull_config_path == str(config_file)
    assert record.vcspull_legacy_count == affected_count


class BranchErrorDetectionFixture(t.NamedTuple):
    """pytest fixture for _looks_like_branch_error classification."""

    test_id: str
    err_msg: str
    has_rev: bool
    expected: bool


BRANCH_ERROR_DETECTION_FIXTURES: list[BranchErrorDetectionFixture] = [
    BranchErrorDetectionFixture(
        test_id="rev-checkout-failure",
        err_msg="Command failed with code 1: git checkout master",
        has_rev=True,
        expected=True,
    ),
    BranchErrorDetectionFixture(
        test_id="checkout-failure-without-rev",
        err_msg="Command failed with code 1: git checkout master",
        has_rev=False,
        expected=False,
    ),
    BranchErrorDetectionFixture(
        test_id="invalid-upstream",
        err_msg="fatal: invalid upstream 'origin/feature'",
        has_rev=False,
        expected=True,
    ),
    BranchErrorDetectionFixture(
        test_id="ambiguous-argument",
        err_msg="fatal: ambiguous argument 'notes': unknown revision",
        has_rev=False,
        expected=True,
    ),
    BranchErrorDetectionFixture(
        test_id="unrelated-network-error",
        err_msg="fatal: unable to access; Could not resolve host: example.com",
        has_rev=True,
        expected=False,
    ),
]


@pytest.mark.parametrize(
    list(BranchErrorDetectionFixture._fields),
    BRANCH_ERROR_DETECTION_FIXTURES,
    ids=[test.test_id for test in BRANCH_ERROR_DETECTION_FIXTURES],
)
def test_looks_like_branch_error(
    test_id: str,
    err_msg: str,
    has_rev: bool,
    expected: bool,
) -> None:
    """Test _looks_like_branch_error classifies sync failures correctly."""
    assert _looks_like_branch_error(err_msg, has_rev=has_rev) is expected
