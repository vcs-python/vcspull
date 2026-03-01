"""Tests for vcspull import command."""

from __future__ import annotations

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
    _resolve_config_file,
    _run_import,
)
from vcspull.config import save_config_yaml, workspace_root_label

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

    # Create existing config with repo1
    existing_config = {
        "~/repos/": {
            "repo1": {"repo": "git+https://github.com/testuser/repo1.git"},
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
