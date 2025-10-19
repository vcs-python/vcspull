"""Test CLI entry point for for vcspull."""

from __future__ import annotations

import contextlib
import json
import shutil
import typing as t

import pytest
import yaml

from vcspull.__about__ import __version__
from vcspull.cli import cli
from vcspull.cli.sync import EXIT_ON_ERROR_MSG, NO_REPOS_FOR_TERM_MSG

if t.TYPE_CHECKING:
    import pathlib

    from libvcs.sync.git import GitSync
    from typing_extensions import TypeAlias

    ExpectedOutput: TypeAlias = t.Optional[t.Union[str, list[str]]]


class SyncCLINonExistentRepo(t.NamedTuple):
    """Pytest fixture for vcspull syncing when repo does not exist."""

    # pytest internal: used for naming test
    test_id: str

    # test parameters
    sync_args: list[str]
    expected_exit_code: int
    expected_in_out: ExpectedOutput = None
    expected_not_in_out: ExpectedOutput = None
    expected_in_err: ExpectedOutput = None
    expected_not_in_err: ExpectedOutput = None


SYNC_CLI_EXISTENT_REPO_FIXTURES: list[SyncCLINonExistentRepo] = [
    SyncCLINonExistentRepo(
        test_id="exists",
        sync_args=["my_git_project"],
        expected_exit_code=0,
        expected_in_out="Already on 'master'",
        expected_not_in_out=NO_REPOS_FOR_TERM_MSG.format(name="my_git_repo"),
    ),
    SyncCLINonExistentRepo(
        test_id="non-existent-only",
        sync_args=["this_isnt_in_the_config"],
        expected_exit_code=0,
        expected_in_out=NO_REPOS_FOR_TERM_MSG.format(name="this_isnt_in_the_config"),
    ),
    SyncCLINonExistentRepo(
        test_id="non-existent-mixed",
        sync_args=["this_isnt_in_the_config", "my_git_project", "another"],
        expected_exit_code=0,
        expected_in_out=[
            NO_REPOS_FOR_TERM_MSG.format(name="this_isnt_in_the_config"),
            NO_REPOS_FOR_TERM_MSG.format(name="another"),
        ],
        expected_not_in_out=NO_REPOS_FOR_TERM_MSG.format(name="my_git_repo"),
    ),
]


@pytest.mark.parametrize(
    list(SyncCLINonExistentRepo._fields),
    SYNC_CLI_EXISTENT_REPO_FIXTURES,
    ids=[test.test_id for test in SYNC_CLI_EXISTENT_REPO_FIXTURES],
)
def test_sync_cli_filter_non_existent(
    tmp_path: pathlib.Path,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
    user_path: pathlib.Path,
    config_path: pathlib.Path,
    git_repo: GitSync,
    test_id: str,
    sync_args: list[str],
    expected_exit_code: int,
    expected_in_out: ExpectedOutput,
    expected_not_in_out: ExpectedOutput,
    expected_in_err: ExpectedOutput,
    expected_not_in_err: ExpectedOutput,
) -> None:
    """Tests vcspull syncing when repo does not exist."""
    config = {
        "~/github_projects/": {
            "my_git_project": {
                "url": f"git+file://{git_repo.path}",
                "remotes": {"test_remote": f"git+file://{git_repo.path}"},
            },
        },
    }
    yaml_config = config_path / ".vcspull.yaml"
    yaml_config_data = yaml.dump(config, default_flow_style=False)
    yaml_config.write_text(yaml_config_data, encoding="utf-8")

    monkeypatch.chdir(tmp_path)

    with contextlib.suppress(SystemExit):
        cli(["sync", *sync_args])

    captured = capsys.readouterr()
    output = "".join([*caplog.messages, captured.out, captured.err])

    if expected_in_out is not None:
        if isinstance(expected_in_out, str):
            expected_in_out = [expected_in_out]
        for needle in expected_in_out:
            assert needle in output

    if expected_not_in_out is not None:
        if isinstance(expected_not_in_out, str):
            expected_not_in_out = [expected_not_in_out]
        for needle in expected_not_in_out:
            assert needle not in output


class SyncFixture(t.NamedTuple):
    """Pytest fixture for vcspull sync."""

    # pytest internal: used for naming test
    test_id: str

    # test params
    sync_args: list[str]
    expected_exit_code: int
    expected_in_out: ExpectedOutput = None
    expected_not_in_out: ExpectedOutput = None
    expected_in_err: ExpectedOutput = None
    expected_not_in_err: ExpectedOutput = None


