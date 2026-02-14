"""Tests for vcspull import command."""

from __future__ import annotations

import json
import logging
import pathlib
import subprocess
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
from vcspull.cli.import_repos import (
    SERVICE_ALIASES,
    _get_importer,
    _resolve_config_file,
    import_repos,
)
from vcspull.config import workspace_root_label

# Get the actual module (not the function from __init__.py)
import_repos_mod = sys.modules["vcspull.cli.import_repos"]

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


class GetImporterFixture(t.NamedTuple):
    """Fixture for _get_importer test cases."""

    test_id: str
    service: str
    token: str | None
    base_url: str | None
    region: str | None
    profile: str | None
    expected_type_name: str
    expected_error: str | None


GET_IMPORTER_FIXTURES: list[GetImporterFixture] = [
    GetImporterFixture(
        test_id="github-direct",
        service="github",
        token=None,
        base_url=None,
        region=None,
        profile=None,
        expected_type_name="GitHubImporter",
        expected_error=None,
    ),
    GetImporterFixture(
        test_id="github-alias-gh",
        service="gh",
        token=None,
        base_url=None,
        region=None,
        profile=None,
        expected_type_name="GitHubImporter",
        expected_error=None,
    ),
    GetImporterFixture(
        test_id="gitlab-direct",
        service="gitlab",
        token="test-token",
        base_url=None,
        region=None,
        profile=None,
        expected_type_name="GitLabImporter",
        expected_error=None,
    ),
    GetImporterFixture(
        test_id="gitlab-alias-gl",
        service="gl",
        token=None,
        base_url=None,
        region=None,
        profile=None,
        expected_type_name="GitLabImporter",
        expected_error=None,
    ),
    GetImporterFixture(
        test_id="codeberg-direct",
        service="codeberg",
        token=None,
        base_url=None,
        region=None,
        profile=None,
        expected_type_name="GiteaImporter",
        expected_error=None,
    ),
    GetImporterFixture(
        test_id="codeberg-alias-cb",
        service="cb",
        token=None,
        base_url=None,
        region=None,
        profile=None,
        expected_type_name="GiteaImporter",
        expected_error=None,
    ),
    GetImporterFixture(
        test_id="codeberg-custom-url",
        service="codeberg",
        token=None,
        base_url="https://my-codeberg-mirror.example.com",
        region=None,
        profile=None,
        expected_type_name="GiteaImporter",
        expected_error=None,
    ),
    GetImporterFixture(
        test_id="gitea-with-url",
        service="gitea",
        token=None,
        base_url="https://gitea.example.com",
        region=None,
        profile=None,
        expected_type_name="GiteaImporter",
        expected_error=None,
    ),
    GetImporterFixture(
        test_id="gitea-without-url-fails",
        service="gitea",
        token=None,
        base_url=None,
        region=None,
        profile=None,
        expected_type_name="",
        expected_error="--url is required for gitea",
    ),
    GetImporterFixture(
        test_id="forgejo-with-url",
        service="forgejo",
        token=None,
        base_url="https://forgejo.example.com",
        region=None,
        profile=None,
        expected_type_name="GiteaImporter",
        expected_error=None,
    ),
    GetImporterFixture(
        test_id="forgejo-without-url-fails",
        service="forgejo",
        token=None,
        base_url=None,
        region=None,
        profile=None,
        expected_type_name="",
        expected_error="--url is required for forgejo",
    ),
    GetImporterFixture(
        test_id="codecommit-direct",
        service="codecommit",
        token=None,
        base_url=None,
        region="us-east-1",
        profile=None,
        expected_type_name="CodeCommitImporter",
        expected_error=None,
    ),
    GetImporterFixture(
        test_id="codecommit-alias-cc",
        service="cc",
        token=None,
        base_url=None,
        region=None,
        profile="myprofile",
        expected_type_name="CodeCommitImporter",
        expected_error=None,
    ),
    GetImporterFixture(
        test_id="codecommit-alias-aws",
        service="aws",
        token=None,
        base_url=None,
        region=None,
        profile=None,
        expected_type_name="CodeCommitImporter",
        expected_error=None,
    ),
    GetImporterFixture(
        test_id="unknown-service-fails",
        service="unknown",
        token=None,
        base_url=None,
        region=None,
        profile=None,
        expected_type_name="",
        expected_error="Unknown service: unknown",
    ),
]


