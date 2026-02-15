"""Tests for vcspull._internal.remotes.codecommit module."""

from __future__ import annotations

import json
import subprocess
import typing as t

import pytest

from vcspull._internal.remotes.base import ImportOptions
from vcspull._internal.remotes.codecommit import CodeCommitImporter


def _aws_ok(
    stdout: str = "",
    stderr: str = "",
) -> subprocess.CompletedProcess[str]:
    """Create a successful subprocess result."""
    return subprocess.CompletedProcess(
        args=["aws"],
        returncode=0,
        stdout=stdout,
        stderr=stderr,
    )


def _aws_err(
    stderr: str = "",
    returncode: int = 1,
) -> subprocess.CompletedProcess[str]:
    """Create a failed subprocess result."""
    return subprocess.CompletedProcess(
        args=["aws"],
        returncode=returncode,
        stdout="",
        stderr=stderr,
    )


def _make_cc_repo(
    name: str,
    *,
    region: str = "us-east-1",
    account_id: str = "123456789012",
    default_branch: str = "main",
    description: str | None = None,
) -> dict[str, t.Any]:
    """Create a CodeCommit repository metadata dict."""
    return {
        "repositoryName": name,
        "cloneUrlHttp": (
            f"https://git-codecommit.{region}.amazonaws.com/v1/repos/{name}"
        ),
        "cloneUrlSsh": (f"ssh://git-codecommit.{region}.amazonaws.com/v1/repos/{name}"),
        "accountId": account_id,
        "defaultBranch": default_branch,
        "repositoryDescription": description,
    }


# ---------------------------------------------------------------------------
# _check_aws_cli
# ---------------------------------------------------------------------------


def test_check_aws_cli_file_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test _check_aws_cli raises DependencyError when aws binary missing."""
    from vcspull._internal.remotes.base import DependencyError

    def mock_run(cmd: list[str], **kwargs: t.Any) -> subprocess.CompletedProcess[str]:
        msg = "aws"
        raise FileNotFoundError(msg)

    # Mock subprocess.run: simulate aws binary not found (FileNotFoundError)
    monkeypatch.setattr("subprocess.run", mock_run)

    with pytest.raises(DependencyError, match="not installed"):
        CodeCommitImporter()


def test_check_aws_cli_nonzero_returncode(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test _check_aws_cli raises DependencyError for non-zero returncode."""
    from vcspull._internal.remotes.base import DependencyError

    # Mock subprocess.run: simulate aws CLI returning non-zero exit code
    monkeypatch.setattr("subprocess.run", lambda cmd, **kw: _aws_err())

    with pytest.raises(DependencyError, match="not installed"):
        CodeCommitImporter()


# ---------------------------------------------------------------------------
# _build_aws_command
# ---------------------------------------------------------------------------