SYNC_REPO_FIXTURES: list[SyncFixture] = [
    # Empty (root command)
    SyncFixture(
        test_id="empty",
        sync_args=[],
        expected_exit_code=0,
        expected_in_out=["{sync", "positional arguments:"],
    ),
    # Version
    SyncFixture(
        test_id="--version",
        sync_args=["--version"],
        expected_exit_code=0,
        expected_in_out=[__version__, ", libvcs"],
    ),
    SyncFixture(
        test_id="-V",
        sync_args=["-V"],
        expected_exit_code=0,
        expected_in_out=[__version__, ", libvcs"],
    ),
    # Help
    SyncFixture(
        test_id="--help",
        sync_args=["--help"],
        expected_exit_code=0,
        expected_in_out=["{sync", "positional arguments:"],
    ),
    SyncFixture(
        test_id="-h",
        sync_args=["-h"],
        expected_exit_code=0,
        expected_in_out=["{sync", "positional arguments:"],
    ),
    # Sync
    SyncFixture(
        test_id="sync--empty",
        sync_args=["sync"],
        expected_exit_code=0,
        expected_in_out=["positional arguments:"],
    ),
    # Sync: Help
    SyncFixture(
        test_id="sync---help",
        sync_args=["sync", "--help"],
        expected_exit_code=0,
        expected_in_out=["filter", "--exit-on-error"],
        expected_not_in_out="--version",
    ),
    SyncFixture(
        test_id="sync--h",
        sync_args=["sync", "-h"],
        expected_exit_code=0,
        expected_in_out=["filter", "--exit-on-error"],
        expected_not_in_out="--version",
    ),
    # Sync: Repo terms
    SyncFixture(
        test_id="sync--one-repo-term",
        sync_args=["sync", "my_git_repo"],
        expected_exit_code=0,
        expected_in_out="my_git_repo",
    ),
]


class SyncNewBehaviourFixture(t.NamedTuple):
    """Fixture for new sync flag behaviours."""

    test_id: str
    cli_args: list[str]
    expect_json: bool
    expected_stdout_contains: list[str]
    expected_log_contains: list[str]
    expected_summary: dict[str, int] | None


SYNC_NEW_BEHAVIOUR_FIXTURES: list[SyncNewBehaviourFixture] = [
    SyncNewBehaviourFixture(
        test_id="dry-run-human",
        cli_args=["sync", "--dry-run", "my_git_repo"],
        expect_json=False,
        expected_stdout_contains=["Would sync my_git_repo", "Summary"],
        expected_log_contains=["Would sync my_git_repo"],
        expected_summary=None,
    ),
    SyncNewBehaviourFixture(
        test_id="dry-run-json",
        cli_args=["sync", "--dry-run", "--json", "my_git_repo"],
        expect_json=True,
        expected_stdout_contains=[],
        expected_log_contains=[],
        expected_summary={"total": 1, "previewed": 1, "synced": 0, "failed": 0},
    ),
    SyncNewBehaviourFixture(
        test_id="workspace-filter-no-match",
        cli_args=["sync", "my_git_repo", "--workspace", "~/other/"],
        expect_json=False,
        expected_stdout_contains=["No repositories matched the criteria."],
        expected_log_contains=[],
        expected_summary=None,
    ),
]


class CLINegativeFixture(t.NamedTuple):
    """Fixture for CLI negative flow validation."""

    test_id: str
    cli_args: list[str]
    scenario: t.Literal["discover-non-dict-config", "status-missing-git"]
    expected_log_fragment: str | None
    expected_stdout_fragment: str | None


CLI_NEGATIVE_FIXTURES: list[CLINegativeFixture] = [
    CLINegativeFixture(
        test_id="discover-invalid-config",
        cli_args=["discover"],
        scenario="discover-non-dict-config",
        expected_log_fragment="not a valid YAML dictionary",
        expected_stdout_fragment=None,
    ),
    CLINegativeFixture(
        test_id="status-missing-git",
        cli_args=["status", "--detailed"],
        scenario="status-missing-git",
        expected_log_fragment=None,
        expected_stdout_fragment="Summary:",
    ),
]