@pytest.mark.parametrize(
    list(GetImporterFixture._fields),
    GET_IMPORTER_FIXTURES,
    ids=[f.test_id for f in GET_IMPORTER_FIXTURES],
)
def test_get_importer(
    test_id: str,
    service: str,
    token: str | None,
    base_url: str | None,
    region: str | None,
    profile: str | None,
    expected_type_name: str,
    expected_error: str | None,
    monkeypatch: MonkeyPatch,
) -> None:
    """Test _get_importer creates the correct importer type."""
    # Mock subprocess.run for CodeCommit tests (aws --version check)
    if service in ("codecommit", "cc", "aws"):
        monkeypatch.setattr(
            "subprocess.run",
            lambda cmd, **kwargs: subprocess.CompletedProcess(
                cmd, 0, stdout="aws-cli/2.x", stderr=""
            ),
        )

    if expected_error:
        with pytest.raises(ValueError, match=expected_error):
            _get_importer(
                service,
                token=token,
                base_url=base_url,
                region=region,
                profile=profile,
            )
    else:
        importer = _get_importer(
            service,
            token=token,
            base_url=base_url,
            region=region,
            profile=profile,
        )
        assert type(importer).__name__ == expected_type_name


def test_codeberg_custom_url_used() -> None:
    """Test that Codeberg importer uses custom base_url when provided."""
    from vcspull._internal.remotes.gitea import GiteaImporter

    importer = _get_importer(
        "codeberg",
        token=None,
        base_url="https://my-codeberg.example.com",
        region=None,
        profile=None,
    )
    assert isinstance(importer, GiteaImporter)
    assert importer._client.base_url == "https://my-codeberg.example.com/api/v1"


def test_codeberg_default_url_used() -> None:
    """Test that Codeberg importer uses default URL when no base_url."""
    from vcspull._internal.remotes.gitea import GiteaImporter

    importer = _get_importer(
        "codeberg",
        token=None,
        base_url=None,
        region=None,
        profile=None,
    )
    assert isinstance(importer, GiteaImporter)
    assert importer._client.base_url == "https://codeberg.org/api/v1"


def test_service_aliases_coverage() -> None:
    """Test that SERVICE_ALIASES covers expected services."""
    expected_aliases = {
        "github",
        "gh",
        "gitlab",
        "gl",
        "codeberg",
        "cb",
        "gitea",
        "forgejo",
        "codecommit",
        "cc",
        "aws",
    }
    assert set(SERVICE_ALIASES.keys()) == expected_aliases


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

    monkeypatch.setattr(
        import_repos_mod,
        "find_home_config_files",
        lambda filetype=None: full_paths,
    )

    result = _resolve_config_file(config_path_str)
    assert result.name == expected_suffix


