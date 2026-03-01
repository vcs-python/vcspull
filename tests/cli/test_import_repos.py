"""Tests for vcspull import command."""

from __future__ import annotations

import argparse
import json
import logging
import pathlib
import sys
import typing as t

import pytest

from vcspull._internal.remotes import (
    AuthenticationError,
    ConfigurationError,
    ImportOptions,
    NotFoundError,
    RateLimitError,
    RemoteRepo,
    ServiceUnavailableError,
)
from vcspull.cli.import_cmd._common import (
    ImportAction,
    _classify_import_action,
    _resolve_config_file,
    _run_import,
)
from vcspull.config import save_config_json, save_config_yaml, workspace_root_label

# Get the actual _common module for monkeypatching
import_common_mod = sys.modules["vcspull.cli.import_cmd._common"]

if t.TYPE_CHECKING:
    from _pytest.monkeypatch import MonkeyPatch


def _make_repo(
    name: str,
    owner: str = "testuser",
    stars: int = 10,
    language: str = "Python",
) -> RemoteRepo:
    """Create a RemoteRepo for testing."""
    return RemoteRepo(
        name=name,
        clone_url=f"https://github.com/{owner}/{name}.git",
        ssh_url=f"git@github.com:{owner}/{name}.git",
        html_url=f"https://github.com/{owner}/{name}",
        description=f"Test repo {name}",
        language=language,
        topics=(),
        stars=stars,
        is_fork=False,
        is_archived=False,
        default_branch="main",
        owner=owner,
    )


def _run_import_defaults(
    importer: t.Any,
    *,
    service_name: str = "github",
    target: str = "testuser",
    workspace: str = "",
    mode: str = "user",
    language: str | None = None,
    topics: str | None = None,
    min_stars: int = 0,
    include_archived: bool = False,
    include_forks: bool = False,
    limit: int = 100,
    config_path_str: str | None = None,
    dry_run: bool = False,
    yes: bool = True,
    output_json: bool = False,
    output_ndjson: bool = False,
    color: str = "never",
    **extra_kwargs: t.Any,
) -> int:
    """Call _run_import with test-friendly defaults for 9 filter/display kwargs.

    The 9 kwargs with test-friendly defaults are: ``language``, ``topics``,
    ``min_stars``, ``include_archived``, ``include_forks``, ``limit``,
    ``output_json``, ``output_ndjson``, and ``color``.  Callers only need
    to supply kwargs that differ from these defaults.

    Parameters
    ----------
    importer : t.Any
        Mock importer instance (satisfies the Importer protocol).
    service_name : str
        Service name, defaults to ``"github"``.
    target : str
        Target user/org/query, defaults to ``"testuser"``.
    workspace : str
        Workspace root directory path.
    mode : str
        Import mode, defaults to ``"user"``.
    language : str | None
        Language filter, defaults to ``None``.
    topics : str | None
        Topics filter, defaults to ``None``.
    min_stars : int
        Minimum star count, defaults to ``0``.
    include_archived : bool
        Include archived repos, defaults to ``False``.
    include_forks : bool
        Include forked repos, defaults to ``False``.
    limit : int
        Repo fetch limit, defaults to ``100``.
    config_path_str : str | None
        Config file path, defaults to ``None``.
    dry_run : bool
        Dry-run mode, defaults to ``False``.
    yes : bool
        Auto-confirm, defaults to ``True``.
    output_json : bool
        JSON output, defaults to ``False``.
    output_ndjson : bool
        NDJSON output, defaults to ``False``.
    color : str
        Color mode, defaults to ``"never"``.
    **extra_kwargs : t.Any
        Forwarded to ``_run_import`` (e.g. ``use_https``, ``flatten_groups``).

    Returns
    -------
    int
        Exit code from ``_run_import``.

    Examples
    --------
    >>> _run_import_defaults.__name__
    '_run_import_defaults'
    """
    return _run_import(
        importer,
        service_name=service_name,
        target=target,
        workspace=workspace,
        mode=mode,
        language=language,
        topics=topics,
        min_stars=min_stars,
        include_archived=include_archived,
        include_forks=include_forks,
        limit=limit,
        config_path_str=config_path_str,
        dry_run=dry_run,
        yes=yes,
        output_json=output_json,
        output_ndjson=output_ndjson,
        color=color,
        **extra_kwargs,
    )


class MockImporter:
    """Reusable mock importer for tests."""

    def __init__(
        self,
        *,
        service_name: str = "MockService",
        repos: list[RemoteRepo] | None = None,
        error: Exception | None = None,
    ) -> None:
        self.service_name = service_name
        self._repos = repos or []
        self._error = error

    def fetch_repos(
        self,
        options: ImportOptions,
    ) -> t.Iterator[RemoteRepo]:
        """Yield mock repos or raise a mock error."""
        if self._error:
            raise self._error
        yield from self._repos


class CapturingMockImporter:
    """Mock importer that captures the ImportOptions passed to fetch_repos."""

    def __init__(
        self,
        *,
        service_name: str = "MockService",
        repos: list[RemoteRepo] | None = None,
    ) -> None:
        self.service_name = service_name
        self._repos = repos or []
        self.captured_options: ImportOptions | None = None

    def fetch_repos(
        self,
        options: ImportOptions,
    ) -> t.Iterator[RemoteRepo]:
        """Capture options and yield repos."""
        self.captured_options = options
        yield from self._repos


class ResolveConfigFixture(t.NamedTuple):
    """Fixture for _resolve_config_file test cases."""

    test_id: str
    config_path_str: str | None
    home_configs: list[str]
    expected_suffix: str


RESOLVE_CONFIG_FIXTURES: list[ResolveConfigFixture] = [
    ResolveConfigFixture(
        test_id="explicit-path-used",
        config_path_str="/custom/config.yaml",
        home_configs=[],
        expected_suffix="config.yaml",
    ),
    ResolveConfigFixture(
        test_id="tilde-expanded",
        config_path_str="~/myconfig.yaml",
        home_configs=[],
        expected_suffix="myconfig.yaml",
    ),
    ResolveConfigFixture(
        test_id="home-config-found",
        config_path_str=None,
        home_configs=["existing.yaml"],
        expected_suffix="existing.yaml",
    ),
    ResolveConfigFixture(
        test_id="default-when-no-home-config",
        config_path_str=None,
        home_configs=[],
        expected_suffix=".vcspull.yaml",
    ),
    ResolveConfigFixture(
        test_id="yml-extension-accepted",
        config_path_str="/custom/config.yml",
        home_configs=[],
        expected_suffix="config.yml",
    ),
    ResolveConfigFixture(
        test_id="json-extension-accepted",
        config_path_str="/custom/config.json",
        home_configs=[],
        expected_suffix="config.json",
    ),
]


@pytest.mark.parametrize(
    list(ResolveConfigFixture._fields),
    RESOLVE_CONFIG_FIXTURES,
    ids=[f.test_id for f in RESOLVE_CONFIG_FIXTURES],
)
def test_resolve_config_file(
    test_id: str,
    config_path_str: str | None,
    home_configs: list[str],
    expected_suffix: str,
    tmp_path: pathlib.Path,
    monkeypatch: MonkeyPatch,
) -> None:
    """Test _resolve_config_file handles various config scenarios."""
    monkeypatch.setenv("HOME", str(tmp_path))

    # Create home config files if needed
    full_paths = []
    for cfg in home_configs:
        cfg_path = tmp_path / cfg
        cfg_path.touch()
        full_paths.append(cfg_path)

    # Mock find_home_config_files: return pre-created config file paths
    # instead of scanning the real home directory
    monkeypatch.setattr(
        import_common_mod,
        "find_home_config_files",
        lambda filetype=None: full_paths,
    )

    result = _resolve_config_file(config_path_str)
    assert result.name == expected_suffix


def test_resolve_config_file_accepts_extensionless_symlink_alias(
    tmp_path: pathlib.Path,
    monkeypatch: MonkeyPatch,
) -> None:
    """Explicit alias paths should inherit a supported target config format."""
    monkeypatch.setenv("HOME", str(tmp_path))

    real_config = tmp_path / ".vcspull.yaml"
    real_config.write_text("~/repos/: {}\n", encoding="utf-8")

    alias_path = tmp_path / "vcspull-config"
    alias_path.symlink_to(real_config)

    result = _resolve_config_file(str(alias_path))

    assert result == alias_path
    assert result.suffix == ""
    assert result.resolve() == real_config.resolve()


class ImportReposFixture(t.NamedTuple):
    """Fixture for _run_import test cases."""

    test_id: str
    service_name: str
    target: str
    mode: str
    dry_run: bool
    yes: bool
    output_json: bool
    mock_repos: list[RemoteRepo]
    mock_error: Exception | None
    expected_log_contains: list[str]
    expected_config_repos: int


IMPORT_REPOS_FIXTURES: list[ImportReposFixture] = [
    ImportReposFixture(
        test_id="basic-github-user-dry-run",
        service_name="github",
        target="testuser",
        mode="user",
        dry_run=True,
        yes=True,
        output_json=False,
        mock_repos=[_make_repo("repo1"), _make_repo("repo2")],
        mock_error=None,
        expected_log_contains=["Found 2 repositories", "Dry run complete"],
        expected_config_repos=0,
    ),
    ImportReposFixture(
        test_id="dry-run-without-yes-skips-confirmation",
        service_name="github",
        target="testuser",
        mode="user",
        dry_run=True,
        yes=False,
        output_json=False,
        mock_repos=[_make_repo("repo1"), _make_repo("repo2")],
        mock_error=None,
        expected_log_contains=["Found 2 repositories", "Dry run complete"],
        expected_config_repos=0,
    ),
    ImportReposFixture(
        test_id="github-user-writes-config",
        service_name="github",
        target="testuser",
        mode="user",
        dry_run=False,
        yes=True,
        output_json=False,
        mock_repos=[_make_repo("repo1")],
        mock_error=None,
        expected_log_contains=["Added 1 repositories"],
        expected_config_repos=1,
    ),
    ImportReposFixture(
        test_id="no-repos-found",
        service_name="github",
        target="emptyuser",
        mode="user",
        dry_run=False,
        yes=True,
        output_json=False,
        mock_repos=[],
        mock_error=None,
        expected_log_contains=["No repositories found"],
        expected_config_repos=0,
    ),
    ImportReposFixture(
        test_id="authentication-error",
        service_name="github",
        target="testuser",
        mode="user",
        dry_run=False,
        yes=True,
        output_json=False,
        mock_repos=[],
        mock_error=AuthenticationError("Bad credentials"),
        expected_log_contains=["Authentication error"],
        expected_config_repos=0,
    ),
    ImportReposFixture(
        test_id="rate-limit-error",
        service_name="github",
        target="testuser",
        mode="user",
        dry_run=False,
        yes=True,
        output_json=False,
        mock_repos=[],
        mock_error=RateLimitError("Rate limit exceeded"),
        expected_log_contains=["Rate limit exceeded"],
        expected_config_repos=0,
    ),
    ImportReposFixture(
        test_id="not-found-error",
        service_name="github",
        target="nosuchuser",
        mode="user",
        dry_run=False,
        yes=True,
        output_json=False,
        mock_repos=[],
        mock_error=NotFoundError("User not found"),
        expected_log_contains=["Not found"],
        expected_config_repos=0,
    ),
    ImportReposFixture(
        test_id="service-unavailable-error",
        service_name="github",
        target="testuser",
        mode="user",
        dry_run=False,
        yes=True,
        output_json=False,
        mock_repos=[],
        mock_error=ServiceUnavailableError("Server error"),
        expected_log_contains=["Service unavailable"],
        expected_config_repos=0,
    ),
    ImportReposFixture(
        test_id="configuration-error",
        service_name="codecommit",
        target="",
        mode="user",
        dry_run=False,
        yes=True,
        output_json=False,
        mock_repos=[],
        mock_error=ConfigurationError("Invalid region"),
        expected_log_contains=["Configuration error"],
        expected_config_repos=0,
    ),
    ImportReposFixture(
        test_id="gitlab-org-mode",
        service_name="gitlab",
        target="testgroup",
        mode="org",
        dry_run=True,
        yes=True,
        output_json=False,
        mock_repos=[_make_repo("group-project")],
        mock_error=None,
        expected_log_contains=["Found 1 repositories"],
        expected_config_repos=0,
    ),
    ImportReposFixture(
        test_id="codeberg-search-mode",
        service_name="codeberg",
        target="python cli",
        mode="search",
        dry_run=True,
        yes=True,
        output_json=False,
        mock_repos=[_make_repo("cli-tool", stars=100)],
        mock_error=None,
        expected_log_contains=["Found 1 repositories"],
        expected_config_repos=0,
    ),
]