@pytest.mark.parametrize(
    list(SyncFixture._fields),
    SYNC_REPO_FIXTURES,
    ids=[test.test_id for test in SYNC_REPO_FIXTURES],
)
def test_sync(
    tmp_path: pathlib.Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    user_path: pathlib.Path,
    config_path: pathlib.Path,
    git_repo: GitSync,
    test_id: str,
    sync_args: list[str],
    expected_exit_code: int,
    expected_in_out: ExpectedOutput,
    expected_not_in_out: ExpectedOutput,
    expected_in_err: ExpectedOutput,
    expected_not_in_err: ExpectedOutput,
) -> None:
    """Tests for vcspull sync."""
    config = {
        "~/github_projects/": {
            "my_git_repo": {
                "url": f"git+file://{git_repo.path}",
                "remotes": {"test_remote": f"git+file://{git_repo.path}"},
            },
            "broken_repo": {
                "url": f"git+file://{git_repo.path}",
                "remotes": {"test_remote": "git+file://non-existent-remote"},
            },
        },
    }
    yaml_config = config_path / ".vcspull.yaml"
    yaml_config_data = yaml.dump(config, default_flow_style=False)
    yaml_config.write_text(yaml_config_data, encoding="utf-8")

    # CLI can sync
    with contextlib.suppress(SystemExit):
        cli(sync_args)

    result = capsys.readouterr()
    output = "".join(list(result.out if expected_exit_code == 0 else result.err))

    if expected_in_out is not None:
        if isinstance(expected_in_out, str):
            expected_in_out = [expected_in_out]
        for needle in expected_in_out:
            assert needle in output

    if expected_not_in_out is not None:
        if isinstance(expected_not_in_out, str):
            expected_not_in_out = [expected_not_in_out]
        for needle in expected_not_in_out:
            assert needle not in output


class SyncBrokenFixture(t.NamedTuple):
    """Tests for vcspull  sync when something breaks."""

    # pytest internal: used for naming test
    test_id: str

    # test params
    sync_args: list[str]
    expected_exit_code: int
    expected_in_out: ExpectedOutput = None
    expected_not_in_out: ExpectedOutput = None
    expected_in_err: ExpectedOutput = None
    expected_not_in_err: ExpectedOutput = None


SYNC_BROKEN_REPO_FIXTURES: list[SyncBrokenFixture] = [
    SyncBrokenFixture(
        test_id="normal-checkout",
        sync_args=["my_git_repo"],
        expected_exit_code=0,
        expected_in_out="Already on 'master'",
    ),
    SyncBrokenFixture(
        test_id="normal-checkout--exit-on-error",
        sync_args=["my_git_repo", "--exit-on-error"],
        expected_exit_code=0,
        expected_in_out="Already on 'master'",
    ),
    SyncBrokenFixture(
        test_id="normal-checkout--x",
        sync_args=["my_git_repo", "-x"],
        expected_exit_code=0,
        expected_in_out="Already on 'master'",
    ),
    SyncBrokenFixture(
        test_id="normal-first-broken",
        sync_args=["my_git_repo_not_found", "my_git_repo"],
        expected_exit_code=0,
        expected_not_in_out=EXIT_ON_ERROR_MSG,
    ),
    SyncBrokenFixture(
        test_id="normal-last-broken",
        sync_args=["my_git_repo", "my_git_repo_not_found"],
        expected_exit_code=0,
        expected_not_in_out=EXIT_ON_ERROR_MSG,
    ),
    SyncBrokenFixture(
        test_id="exit-on-error--exit-on-error-first-broken",
        sync_args=["my_git_repo_not_found", "my_git_repo", "--exit-on-error"],
        expected_exit_code=1,
        expected_in_err=EXIT_ON_ERROR_MSG,
    ),
    SyncBrokenFixture(
        test_id="exit-on-error--x-first-broken",
        sync_args=["my_git_repo_not_found", "my_git_repo", "-x"],
        expected_exit_code=1,
        expected_in_err=EXIT_ON_ERROR_MSG,
        expected_not_in_out="master",
    ),
    #
    # Verify ordering
    #
    SyncBrokenFixture(
        test_id="exit-on-error--exit-on-error-last-broken",
        sync_args=["my_git_repo", "my_git_repo_not_found", "-x"],
        expected_exit_code=1,
        expected_in_out="Already on 'master'",
        expected_in_err=EXIT_ON_ERROR_MSG,
    ),
    SyncBrokenFixture(
        test_id="exit-on-error--x-last-item",
        sync_args=["my_git_repo", "my_git_repo_not_found", "--exit-on-error"],
        expected_exit_code=1,
        expected_in_out="Already on 'master'",
        expected_in_err=EXIT_ON_ERROR_MSG,
    ),
]