def test_build_aws_command_no_flags(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test _build_aws_command with no region/profile."""
    # Mock subprocess.run: allow CodeCommitImporter construction (aws --version check)
    monkeypatch.setattr("subprocess.run", lambda cmd, **kw: _aws_ok("aws-cli/2.x"))

    importer = CodeCommitImporter()
    result = importer._build_aws_command("codecommit", "list-repositories")
    assert result == ["aws", "--output", "json", "codecommit", "list-repositories"]


def test_build_aws_command_with_region(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test _build_aws_command appends --region."""
    # Mock subprocess.run: allow CodeCommitImporter construction (aws --version check)
    monkeypatch.setattr("subprocess.run", lambda cmd, **kw: _aws_ok("aws-cli/2.x"))

    importer = CodeCommitImporter(region="eu-west-1")
    result = importer._build_aws_command("codecommit", "list-repositories")
    assert result == [
        "aws",
        "--output",
        "json",
        "--region",
        "eu-west-1",
        "codecommit",
        "list-repositories",
    ]


def test_build_aws_command_with_profile(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test _build_aws_command appends --profile."""
    # Mock subprocess.run: allow CodeCommitImporter construction (aws --version check)
    monkeypatch.setattr("subprocess.run", lambda cmd, **kw: _aws_ok("aws-cli/2.x"))

    importer = CodeCommitImporter(profile="myprofile")
    result = importer._build_aws_command("codecommit", "list-repositories")
    assert result == [
        "aws",
        "--output",
        "json",
        "--profile",
        "myprofile",
        "codecommit",
        "list-repositories",
    ]


def test_build_aws_command_with_region_and_profile(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test _build_aws_command with both region and profile."""
    # Mock subprocess.run: allow CodeCommitImporter construction (aws --version check)
    monkeypatch.setattr("subprocess.run", lambda cmd, **kw: _aws_ok("aws-cli/2.x"))

    importer = CodeCommitImporter(region="ap-south-1", profile="prod")
    result = importer._build_aws_command("sts", "get-caller-identity")
    assert result == [
        "aws",
        "--output",
        "json",
        "--region",
        "ap-south-1",
        "--profile",
        "prod",
        "sts",
        "get-caller-identity",
    ]


# ---------------------------------------------------------------------------
# _run_aws_command — error handling
# ---------------------------------------------------------------------------


class RunAwsErrorFixture(t.NamedTuple):
    """Fixture for _run_aws_command error test cases."""

    test_id: str
    stderr: str
    expected_error_type: str
    expected_match: str


RUN_AWS_ERROR_FIXTURES: list[RunAwsErrorFixture] = [
    RunAwsErrorFixture(
        test_id="credential-error",
        stderr="Unable to locate credentials",
        expected_error_type="AuthenticationError",
        expected_match="credentials not configured",
    ),
    RunAwsErrorFixture(
        test_id="endpoint-connection-error",
        stderr="Could not connect to the endpoint URL",
        expected_error_type="ConfigurationError",
        expected_match="Could not connect",
    ),
    RunAwsErrorFixture(
        test_id="invalid-region-error",
        stderr="Invalid region: foobar-1",
        expected_error_type="ConfigurationError",
        expected_match="Invalid AWS region",
    ),
    RunAwsErrorFixture(
        test_id="generic-aws-error",
        stderr="Something unexpected happened",
        expected_error_type="ConfigurationError",
        expected_match="AWS CLI error",
    ),
]


@pytest.mark.parametrize(
    list(RunAwsErrorFixture._fields),
    RUN_AWS_ERROR_FIXTURES,
    ids=[f.test_id for f in RUN_AWS_ERROR_FIXTURES],
)
def test_run_aws_command_errors(
    test_id: str,
    stderr: str,
    expected_error_type: str,
    expected_match: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test _run_aws_command handles various AWS CLI errors."""
    from vcspull._internal.remotes import base

    call_count = 0

    def mock_run(cmd: list[str], **kwargs: t.Any) -> subprocess.CompletedProcess[str]:
        nonlocal call_count
        call_count += 1
        # First call is _check_aws_cli — succeed
        if call_count == 1:
            return _aws_ok("aws-cli/2.x")
        # Subsequent calls fail with the test error
        return _aws_err(stderr=stderr)

    # Mock subprocess.run: first call passes aws --version, subsequent calls fail
    # with the specific AWS CLI error under test
    monkeypatch.setattr("subprocess.run", mock_run)
    importer = CodeCommitImporter()

    error_class = getattr(base, expected_error_type)
    with pytest.raises(error_class, match=expected_match):
        importer._run_aws_command("codecommit", "list-repositories")


def test_run_aws_command_json_parse_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test _run_aws_command raises ConfigurationError for invalid JSON."""
    from vcspull._internal.remotes.base import ConfigurationError

    call_count = 0

    def mock_run(cmd: list[str], **kwargs: t.Any) -> subprocess.CompletedProcess[str]:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return _aws_ok("aws-cli/2.x")
        return _aws_ok(stdout="not valid json {{{")

    # Mock subprocess.run: first call passes aws --version, second returns invalid JSON
    monkeypatch.setattr("subprocess.run", mock_run)
    importer = CodeCommitImporter()

    with pytest.raises(ConfigurationError, match="Invalid JSON"):
        importer._run_aws_command("codecommit", "list-repositories")


def test_run_aws_command_file_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test _run_aws_command raises DependencyError when aws disappears mid-session."""
    from vcspull._internal.remotes.base import DependencyError

    call_count = 0

    def mock_run(cmd: list[str], **kwargs: t.Any) -> subprocess.CompletedProcess[str]:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return _aws_ok("aws-cli/2.x")
        msg = "aws"
        raise FileNotFoundError(msg)

    # Mock subprocess.run: first call passes aws --version, second raises
    # FileNotFoundError to simulate aws binary disappearing mid-session
    monkeypatch.setattr("subprocess.run", mock_run)
    importer = CodeCommitImporter()

    with pytest.raises(DependencyError, match="not found"):
        importer._run_aws_command("codecommit", "list-repositories")


# ---------------------------------------------------------------------------
# fetch_repos
# ---------------------------------------------------------------------------


def test_fetch_repos_basic(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test fetch_repos returns repos from list + batch-get pipeline."""
    repos_data = [_make_cc_repo("my-repo"), _make_cc_repo("other-repo")]

    call_count = 0

    def mock_run(cmd: list[str], **kwargs: t.Any) -> subprocess.CompletedProcess[str]:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            # _check_aws_cli
            return _aws_ok("aws-cli/2.x")
        if "list-repositories" in cmd:
            return _aws_ok(
                json.dumps(
                    {
                        "repositories": [
                            {"repositoryName": "my-repo"},
                            {"repositoryName": "other-repo"},
                        ]
                    }
                )
            )
        if "batch-get-repositories" in cmd:
            return _aws_ok(json.dumps({"repositories": repos_data}))
        return _aws_err(stderr="unknown command")

    # Mock subprocess.run: simulate aws --version, list-repositories, and
    # batch-get-repositories responses to test the full fetch pipeline
    monkeypatch.setattr("subprocess.run", mock_run)
    importer = CodeCommitImporter()
    options = ImportOptions()
    repos = list(importer.fetch_repos(options))

    assert len(repos) == 2
    assert repos[0].name == "my-repo"
    assert repos[1].name == "other-repo"


def test_fetch_repos_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test fetch_repos returns nothing when no repositories exist."""
    call_count = 0

    def mock_run(cmd: list[str], **kwargs: t.Any) -> subprocess.CompletedProcess[str]:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return _aws_ok("aws-cli/2.x")
        if "list-repositories" in cmd:
            return _aws_ok(json.dumps({"repositories": []}))
        return _aws_err(stderr="unknown command")

    # Mock subprocess.run: simulate aws --version and empty list-repositories response
    monkeypatch.setattr("subprocess.run", mock_run)
    importer = CodeCommitImporter()
    options = ImportOptions()
    repos = list(importer.fetch_repos(options))

    assert len(repos) == 0


def test_fetch_repos_name_filter(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test fetch_repos filters by target name."""
    repos_data = [_make_cc_repo("django-app")]

    call_count = 0

    def mock_run(cmd: list[str], **kwargs: t.Any) -> subprocess.CompletedProcess[str]:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return _aws_ok("aws-cli/2.x")
        if "list-repositories" in cmd:
            return _aws_ok(
                json.dumps(
                    {
                        "repositories": [
                            {"repositoryName": "django-app"},
                            {"repositoryName": "flask-app"},
                            {"repositoryName": "react-app"},
                        ]
                    }
                )
            )
        if "batch-get-repositories" in cmd:
            # Only django-app should be requested
            assert "django-app" in cmd
            return _aws_ok(json.dumps({"repositories": repos_data}))
        return _aws_err(stderr="unknown command")

    # Mock subprocess.run: simulate aws --version, list-repositories with
    # multiple repos, and batch-get for only the name-filtered subset
    monkeypatch.setattr("subprocess.run", mock_run)
    importer = CodeCommitImporter()
    options = ImportOptions(target="django")
    repos = list(importer.fetch_repos(options))

    assert len(repos) == 1
    assert repos[0].name == "django-app"


def test_fetch_repos_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test fetch_repos respects limit option."""
    repos_data = [_make_cc_repo(f"repo{i}") for i in range(5)]

    call_count = 0

    def mock_run(cmd: list[str], **kwargs: t.Any) -> subprocess.CompletedProcess[str]:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return _aws_ok("aws-cli/2.x")
        if "list-repositories" in cmd:
            return _aws_ok(
                json.dumps(
                    {"repositories": [{"repositoryName": f"repo{i}"} for i in range(5)]}
                )
            )
        if "batch-get-repositories" in cmd:
            return _aws_ok(json.dumps({"repositories": repos_data}))
        return _aws_err(stderr="unknown command")

    # Mock subprocess.run: simulate full pipeline to verify limit is respected
    monkeypatch.setattr("subprocess.run", mock_run)
    importer = CodeCommitImporter()
    options = ImportOptions(limit=2)
    repos = list(importer.fetch_repos(options))

    assert len(repos) == 2


def test_fetch_repos_batch_processing(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test fetch_repos batches in groups of 25."""
    # Create 30 repos — should result in 2 batch-get calls (25 + 5)
    batch_get_calls: list[list[str]] = []

    call_count = 0

    def mock_run(cmd: list[str], **kwargs: t.Any) -> subprocess.CompletedProcess[str]:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return _aws_ok("aws-cli/2.x")
        if "list-repositories" in cmd:
            return _aws_ok(
                json.dumps(
                    {
                        "repositories": [
                            {"repositoryName": f"repo{i}"} for i in range(30)
                        ]
                    }
                )
            )
        if "batch-get-repositories" in cmd:
            # Extract repo names from command (after --repository-names)
            names_idx = cmd.index("--repository-names") + 1
            repo_names = cmd[names_idx:]
            batch_get_calls.append(repo_names)
            repos = [_make_cc_repo(name) for name in repo_names]
            return _aws_ok(json.dumps({"repositories": repos}))
        return _aws_err(stderr="unknown command")

    # Mock subprocess.run: simulate 30 repos to verify batch-get splits at 25
    monkeypatch.setattr("subprocess.run", mock_run)
    importer = CodeCommitImporter()
    options = ImportOptions(limit=100)
    repos = list(importer.fetch_repos(options))

    assert len(repos) == 30
    assert len(batch_get_calls) == 2
    assert len(batch_get_calls[0]) == 25
    assert len(batch_get_calls[1]) == 5


def test_fetch_repos_pagination(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test fetch_repos handles nextToken pagination across list-repositories calls."""
    call_count = 0
    list_calls: list[list[str]] = []

    def mock_run(cmd: list[str], **kwargs: t.Any) -> subprocess.CompletedProcess[str]:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return _aws_ok("aws-cli/2.x")
        if "list-repositories" in cmd:
            list_calls.append(cmd)
            if "--next-token" not in cmd:
                # First page: return 2 repos + nextToken
                return _aws_ok(
                    json.dumps(
                        {
                            "repositories": [
                                {"repositoryName": "page1-repo1"},
                                {"repositoryName": "page1-repo2"},
                            ],
                            "nextToken": "token-page2",
                        }
                    )
                )
            # Second page: return 1 repo, no nextToken
            return _aws_ok(
                json.dumps(
                    {
                        "repositories": [
                            {"repositoryName": "page2-repo1"},
                        ],
                    }
                )
            )
        if "batch-get-repositories" in cmd:
            names_idx = cmd.index("--repository-names") + 1
            repo_names = cmd[names_idx:]
            repos = [_make_cc_repo(name) for name in repo_names]
            return _aws_ok(json.dumps({"repositories": repos}))
        return _aws_err(stderr="unknown command")

    # Mock subprocess.run: simulate paginated list-repositories with nextToken
    # to verify the importer follows pagination tokens across pages
    monkeypatch.setattr("subprocess.run", mock_run)
    importer = CodeCommitImporter()
    options = ImportOptions()
    repos = list(importer.fetch_repos(options))

    # Should have consumed both pages
    assert len(repos) == 3
    assert {r.name for r in repos} == {"page1-repo1", "page1-repo2", "page2-repo1"}
    # Should have made 2 list-repositories calls
    assert len(list_calls) == 2
    assert "--next-token" not in list_calls[0]
    assert "--next-token" in list_calls[1]


# ---------------------------------------------------------------------------
# _parse_repo — region extraction
# ---------------------------------------------------------------------------


def test_parse_repo_region_from_clone_url(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test _parse_repo extracts region from clone URL when not set."""
    # Mock subprocess.run: allow CodeCommitImporter construction (aws --version check)
    monkeypatch.setattr("subprocess.run", lambda cmd, **kw: _aws_ok("aws-cli/2.x"))

    # No region set — should extract from clone URL
    importer = CodeCommitImporter(region=None)
    data = _make_cc_repo("my-repo", region="us-west-2")
    repo = importer._parse_repo(data)

    assert "us-west-2" in repo.html_url
    assert "us-east-1" not in repo.html_url


def test_parse_repo_region_explicit(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test _parse_repo uses explicit region when set."""
    # Mock subprocess.run: allow CodeCommitImporter construction (aws --version check)
    monkeypatch.setattr("subprocess.run", lambda cmd, **kw: _aws_ok("aws-cli/2.x"))

    importer = CodeCommitImporter(region="eu-central-1")
    data = _make_cc_repo("my-repo", region="us-west-2")
    repo = importer._parse_repo(data)

    # Explicit region takes precedence over clone URL
    assert "eu-central-1" in repo.html_url


def test_parse_repo_fallback_region(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test _parse_repo falls back to us-east-1 when no region info available."""
    # Mock subprocess.run: allow CodeCommitImporter construction (aws --version check)
    monkeypatch.setattr("subprocess.run", lambda cmd, **kw: _aws_ok("aws-cli/2.x"))

    importer = CodeCommitImporter(region=None)
    # Data without a recognizable clone URL
    data = {
        "repositoryName": "my-repo",
        "cloneUrlHttp": "",
        "cloneUrlSsh": "",
        "accountId": "123456789012",
    }
    repo = importer._parse_repo(data)

    assert "us-east-1" in repo.html_url


def test_parse_repo_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test _parse_repo maps all fields correctly."""
    # Mock subprocess.run: allow CodeCommitImporter construction (aws --version check)
    monkeypatch.setattr("subprocess.run", lambda cmd, **kw: _aws_ok("aws-cli/2.x"))

    importer = CodeCommitImporter(region="us-east-1")
    data = _make_cc_repo(
        "test-repo",
        region="us-east-1",
        account_id="999888777666",
        default_branch="develop",
        description="A test repository",
    )
    repo = importer._parse_repo(data)

    assert repo.name == "test-repo"
    assert "git-codecommit.us-east-1" in repo.clone_url
    assert "git-codecommit.us-east-1" in repo.ssh_url
    assert repo.description == "A test repository"
    assert repo.language is None
    assert repo.topics == ()
    assert repo.stars == 0
    assert repo.is_fork is False
    assert repo.is_archived is False
    assert repo.default_branch == "develop"
    assert repo.owner == "999888777666"


# ---------------------------------------------------------------------------
# is_authenticated
# ---------------------------------------------------------------------------


def test_is_authenticated_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test is_authenticated returns True when sts get-caller-identity succeeds."""
    call_count = 0

    def mock_run(cmd: list[str], **kwargs: t.Any) -> subprocess.CompletedProcess[str]:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return _aws_ok("aws-cli/2.x")
        # sts get-caller-identity succeeds
        return _aws_ok(
            json.dumps(
                {"UserId": "AIDA...", "Account": "123456789012", "Arn": "arn:..."}
            )
        )

    # Mock subprocess.run: first call passes aws --version, second returns
    # successful sts get-caller-identity to confirm credentials are valid
    monkeypatch.setattr("subprocess.run", mock_run)
    importer = CodeCommitImporter()

    assert importer.is_authenticated is True


def test_is_authenticated_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test is_authenticated returns False when credentials are missing."""
    call_count = 0

    def mock_run(cmd: list[str], **kwargs: t.Any) -> subprocess.CompletedProcess[str]:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return _aws_ok("aws-cli/2.x")
        # sts get-caller-identity fails with credential error
        return _aws_err(stderr="Unable to locate credentials")

    # Mock subprocess.run: first call passes aws --version, second fails
    # sts get-caller-identity with credential error to simulate missing credentials
    monkeypatch.setattr("subprocess.run", mock_run)
    importer = CodeCommitImporter()

    assert importer.is_authenticated is False


def test_codecommit_timeout_raises_service_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test _run_aws_command raises ServiceUnavailableError on timeout.

    If the AWS CLI hangs (broken credential provider, network issue),
    subprocess.run should time out and the error should propagate as
    ServiceUnavailableError rather than blocking indefinitely.
    """
    from vcspull._internal.remotes.base import ServiceUnavailableError

    call_count = 0

    def mock_run(*args: t.Any, **kwargs: t.Any) -> subprocess.CompletedProcess[str]:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            # _check_aws_cli: aws --version succeeds
            return _aws_ok("aws-cli/2.x")
        # Mock subprocess.run: second call (actual command) raises
        # TimeoutExpired to simulate a hung AWS CLI process
        raise subprocess.TimeoutExpired(cmd="aws", timeout=60)

    monkeypatch.setattr("subprocess.run", mock_run)
    importer = CodeCommitImporter()

    with pytest.raises(ServiceUnavailableError, match="timed out"):
        importer._run_aws_command("codecommit", "list-repositories")