@pytest.mark.parametrize(
    list(ImportReposFixture._fields),
    IMPORT_REPOS_FIXTURES,
    ids=[f.test_id for f in IMPORT_REPOS_FIXTURES],
)
def test_import_repos(
    test_id: str,
    service_name: str,
    target: str,
    mode: str,
    dry_run: bool,
    yes: bool,
    output_json: bool,
    mock_repos: list[RemoteRepo],
    mock_error: Exception | None,
    expected_log_contains: list[str],
    expected_config_repos: int,
    tmp_path: pathlib.Path,
    monkeypatch: MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test _run_import with various scenarios."""
    caplog.set_level(logging.INFO)

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)

    workspace = tmp_path / "repos"
    workspace.mkdir()
    config_file = tmp_path / ".vcspull.yaml"

    importer = MockImporter(repos=mock_repos, error=mock_error)

    _run_import_defaults(
        importer,
        service_name=service_name,
        target=target,
        workspace=str(workspace),
        mode=mode,
        config_path_str=str(config_file),
        dry_run=dry_run,
        yes=yes,
        output_json=output_json,
    )

    for expected_text in expected_log_contains:
        assert expected_text in caplog.text, (
            f"Expected '{expected_text}' in log, got: {caplog.text}"
        )

    if expected_config_repos > 0:
        assert config_file.exists()
        import yaml

        with config_file.open() as f:
            config = yaml.safe_load(f)
        assert config is not None
        total_repos = sum(len(repos) for repos in config.values())
        assert total_repos == expected_config_repos


def test_import_repos_user_abort(
    tmp_path: pathlib.Path,
    monkeypatch: MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test _run_import aborts when user declines confirmation."""
    caplog.set_level(logging.INFO)

    monkeypatch.setenv("HOME", str(tmp_path))
    workspace = tmp_path / "repos"
    workspace.mkdir()
    config_file = tmp_path / ".vcspull.yaml"

    # Mock builtins.input: simulate user typing "n" to decline confirmation
    monkeypatch.setattr("builtins.input", lambda _: "n")
    # Mock sys.stdin: fake TTY so the confirmation prompt is shown
    monkeypatch.setattr(
        "sys.stdin", type("FakeTTY", (), {"isatty": lambda self: True})()
    )

    importer = MockImporter(repos=[_make_repo("repo1")])

    _run_import_defaults(
        importer,
        workspace=str(workspace),
        config_path_str=str(config_file),
        yes=False,  # Require confirmation
    )

    assert "Aborted by user" in caplog.text
    assert not config_file.exists()


def test_import_repos_eoferror_aborts(
    tmp_path: pathlib.Path,
    monkeypatch: MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test _run_import aborts gracefully on EOFError from input()."""
    caplog.set_level(logging.INFO)

    monkeypatch.setenv("HOME", str(tmp_path))
    workspace = tmp_path / "repos"
    workspace.mkdir()
    config_file = tmp_path / ".vcspull.yaml"

    # Mock input() to raise EOFError (e.g., piped stdin)
    def raise_eof(_: str) -> str:
        raise EOFError

    # Mock builtins.input: simulate EOFError from piped/closed stdin
    monkeypatch.setattr("builtins.input", raise_eof)
    # Mock sys.stdin: fake TTY so the confirmation prompt path is exercised
    monkeypatch.setattr(
        "sys.stdin", type("FakeTTY", (), {"isatty": lambda self: True})()
    )

    importer = MockImporter(repos=[_make_repo("repo1")])

    _run_import_defaults(
        importer,
        workspace=str(workspace),
        config_path_str=str(config_file),
        yes=False,
    )

    assert "Aborted by user" in caplog.text
    assert not config_file.exists()


def test_import_repos_non_tty_aborts(
    tmp_path: pathlib.Path,
    monkeypatch: MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test _run_import aborts when stdin is not a TTY."""
    caplog.set_level(logging.INFO)

    monkeypatch.setenv("HOME", str(tmp_path))
    workspace = tmp_path / "repos"
    workspace.mkdir()
    config_file = tmp_path / ".vcspull.yaml"

    # Mock sys.stdin: fake non-TTY to test non-interactive abort path
    monkeypatch.setattr(
        "sys.stdin", type("FakeNonTTY", (), {"isatty": lambda self: False})()
    )

    importer = MockImporter(repos=[_make_repo("repo1")])

    result = _run_import_defaults(
        importer,
        workspace=str(workspace),
        config_path_str=str(config_file),
        yes=False,
    )

    assert result == 1, "Non-interactive abort must return non-zero exit code"
    assert "Non-interactive mode" in caplog.text
    assert not config_file.exists()


def test_import_repos_skips_existing(
    tmp_path: pathlib.Path,
    monkeypatch: MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test _run_import skips repositories already in config."""
    import yaml

    caplog.set_level(logging.INFO)

    monkeypatch.setenv("HOME", str(tmp_path))
    workspace = tmp_path / "repos"
    workspace.mkdir()
    config_file = tmp_path / ".vcspull.yaml"

    # Create existing config with repo1
    existing_config = {
        "~/repos/": {
            "repo1": {"repo": "git+https://github.com/testuser/repo1.git"},
        }
    }
    save_config_yaml(config_file, existing_config)

    importer = MockImporter(repos=[_make_repo("repo1"), _make_repo("repo2")])

    _run_import_defaults(
        importer,
        workspace=str(workspace),
        config_path_str=str(config_file),
    )

    assert "Added 1 repositories" in caplog.text
    assert "Skipped 1 existing" in caplog.text

    with config_file.open() as f:
        final_config = yaml.safe_load(f)

    assert "repo1" in final_config["~/repos/"]
    assert "repo2" in final_config["~/repos/"]


def test_import_repos_all_existing(
    tmp_path: pathlib.Path,
    monkeypatch: MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test _run_import handles all repos already existing."""
    caplog.set_level(logging.INFO)

    monkeypatch.setenv("HOME", str(tmp_path))
    workspace = tmp_path / "repos"
    workspace.mkdir()
    config_file = tmp_path / ".vcspull.yaml"

    # Create existing config with repo1 using SSH URL (matches default import URL)
    existing_config = {
        "~/repos/": {
            "repo1": {"repo": "git+git@github.com:testuser/repo1.git"},
        }
    }
    save_config_yaml(config_file, existing_config)

    importer = MockImporter(repos=[_make_repo("repo1")])

    _run_import_defaults(
        importer,
        workspace=str(workspace),
        config_path_str=str(config_file),
    )

    assert "All repositories already exist" in caplog.text


def test_import_repos_json_output(
    tmp_path: pathlib.Path,
    monkeypatch: MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Test _run_import JSON output format."""
    monkeypatch.setenv("HOME", str(tmp_path))
    workspace = tmp_path / "repos"
    workspace.mkdir()

    importer = MockImporter(repos=[_make_repo("repo1", stars=50)])

    _run_import_defaults(
        importer,
        workspace=str(workspace),
        config_path_str=str(tmp_path / "config.yaml"),
        dry_run=True,
        output_json=True,
    )

    captured = capsys.readouterr()
    output = json.loads(captured.out)

    assert isinstance(output, list)
    assert len(output) == 1
    assert output[0]["name"] == "repo1"
    assert output[0]["stars"] == 50


def test_import_repos_ndjson_output(
    tmp_path: pathlib.Path,
    monkeypatch: MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Test _run_import NDJSON output format."""
    monkeypatch.setenv("HOME", str(tmp_path))
    workspace = tmp_path / "repos"
    workspace.mkdir()

    importer = MockImporter(repos=[_make_repo("repo1"), _make_repo("repo2")])

    _run_import_defaults(
        importer,
        workspace=str(workspace),
        config_path_str=str(tmp_path / "config.yaml"),
        dry_run=True,
        output_ndjson=True,
    )

    captured = capsys.readouterr()
    lines = captured.out.strip().split("\n")

    assert len(lines) == 2
    assert json.loads(lines[0])["name"] == "repo1"
    assert json.loads(lines[1])["name"] == "repo2"


def test_import_repos_topics_filter(
    tmp_path: pathlib.Path,
    monkeypatch: MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test _run_import passes topics filter correctly."""
    caplog.set_level(logging.INFO)

    monkeypatch.setenv("HOME", str(tmp_path))
    workspace = tmp_path / "repos"
    workspace.mkdir()

    received_options: list[ImportOptions] = []

    class CapturingImporter:
        service_name = "MockService"

        def fetch_repos(
            self,
            options: ImportOptions,
        ) -> t.Iterator[RemoteRepo]:
            received_options.append(options)
            return iter([])

    _run_import_defaults(
        CapturingImporter(),
        workspace=str(workspace),
        language="Python",
        topics="cli,tool,python",
        min_stars=50,
        include_archived=True,
        include_forks=True,
        limit=200,
        config_path_str=str(tmp_path / "config.yaml"),
        dry_run=True,
    )

    assert len(received_options) == 1
    opts = received_options[0]
    assert opts.language == "Python"
    assert opts.topics == ["cli", "tool", "python"]
    assert opts.min_stars == 50
    assert opts.include_archived is True
    assert opts.include_forks is True
    assert opts.limit == 200


def test_import_repos_codecommit_no_target_required(
    tmp_path: pathlib.Path,
    monkeypatch: MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test _run_import allows empty target for codecommit."""
    caplog.set_level(logging.INFO)

    monkeypatch.setenv("HOME", str(tmp_path))
    workspace = tmp_path / "repos"
    workspace.mkdir()

    importer = MockImporter(
        service_name="CodeCommit",
        repos=[_make_repo("aws-repo")],
    )

    _run_import_defaults(
        importer,
        service_name="codecommit",
        target="",  # Empty target is OK for CodeCommit
        workspace=str(workspace),
        config_path_str=str(tmp_path / "config.yaml"),
        dry_run=True,
    )

    # Should succeed and find repos
    assert "Found 1 repositories" in caplog.text
    # Should NOT have target required error
    assert "TARGET is required" not in caplog.text


def test_import_repos_many_repos_truncates_preview(
    tmp_path: pathlib.Path,
    monkeypatch: MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test _run_import shows '...and X more' when many repos."""
    caplog.set_level(logging.INFO)

    monkeypatch.setenv("HOME", str(tmp_path))
    workspace = tmp_path / "repos"
    workspace.mkdir()

    # Create 15 repos
    many_repos = [_make_repo(f"repo{i}") for i in range(15)]

    importer = MockImporter(repos=many_repos)

    _run_import_defaults(
        importer,
        workspace=str(workspace),
        config_path_str=str(tmp_path / "config.yaml"),
        dry_run=True,
    )

    assert "Found 15 repositories" in caplog.text
    assert "and 5 more" in caplog.text


def test_import_repos_config_load_error(
    tmp_path: pathlib.Path,
    monkeypatch: MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test _run_import handles config load errors."""
    caplog.set_level(logging.ERROR)

    monkeypatch.setenv("HOME", str(tmp_path))
    workspace = tmp_path / "repos"
    workspace.mkdir()

    # Create an invalid YAML file
    config_file = tmp_path / ".vcspull.yaml"
    config_file.write_text("invalid: yaml: content: [", encoding="utf-8")

    importer = MockImporter(repos=[_make_repo("repo1")])

    _run_import_defaults(
        importer,
        workspace=str(workspace),
        config_path_str=str(config_file),
    )

    assert "Error loading config" in caplog.text


def test_import_repos_duplicate_workspace_roots_preserved(
    tmp_path: pathlib.Path,
    monkeypatch: MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test _run_import preserves repos from duplicate workspace root sections.

    PyYAML's default SafeLoader silently drops duplicate keys, so a config
    with two ``~/code/`` sections would lose repos from the first section.
    Using DuplicateAwareConfigReader + merge_duplicate_workspace_roots
    ensures all repos are preserved.
    """
    import yaml

    caplog.set_level(logging.INFO)

    monkeypatch.setenv("HOME", str(tmp_path))
    workspace = tmp_path / "repos"
    workspace.mkdir()

    config_file = tmp_path / ".vcspull.yaml"
    # Manually write duplicate workspace roots (can't use yaml.dump for this)
    config_file.write_text(
        "~/code/:\n"
        "  existing-repo-a:\n"
        "    repo: git+https://github.com/user/existing-repo-a.git\n"
        "~/code/:\n"
        "  existing-repo-b:\n"
        "    repo: git+https://github.com/user/existing-repo-b.git\n",
        encoding="utf-8",
    )

    # Import a new repo into a different workspace
    importer = MockImporter(repos=[_make_repo("new-repo")])

    result = _run_import(
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
    )

    assert result == 0

    # Reload and verify both original repos are still present
    saved = yaml.safe_load(config_file.read_text(encoding="utf-8"))
    assert "existing-repo-a" in saved["~/code/"]
    assert "existing-repo-b" in saved["~/code/"]


def test_import_repos_workspace_normalization_no_duplicate_section(
    tmp_path: pathlib.Path,
    monkeypatch: MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test _run_import normalizes workspace labels to avoid duplicates.

    When existing config has ``~/code`` (no trailing slash) and the import
    workspace resolves to ``~/code/``, repos should be added under the
    existing ``~/code`` section instead of creating a new ``~/code/`` section.
    """
    import yaml

    caplog.set_level(logging.INFO)

    monkeypatch.setenv("HOME", str(tmp_path))

    # Create the workspace directory that the label refers to
    code_dir = tmp_path / "code"
    code_dir.mkdir()

    config_file = tmp_path / ".vcspull.yaml"
    # Existing config uses ~/code (no trailing slash)
    save_config_yaml(
        config_file,
        {
            "~/code": {
                "existing-repo": {
                    "repo": "git+https://github.com/user/existing-repo.git"
                },
            },
        },
    )

    importer = MockImporter(repos=[_make_repo("new-repo")])

    result = _run_import(
        importer,
        service_name="github",
        target="testuser",
        # workspace resolves to ~/code/ (with trailing slash via label)
        workspace=str(code_dir),
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
    )

    assert result == 0

    saved = yaml.safe_load(config_file.read_text(encoding="utf-8"))
    # Both repos should be under the same section — no duplicate key created
    assert "~/code" in saved
    assert "existing-repo" in saved["~/code"]
    assert "new-repo" in saved["~/code"]
    # No separate ~/code/ section
    assert "~/code/" not in saved or saved.get("~/code/") is None


def test_import_repos_dry_run_tolerates_malformed_config(
    tmp_path: pathlib.Path,
    monkeypatch: MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test --dry-run previews even when config file is malformed.

    Instead of returning exit code 1, dry-run should warn and preview
    against an empty config.
    """
    caplog.set_level(logging.WARNING)

    monkeypatch.setenv("HOME", str(tmp_path))
    workspace = tmp_path / "repos"
    workspace.mkdir()

    config_file = tmp_path / ".vcspull.yaml"
    config_file.write_text("invalid: yaml: content: [", encoding="utf-8")

    importer = MockImporter(repos=[_make_repo("repo1")])

    result = _run_import(
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
        dry_run=True,
        yes=True,
        output_json=False,
        output_ndjson=False,
        color="never",
    )

    assert result == 0
    assert "dry-run will preview against empty config" in caplog.text


def test_import_repos_dry_run_tolerates_non_dict_config(
    tmp_path: pathlib.Path,
    monkeypatch: MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test --dry-run handles a YAML list (non-dict) config gracefully."""
    caplog.set_level(logging.WARNING)

    monkeypatch.setenv("HOME", str(tmp_path))
    workspace = tmp_path / "repos"
    workspace.mkdir()

    config_file = tmp_path / ".vcspull.yaml"
    config_file.write_text("- item1\n- item2\n", encoding="utf-8")

    importer = MockImporter(repos=[_make_repo("repo1")])

    result = _run_import(
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
        dry_run=True,
        yes=True,
        output_json=False,
        output_ndjson=False,
        color="never",
    )

    assert result == 0
    assert "dry-run will preview against empty config" in caplog.text


def test_import_repos_skip_unchanged_counter(
    tmp_path: pathlib.Path,
    monkeypatch: MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that SKIP_UNCHANGED repos are counted in summary output."""
    caplog.set_level(logging.INFO)

    monkeypatch.setenv("HOME", str(tmp_path))
    workspace = tmp_path / "repos"
    workspace.mkdir()

    workspace_label = workspace_root_label(
        workspace, cwd=pathlib.Path.cwd(), home=tmp_path
    )

    config_file = tmp_path / ".vcspull.yaml"
    # Pre-populate with a repo whose URL matches what the importer returns
    save_config_yaml(
        config_file,
        {
            workspace_label: {
                "repo1": {"repo": "git+git@github.com:testuser/repo1.git"},
            },
        },
    )

    importer = MockImporter(repos=[_make_repo("repo1")])

    result = _run_import(
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
    )

    assert result == 0
    assert "1 repositories unchanged" in caplog.text


def test_import_no_args_shows_help(capsys: pytest.CaptureFixture[str]) -> None:
    """Test that 'vcspull import' without args shows help."""
    from vcspull.cli import cli

    cli(["import"])

    captured = capsys.readouterr()
    assert "usage: vcspull import" in captured.out
    assert "Import repositories from remote services" in captured.out


class UrlSchemeFixture(t.NamedTuple):
    """Fixture for SSH vs HTTPS URL scheme test cases."""

    test_id: str
    use_https: bool
    expected_url: str


URL_SCHEME_FIXTURES: list[UrlSchemeFixture] = [
    UrlSchemeFixture(
        test_id="defaults-to-ssh-urls",
        use_https=False,
        expected_url="git+git@github.com:testuser/myrepo.git",
    ),
    UrlSchemeFixture(
        test_id="https-flag-writes-https-urls",
        use_https=True,
        expected_url="git+https://github.com/testuser/myrepo.git",
    ),
]


@pytest.mark.parametrize(
    list(UrlSchemeFixture._fields),
    URL_SCHEME_FIXTURES,
    ids=[f.test_id for f in URL_SCHEME_FIXTURES],
)
def test_import_repos_url_scheme(
    test_id: str,
    use_https: bool,
    expected_url: str,
    tmp_path: pathlib.Path,
    monkeypatch: MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test _run_import writes SSH or HTTPS URLs based on use_https flag."""
    import yaml

    del test_id
    caplog.set_level(logging.INFO)

    monkeypatch.setenv("HOME", str(tmp_path))
    workspace = tmp_path / "repos"
    workspace.mkdir()
    config_file = tmp_path / ".vcspull.yaml"

    importer = MockImporter(repos=[_make_repo("myrepo")])

    _run_import_defaults(
        importer,
        workspace=str(workspace),
        config_path_str=str(config_file),
        use_https=use_https,
    )

    assert config_file.exists()
    with config_file.open() as f:
        config = yaml.safe_load(f)

    repo_url = config["~/repos/"]["myrepo"]["repo"]
    assert repo_url == expected_url


class UrlSchemeCliFixture(t.NamedTuple):
    """Fixture for SSH vs HTTPS CLI flag test cases."""

    test_id: str
    extra_args: list[str]
    expected_use_https: bool


URL_SCHEME_CLI_FIXTURES: list[UrlSchemeCliFixture] = [
    UrlSchemeCliFixture(
        test_id="https-flag-via-cli",
        extra_args=["--https"],
        expected_use_https=True,
    ),
    UrlSchemeCliFixture(
        test_id="ssh-default-via-cli",
        extra_args=[],
        expected_use_https=False,
    ),
]


@pytest.mark.parametrize(
    list(UrlSchemeCliFixture._fields),
    URL_SCHEME_CLI_FIXTURES,
    ids=[f.test_id for f in URL_SCHEME_CLI_FIXTURES],
)
def test_import_url_scheme_via_cli(
    test_id: str,
    extra_args: list[str],
    expected_use_https: bool,
) -> None:
    """Test that --https flag controls use_https in the CLI parser."""
    del test_id
    from vcspull.cli import create_parser

    parser = create_parser(return_subparsers=False)
    args = parser.parse_args(
        ["import", "github", "testuser", "-w", "/tmp/repos", *extra_args]
    )
    assert args.use_https is expected_use_https


def test_import_flatten_groups_flag_via_cli() -> None:
    """Test that --flatten-groups flag is recognized by the GitLab subparser."""
    from vcspull.cli import create_parser

    parser = create_parser(return_subparsers=False)
    args = parser.parse_args(
        ["import", "gitlab", "group/subgroup", "-w", "/tmp/repos", "--flatten-groups"]
    )
    assert args.flatten_groups is True


def test_import_with_shared_flag_via_cli() -> None:
    """Test that --with-shared flag is recognized by the GitLab subparser."""
    from vcspull.cli import create_parser

    parser = create_parser(return_subparsers=False)
    args = parser.parse_args(
        ["import", "gitlab", "my-group", "-w", "/tmp/repos", "--with-shared"]
    )
    assert args.with_shared is True


def test_import_skip_group_flag_via_cli() -> None:
    """Test that --skip-group is recognized and repeatable by the GitLab subparser."""
    from vcspull.cli import create_parser

    parser = create_parser(return_subparsers=False)
    args = parser.parse_args(
        [
            "import",
            "gitlab",
            "my-group",
            "-w",
            "/tmp/repos",
            "--skip-group",
            "bots",
            "--skip-group",
            "archived",
        ]
    )
    assert args.skip_groups == ["bots", "archived"]


def test_import_repos_rejects_unsupported_config_type(
    tmp_path: pathlib.Path,
    monkeypatch: MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test _run_import rejects unsupported config file types."""
    caplog.set_level(logging.ERROR)

    monkeypatch.setenv("HOME", str(tmp_path))
    workspace = tmp_path / "repos"
    workspace.mkdir()

    importer = MockImporter(repos=[_make_repo("repo1")])

    _run_import_defaults(
        importer,
        workspace=str(workspace),
        config_path_str=str(tmp_path / "config.toml"),
    )

    assert "Unsupported config file type" in caplog.text


def test_import_repos_catches_multiple_config_warning(
    tmp_path: pathlib.Path,
    monkeypatch: MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test _run_import logs error instead of crashing on MultipleConfigWarning."""
    from vcspull.exc import MultipleConfigWarning

    caplog.set_level(logging.ERROR)

    monkeypatch.setenv("HOME", str(tmp_path))
    workspace = tmp_path / "repos"
    workspace.mkdir()

    importer = MockImporter(repos=[_make_repo("repo1")])

    # Mock _resolve_config_file: raise MultipleConfigWarning to test error handling
    def raise_multiple_config(_: str | None) -> pathlib.Path:
        raise MultipleConfigWarning(MultipleConfigWarning.message)

    monkeypatch.setattr(
        import_common_mod,
        "_resolve_config_file",
        raise_multiple_config,
    )

    _run_import_defaults(
        importer,
        workspace=str(workspace),
        config_path_str=None,
    )

    assert "Multiple configs" in caplog.text


def test_import_repos_invalid_limit(
    tmp_path: pathlib.Path,
    monkeypatch: MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test _run_import logs error for invalid limit (e.g. -1)."""
    caplog.set_level(logging.ERROR)

    monkeypatch.setenv("HOME", str(tmp_path))
    workspace = tmp_path / "repos"
    workspace.mkdir()

    importer = MockImporter(repos=[_make_repo("repo1")])

    _run_import_defaults(
        importer,
        workspace=str(workspace),
        limit=-1,
        config_path_str=str(tmp_path / "config.yaml"),
    )

    assert "limit must be >= 0" in caplog.text


class ExitCodeFixture(t.NamedTuple):
    """Fixture for exit-code test cases (error vs success)."""

    test_id: str
    mock_repos: list[RemoteRepo]
    mock_error: Exception | None
    expected_zero: bool


EXIT_CODE_FIXTURES: list[ExitCodeFixture] = [
    ExitCodeFixture(
        test_id="returns-nonzero-on-error",
        mock_repos=[],
        mock_error=AuthenticationError("Bad credentials"),
        expected_zero=False,
    ),
    ExitCodeFixture(
        test_id="returns-zero-on-success",
        mock_repos=[_make_repo("repo1")],
        mock_error=None,
        expected_zero=True,
    ),
]


@pytest.mark.parametrize(
    list(ExitCodeFixture._fields),
    EXIT_CODE_FIXTURES,
    ids=[f.test_id for f in EXIT_CODE_FIXTURES],
)
def test_import_repos_exit_code(
    test_id: str,
    mock_repos: list[RemoteRepo],
    mock_error: Exception | None,
    expected_zero: bool,
    tmp_path: pathlib.Path,
    monkeypatch: MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test _run_import returns correct exit code on error vs success."""
    del test_id
    caplog.set_level(logging.DEBUG)

    monkeypatch.setenv("HOME", str(tmp_path))
    workspace = tmp_path / "repos"
    workspace.mkdir()

    importer = MockImporter(repos=mock_repos, error=mock_error)

    result = _run_import_defaults(
        importer,
        workspace=str(workspace),
        config_path_str=str(tmp_path / "config.yaml"),
    )

    if expected_zero:
        assert result == 0
    else:
        assert result != 0


def test_import_repos_json_config_write(
    tmp_path: pathlib.Path,
    monkeypatch: MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test _run_import writes valid JSON when config path has .json extension."""
    caplog.set_level(logging.INFO)

    monkeypatch.setenv("HOME", str(tmp_path))
    workspace = tmp_path / "repos"
    workspace.mkdir()
    config_file = tmp_path / ".vcspull.json"

    importer = MockImporter(repos=[_make_repo("repo1")])

    result = _run_import_defaults(
        importer,
        workspace=str(workspace),
        config_path_str=str(config_file),
    )

    assert result == 0
    assert config_file.exists()
    loaded = json.loads(config_file.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    total_repos = sum(len(repos) for repos in loaded.values())
    assert total_repos == 1


def test_import_repos_rejects_non_dict_config(
    tmp_path: pathlib.Path,
    monkeypatch: MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test _run_import rejects config that is a YAML list instead of dict."""
    caplog.set_level(logging.ERROR)

    monkeypatch.setenv("HOME", str(tmp_path))
    workspace = tmp_path / "repos"
    workspace.mkdir()
    config_file = tmp_path / ".vcspull.yaml"
    # Write a YAML list instead of a mapping
    config_file.write_text("- item1\n- item2\n", encoding="utf-8")

    importer = MockImporter(repos=[_make_repo("repo1")])

    _run_import_defaults(
        importer,
        workspace=str(workspace),
        config_path_str=str(config_file),
    )

    assert "not a valid mapping" in caplog.text


def test_import_repos_non_mapping_workspace_returns_error(
    tmp_path: pathlib.Path,
    monkeypatch: MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test _run_import returns non-zero when a workspace section is not a mapping."""
    caplog.set_level(logging.ERROR)

    monkeypatch.setenv("HOME", str(tmp_path))
    workspace = tmp_path / "repos"
    workspace.mkdir()
    config_file = tmp_path / ".vcspull.yaml"
    # Workspace section is a string, not a mapping
    label = workspace_root_label(workspace, cwd=pathlib.Path.cwd(), home=tmp_path)
    config_file.write_text(f"{label}: invalid_string\n", encoding="utf-8")

    importer = MockImporter(repos=[_make_repo("repo1")])

    result = _run_import_defaults(
        importer,
        workspace=str(workspace),
        config_path_str=str(config_file),
    )

    assert result == 1
    assert "not a mapping in config" in caplog.text


class NestedGroupImportFixture(t.NamedTuple):
    """Fixture for nested-group workspace persistence cases."""

    test_id: str
    target: str
    mode: str
    flatten_groups: bool
    workspace_relpath: str
    mock_repos: list[RemoteRepo]
    expected_sections: dict[str, tuple[str, ...]]


NESTED_GROUP_IMPORT_FIXTURES: list[NestedGroupImportFixture] = [
    NestedGroupImportFixture(
        test_id="comment-example-relative-subpaths",
        target="a/b",
        mode="org",
        flatten_groups=False,
        workspace_relpath="repos",
        mock_repos=[
            _make_repo("h", owner="a/b"),
            _make_repo("d", owner="a/b/c"),
            _make_repo("e", owner="a/b/c"),
            _make_repo("g", owner="a/b/f"),
        ],
        expected_sections={
            "": ("h",),
            "c": ("d", "e"),
            "f": ("g",),
        },
    ),
    NestedGroupImportFixture(
        test_id="deep-nesting-under-target",
        target="a/b",
        mode="org",
        flatten_groups=False,
        workspace_relpath="repos",
        mock_repos=[
            _make_repo("r1", owner="a/b/c/d"),
            _make_repo("r2", owner="a/b/c/d/e"),
        ],
        expected_sections={
            "c/d": ("r1",),
            "c/d/e": ("r2",),
        },
    ),
    NestedGroupImportFixture(
        test_id="non-org-mode-no-subpathing",
        target="a/b",
        mode="user",
        flatten_groups=False,
        workspace_relpath="repos",
        mock_repos=[
            _make_repo("h", owner="a/b"),
            _make_repo("d", owner="a/b/c"),
            _make_repo("g", owner="a/b/f"),
        ],
        expected_sections={
            "": ("h", "d", "g"),
        },
    ),
    NestedGroupImportFixture(
        test_id="owner-outside-target-fallback-base",
        target="a/b",
        mode="org",
        flatten_groups=False,
        workspace_relpath="repos",
        mock_repos=[
            _make_repo("inside", owner="a/b/c"),
            _make_repo("outside", owner="z/y"),
        ],
        expected_sections={
            "c": ("inside",),
            "": ("outside",),
        },
    ),
    NestedGroupImportFixture(
        test_id="traversal-in-owner-flattened-to-base",
        target="a/b",
        mode="org",
        flatten_groups=False,
        workspace_relpath="repos",
        mock_repos=[
            _make_repo("evil", owner="a/b/../../escape"),
            _make_repo("safe", owner="a/b/c"),
        ],
        expected_sections={
            "": ("evil",),
            "c": ("safe",),
        },
    ),
    NestedGroupImportFixture(
        test_id="flatten-groups-flag-uses-single-workspace",
        target="a/b",
        mode="org",
        flatten_groups=True,
        workspace_relpath="repos",
        mock_repos=[
            _make_repo("h", owner="a/b"),
            _make_repo("d", owner="a/b/c"),
            _make_repo("g", owner="a/b/f"),
        ],
        expected_sections={
            "": ("h", "d", "g"),
        },
    ),
    NestedGroupImportFixture(
        test_id="workspace-subdirectory-root-is-supported",
        target="a/b",
        mode="org",
        flatten_groups=False,
        workspace_relpath="projects/python",
        mock_repos=[
            _make_repo("h", owner="a/b"),
            _make_repo("d", owner="a/b/c"),
        ],
        expected_sections={
            "": ("h",),
            "c": ("d",),
        },
    ),
]


@pytest.mark.parametrize(
    list(NestedGroupImportFixture._fields),
    NESTED_GROUP_IMPORT_FIXTURES,
    ids=[fixture.test_id for fixture in NESTED_GROUP_IMPORT_FIXTURES],
)
def test_import_nested_groups(
    test_id: str,
    target: str,
    mode: str,
    flatten_groups: bool,
    workspace_relpath: str,
    mock_repos: list[RemoteRepo],
    expected_sections: dict[str, tuple[str, ...]],
    tmp_path: pathlib.Path,
    monkeypatch: MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that nested groups are preserved in config."""
    import yaml

    del test_id
    caplog.set_level(logging.INFO)
    monkeypatch.setenv("HOME", str(tmp_path))

    workspace = tmp_path / workspace_relpath
    workspace.mkdir(parents=True)
    config_file = tmp_path / ".vcspull.yaml"

    importer = MockImporter(service_name="GitLab", repos=mock_repos)

    _run_import_defaults(
        importer,
        service_name="gitlab",
        target=target,
        workspace=str(workspace),
        mode=mode,
        config_path_str=str(config_file),
        flatten_groups=flatten_groups,
    )

    assert config_file.exists()
    with config_file.open() as f:
        config = yaml.safe_load(f)

    cwd = pathlib.Path.cwd()
    home = pathlib.Path.home()
    expected_labels: dict[str, tuple[str, ...]] = {}
    for subpath, repo_names in expected_sections.items():
        expected_path = workspace if not subpath else workspace / subpath
        label = workspace_root_label(expected_path, cwd=cwd, home=home)
        expected_labels[label] = repo_names

    assert set(config.keys()) == set(expected_labels.keys())
    for label, expected_repo_names in expected_labels.items():
        assert isinstance(config[label], dict)
        assert set(config[label].keys()) == set(expected_repo_names)


class LanguageWarningFixture(t.NamedTuple):
    """Fixture for --language warning test cases."""

    test_id: str
    service_name: str
    language: str | None
    expect_warning: bool


LANGUAGE_WARNING_FIXTURES: list[LanguageWarningFixture] = [
    LanguageWarningFixture(
        test_id="gitlab-with-language-warns",
        service_name="gitlab",
        language="Python",
        expect_warning=True,
    ),
    LanguageWarningFixture(
        test_id="codecommit-with-language-warns",
        service_name="codecommit",
        language="Python",
        expect_warning=True,
    ),
    LanguageWarningFixture(
        test_id="github-with-language-no-warning",
        service_name="github",
        language="Python",
        expect_warning=False,
    ),
    LanguageWarningFixture(
        test_id="gitlab-without-language-no-warning",
        service_name="gitlab",
        language=None,
        expect_warning=False,
    ),
]


@pytest.mark.parametrize(
    list(LanguageWarningFixture._fields),
    LANGUAGE_WARNING_FIXTURES,
    ids=[f.test_id for f in LANGUAGE_WARNING_FIXTURES],
)
def test_import_repos_language_warning(
    test_id: str,
    service_name: str,
    language: str | None,
    expect_warning: bool,
    tmp_path: pathlib.Path,
    monkeypatch: MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that --language warns for services without language metadata."""
    caplog.set_level(logging.WARNING)

    monkeypatch.setenv("HOME", str(tmp_path))
    workspace = tmp_path / "repos"
    workspace.mkdir()

    display_name = {"gitlab": "GitLab", "codecommit": "CodeCommit"}.get(
        service_name, "GitHub"
    )
    importer = MockImporter(service_name=display_name)

    _run_import_defaults(
        importer,
        service_name=service_name,
        target="testuser" if service_name != "codecommit" else "",
        workspace=str(workspace),
        language=language,
        config_path_str=str(tmp_path / "config.yaml"),
        dry_run=True,
    )

    if expect_warning:
        assert "does not return language metadata" in caplog.text
    else:
        assert "does not return language metadata" not in caplog.text


class UnsupportedFilterFixture(t.NamedTuple):
    """Fixture for unsupported CodeCommit filter warning test cases."""

    test_id: str
    service_name: str
    topics: str | None
    min_stars: int
    expect_topics_warning: bool
    expect_stars_warning: bool


UNSUPPORTED_FILTER_FIXTURES: list[UnsupportedFilterFixture] = [
    UnsupportedFilterFixture(
        test_id="codecommit-with-topics-warns",
        service_name="codecommit",
        topics="python,cli",
        min_stars=0,
        expect_topics_warning=True,
        expect_stars_warning=False,
    ),
    UnsupportedFilterFixture(
        test_id="codecommit-with-min-stars-warns",
        service_name="codecommit",
        topics=None,
        min_stars=10,
        expect_topics_warning=False,
        expect_stars_warning=True,
    ),
    UnsupportedFilterFixture(
        test_id="codecommit-with-both-warns",
        service_name="codecommit",
        topics="python",
        min_stars=5,
        expect_topics_warning=True,
        expect_stars_warning=True,
    ),
    UnsupportedFilterFixture(
        test_id="github-with-topics-no-warning",
        service_name="github",
        topics="python,cli",
        min_stars=10,
        expect_topics_warning=False,
        expect_stars_warning=False,
    ),
]


@pytest.mark.parametrize(
    list(UnsupportedFilterFixture._fields),
    UNSUPPORTED_FILTER_FIXTURES,
    ids=[f.test_id for f in UNSUPPORTED_FILTER_FIXTURES],
)
def test_import_repos_unsupported_filter_warning(
    test_id: str,
    service_name: str,
    topics: str | None,
    min_stars: int,
    expect_topics_warning: bool,
    expect_stars_warning: bool,
    tmp_path: pathlib.Path,
    monkeypatch: MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that --topics/--min-stars warn for CodeCommit."""
    caplog.set_level(logging.WARNING)

    monkeypatch.setenv("HOME", str(tmp_path))
    workspace = tmp_path / "repos"
    workspace.mkdir()

    display_name = "CodeCommit" if service_name == "codecommit" else "GitHub"
    importer = MockImporter(service_name=display_name)

    _run_import_defaults(
        importer,
        service_name=service_name,
        target="testuser" if service_name != "codecommit" else "",
        workspace=str(workspace),
        topics=topics,
        min_stars=min_stars,
        config_path_str=str(tmp_path / "config.yaml"),
        dry_run=True,
    )

    if expect_topics_warning:
        assert "does not support topic filtering" in caplog.text
    else:
        assert "does not support topic filtering" not in caplog.text

    if expect_stars_warning:
        assert "does not track star counts" in caplog.text
    else:
        assert "does not track star counts" not in caplog.text


class WithSharedModeWarningFixture(t.NamedTuple):
    """Fixture for --with-shared outside-org-mode warning test cases."""

    test_id: str
    mode: str
    with_shared: bool
    expect_warning: bool


WITH_SHARED_MODE_WARNING_FIXTURES: list[WithSharedModeWarningFixture] = [
    WithSharedModeWarningFixture(
        test_id="user-mode-with-shared-warns",
        mode="user",
        with_shared=True,
        expect_warning=True,
    ),
    WithSharedModeWarningFixture(
        test_id="org-mode-with-shared-no-warning",
        mode="org",
        with_shared=True,
        expect_warning=False,
    ),
    WithSharedModeWarningFixture(
        test_id="user-mode-without-shared-no-warning",
        mode="user",
        with_shared=False,
        expect_warning=False,
    ),
    WithSharedModeWarningFixture(
        test_id="search-mode-with-shared-warns",
        mode="search",
        with_shared=True,
        expect_warning=True,
    ),
]


@pytest.mark.parametrize(
    list(WithSharedModeWarningFixture._fields),
    WITH_SHARED_MODE_WARNING_FIXTURES,
    ids=[f.test_id for f in WITH_SHARED_MODE_WARNING_FIXTURES],
)
def test_import_repos_with_shared_mode_warning(
    test_id: str,
    mode: str,
    with_shared: bool,
    expect_warning: bool,
    tmp_path: pathlib.Path,
    monkeypatch: MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that --with-shared warns when used outside org mode."""
    caplog.set_level(logging.WARNING)

    del test_id

    monkeypatch.setenv("HOME", str(tmp_path))
    workspace = tmp_path / "repos"
    workspace.mkdir()

    importer = MockImporter(service_name="GitLab")

    _run_import_defaults(
        importer,
        service_name="gitlab",
        workspace=str(workspace),
        mode=mode,
        config_path_str=str(tmp_path / "config.yaml"),
        dry_run=True,
        with_shared=with_shared,
    )

    if expect_warning:
        assert "--with-shared has no effect outside org mode" in caplog.text
    else:
        assert "--with-shared has no effect outside org mode" not in caplog.text


# ── New tests for per-service subparser architecture ──


def test_alias_parsing_gh() -> None:
    """Test that 'import gh' resolves the same as 'import github'."""
    from vcspull.cli import create_parser

    parser = create_parser(return_subparsers=False)
    args = parser.parse_args(["import", "gh", "myuser", "-w", "/tmp/repos"])
    assert args.import_service in ("github", "gh")
    assert hasattr(args, "import_handler")


def test_alias_parsing_gl() -> None:
    """Test that 'import gl' resolves the same as 'import gitlab'."""
    from vcspull.cli import create_parser

    parser = create_parser(return_subparsers=False)
    args = parser.parse_args(["import", "gl", "myuser", "-w", "/tmp/repos"])
    assert args.import_service in ("gitlab", "gl")
    assert hasattr(args, "import_handler")


def test_alias_parsing_cb() -> None:
    """Test that 'import cb' resolves the same as 'import codeberg'."""
    from vcspull.cli import create_parser

    parser = create_parser(return_subparsers=False)
    args = parser.parse_args(["import", "cb", "myuser", "-w", "/tmp/repos"])
    assert args.import_service in ("codeberg", "cb")
    assert hasattr(args, "import_handler")


def test_alias_parsing_cc() -> None:
    """Test that 'import cc' resolves the same as 'import codecommit'."""
    from vcspull.cli import create_parser

    parser = create_parser(return_subparsers=False)
    args = parser.parse_args(["import", "cc", "-w", "/tmp/repos"])
    assert args.import_service in ("codecommit", "cc")
    assert hasattr(args, "import_handler")


def test_alias_parsing_aws() -> None:
    """Test that 'import aws' resolves the same as 'import codecommit'."""
    from vcspull.cli import create_parser

    parser = create_parser(return_subparsers=False)
    args = parser.parse_args(["import", "aws", "-w", "/tmp/repos"])
    assert args.import_service in ("codecommit", "aws")
    assert hasattr(args, "import_handler")


def test_flatten_groups_only_on_gitlab() -> None:
    """Test that --flatten-groups is only available on the gitlab subparser."""
    from vcspull.cli import create_parser

    parser = create_parser(return_subparsers=False)

    # Should work for gitlab
    args = parser.parse_args(
        ["import", "gitlab", "mygroup", "-w", "/tmp/repos", "--flatten-groups"]
    )
    assert args.flatten_groups is True

    # Should fail for github
    with pytest.raises(SystemExit):
        parser.parse_args(
            ["import", "github", "myuser", "-w", "/tmp/repos", "--flatten-groups"]
        )


def test_with_shared_only_on_gitlab() -> None:
    """Test that --with-shared is only available on the gitlab subparser."""
    from vcspull.cli import create_parser

    parser = create_parser(return_subparsers=False)

    # Should work for gitlab
    args = parser.parse_args(
        ["import", "gitlab", "mygroup", "-w", "/tmp/repos", "--with-shared"]
    )
    assert args.with_shared is True

    # Should fail for github
    with pytest.raises(SystemExit):
        parser.parse_args(
            ["import", "github", "myuser", "-w", "/tmp/repos", "--with-shared"]
        )


def test_skip_group_only_on_gitlab() -> None:
    """Test that --skip-group is only available on the gitlab subparser."""
    from vcspull.cli import create_parser

    parser = create_parser(return_subparsers=False)

    # Should work for gitlab
    args = parser.parse_args(
        ["import", "gitlab", "mygroup", "-w", "/tmp/repos", "--skip-group", "bots"]
    )
    assert args.skip_groups == ["bots"]

    # Should fail for github
    with pytest.raises(SystemExit):
        parser.parse_args(
            ["import", "github", "myuser", "-w", "/tmp/repos", "--skip-group", "bots"]
        )


def test_region_only_on_codecommit() -> None:
    """Test that --region is only available on the codecommit subparser."""
    from vcspull.cli import create_parser

    parser = create_parser(return_subparsers=False)

    # Should work for codecommit
    args = parser.parse_args(
        ["import", "codecommit", "-w", "/tmp/repos", "--region", "us-east-1"]
    )
    assert args.region == "us-east-1"

    # Should fail for github
    with pytest.raises(SystemExit):
        parser.parse_args(
            ["import", "github", "myuser", "-w", "/tmp/repos", "--region", "us-east-1"]
        )


def test_url_required_for_gitea() -> None:
    """Test that --url is required for the gitea subparser."""
    from vcspull.cli import create_parser

    parser = create_parser(return_subparsers=False)

    # Should fail without --url
    with pytest.raises(SystemExit):
        parser.parse_args(["import", "gitea", "myuser", "-w", "/tmp/repos"])

    # Should work with --url
    args = parser.parse_args(
        [
            "import",
            "gitea",
            "myuser",
            "-w",
            "/tmp/repos",
            "--url",
            "https://git.example.com",
        ]
    )
    assert args.base_url == "https://git.example.com"


def test_url_required_for_forgejo() -> None:
    """Test that --url is required for the forgejo subparser."""
    from vcspull.cli import create_parser

    parser = create_parser(return_subparsers=False)

    # Should fail without --url
    with pytest.raises(SystemExit):
        parser.parse_args(["import", "forgejo", "myuser", "-w", "/tmp/repos"])

    # Should work with --url
    args = parser.parse_args(
        [
            "import",
            "forgejo",
            "myuser",
            "-w",
            "/tmp/repos",
            "--url",
            "https://forgejo.example.com",
        ]
    )
    assert args.base_url == "https://forgejo.example.com"


def test_codecommit_target_is_optional() -> None:
    """Test that target is optional for the codecommit subparser."""
    from vcspull.cli import create_parser

    parser = create_parser(return_subparsers=False)

    # Should work without target
    args = parser.parse_args(["import", "codecommit", "-w", "/tmp/repos"])
    assert args.target == ""

    # Should work with target
    args = parser.parse_args(["import", "codecommit", "myprefix", "-w", "/tmp/repos"])
    assert args.target == "myprefix"


def test_run_import_rejects_skip_group_with_slash(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """_run_import returns 1 when a --skip-group value contains a slash.

    A value like 'bots/subteam' can never match any single owner path segment
    (filter_repo splits repo.owner on '/' and compares segments individually),
    so such values silently have no effect.  The early validation catches
    this and returns a non-zero exit code.
    """
    import logging

    caplog.set_level(logging.ERROR)
    monkeypatch.setenv("HOME", str(tmp_path))

    workspace = tmp_path / "repos"
    workspace.mkdir()

    result = _run_import_defaults(
        MockImporter(),
        service_name="gitlab",
        target="my-group",
        workspace=str(workspace),
        mode="org",
        config_path_str=str(tmp_path / "config.yaml"),
        skip_groups=["bots/subteam"],
    )

    assert result == 1
    assert "bots/subteam" in caplog.text
    assert "'/' is not allowed" in caplog.text


def test_run_import_forwards_with_shared_and_skip_groups(
    tmp_path: pathlib.Path,
    monkeypatch: MonkeyPatch,
) -> None:
    """Test that with_shared and skip_groups are forwarded to ImportOptions."""
    monkeypatch.setenv("HOME", str(tmp_path))
    workspace = tmp_path / "repos"
    workspace.mkdir()

    importer = CapturingMockImporter()

    _run_import_defaults(
        importer,
        service_name="gitlab",
        target="my-group",
        workspace=str(workspace),
        mode="org",
        config_path_str=str(tmp_path / "config.yaml"),
        dry_run=True,
        with_shared=True,
        skip_groups=["bots", "archived"],
    )

    assert importer.captured_options is not None
    assert importer.captured_options.with_shared is True
    assert importer.captured_options.skip_groups == ["bots", "archived"]


# ---------------------------------------------------------------------------
# ImportAction classifier unit tests
# ---------------------------------------------------------------------------

_SSH = "git+git@github.com:testuser/repo1.git"
_HTTPS = "git+https://github.com/testuser/repo1.git"


class ImportActionFixture(t.NamedTuple):
    """Fixture for _classify_import_action unit tests."""

    test_id: str
    existing_entry: t.Any
    incoming_url: str
    sync: bool
    expected_action: ImportAction


IMPORT_ACTION_FIXTURES: list[ImportActionFixture] = [
    ImportActionFixture("add-no-sync", None, _SSH, False, ImportAction.ADD),
    ImportActionFixture("add-with-sync", None, _SSH, True, ImportAction.ADD),
    ImportActionFixture(
        "skip-unchanged-no-sync",
        {"repo": _SSH},
        _SSH,
        False,
        ImportAction.SKIP_UNCHANGED,
    ),
    ImportActionFixture(
        "skip-unchanged-with-sync",
        {"repo": _SSH},
        _SSH,
        True,
        ImportAction.SKIP_UNCHANGED,
    ),
    ImportActionFixture(
        "skip-unchanged-pinned-no-sync",
        {"repo": _SSH, "options": {"pin": True}},
        _SSH,
        False,
        ImportAction.SKIP_UNCHANGED,
    ),
    ImportActionFixture(
        "skip-unchanged-pinned-with-sync",
        {"repo": _SSH, "options": {"pin": True}},
        _SSH,
        True,
        ImportAction.SKIP_UNCHANGED,
    ),
    ImportActionFixture(
        "url-key-takes-precedence",
        {"repo": _HTTPS, "url": _SSH},
        _SSH,
        False,
        ImportAction.SKIP_UNCHANGED,
    ),
    ImportActionFixture(
        "skip-existing-no-sync",
        {"repo": _HTTPS},
        _SSH,
        False,
        ImportAction.SKIP_EXISTING,
    ),
    ImportActionFixture(
        "update-url-with-sync",
        {"repo": _HTTPS},
        _SSH,
        True,
        ImportAction.UPDATE_URL,
    ),
    ImportActionFixture(
        "skip-pinned-global-pin",
        {"repo": _HTTPS, "options": {"pin": True}},
        _SSH,
        True,
        ImportAction.SKIP_PINNED,
    ),
    ImportActionFixture(
        "skip-pinned-allow-overwrite-false",
        {"repo": _HTTPS, "options": {"allow_overwrite": False}},
        _SSH,
        True,
        ImportAction.SKIP_PINNED,
    ),
    ImportActionFixture(
        "skip-pinned-import-specific",
        {"repo": _HTTPS, "options": {"pin": {"import": True}}},
        _SSH,
        True,
        ImportAction.SKIP_PINNED,
    ),
    ImportActionFixture(
        "not-pinned-add-specific",
        {"repo": _HTTPS, "options": {"pin": {"add": True}}},
        _SSH,
        True,
        ImportAction.UPDATE_URL,
    ),
    ImportActionFixture(
        "str-entry-skip-existing",
        _HTTPS,
        _SSH,
        False,
        ImportAction.SKIP_EXISTING,
    ),
    ImportActionFixture(
        "str-entry-update-url",
        _HTTPS,
        _SSH,
        True,
        ImportAction.UPDATE_URL,
    ),
    ImportActionFixture(
        "non-dict-non-str-entry",
        42,
        _SSH,
        False,
        ImportAction.SKIP_EXISTING,
    ),
]


@pytest.mark.parametrize(
    list(ImportActionFixture._fields),
    IMPORT_ACTION_FIXTURES,
    ids=[f.test_id for f in IMPORT_ACTION_FIXTURES],
)
def test_classify_import_action(
    test_id: str,
    existing_entry: dict[str, t.Any] | str | None,
    incoming_url: str,
    sync: bool,
    expected_action: ImportAction,
) -> None:
    """Test _classify_import_action covers all permutations."""
    action = _classify_import_action(
        incoming_url=incoming_url,
        existing_entry=existing_entry,
        sync=sync,
    )
    assert action == expected_action


# ---------------------------------------------------------------------------
# --sync integration tests
# ---------------------------------------------------------------------------


def test_import_sync_updates_url(
    tmp_path: pathlib.Path,
    monkeypatch: MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test --sync updates an existing entry when URL has changed."""
    caplog.set_level(logging.INFO)
    monkeypatch.setenv("HOME", str(tmp_path))
    workspace = tmp_path / "repos"
    workspace.mkdir()
    config_file = tmp_path / ".vcspull.yaml"

    save_config_yaml(config_file, {"~/repos/": {"repo1": {"repo": _HTTPS}}})

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

    from vcspull._internal.config_reader import ConfigReader

    final_config = ConfigReader._from_file(config_file)
    assert final_config is not None
    assert final_config["~/repos/"]["repo1"]["repo"] == _SSH
    assert "Updated" in caplog.text


def test_import_sync_updates_url_json(
    tmp_path: pathlib.Path,
    monkeypatch: MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test --sync updates an existing entry in a JSON config file."""
    caplog.set_level(logging.INFO)
    monkeypatch.setenv("HOME", str(tmp_path))
    workspace = tmp_path / "repos"
    workspace.mkdir()
    config_file = tmp_path / ".vcspull.json"

    # Write initial JSON config with HTTPS URL
    save_config_json(config_file, {"~/repos/": {"repo1": {"repo": _HTTPS}}})

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

    from vcspull._internal.config_reader import ConfigReader

    final_config = ConfigReader._from_file(config_file)
    assert final_config is not None
    assert final_config["~/repos/"]["repo1"]["repo"] == _SSH
    assert "Updated" in caplog.text


def test_import_sync_string_entry_to_dict(
    tmp_path: pathlib.Path,
    monkeypatch: MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test --sync converts a string-format config entry to dict format."""
    caplog.set_level(logging.INFO)
    monkeypatch.setenv("HOME", str(tmp_path))
    workspace = tmp_path / "repos"
    workspace.mkdir()
    config_file = tmp_path / ".vcspull.yaml"

    # Initial config uses string-format entry (not dict)
    save_config_yaml(config_file, {"~/repos/": {"repo1": _HTTPS}})

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

    from vcspull._internal.config_reader import ConfigReader

    final_config = ConfigReader._from_file(config_file)
    assert final_config is not None
    # String entry should be converted to dict format with new URL
    assert final_config["~/repos/"]["repo1"]["repo"] == _SSH
    assert "Updated" in caplog.text


def test_import_no_sync_skips_changed_url(
    tmp_path: pathlib.Path,
    monkeypatch: MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Without --sync, changed URLs are silently skipped."""
    caplog.set_level(logging.INFO)
    monkeypatch.setenv("HOME", str(tmp_path))
    workspace = tmp_path / "repos"
    workspace.mkdir()
    config_file = tmp_path / ".vcspull.yaml"

    save_config_yaml(config_file, {"~/repos/": {"repo1": {"repo": _HTTPS}}})

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
        sync=False,
    )

    assert "use --sync" in caplog.text

    from vcspull._internal.config_reader import ConfigReader

    final_config = ConfigReader._from_file(config_file)
    assert final_config is not None
    assert final_config["~/repos/"]["repo1"]["repo"] == _HTTPS


def test_import_sync_respects_pin_true(
    tmp_path: pathlib.Path,
    monkeypatch: MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """--sync must not update URL for an entry with options.pin: true."""
    caplog.set_level(logging.INFO)
    monkeypatch.setenv("HOME", str(tmp_path))
    workspace = tmp_path / "repos"
    workspace.mkdir()
    config_file = tmp_path / ".vcspull.yaml"

    save_config_yaml(
        config_file,
        {"~/repos/": {"repo1": {"repo": _HTTPS, "options": {"pin": True}}}},
    )

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

    from vcspull._internal.config_reader import ConfigReader

    final_config = ConfigReader._from_file(config_file)
    assert final_config is not None
    # URL must NOT have changed
    assert final_config["~/repos/"]["repo1"]["repo"] == _HTTPS
    assert "Skipping pinned" in caplog.text


def test_import_sync_skip_pinned_shows_pin_reason(
    tmp_path: pathlib.Path,
    monkeypatch: MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """--sync skip log must include pin_reason when set."""
    caplog.set_level(logging.INFO)
    monkeypatch.setenv("HOME", str(tmp_path))
    workspace = tmp_path / "repos"
    workspace.mkdir()
    config_file = tmp_path / ".vcspull.yaml"

    save_config_yaml(
        config_file,
        {
            "~/repos/": {
                "repo1": {
                    "repo": _HTTPS,
                    "options": {
                        "pin": True,
                        "pin_reason": "pinned to company fork",
                    },
                }
            }
        },
    )

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

    assert "Skipping pinned" in caplog.text
    assert "pinned to company fork" in caplog.text


def test_import_sync_respects_allow_overwrite_false(
    tmp_path: pathlib.Path,
    monkeypatch: MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """--sync must not update URL for an entry with options.allow_overwrite: false."""
    caplog.set_level(logging.INFO)
    monkeypatch.setenv("HOME", str(tmp_path))
    workspace = tmp_path / "repos"
    workspace.mkdir()
    config_file = tmp_path / ".vcspull.yaml"

    save_config_yaml(
        config_file,
        {
            "~/repos/": {
                "repo1": {
                    "repo": _HTTPS,
                    "options": {"allow_overwrite": False},
                }
            }
        },
    )

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

    from vcspull._internal.config_reader import ConfigReader

    final_config = ConfigReader._from_file(config_file)
    assert final_config is not None
    assert final_config["~/repos/"]["repo1"]["repo"] == _HTTPS
    assert "Skipping pinned" in caplog.text


def test_import_sync_preserves_metadata(
    tmp_path: pathlib.Path,
    monkeypatch: MonkeyPatch,
) -> None:
    """--sync preserves existing metadata (options, etc.) when updating URL."""
    monkeypatch.setenv("HOME", str(tmp_path))
    workspace = tmp_path / "repos"
    workspace.mkdir()
    config_file = tmp_path / ".vcspull.yaml"

    save_config_yaml(
        config_file,
        {
            "~/repos/": {
                "repo1": {
                    "repo": _HTTPS,
                    "options": {"pin": {"fmt": True}},
                }
            }
        },
    )

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

    from vcspull._internal.config_reader import ConfigReader

    final_config = ConfigReader._from_file(config_file)
    assert final_config is not None
    entry = final_config["~/repos/"]["repo1"]
    assert entry["repo"] == _SSH
    # Options must be preserved
    assert entry.get("options", {}).get("pin", {}).get("fmt") is True


def test_import_sync_saves_config_when_only_url_updates(
    tmp_path: pathlib.Path,
    monkeypatch: MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Config must be saved when updated_url_count > 0 even if added_count == 0."""
    caplog.set_level(logging.INFO)
    monkeypatch.setenv("HOME", str(tmp_path))
    workspace = tmp_path / "repos"
    workspace.mkdir()
    config_file = tmp_path / ".vcspull.yaml"

    save_config_yaml(config_file, {"~/repos/": {"repo1": {"repo": _HTTPS}}})

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

    # Verify the URL was updated (content check is more reliable than mtime on
    # filesystems with coarse timestamp granularity, e.g. NTFS on WSL2).
    content = config_file.read_text(encoding="utf-8")
    assert _SSH in content, "Config must be saved with SSH URL after sync"
    assert _HTTPS not in content, "Old HTTPS URL must be replaced"


def test_import_parser_has_sync_flag() -> None:
    """The shared parent parser must expose --sync."""
    from vcspull.cli.import_cmd._common import _create_shared_parent

    parser = argparse.ArgumentParser(parents=[_create_shared_parent()])
    args = parser.parse_args(["--sync"])
    assert args.sync is True

    args2 = parser.parse_args([])
    assert args2.sync is False


# ---------------------------------------------------------------------------
# Provenance tracking and prune tests
# ---------------------------------------------------------------------------


def test_import_sync_tags_provenance(
    tmp_path: pathlib.Path,
    monkeypatch: MonkeyPatch,
) -> None:
    """--sync with import_source tags new repos with metadata.imported_from."""
    monkeypatch.setenv("HOME", str(tmp_path))
    workspace = tmp_path / "repos"
    workspace.mkdir()
    config_file = tmp_path / ".vcspull.yaml"

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
        import_source="github:testuser",
    )

    from vcspull._internal.config_reader import ConfigReader

    final_config = ConfigReader._from_file(config_file)
    assert final_config is not None
    entry = final_config["~/repos/"]["repo1"]
    assert entry["metadata"]["imported_from"] == "github:testuser"


def test_import_sync_prunes_stale_tagged_repo(
    tmp_path: pathlib.Path,
    monkeypatch: MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """--sync removes entries tagged with matching source that are no longer remote."""
    caplog.set_level(logging.INFO)
    monkeypatch.setenv("HOME", str(tmp_path))
    workspace = tmp_path / "repos"
    workspace.mkdir()
    config_file = tmp_path / ".vcspull.yaml"

    # Existing config: old-repo was previously imported from github:testuser
    save_config_yaml(
        config_file,
        {
            "~/repos/": {
                "old-repo": {
                    "repo": _SSH,
                    "metadata": {"imported_from": "github:testuser"},
                },
            }
        },
    )

    # Remote only has repo1 now (old-repo was deleted/renamed)
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
        import_source="github:testuser",
    )

    from vcspull._internal.config_reader import ConfigReader

    final_config = ConfigReader._from_file(config_file)
    assert final_config is not None
    assert "old-repo" not in final_config["~/repos/"]
    assert "repo1" in final_config["~/repos/"]
    assert "Pruned 1 repositories" in caplog.text


def test_import_sync_preserves_manually_added_repo(
    tmp_path: pathlib.Path,
    monkeypatch: MonkeyPatch,
) -> None:
    """--sync does not prune repos without an imported_from tag."""
    monkeypatch.setenv("HOME", str(tmp_path))
    workspace = tmp_path / "repos"
    workspace.mkdir()
    config_file = tmp_path / ".vcspull.yaml"

    # manual-repo has no metadata.imported_from
    save_config_yaml(
        config_file,
        {
            "~/repos/": {
                "manual-repo": {"repo": "git+https://example.com/manual.git"},
            }
        },
    )

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
        import_source="github:testuser",
    )

    from vcspull._internal.config_reader import ConfigReader

    final_config = ConfigReader._from_file(config_file)
    assert final_config is not None
    assert "manual-repo" in final_config["~/repos/"]
    assert "repo1" in final_config["~/repos/"]


def test_import_sync_preserves_differently_tagged_repo(
    tmp_path: pathlib.Path,
    monkeypatch: MonkeyPatch,
) -> None:
    """--sync does not prune repos tagged with a different source."""
    monkeypatch.setenv("HOME", str(tmp_path))
    workspace = tmp_path / "repos"
    workspace.mkdir()
    config_file = tmp_path / ".vcspull.yaml"

    # other-org-repo was imported from a different org
    save_config_yaml(
        config_file,
        {
            "~/repos/": {
                "other-org-repo": {
                    "repo": "git+https://github.com/other/repo.git",
                    "metadata": {"imported_from": "github:other-org"},
                },
            }
        },
    )

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
        import_source="github:testuser",
    )

    from vcspull._internal.config_reader import ConfigReader

    final_config = ConfigReader._from_file(config_file)
    assert final_config is not None
    assert "other-org-repo" in final_config["~/repos/"]


def test_import_sync_respects_pin_on_prune(
    tmp_path: pathlib.Path,
    monkeypatch: MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """--sync does not prune pinned entries even if they match the import source."""
    caplog.set_level(logging.INFO)
    monkeypatch.setenv("HOME", str(tmp_path))
    workspace = tmp_path / "repos"
    workspace.mkdir()
    config_file = tmp_path / ".vcspull.yaml"

    save_config_yaml(
        config_file,
        {
            "~/repos/": {
                "pinned-repo": {
                    "repo": _SSH,
                    "options": {"pin": True},
                    "metadata": {"imported_from": "github:testuser"},
                },
            }
        },
    )

    # pinned-repo is not on the remote
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
        import_source="github:testuser",
    )

    from vcspull._internal.config_reader import ConfigReader

    final_config = ConfigReader._from_file(config_file)
    assert final_config is not None
    # Pinned repo must survive even though it's stale
    assert "pinned-repo" in final_config["~/repos/"]
    assert "Skipping pruning pinned repo" in caplog.text


def test_import_sync_prune_dry_run(
    tmp_path: pathlib.Path,
    monkeypatch: MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """--sync --dry-run previews prune candidates without deleting them."""
    caplog.set_level(logging.INFO)
    monkeypatch.setenv("HOME", str(tmp_path))
    workspace = tmp_path / "repos"
    workspace.mkdir()
    config_file = tmp_path / ".vcspull.yaml"

    save_config_yaml(
        config_file,
        {
            "~/repos/": {
                "stale-repo": {
                    "repo": _SSH,
                    "metadata": {"imported_from": "github:testuser"},
                },
            }
        },
    )

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
        dry_run=True,
        yes=True,
        output_json=False,
        output_ndjson=False,
        color="never",
        sync=True,
        import_source="github:testuser",
    )

    assert "Would prune: stale-repo" in caplog.text

    # Config should NOT have been modified (dry-run)
    from vcspull._internal.config_reader import ConfigReader

    final_config = ConfigReader._from_file(config_file)
    assert final_config is not None
    assert "stale-repo" in final_config["~/repos/"]


def test_import_sync_updates_provenance_tag(
    tmp_path: pathlib.Path,
    monkeypatch: MonkeyPatch,
) -> None:
    """Re-importing with --sync updates imported_from tag if it was missing."""
    monkeypatch.setenv("HOME", str(tmp_path))
    workspace = tmp_path / "repos"
    workspace.mkdir()
    config_file = tmp_path / ".vcspull.yaml"

    # Existing entry without metadata
    save_config_yaml(
        config_file,
        {"~/repos/": {"repo1": {"repo": _SSH}}},
    )

    # Re-import same repo (URL unchanged → SKIP_UNCHANGED, no tag update)
    # But if the URL has changed, UPDATE_URL should also set the tag
    importer = MockImporter(repos=[_make_repo("repo1")])
    # repo1's SSH URL is _SSH, existing has _SSH → SKIP_UNCHANGED
    # Let's use HTTPS in existing so URL differs and UPDATE_URL fires
    save_config_yaml(
        config_file,
        {"~/repos/": {"repo1": {"repo": _HTTPS}}},
    )

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
        import_source="github:testuser",
    )

    from vcspull._internal.config_reader import ConfigReader

    final_config = ConfigReader._from_file(config_file)
    assert final_config is not None
    entry = final_config["~/repos/"]["repo1"]
    assert entry["repo"] == _SSH
    assert entry["metadata"]["imported_from"] == "github:testuser"


def test_import_skip_unchanged_tags_provenance(
    tmp_path: pathlib.Path,
    monkeypatch: MonkeyPatch,
) -> None:
    """SKIP_UNCHANGED entries get imported_from stamped when import_source is set."""
    monkeypatch.setenv("HOME", str(tmp_path))
    workspace = tmp_path / "repos"
    workspace.mkdir()
    config_file = tmp_path / ".vcspull.yaml"

    # Existing entry with matching URL but no metadata
    save_config_yaml(
        config_file,
        {"~/repos/": {"repo1": {"repo": _SSH}}},
    )

    # Same URL → SKIP_UNCHANGED, but should still stamp provenance
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
        import_source="github:testuser",
    )

    from vcspull._internal.config_reader import ConfigReader

    final_config = ConfigReader._from_file(config_file)
    assert final_config is not None
    entry = final_config["~/repos/"]["repo1"]
    assert isinstance(entry, dict)
    assert entry["metadata"]["imported_from"] == "github:testuser"


def test_import_skip_unchanged_tags_provenance_string_entry(
    tmp_path: pathlib.Path,
    monkeypatch: MonkeyPatch,
) -> None:
    """SKIP_UNCHANGED converts string entries to dict form for provenance."""
    monkeypatch.setenv("HOME", str(tmp_path))
    workspace = tmp_path / "repos"
    workspace.mkdir()
    config_file = tmp_path / ".vcspull.yaml"

    # Existing entry as a plain string (not dict form)
    save_config_yaml(
        config_file,
        {"~/repos/": {"repo1": _SSH}},
    )

    # Same URL → SKIP_UNCHANGED, should convert to dict and stamp provenance
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
        import_source="github:testuser",
    )

    from vcspull._internal.config_reader import ConfigReader

    final_config = ConfigReader._from_file(config_file)
    assert final_config is not None
    entry = final_config["~/repos/"]["repo1"]
    assert isinstance(entry, dict), "String entry should be converted to dict form"
    assert entry["repo"] == _SSH
    assert entry["metadata"]["imported_from"] == "github:testuser"


def test_import_provenance_tagging_logs_message(
    tmp_path: pathlib.Path,
    monkeypatch: MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Provenance-only save emits a log message about tagged repositories."""
    caplog.set_level(logging.INFO)
    monkeypatch.setenv("HOME", str(tmp_path))
    workspace = tmp_path / "repos"
    workspace.mkdir()
    config_file = tmp_path / ".vcspull.yaml"

    # Existing entry with matching URL — will be SKIP_UNCHANGED
    save_config_yaml(
        config_file,
        {"~/repos/": {"repo1": {"repo": _SSH}}},
    )

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
        import_source="github:testuser",
    )

    assert "Tagged 1 repositories with import provenance" in caplog.text


def test_import_provenance_survives_non_dict_metadata(
    tmp_path: pathlib.Path,
    monkeypatch: MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Provenance stamping replaces non-dict metadata with a proper dict."""
    caplog.set_level(logging.INFO)
    monkeypatch.setenv("HOME", str(tmp_path))
    workspace = tmp_path / "repos"
    workspace.mkdir()
    config_file = tmp_path / ".vcspull.yaml"

    # Existing entry with non-dict metadata — would crash without guard
    save_config_yaml(
        config_file,
        {"~/repos/": {"repo1": {"repo": _SSH, "metadata": "legacy-string"}}},
    )

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
        import_source="github:testuser",
    )

    from vcspull._internal.config_reader import ConfigReader

    final_config = ConfigReader._from_file(config_file)
    assert final_config is not None
    entry = final_config["~/repos/"]["repo1"]
    assert isinstance(entry["metadata"], dict)
    assert entry["metadata"]["imported_from"] == "github:testuser"


def test_import_provenance_survives_null_metadata(
    tmp_path: pathlib.Path,
    monkeypatch: MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Provenance stamping replaces null metadata with a proper dict (SKIP path)."""
    caplog.set_level(logging.INFO)
    monkeypatch.setenv("HOME", str(tmp_path))
    workspace = tmp_path / "repos"
    workspace.mkdir()
    config_file = tmp_path / ".vcspull.yaml"

    # Existing entry with metadata: null (YAML null → Python None)
    save_config_yaml(
        config_file,
        {"~/repos/": {"repo1": {"repo": _SSH, "metadata": None}}},
    )

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
        import_source="github:testuser",
    )

    from vcspull._internal.config_reader import ConfigReader

    final_config = ConfigReader._from_file(config_file)
    assert final_config is not None
    entry = final_config["~/repos/"]["repo1"]
    assert isinstance(entry["metadata"], dict)
    assert entry["metadata"]["imported_from"] == "github:testuser"


def test_import_update_url_survives_null_metadata(
    tmp_path: pathlib.Path,
    monkeypatch: MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Provenance stamping replaces null metadata with a proper dict (UPDATE path)."""
    caplog.set_level(logging.INFO)
    monkeypatch.setenv("HOME", str(tmp_path))
    workspace = tmp_path / "repos"
    workspace.mkdir()
    config_file = tmp_path / ".vcspull.yaml"

    # Existing entry with a different URL and metadata: null
    save_config_yaml(
        config_file,
        {
            "~/repos/": {
                "repo1": {
                    "repo": "git+git@github.com:testuser/repo1-OLD.git",
                    "metadata": None,
                },
            },
        },
    )

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
        import_source="github:testuser",
    )

    from vcspull._internal.config_reader import ConfigReader

    final_config = ConfigReader._from_file(config_file)
    assert final_config is not None
    entry = final_config["~/repos/"]["repo1"]
    assert isinstance(entry["metadata"], dict)
    assert entry["metadata"]["imported_from"] == "github:testuser"
    assert entry["repo"] == _SSH


# ---------------------------------------------------------------------------
# --prune standalone flag tests
# ---------------------------------------------------------------------------


def test_import_prune_removes_stale_tagged_repo(
    tmp_path: pathlib.Path,
    monkeypatch: MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """--prune alone removes stale tagged entry."""
    caplog.set_level(logging.INFO)
    monkeypatch.setenv("HOME", str(tmp_path))
    workspace = tmp_path / "repos"
    workspace.mkdir()
    config_file = tmp_path / ".vcspull.yaml"

    save_config_yaml(
        config_file,
        {
            "~/repos/": {
                "stale-repo": {
                    "repo": _SSH,
                    "metadata": {"imported_from": "github:testuser"},
                },
            }
        },
    )

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
        prune=True,
        import_source="github:testuser",
    )

    from vcspull._internal.config_reader import ConfigReader

    final_config = ConfigReader._from_file(config_file)
    assert final_config is not None
    assert "stale-repo" not in final_config["~/repos/"]
    assert "repo1" in final_config["~/repos/"]
    assert "Pruned 1 repositories" in caplog.text


def test_import_prune_does_not_update_urls(
    tmp_path: pathlib.Path,
    monkeypatch: MonkeyPatch,
) -> None:
    """--prune alone does NOT update a changed URL."""
    monkeypatch.setenv("HOME", str(tmp_path))
    workspace = tmp_path / "repos"
    workspace.mkdir()
    config_file = tmp_path / ".vcspull.yaml"

    save_config_yaml(
        config_file,
        {"~/repos/": {"repo1": {"repo": _HTTPS}}},
    )

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
        prune=True,
        import_source="github:testuser",
    )

    from vcspull._internal.config_reader import ConfigReader

    final_config = ConfigReader._from_file(config_file)
    assert final_config is not None
    # URL should NOT have changed (prune doesn't update URLs)
    assert final_config["~/repos/"]["repo1"]["repo"] == _HTTPS


def test_import_prune_preserves_untagged_repo(
    tmp_path: pathlib.Path,
    monkeypatch: MonkeyPatch,
) -> None:
    """--prune does not remove manually added repos (no imported_from tag)."""
    monkeypatch.setenv("HOME", str(tmp_path))
    workspace = tmp_path / "repos"
    workspace.mkdir()
    config_file = tmp_path / ".vcspull.yaml"

    save_config_yaml(
        config_file,
        {
            "~/repos/": {
                "manual-repo": {"repo": "git+https://example.com/manual.git"},
            }
        },
    )

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
        prune=True,
        import_source="github:testuser",
    )

    from vcspull._internal.config_reader import ConfigReader

    final_config = ConfigReader._from_file(config_file)
    assert final_config is not None
    assert "manual-repo" in final_config["~/repos/"]


def test_import_prune_respects_pin(
    tmp_path: pathlib.Path,
    monkeypatch: MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """--prune does not prune pinned repos."""
    caplog.set_level(logging.INFO)
    monkeypatch.setenv("HOME", str(tmp_path))
    workspace = tmp_path / "repos"
    workspace.mkdir()
    config_file = tmp_path / ".vcspull.yaml"

    save_config_yaml(
        config_file,
        {
            "~/repos/": {
                "pinned-repo": {
                    "repo": _SSH,
                    "options": {"pin": True},
                    "metadata": {"imported_from": "github:testuser"},
                },
            }
        },
    )

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
        prune=True,
        import_source="github:testuser",
    )

    from vcspull._internal.config_reader import ConfigReader

    final_config = ConfigReader._from_file(config_file)
    assert final_config is not None
    assert "pinned-repo" in final_config["~/repos/"]
    assert "Skipping pruning pinned repo" in caplog.text


def test_import_prune_pinned_skip_count_in_summary(
    tmp_path: pathlib.Path,
    monkeypatch: MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Prune-phase SKIP_PINNED increments skip_pinned_count for the summary."""
    caplog.set_level(logging.INFO)
    monkeypatch.setenv("HOME", str(tmp_path))
    workspace = tmp_path / "repos"
    workspace.mkdir()
    config_file = tmp_path / ".vcspull.yaml"

    save_config_yaml(
        config_file,
        {
            "~/repos/": {
                "pinned-repo": {
                    "repo": _SSH,
                    "options": {"pin": True},
                    "metadata": {"imported_from": "github:testuser"},
                },
            }
        },
    )

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
        prune=True,
        import_source="github:testuser",
    )

    assert "Skipped 1 pinned repositories" in caplog.text


def test_import_prune_dry_run(
    tmp_path: pathlib.Path,
    monkeypatch: MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """--prune --dry-run previews prune candidates without deleting them."""
    caplog.set_level(logging.INFO)
    monkeypatch.setenv("HOME", str(tmp_path))
    workspace = tmp_path / "repos"
    workspace.mkdir()
    config_file = tmp_path / ".vcspull.yaml"

    save_config_yaml(
        config_file,
        {
            "~/repos/": {
                "stale-repo": {
                    "repo": _SSH,
                    "metadata": {"imported_from": "github:testuser"},
                },
            }
        },
    )

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
        dry_run=True,
        yes=True,
        output_json=False,
        output_ndjson=False,
        color="never",
        prune=True,
        import_source="github:testuser",
    )

    assert "Would prune: stale-repo" in caplog.text

    # Config should NOT have been modified (dry-run)
    from vcspull._internal.config_reader import ConfigReader

    final_config = ConfigReader._from_file(config_file)
    assert final_config is not None
    assert "stale-repo" in final_config["~/repos/"]


def test_import_dry_run_shows_summary_counts(
    tmp_path: pathlib.Path,
    monkeypatch: MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """--dry-run displays summary counts (add, prune, unchanged)."""
    caplog.set_level(logging.INFO)
    monkeypatch.setenv("HOME", str(tmp_path))
    workspace = tmp_path / "repos"
    workspace.mkdir()
    config_file = tmp_path / ".vcspull.yaml"

    # Existing: unchanged repo + stale repo (will be pruned)
    save_config_yaml(
        config_file,
        {
            "~/repos/": {
                "repo1": {
                    "repo": _SSH,
                    "metadata": {"imported_from": "github:testuser"},
                },
                "stale-repo": {
                    "repo": "git+git@github.com:testuser/stale-repo.git",
                    "metadata": {"imported_from": "github:testuser"},
                },
            }
        },
    )

    # Remote has repo1 (unchanged) + repo2 (new). stale-repo is missing → prune.
    importer = MockImporter(
        repos=[_make_repo("repo1"), _make_repo("repo2")],
    )
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
        dry_run=True,
        yes=True,
        output_json=False,
        output_ndjson=False,
        color="never",
        sync=True,
        import_source="github:testuser",
    )

    assert "[DRY-RUN] Would add 1 repositories" in caplog.text
    assert "[DRY-RUN] Would prune 1 stale entries" in caplog.text
    assert "[DRY-RUN] 1 repositories unchanged" in caplog.text
    assert "Dry run complete" in caplog.text


def test_import_dry_run_no_changes_no_write_message(
    tmp_path: pathlib.Path,
    monkeypatch: MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Dry run with zero changes says 'No changes' instead of 'Would write'."""
    caplog.set_level(logging.INFO)
    monkeypatch.setenv("HOME", str(tmp_path))
    workspace = tmp_path / "repos"
    workspace.mkdir()
    config_file = tmp_path / ".vcspull.yaml"

    # All repos already match → SKIP_UNCHANGED, no adds/updates/prunes
    save_config_yaml(
        config_file,
        {
            "~/repos/": {
                "repo1": {
                    "repo": _SSH,
                    "metadata": {"imported_from": "github:testuser"},
                },
            },
        },
    )

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
        dry_run=True,
        yes=True,
        output_json=False,
        output_ndjson=False,
        color="never",
        sync=True,
        import_source="github:testuser",
    )

    assert "No changes to write" in caplog.text
    assert "Would write to" not in caplog.text


def test_import_dry_run_provenance_tag_shows_write_message(
    tmp_path: pathlib.Path,
    monkeypatch: MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Dry run reports 'Would write' when only provenance tagging is needed."""
    caplog.set_level(logging.INFO)
    monkeypatch.setenv("HOME", str(tmp_path))
    workspace = tmp_path / "repos"
    workspace.mkdir()
    config_file = tmp_path / ".vcspull.yaml"

    # Repo URL matches but NO imported_from tag → provenance tagging needed
    save_config_yaml(
        config_file,
        {
            "~/repos/": {
                "repo1": {
                    "repo": _SSH,
                },
            },
        },
    )

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
        dry_run=True,
        yes=True,
        output_json=False,
        output_ndjson=False,
        color="never",
        sync=True,
        import_source="github:testuser",
    )

    assert "Would tag 1 repositories" in caplog.text
    assert "Would write to" in caplog.text
    assert "No changes to write" not in caplog.text


# ---------------------------------------------------------------------------
# Collision / cross-source prune tests
# ---------------------------------------------------------------------------


def test_import_sync_prune_same_name_different_sources(
    tmp_path: pathlib.Path,
    monkeypatch: MonkeyPatch,
) -> None:
    """Pruning source A leaves source B entry with the same repo name intact."""
    monkeypatch.setenv("HOME", str(tmp_path))
    workspace_a = tmp_path / "code"
    workspace_a.mkdir()
    workspace_b = tmp_path / "work"
    workspace_b.mkdir()
    config_file = tmp_path / ".vcspull.yaml"

    # Two workspaces, each with "shared-name" from different sources
    save_config_yaml(
        config_file,
        {
            "~/code/": {
                "shared-name": {
                    "repo": "git+git@github.com:org-a/shared-name.git",
                    "metadata": {"imported_from": "github:org-a"},
                },
            },
            "~/work/": {
                "shared-name": {
                    "repo": "git+git@github.com:org-b/shared-name.git",
                    "metadata": {"imported_from": "github:org-b"},
                },
            },
        },
    )

    # Sync with org-a, but org-a no longer has "shared-name" → prune from org-a
    importer = MockImporter(repos=[_make_repo("other-repo", owner="org-a")])
    _run_import(
        importer,
        service_name="github",
        target="org-a",
        workspace=str(workspace_a),
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
        import_source="github:org-a",
    )

    from vcspull._internal.config_reader import ConfigReader

    final_config = ConfigReader._from_file(config_file)
    assert final_config is not None

    # org-a's shared-name should be pruned
    assert "shared-name" not in final_config.get("~/code/", {})
    # org-b's shared-name should be untouched
    assert "shared-name" in final_config["~/work/"]
    entry_b = final_config["~/work/"]["shared-name"]
    assert entry_b["metadata"]["imported_from"] == "github:org-b"


def test_import_prune_cross_workspace_same_name(
    tmp_path: pathlib.Path,
    monkeypatch: MonkeyPatch,
) -> None:
    """Pruning one workspace leaves the other workspace's same-name entry intact."""
    monkeypatch.setenv("HOME", str(tmp_path))
    workspace_code = tmp_path / "code"
    workspace_code.mkdir()
    workspace_work = tmp_path / "work"
    workspace_work.mkdir()
    config_file = tmp_path / ".vcspull.yaml"

    # Both workspaces have "myrepo" with different import tags
    save_config_yaml(
        config_file,
        {
            "~/code/": {
                "myrepo": {
                    "repo": "git+git@github.com:user-a/myrepo.git",
                    "metadata": {"imported_from": "github:user-a"},
                },
            },
            "~/work/": {
                "myrepo": {
                    "repo": "git+git@github.com:user-b/myrepo.git",
                    "metadata": {"imported_from": "github:user-b"},
                },
            },
        },
    )

    # Prune user-a: remote has other-repo but not myrepo → myrepo stale
    importer = MockImporter(repos=[_make_repo("other-repo", owner="user-a")])
    _run_import(
        importer,
        service_name="github",
        target="user-a",
        workspace=str(workspace_code),
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
        prune=True,
        import_source="github:user-a",
    )

    from vcspull._internal.config_reader import ConfigReader

    final_config = ConfigReader._from_file(config_file)
    assert final_config is not None

    # user-a's entry should be pruned
    assert "myrepo" not in final_config.get("~/code/", {})
    # user-b's entry should be untouched
    assert "myrepo" in final_config["~/work/"]
    assert (
        final_config["~/work/"]["myrepo"]["metadata"]["imported_from"]
        == "github:user-b"
    )


def test_import_sync_same_name_from_remote_not_pruned(
    tmp_path: pathlib.Path,
    monkeypatch: MonkeyPatch,
) -> None:
    """A repo matching fetched_repo_names is NOT pruned even if URL changed."""
    monkeypatch.setenv("HOME", str(tmp_path))
    workspace = tmp_path / "repos"
    workspace.mkdir()
    config_file = tmp_path / ".vcspull.yaml"

    # Existing repo with old URL, tagged from same source
    save_config_yaml(
        config_file,
        {
            "~/repos/": {
                "repo-x": {
                    "repo": "git+git@github.com:testuser/repo-x-OLD.git",
                    "metadata": {"imported_from": "github:testuser"},
                },
            },
        },
    )

    # Remote still has "repo-x" (new URL) → UPDATE_URL, NOT prune
    importer = MockImporter(repos=[_make_repo("repo-x")])
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
        import_source="github:testuser",
    )

    from vcspull._internal.config_reader import ConfigReader

    final_config = ConfigReader._from_file(config_file)
    assert final_config is not None

    # repo-x should still exist (not pruned) with updated URL
    assert "repo-x" in final_config["~/repos/"]
    entry = final_config["~/repos/"]["repo-x"]
    assert entry["repo"] == _SSH.replace("repo1", "repo-x")
    assert entry["metadata"]["imported_from"] == "github:testuser"


def test_import_prune_cross_workspace_same_source_same_name(
    tmp_path: pathlib.Path,
    monkeypatch: MonkeyPatch,
) -> None:
    """Stale entry in workspace B is pruned even if workspace A has same name."""
    monkeypatch.setenv("HOME", str(tmp_path))
    workspace_a = tmp_path / "code"
    workspace_a.mkdir()
    workspace_b = tmp_path / "work"
    workspace_b.mkdir()
    config_file = tmp_path / ".vcspull.yaml"

    # Both workspaces have "myrepo" from the same import source
    save_config_yaml(
        config_file,
        {
            "~/code/": {
                "myrepo": {
                    "repo": "git+git@github.com:testuser/myrepo.git",
                    "metadata": {"imported_from": "github:testuser"},
                },
            },
            "~/work/": {
                "myrepo": {
                    "repo": "git+git@github.com:testuser/myrepo.git",
                    "metadata": {"imported_from": "github:testuser"},
                },
            },
        },
    )

    # Remote returns myrepo only to workspace A — workspace B's entry is stale
    importer = MockImporter(repos=[_make_repo("myrepo")])
    _run_import(
        importer,
        service_name="github",
        target="testuser",
        workspace=str(workspace_a),
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
        import_source="github:testuser",
    )

    from vcspull._internal.config_reader import ConfigReader

    final_config = ConfigReader._from_file(config_file)
    assert final_config is not None

    # Workspace A keeps myrepo (it was imported there)
    assert "myrepo" in final_config["~/code/"]
    # Workspace B's stale myrepo should be pruned
    assert "myrepo" not in final_config.get("~/work/", {})


def test_import_parser_has_prune_flag() -> None:
    """The shared parent parser must expose --prune."""
    from vcspull.cli.import_cmd._common import _create_shared_parent

    parser = argparse.ArgumentParser(parents=[_create_shared_parent()])
    args = parser.parse_args(["--prune"])
    assert args.prune is True

    args2 = parser.parse_args([])
    assert args2.prune is False


def test_import_parser_has_prune_untracked_flag() -> None:
    """The shared parent parser must expose --prune-untracked."""
    from vcspull.cli.import_cmd._common import _create_shared_parent

    parser = argparse.ArgumentParser(parents=[_create_shared_parent()])
    args = parser.parse_args(["--prune-untracked"])
    assert args.prune_untracked is True

    args2 = parser.parse_args([])
    assert args2.prune_untracked is False


# ---------------------------------------------------------------------------
# --prune-untracked tests
# ---------------------------------------------------------------------------


def test_prune_untracked_removes_untagged_dict(
    tmp_path: pathlib.Path,
    monkeypatch: MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """--prune-untracked removes dict entries without import provenance."""
    caplog.set_level(logging.INFO)
    monkeypatch.setenv("HOME", str(tmp_path))
    workspace = tmp_path / "repos"
    workspace.mkdir()
    config_file = tmp_path / ".vcspull.yaml"

    save_config_yaml(
        config_file,
        {
            "~/repos/": {
                "manual-repo": {"repo": "git+https://example.com/manual.git"},
            }
        },
    )

    importer = MockImporter(repos=[_make_repo("repo1")])
    result = _run_import(
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
        prune=True,
        prune_untracked=True,
        import_source="github:testuser",
    )

    assert result == 0
    from vcspull._internal.config_reader import ConfigReader

    final_config = ConfigReader._from_file(config_file)
    assert final_config is not None
    assert "manual-repo" not in final_config.get("~/repos/", {})
    assert "repo1" in final_config["~/repos/"]


def test_prune_untracked_removes_string_entry(
    tmp_path: pathlib.Path,
    monkeypatch: MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """--prune-untracked removes plain string entries (no metadata possible)."""
    caplog.set_level(logging.INFO)
    monkeypatch.setenv("HOME", str(tmp_path))
    workspace = tmp_path / "repos"
    workspace.mkdir()
    config_file = tmp_path / ".vcspull.yaml"

    save_config_yaml(
        config_file,
        {
            "~/repos/": {
                "string-repo": "git+https://example.com/string.git",
            }
        },
    )

    importer = MockImporter(repos=[_make_repo("repo1")])
    result = _run_import(
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
        prune=True,
        prune_untracked=True,
        import_source="github:testuser",
    )

    assert result == 0
    from vcspull._internal.config_reader import ConfigReader

    final_config = ConfigReader._from_file(config_file)
    assert final_config is not None
    assert "string-repo" not in final_config.get("~/repos/", {})
    assert "repo1" in final_config["~/repos/"]


def test_prune_untracked_preserves_different_source(
    tmp_path: pathlib.Path,
    monkeypatch: MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """--prune-untracked keeps entries tagged by a different import source."""
    caplog.set_level(logging.INFO)
    monkeypatch.setenv("HOME", str(tmp_path))
    workspace = tmp_path / "repos"
    workspace.mkdir()
    config_file = tmp_path / ".vcspull.yaml"

    save_config_yaml(
        config_file,
        {
            "~/repos/": {
                "gitlab-repo": {
                    "repo": "git+https://gitlab.com/other/repo.git",
                    "metadata": {"imported_from": "gitlab:other"},
                },
            }
        },
    )

    importer = MockImporter(repos=[_make_repo("repo1")])
    result = _run_import(
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
        prune=True,
        prune_untracked=True,
        import_source="github:testuser",
    )

    assert result == 0
    from vcspull._internal.config_reader import ConfigReader

    final_config = ConfigReader._from_file(config_file)
    assert final_config is not None
    assert "gitlab-repo" in final_config["~/repos/"]
    assert "repo1" in final_config["~/repos/"]


def test_prune_untracked_preserves_pinned(
    tmp_path: pathlib.Path,
    monkeypatch: MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """--prune-untracked keeps pinned entries even without provenance."""
    caplog.set_level(logging.INFO)
    monkeypatch.setenv("HOME", str(tmp_path))
    workspace = tmp_path / "repos"
    workspace.mkdir()
    config_file = tmp_path / ".vcspull.yaml"

    save_config_yaml(
        config_file,
        {
            "~/repos/": {
                "pinned-repo": {
                    "repo": "git+https://example.com/pinned.git",
                    "options": {"pin": True},
                },
            }
        },
    )

    importer = MockImporter(repos=[_make_repo("repo1")])
    result = _run_import(
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
        prune=True,
        prune_untracked=True,
        import_source="github:testuser",
    )

    assert result == 0
    from vcspull._internal.config_reader import ConfigReader

    final_config = ConfigReader._from_file(config_file)
    assert final_config is not None
    assert "pinned-repo" in final_config["~/repos/"]
    assert "Skipping pruning pinned untracked repo: pinned-repo" in caplog.text


def test_prune_untracked_preserves_other_workspace(
    tmp_path: pathlib.Path,
    monkeypatch: MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """--prune-untracked only touches workspaces the import targets."""
    caplog.set_level(logging.INFO)
    monkeypatch.setenv("HOME", str(tmp_path))
    workspace = tmp_path / "repos"
    workspace.mkdir()
    other_workspace = tmp_path / "other"
    other_workspace.mkdir()
    config_file = tmp_path / ".vcspull.yaml"

    save_config_yaml(
        config_file,
        {
            "~/repos/": {},
            "~/other/": {
                "unrelated-repo": {
                    "repo": "git+https://example.com/unrelated.git",
                },
            },
        },
    )

    importer = MockImporter(repos=[_make_repo("repo1")])
    result = _run_import(
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
        prune=True,
        prune_untracked=True,
        import_source="github:testuser",
    )

    assert result == 0
    from vcspull._internal.config_reader import ConfigReader

    final_config = ConfigReader._from_file(config_file)
    assert final_config is not None
    # Other workspace should be untouched
    assert "unrelated-repo" in final_config["~/other/"]


def test_prune_untracked_requires_sync_or_prune(
    tmp_path: pathlib.Path,
    monkeypatch: MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """--prune-untracked alone (no --sync/--prune) returns error."""
    caplog.set_level(logging.ERROR)
    monkeypatch.setenv("HOME", str(tmp_path))
    workspace = tmp_path / "repos"
    workspace.mkdir()
    config_file = tmp_path / ".vcspull.yaml"

    save_config_yaml(config_file, {"~/repos/": {}})

    importer = MockImporter(repos=[_make_repo("repo1")])
    result = _run_import(
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
        prune=False,
        prune_untracked=True,
        import_source="github:testuser",
    )

    assert result == 1
    assert "--prune-untracked requires --sync or --prune" in caplog.text


def test_prune_untracked_dry_run(
    tmp_path: pathlib.Path,
    monkeypatch: MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """--prune-untracked --dry-run logs without modifying config."""
    caplog.set_level(logging.INFO)
    monkeypatch.setenv("HOME", str(tmp_path))
    workspace = tmp_path / "repos"
    workspace.mkdir()
    config_file = tmp_path / ".vcspull.yaml"

    save_config_yaml(
        config_file,
        {
            "~/repos/": {
                "manual-repo": {"repo": "git+https://example.com/manual.git"},
            }
        },
    )

    importer = MockImporter(repos=[_make_repo("repo1")])
    result = _run_import(
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
        dry_run=True,
        yes=True,
        output_json=False,
        output_ndjson=False,
        color="never",
        prune=True,
        prune_untracked=True,
        import_source="github:testuser",
    )

    assert result == 0
    assert "--prune-untracked: Would remove manual-repo" in caplog.text

    # Config should NOT have been modified
    from vcspull._internal.config_reader import ConfigReader

    final_config = ConfigReader._from_file(config_file)
    assert final_config is not None
    assert "manual-repo" in final_config["~/repos/"]


def test_prune_untracked_with_sync(
    tmp_path: pathlib.Path,
    monkeypatch: MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """--sync --prune-untracked: URLs updated AND untracked entries removed."""
    caplog.set_level(logging.INFO)
    monkeypatch.setenv("HOME", str(tmp_path))
    workspace = tmp_path / "repos"
    workspace.mkdir()
    config_file = tmp_path / ".vcspull.yaml"

    save_config_yaml(
        config_file,
        {
            "~/repos/": {
                # Existing repo with outdated URL (should be updated by --sync)
                "repo1": {
                    "repo": _HTTPS,
                    "metadata": {"imported_from": "github:testuser"},
                },
                # Manual repo without provenance (should be removed)
                "manual-repo": {
                    "repo": "git+https://example.com/manual.git",
                },
            }
        },
    )

    importer = MockImporter(repos=[_make_repo("repo1")])
    result = _run_import(
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
        prune_untracked=True,
        import_source="github:testuser",
    )

    assert result == 0
    from vcspull._internal.config_reader import ConfigReader

    final_config = ConfigReader._from_file(config_file)
    assert final_config is not None
    # repo1 should have been updated to SSH URL (--sync updates URLs)
    assert "repo1" in final_config["~/repos/"]
    assert final_config["~/repos/"]["repo1"]["repo"] == _SSH
    # manual-repo should have been removed (untracked)
    assert "manual-repo" not in final_config.get("~/repos/", {})