@pytest.mark.parametrize(
    list(SyncBrokenFixture._fields),
    SYNC_BROKEN_REPO_FIXTURES,
    ids=[test.test_id for test in SYNC_BROKEN_REPO_FIXTURES],
)
def test_sync_broken(
    tmp_path: pathlib.Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    user_path: pathlib.Path,
    config_path: pathlib.Path,
    git_repo: GitSync,
    test_id: str,
    sync_args: list[str],
    expected_exit_code: int,
    expected_in_out: ExpectedOutput,
    expected_not_in_out: ExpectedOutput,
    expected_in_err: ExpectedOutput,
    expected_not_in_err: ExpectedOutput,
) -> None:
    """Tests for syncing in vcspull when unexpected error occurs."""
    github_projects = user_path / "github_projects"
    my_git_repo = github_projects / "my_git_repo"
    if my_git_repo.is_dir():
        shutil.rmtree(my_git_repo)

    config = {
        "~/github_projects/": {
            "my_git_repo": {
                "url": f"git+file://{git_repo.path}",
                "remotes": {"test_remote": f"git+file://{git_repo.path}"},
            },
            "my_git_repo_not_found": {
                "url": "git+file:///dev/null",
            },
        },
    }
    yaml_config = config_path / ".vcspull.yaml"
    yaml_config_data = yaml.dump(config, default_flow_style=False)
    yaml_config.write_text(yaml_config_data, encoding="utf-8")

    # CLI can sync
    assert isinstance(sync_args, list)

    with contextlib.suppress(SystemExit):
        cli(["sync", *sync_args])

    result = capsys.readouterr()
    out = "".join(list(result.out))
    err = "".join(list(result.err))

    if expected_in_out is not None:
        if isinstance(expected_in_out, str):
            expected_in_out = [expected_in_out]
        for needle in expected_in_out:
            assert needle in out

    if expected_not_in_out is not None:
        if isinstance(expected_not_in_out, str):
            expected_not_in_out = [expected_not_in_out]
        for needle in expected_not_in_out:
            assert needle not in out

    if expected_in_err is not None:
        if isinstance(expected_in_err, str):
            expected_in_err = [expected_in_err]
        for needle in expected_in_err:
            assert needle in err

    if expected_not_in_err is not None:
        if isinstance(expected_not_in_err, str):
            expected_not_in_err = [expected_not_in_err]
        for needle in expected_not_in_err:
            assert needle not in err


@pytest.mark.parametrize(
    list(SyncNewBehaviourFixture._fields),
    SYNC_NEW_BEHAVIOUR_FIXTURES,
    ids=[fixture.test_id for fixture in SYNC_NEW_BEHAVIOUR_FIXTURES],
)
def test_sync_new_behaviours(
    test_id: str,
    cli_args: list[str],
    expect_json: bool,
    expected_stdout_contains: list[str],
    expected_log_contains: list[str],
    expected_summary: dict[str, int] | None,
    tmp_path: pathlib.Path,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
    user_path: pathlib.Path,
    config_path: pathlib.Path,
    git_repo: GitSync,
) -> None:
    """Test new sync behaviours such as dry-run preview and workspace filtering."""
    import logging

    caplog.set_level(logging.INFO)

    config = {
        "~/github_projects/": {
            "my_git_repo": {
                "url": f"git+file://{git_repo.path}",
                "remotes": {"origin": f"git+file://{git_repo.path}"},
            },
        },
    }
    yaml_config = config_path / ".vcspull.yaml"
    yaml_config.write_text(
        yaml.dump(config, default_flow_style=False), encoding="utf-8"
    )

    monkeypatch.chdir(tmp_path)

    with contextlib.suppress(SystemExit):
        cli(cli_args)

    captured = capsys.readouterr()
    stdout = "".join([captured.out, captured.err])

    for needle in expected_stdout_contains:
        assert needle in stdout

    for needle in expected_log_contains:
        assert needle in caplog.text

    if expect_json:
        start = captured.out.find("[")
        assert start >= 0, "Expected JSON payload in stdout"
        payload = json.loads(captured.out[start:])
        assert isinstance(payload, list)
        statuses = [event for event in payload if event.get("reason") == "sync"]
        assert any(event.get("status") == "preview" for event in statuses)
        summary = next(event for event in payload if event.get("reason") == "summary")
        assert expected_summary is not None
        assert summary["total"] == expected_summary["total"]
        assert summary["previewed"] == expected_summary["previewed"]
        assert summary["synced"] == expected_summary["synced"]
        assert summary["failed"] == expected_summary["failed"]