class ImportReposFixture(t.NamedTuple):
    """Fixture for import_repos test cases."""

    test_id: str
    service: str
    target: str
    mode: str
    base_url: str | None
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
        service="github",
        target="testuser",
        mode="user",
        base_url=None,
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
        service="github",
        target="testuser",
        mode="user",
        base_url=None,
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
        service="github",
        target="emptyuser",
        mode="user",
        base_url=None,
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
        service="github",
        target="testuser",
        mode="user",
        base_url=None,
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
        service="github",
        target="testuser",
        mode="user",
        base_url=None,
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
        service="github",
        target="nosuchuser",
        mode="user",
        base_url=None,
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
        service="github",
        target="testuser",
        mode="user",
        base_url=None,
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
        service="codecommit",
        target="",
        mode="user",
        base_url=None,
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
        service="gitlab",
        target="testgroup",
        mode="org",
        base_url=None,
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
        service="codeberg",
        target="python cli",
        mode="search",
        base_url=None,
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
    service: str,
    target: str,
    mode: str,
    base_url: str | None,
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
    """Test import_repos with various scenarios."""
    caplog.set_level(logging.INFO)

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)

    workspace = tmp_path / "repos"
    workspace.mkdir()
    config_file = tmp_path / ".vcspull.yaml"

    # Mock the importer
    class MockImporter:
        service_name = "MockService"

        def fetch_repos(
            self,
            options: ImportOptions,
        ) -> t.Iterator[RemoteRepo]:
            if mock_error:
                raise mock_error
            yield from mock_repos

    monkeypatch.setattr(
        import_repos_mod,
        "_get_importer",
        lambda *args, **kwargs: MockImporter(),
    )

    import_repos(
        service=service,
        target=target,
        workspace=str(workspace),
        mode=mode,
        base_url=base_url,
        token=None,
        region=None,
        profile=None,
        language=None,
        topics=None,
        min_stars=0,
        include_archived=False,
        include_forks=False,
        limit=100,
        config_path_str=str(config_file),
        dry_run=dry_run,
        yes=yes,
        output_json=output_json,
        output_ndjson=False,
        color="never",
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


def test_import_repos_missing_target(
    tmp_path: pathlib.Path,
    monkeypatch: MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test import_repos fails when target is missing for non-codecommit."""
    caplog.set_level(logging.ERROR)

    monkeypatch.setenv("HOME", str(tmp_path))
    workspace = tmp_path / "repos"
    workspace.mkdir()

    import_repos(
        service="github",
        target="",  # Empty target
        workspace=str(workspace),
        mode="user",
        base_url=None,
        token=None,
        region=None,
        profile=None,
        language=None,
        topics=None,
        min_stars=0,
        include_archived=False,
        include_forks=False,
        limit=100,
        config_path_str=str(tmp_path / "config.yaml"),
        dry_run=False,
        yes=True,
        output_json=False,
        output_ndjson=False,
        color="never",
    )

    assert "TARGET is required" in caplog.text


def test_import_repos_unknown_service(
    tmp_path: pathlib.Path,
    monkeypatch: MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test import_repos fails for unknown service."""
    caplog.set_level(logging.ERROR)

    monkeypatch.setenv("HOME", str(tmp_path))
    workspace = tmp_path / "repos"
    workspace.mkdir()

    import_repos(
        service="unknownservice",
        target="testuser",
        workspace=str(workspace),
        mode="user",
        base_url=None,
        token=None,
        region=None,
        profile=None,
        language=None,
        topics=None,
        min_stars=0,
        include_archived=False,
        include_forks=False,
        limit=100,
        config_path_str=str(tmp_path / "config.yaml"),
        dry_run=False,
        yes=True,
        output_json=False,
        output_ndjson=False,
        color="never",
    )

    assert "Unknown service" in caplog.text


def test_import_repos_user_abort(
    tmp_path: pathlib.Path,
    monkeypatch: MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test import_repos aborts when user declines confirmation."""
    caplog.set_level(logging.INFO)

    monkeypatch.setenv("HOME", str(tmp_path))
    workspace = tmp_path / "repos"
    workspace.mkdir()
    config_file = tmp_path / ".vcspull.yaml"

    # Mock user input and ensure isatty returns True so we reach input()
    monkeypatch.setattr("builtins.input", lambda _: "n")
    monkeypatch.setattr(
        "sys.stdin", type("FakeTTY", (), {"isatty": lambda self: True})()
    )

    # Mock the importer
    class MockImporter:
        service_name = "MockService"

        def fetch_repos(
            self,
            options: ImportOptions,
        ) -> t.Iterator[RemoteRepo]:
            yield _make_repo("repo1")

    monkeypatch.setattr(
        import_repos_mod,
        "_get_importer",
        lambda *args, **kwargs: MockImporter(),
    )

    import_repos(
        service="github",
        target="testuser",
        workspace=str(workspace),
        mode="user",
        base_url=None,
        token=None,
        region=None,
        profile=None,
        language=None,
        topics=None,
        min_stars=0,
        include_archived=False,
        include_forks=False,
        limit=100,
        config_path_str=str(config_file),
        dry_run=False,
        yes=False,  # Require confirmation
        output_json=False,
        output_ndjson=False,
        color="never",
    )

    assert "Aborted by user" in caplog.text
    assert not config_file.exists()


def test_import_repos_eoferror_aborts(
    tmp_path: pathlib.Path,
    monkeypatch: MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test import_repos aborts gracefully on EOFError from input()."""
    caplog.set_level(logging.INFO)

    monkeypatch.setenv("HOME", str(tmp_path))
    workspace = tmp_path / "repos"
    workspace.mkdir()
    config_file = tmp_path / ".vcspull.yaml"

    # Mock input() to raise EOFError (e.g., piped stdin)
    def raise_eof(_: str) -> str:
        raise EOFError

    monkeypatch.setattr("builtins.input", raise_eof)
    # Ensure isatty returns True so we reach input()
    monkeypatch.setattr(
        "sys.stdin", type("FakeTTY", (), {"isatty": lambda self: True})()
    )

    class MockImporter:
        service_name = "MockService"

        def fetch_repos(
            self,
            options: ImportOptions,
        ) -> t.Iterator[RemoteRepo]:
            yield _make_repo("repo1")

    monkeypatch.setattr(
        import_repos_mod,
        "_get_importer",
        lambda *args, **kwargs: MockImporter(),
    )

    import_repos(
        service="github",
        target="testuser",
        workspace=str(workspace),
        mode="user",
        base_url=None,
        token=None,
        region=None,
        profile=None,
        language=None,
        topics=None,
        min_stars=0,
        include_archived=False,
        include_forks=False,
        limit=100,
        config_path_str=str(config_file),
        dry_run=False,
        yes=False,
        output_json=False,
        output_ndjson=False,
        color="never",
    )

    assert "Aborted by user" in caplog.text
    assert not config_file.exists()


def test_import_repos_non_tty_aborts(
    tmp_path: pathlib.Path,
    monkeypatch: MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test import_repos aborts when stdin is not a TTY."""
    caplog.set_level(logging.INFO)

    monkeypatch.setenv("HOME", str(tmp_path))
    workspace = tmp_path / "repos"
    workspace.mkdir()
    config_file = tmp_path / ".vcspull.yaml"

    # Mock stdin.isatty() to return False
    monkeypatch.setattr(
        "sys.stdin", type("FakeNonTTY", (), {"isatty": lambda self: False})()
    )

    class MockImporter:
        service_name = "MockService"

        def fetch_repos(
            self,
            options: ImportOptions,
        ) -> t.Iterator[RemoteRepo]:
            yield _make_repo("repo1")

    monkeypatch.setattr(
        import_repos_mod,
        "_get_importer",
        lambda *args, **kwargs: MockImporter(),
    )

    import_repos(
        service="github",
        target="testuser",
        workspace=str(workspace),
        mode="user",
        base_url=None,
        token=None,
        region=None,
        profile=None,
        language=None,
        topics=None,
        min_stars=0,
        include_archived=False,
        include_forks=False,
        limit=100,
        config_path_str=str(config_file),
        dry_run=False,
        yes=False,
        output_json=False,
        output_ndjson=False,
        color="never",
    )

    assert "Non-interactive mode" in caplog.text
    assert not config_file.exists()


def test_import_repos_skips_existing(
    tmp_path: pathlib.Path,
    monkeypatch: MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test import_repos skips repositories already in config."""
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
    config_file.write_text(yaml.dump(existing_config), encoding="utf-8")

    # Mock the importer to return repo1 (existing) and repo2 (new)
    class MockImporter:
        service_name = "MockService"

        def fetch_repos(
            self,
            options: ImportOptions,
        ) -> t.Iterator[RemoteRepo]:
            yield _make_repo("repo1")
            yield _make_repo("repo2")

    monkeypatch.setattr(
        import_repos_mod,
        "_get_importer",
        lambda *args, **kwargs: MockImporter(),
    )

    import_repos(
        service="github",
        target="testuser",
        workspace=str(workspace),
        mode="user",
        base_url=None,
        token=None,
        region=None,
        profile=None,
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
    """Test import_repos handles all repos already existing."""
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
    config_file.write_text(yaml.dump(existing_config), encoding="utf-8")

    # Mock the importer to return only repo1 (existing)
    class MockImporter:
        service_name = "MockService"

        def fetch_repos(
            self,
            options: ImportOptions,
        ) -> t.Iterator[RemoteRepo]:
            yield _make_repo("repo1")

    monkeypatch.setattr(
        import_repos_mod,
        "_get_importer",
        lambda *args, **kwargs: MockImporter(),
    )

    import_repos(
        service="github",
        target="testuser",
        workspace=str(workspace),
        mode="user",
        base_url=None,
        token=None,
        region=None,
        profile=None,
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

    assert "All repositories already exist" in caplog.text


def test_import_repos_json_output(
    tmp_path: pathlib.Path,
    monkeypatch: MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Test import_repos JSON output format."""
    monkeypatch.setenv("HOME", str(tmp_path))
    workspace = tmp_path / "repos"
    workspace.mkdir()

    # Mock the importer
    class MockImporter:
        service_name = "MockService"

        def fetch_repos(
            self,
            options: ImportOptions,
        ) -> t.Iterator[RemoteRepo]:
            yield _make_repo("repo1", stars=50)

    monkeypatch.setattr(
        import_repos_mod,
        "_get_importer",
        lambda *args, **kwargs: MockImporter(),
    )

    import_repos(
        service="github",
        target="testuser",
        workspace=str(workspace),
        mode="user",
        base_url=None,
        token=None,
        region=None,
        profile=None,
        language=None,
        topics=None,
        min_stars=0,
        include_archived=False,
        include_forks=False,
        limit=100,
        config_path_str=str(tmp_path / "config.yaml"),
        dry_run=True,
        yes=True,
        output_json=True,
        output_ndjson=False,
        color="never",
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
    """Test import_repos NDJSON output format."""
    monkeypatch.setenv("HOME", str(tmp_path))
    workspace = tmp_path / "repos"
    workspace.mkdir()

    # Mock the importer
    class MockImporter:
        service_name = "MockService"

        def fetch_repos(
            self,
            options: ImportOptions,
        ) -> t.Iterator[RemoteRepo]:
            yield _make_repo("repo1")
            yield _make_repo("repo2")

    monkeypatch.setattr(
        import_repos_mod,
        "_get_importer",
        lambda *args, **kwargs: MockImporter(),
    )

    import_repos(
        service="github",
        target="testuser",
        workspace=str(workspace),
        mode="user",
        base_url=None,
        token=None,
        region=None,
        profile=None,
        language=None,
        topics=None,
        min_stars=0,
        include_archived=False,
        include_forks=False,
        limit=100,
        config_path_str=str(tmp_path / "config.yaml"),
        dry_run=True,
        yes=True,
        output_json=False,
        output_ndjson=True,
        color="never",
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
    """Test import_repos passes topics filter correctly."""
    caplog.set_level(logging.INFO)

    monkeypatch.setenv("HOME", str(tmp_path))
    workspace = tmp_path / "repos"
    workspace.mkdir()

    received_options: list[ImportOptions] = []

    class MockImporter:
        service_name = "MockService"

        def fetch_repos(
            self,
            options: ImportOptions,
        ) -> t.Iterator[RemoteRepo]:
            received_options.append(options)
            return iter([])

    monkeypatch.setattr(
        import_repos_mod,
        "_get_importer",
        lambda *args, **kwargs: MockImporter(),
    )

    import_repos(
        service="github",
        target="testuser",
        workspace=str(workspace),
        mode="user",
        base_url=None,
        token=None,
        region=None,
        profile=None,
        language="Python",
        topics="cli,tool,python",
        min_stars=50,
        include_archived=True,
        include_forks=True,
        limit=200,
        config_path_str=str(tmp_path / "config.yaml"),
        dry_run=True,
        yes=True,
        output_json=False,
        output_ndjson=False,
        color="never",
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
    """Test import_repos allows empty target for codecommit."""
    caplog.set_level(logging.INFO)

    monkeypatch.setenv("HOME", str(tmp_path))
    workspace = tmp_path / "repos"
    workspace.mkdir()

    class MockImporter:
        service_name = "CodeCommit"

        def fetch_repos(
            self,
            options: ImportOptions,
        ) -> t.Iterator[RemoteRepo]:
            yield _make_repo("aws-repo")

    monkeypatch.setattr(
        import_repos_mod,
        "_get_importer",
        lambda *args, **kwargs: MockImporter(),
    )

    import_repos(
        service="codecommit",
        target="",  # Empty target is OK for CodeCommit
        workspace=str(workspace),
        mode="user",
        base_url=None,
        token=None,
        region="us-east-1",
        profile=None,
        language=None,
        topics=None,
        min_stars=0,
        include_archived=False,
        include_forks=False,
        limit=100,
        config_path_str=str(tmp_path / "config.yaml"),
        dry_run=True,
        yes=True,
        output_json=False,
        output_ndjson=False,
        color="never",
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
    """Test import_repos shows '...and X more' when many repos."""
    caplog.set_level(logging.INFO)

    monkeypatch.setenv("HOME", str(tmp_path))
    workspace = tmp_path / "repos"
    workspace.mkdir()

    # Create 15 repos
    many_repos = [_make_repo(f"repo{i}") for i in range(15)]

    class MockImporter:
        service_name = "MockService"

        def fetch_repos(
            self,
            options: ImportOptions,
        ) -> t.Iterator[RemoteRepo]:
            yield from many_repos

    monkeypatch.setattr(
        import_repos_mod,
        "_get_importer",
        lambda *args, **kwargs: MockImporter(),
    )

    import_repos(
        service="github",
        target="testuser",
        workspace=str(workspace),
        mode="user",
        base_url=None,
        token=None,
        region=None,
        profile=None,
        language=None,
        topics=None,
        min_stars=0,
        include_archived=False,
        include_forks=False,
        limit=100,
        config_path_str=str(tmp_path / "config.yaml"),
        dry_run=True,
        yes=True,
        output_json=False,
        output_ndjson=False,
        color="never",
    )

    assert "Found 15 repositories" in caplog.text
    assert "and 5 more" in caplog.text


def test_import_repos_config_load_error(
    tmp_path: pathlib.Path,
    monkeypatch: MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test import_repos handles config load errors."""
    caplog.set_level(logging.ERROR)

    monkeypatch.setenv("HOME", str(tmp_path))
    workspace = tmp_path / "repos"
    workspace.mkdir()

    # Create an invalid YAML file
    config_file = tmp_path / ".vcspull.yaml"
    config_file.write_text("invalid: yaml: content: [", encoding="utf-8")

    class MockImporter:
        service_name = "MockService"

        def fetch_repos(
            self,
            options: ImportOptions,
        ) -> t.Iterator[RemoteRepo]:
            yield _make_repo("repo1")

    monkeypatch.setattr(
        import_repos_mod,
        "_get_importer",
        lambda *args, **kwargs: MockImporter(),
    )

    import_repos(
        service="github",
        target="testuser",
        workspace=str(workspace),
        mode="user",
        base_url=None,
        token=None,
        region=None,
        profile=None,
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

    assert "Error loading config" in caplog.text


def test_import_no_args_shows_help(capsys: pytest.CaptureFixture[str]) -> None:
    """Test that 'vcspull import' without args shows help (like --help)."""
    from vcspull.cli import cli

    # Call cli with just "import" - should show help and not error
    cli(["import"])

    captured = capsys.readouterr()
    # Verify help is shown (usage line and description)
    assert "usage: vcspull import" in captured.out
    assert "Import repositories from remote services" in captured.out
    assert "positional arguments:" in captured.out
    assert "SERVICE" in captured.out


def test_import_only_service_shows_help(capsys: pytest.CaptureFixture[str]) -> None:
    """Test that 'vcspull import github' without workspace shows help."""
    from vcspull.cli import cli

    # Call cli with just "import github" - missing workspace
    cli(["import", "github"])

    captured = capsys.readouterr()
    # Verify help is shown
    assert "usage: vcspull import" in captured.out
    assert "-w, --workspace DIR" in captured.out


def test_import_repos_defaults_to_ssh_urls(
    tmp_path: pathlib.Path,
    monkeypatch: MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test import_repos writes SSH URLs to config by default."""
    import yaml

    caplog.set_level(logging.INFO)

    monkeypatch.setenv("HOME", str(tmp_path))
    workspace = tmp_path / "repos"
    workspace.mkdir()
    config_file = tmp_path / ".vcspull.yaml"

    class MockImporter:
        service_name = "MockService"

        def fetch_repos(
            self,
            options: ImportOptions,
        ) -> t.Iterator[RemoteRepo]:
            yield _make_repo("myrepo")

    monkeypatch.setattr(
        import_repos_mod,
        "_get_importer",
        lambda *args, **kwargs: MockImporter(),
    )

    import_repos(
        service="github",
        target="testuser",
        workspace=str(workspace),
        mode="user",
        base_url=None,
        token=None,
        region=None,
        profile=None,
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

    assert config_file.exists()
    with config_file.open() as f:
        config = yaml.safe_load(f)

    repo_url = config["~/repos/"]["myrepo"]["repo"]
    assert repo_url == "git+git@github.com:testuser/myrepo.git"


def test_import_repos_https_flag(
    tmp_path: pathlib.Path,
    monkeypatch: MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test import_repos writes HTTPS URLs when use_https=True."""
    import yaml

    caplog.set_level(logging.INFO)

    monkeypatch.setenv("HOME", str(tmp_path))
    workspace = tmp_path / "repos"
    workspace.mkdir()
    config_file = tmp_path / ".vcspull.yaml"

    class MockImporter:
        service_name = "MockService"

        def fetch_repos(
            self,
            options: ImportOptions,
        ) -> t.Iterator[RemoteRepo]:
            yield _make_repo("myrepo")

    monkeypatch.setattr(
        import_repos_mod,
        "_get_importer",
        lambda *args, **kwargs: MockImporter(),
    )

    import_repos(
        service="github",
        target="testuser",
        workspace=str(workspace),
        mode="user",
        base_url=None,
        token=None,
        region=None,
        profile=None,
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
        use_https=True,
    )

    assert config_file.exists()
    with config_file.open() as f:
        config = yaml.safe_load(f)

    repo_url = config["~/repos/"]["myrepo"]["repo"]
    assert repo_url == "git+https://github.com/testuser/myrepo.git"


def test_import_https_flag_via_cli(capsys: pytest.CaptureFixture[str]) -> None:
    """Test that --https flag is recognized by the CLI parser."""
    from vcspull.cli import create_parser

    parser = create_parser(return_subparsers=False)
    args = parser.parse_args(
        ["import", "github", "testuser", "-w", "/tmp/repos", "--https"]
    )
    assert args.use_https is True
    assert args.flatten_groups is False


def test_import_ssh_default_via_cli(capsys: pytest.CaptureFixture[str]) -> None:
    """Test that SSH is the default (no --https flag)."""
    from vcspull.cli import create_parser

    parser = create_parser(return_subparsers=False)
    args = parser.parse_args(["import", "github", "testuser", "-w", "/tmp/repos"])
    assert args.use_https is False
    assert args.flatten_groups is False


def test_import_flatten_groups_flag_via_cli(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Test that --flatten-groups flag is recognized by the CLI parser."""
    from vcspull.cli import create_parser

    parser = create_parser(return_subparsers=False)
    args = parser.parse_args(
        ["import", "gitlab", "group/subgroup", "-w", "/tmp/repos", "--flatten-groups"]
    )
    assert args.flatten_groups is True


def test_import_repos_rejects_non_yaml_config(
    tmp_path: pathlib.Path,
    monkeypatch: MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test import_repos rejects non-YAML config file paths."""
    caplog.set_level(logging.ERROR)

    monkeypatch.setenv("HOME", str(tmp_path))
    workspace = tmp_path / "repos"
    workspace.mkdir()

    class MockImporter:
        service_name = "MockService"

        def fetch_repos(
            self,
            options: ImportOptions,
        ) -> t.Iterator[RemoteRepo]:
            yield _make_repo("repo1")

    monkeypatch.setattr(
        import_repos_mod,
        "_get_importer",
        lambda *args, **kwargs: MockImporter(),
    )

    import_repos(
        service="github",
        target="testuser",
        workspace=str(workspace),
        mode="user",
        base_url=None,
        token=None,
        region=None,
        profile=None,
        language=None,
        topics=None,
        min_stars=0,
        include_archived=False,
        include_forks=False,
        limit=100,
        config_path_str=str(tmp_path / "config.json"),
        dry_run=False,
        yes=True,
        output_json=False,
        output_ndjson=False,
        color="never",
    )

    assert "Only YAML config files are supported" in caplog.text


def test_import_repos_catches_multiple_config_warning(
    tmp_path: pathlib.Path,
    monkeypatch: MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test import_repos logs error instead of crashing on MultipleConfigWarning."""
    from vcspull.exc import MultipleConfigWarning

    caplog.set_level(logging.ERROR)

    monkeypatch.setenv("HOME", str(tmp_path))
    workspace = tmp_path / "repos"
    workspace.mkdir()

    class MockImporter:
        service_name = "MockService"

        def fetch_repos(
            self,
            options: ImportOptions,
        ) -> t.Iterator[RemoteRepo]:
            yield _make_repo("repo1")

    monkeypatch.setattr(
        import_repos_mod,
        "_get_importer",
        lambda *args, **kwargs: MockImporter(),
    )

    # Mock _resolve_config_file to raise MultipleConfigWarning
    def raise_multiple_config(_: str | None) -> pathlib.Path:
        raise MultipleConfigWarning(MultipleConfigWarning.message)

    monkeypatch.setattr(
        import_repos_mod,
        "_resolve_config_file",
        raise_multiple_config,
    )

    import_repos(
        service="github",
        target="testuser",
        workspace=str(workspace),
        mode="user",
        base_url=None,
        token=None,
        region=None,
        profile=None,
        language=None,
        topics=None,
        min_stars=0,
        include_archived=False,
        include_forks=False,
        limit=100,
        config_path_str=None,
        dry_run=False,
        yes=True,
        output_json=False,
        output_ndjson=False,
        color="never",
    )

    assert "Multiple configs" in caplog.text


def test_import_repos_invalid_limit(
    tmp_path: pathlib.Path,
    monkeypatch: MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test import_repos logs error for invalid limit (e.g. 0)."""
    caplog.set_level(logging.ERROR)

    monkeypatch.setenv("HOME", str(tmp_path))
    workspace = tmp_path / "repos"
    workspace.mkdir()

    class MockImporter:
        service_name = "MockService"

        def fetch_repos(
            self,
            options: ImportOptions,
        ) -> t.Iterator[RemoteRepo]:
            yield _make_repo("repo1")

    monkeypatch.setattr(
        import_repos_mod,
        "_get_importer",
        lambda *args, **kwargs: MockImporter(),
    )

    import_repos(
        service="github",
        target="testuser",
        workspace=str(workspace),
        mode="user",
        base_url=None,
        token=None,
        region=None,
        profile=None,
        language=None,
        topics=None,
        min_stars=0,
        include_archived=False,
        include_forks=False,
        limit=0,
        config_path_str=str(tmp_path / "config.yaml"),
        dry_run=False,
        yes=True,
        output_json=False,
        output_ndjson=False,
        color="never",
    )

    assert "limit must be >= 1" in caplog.text


def test_import_repos_rejects_non_dict_config(
    tmp_path: pathlib.Path,
    monkeypatch: MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test import_repos rejects config that is a YAML list instead of dict."""
    caplog.set_level(logging.ERROR)

    monkeypatch.setenv("HOME", str(tmp_path))
    workspace = tmp_path / "repos"
    workspace.mkdir()
    config_file = tmp_path / ".vcspull.yaml"
    # Write a YAML list instead of a mapping
    config_file.write_text("- item1\n- item2\n", encoding="utf-8")

    class MockImporter:
        service_name = "MockService"

        def fetch_repos(
            self,
            options: ImportOptions,
        ) -> t.Iterator[RemoteRepo]:
            yield _make_repo("repo1")

    monkeypatch.setattr(
        import_repos_mod,
        "_get_importer",
        lambda *args, **kwargs: MockImporter(),
    )

    import_repos(
        service="github",
        target="testuser",
        workspace=str(workspace),
        mode="user",
        base_url=None,
        token=None,
        region=None,
        profile=None,
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

    assert "not a valid YAML mapping" in caplog.text


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

    class MockImporter:
        service_name = "GitLab"

        def fetch_repos(self, options: ImportOptions) -> t.Iterator[RemoteRepo]:
            yield from mock_repos

    # Mock the importer factory so import_repos() exercises only workspace mapping.
    monkeypatch.setattr(
        import_repos_mod,
        "_get_importer",
        lambda *args, **kwargs: MockImporter(),
    )

    import_repos(
        service="gitlab",
        target=target,
        workspace=str(workspace),
        mode=mode,
        base_url=None,
        token=None,
        region=None,
        profile=None,
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
    service: str
    language: str | None
    expect_warning: bool


LANGUAGE_WARNING_FIXTURES: list[LanguageWarningFixture] = [
    LanguageWarningFixture(
        test_id="gitlab-with-language-warns",
        service="gitlab",
        language="Python",
        expect_warning=True,
    ),
    LanguageWarningFixture(
        test_id="codecommit-with-language-warns",
        service="codecommit",
        language="Python",
        expect_warning=True,
    ),
    LanguageWarningFixture(
        test_id="github-with-language-no-warning",
        service="github",
        language="Python",
        expect_warning=False,
    ),
    LanguageWarningFixture(
        test_id="gitlab-without-language-no-warning",
        service="gitlab",
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
    service: str,
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

    class MockImporter:
        service_name = {"gitlab": "GitLab", "codecommit": "CodeCommit"}.get(
            service, "GitHub"
        )

        def fetch_repos(
            self,
            options: ImportOptions,
        ) -> t.Iterator[RemoteRepo]:
            return iter([])

    monkeypatch.setattr(
        import_repos_mod,
        "_get_importer",
        lambda *args, **kwargs: MockImporter(),
    )

    import_repos(
        service=service,
        target="testuser" if service != "codecommit" else "",
        workspace=str(workspace),
        mode="user",
        base_url=None,
        token=None,
        region="us-east-1" if service == "codecommit" else None,
        profile=None,
        language=language,
        topics=None,
        min_stars=0,
        include_archived=False,
        include_forks=False,
        limit=100,
        config_path_str=str(tmp_path / "config.yaml"),
        dry_run=True,
        yes=True,
        output_json=False,
        output_ndjson=False,
        color="never",
    )

    if expect_warning:
        assert "does not return language metadata" in caplog.text
    else:
        assert "does not return language metadata" not in caplog.text