@pytest.mark.parametrize(
    list(CLINegativeFixture._fields),
    CLI_NEGATIVE_FIXTURES,
    ids=[fixture.test_id for fixture in CLI_NEGATIVE_FIXTURES],
)
def test_cli_negative_flows(
    test_id: str,
    cli_args: list[str],
    scenario: t.Literal["discover-non-dict-config", "status-missing-git"],
    expected_log_fragment: str | None,
    expected_stdout_fragment: str | None,
    tmp_path: pathlib.Path,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Exercise common CLI error flows without raising."""
    import logging
    import subprocess

    import yaml

    caplog.set_level(logging.INFO)

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)

    if scenario == "discover-non-dict-config":
        scan_dir = tmp_path / "scan"
        scan_dir.mkdir(parents=True, exist_ok=True)
        config_file = tmp_path / "config.yaml"
        config_file.write_text("[]\n", encoding="utf-8")

        with contextlib.suppress(SystemExit):
            cli([*cli_args, str(scan_dir), "--file", str(config_file)])
    else:
        workspace_dir = tmp_path / "workspace"
        repo_dir = workspace_dir / "project"
        repo_dir.mkdir(parents=True, exist_ok=True)
        (repo_dir / ".git").mkdir()

        config_file = tmp_path / "status.yaml"
        config_file.write_text(
            yaml.dump(
                {
                    "~/workspace/": {
                        "project": {
                            "url": "git+https://example.com/project.git",
                            "path": str(repo_dir),
                        },
                    },
                }
            ),
            encoding="utf-8",
        )

        def _missing_git(
            cmd: list[str], **kwargs: object
        ) -> subprocess.CompletedProcess[str]:
            if cmd and cmd[0] == "git":
                error_message = "git not installed"
                raise FileNotFoundError(error_message)
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

        monkeypatch.setattr("vcspull.cli.status.subprocess.run", _missing_git)

        with contextlib.suppress(SystemExit):
            cli([*cli_args, "--file", str(config_file)])

    captured = capsys.readouterr()

    if expected_log_fragment is not None:
        assert expected_log_fragment in caplog.text

    if expected_stdout_fragment is not None:
        assert expected_stdout_fragment in captured.out


def test_sync_ndjson_machine_output(
    tmp_path: pathlib.Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    user_path: pathlib.Path,
    config_path: pathlib.Path,
    git_repo: GitSync,
) -> None:
    """NDJSON mode should emit pure JSON lines without progress noise."""
    config = {
        "~/github_projects/": {
            "my_git_repo": {
                "url": f"git+file://{git_repo.path}",
                "remotes": {"origin": f"git+file://{git_repo.path}"},
            },
        },
    }
    yaml_config = config_path / ".vcspull.yaml"
    yaml_config.write_text(
        yaml.dump(config, default_flow_style=False), encoding="utf-8"
    )

    monkeypatch.chdir(tmp_path)

    with contextlib.suppress(SystemExit):
        cli(["sync", "--ndjson", "--dry-run", "my_git_repo"])

    captured = capsys.readouterr()
    ndjson_lines = [line for line in captured.out.splitlines() if line.strip()]
    assert ndjson_lines, "Expected NDJSON payload on stdout"

    events = [json.loads(line) for line in ndjson_lines]
    reasons = {event["reason"] for event in events}
    assert reasons >= {"sync", "summary"}
    preview_statuses = {
        event.get("status") for event in events if event["reason"] == "sync"
    }
    assert preview_statuses == {"preview"}


def test_sync_json_machine_output(
    tmp_path: pathlib.Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    user_path: pathlib.Path,
    config_path: pathlib.Path,
    git_repo: GitSync,
) -> None:
    """JSON mode should emit a single array without progress chatter."""
    config = {
        "~/github_projects/": {
            "my_git_repo": {
                "url": f"git+file://{git_repo.path}",
                "remotes": {"origin": f"git+file://{git_repo.path}"},
            },
        },
    }
    yaml_config = config_path / ".vcspull.yaml"
    yaml_config.write_text(
        yaml.dump(config, default_flow_style=False), encoding="utf-8"
    )

    monkeypatch.chdir(tmp_path)

    with contextlib.suppress(SystemExit):
        cli(["sync", "--json", "--dry-run", "my_git_repo"])

    captured = capsys.readouterr()
    payload = captured.out.strip()
    assert payload.startswith("[") and payload.endswith("]"), payload
    events = json.loads(payload)
    assert isinstance(events, list)
    reasons = {event["reason"] for event in events}
    assert reasons >= {"sync", "summary"}
