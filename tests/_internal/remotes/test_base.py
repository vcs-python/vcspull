"""Tests for vcspull._internal.remotes.base module."""

from __future__ import annotations

import typing as t

import pytest

from vcspull._internal.remotes.base import (
    ImportMode,
    ImportOptions,
    RemoteRepo,
    filter_repo,
)


class FilterRepoFixture(t.NamedTuple):
    """Fixture for filter_repo test cases."""

    test_id: str
    repo_kwargs: dict[str, t.Any]
    options_kwargs: dict[str, t.Any]
    expected: bool


FILTER_REPO_FIXTURES: list[FilterRepoFixture] = [
    FilterRepoFixture(
        test_id="passes-all-defaults",
        repo_kwargs={
            "name": "test",
            "clone_url": "https://github.com/user/test.git",
            "ssh_url": "git@github.com:user/test.git",
            "html_url": "https://github.com/user/test",
            "description": None,
            "language": "Python",
            "topics": (),
            "stars": 50,
            "is_fork": False,
            "is_archived": False,
            "default_branch": "main",
            "owner": "user",
        },
        options_kwargs={},
        expected=True,
    ),
    FilterRepoFixture(
        test_id="excludes-fork-by-default",
        repo_kwargs={
            "name": "fork",
            "clone_url": "https://github.com/user/fork.git",
            "ssh_url": "git@github.com:user/fork.git",
            "html_url": "https://github.com/user/fork",
            "description": None,
            "language": "Python",
            "topics": (),
            "stars": 10,
            "is_fork": True,
            "is_archived": False,
            "default_branch": "main",
            "owner": "user",
        },
        options_kwargs={"include_forks": False},
        expected=False,
    ),
    FilterRepoFixture(
        test_id="includes-fork-when-enabled",
        repo_kwargs={
            "name": "fork",
            "clone_url": "https://github.com/user/fork.git",
            "ssh_url": "git@github.com:user/fork.git",
            "html_url": "https://github.com/user/fork",
            "description": None,
            "language": "Python",
            "topics": (),
            "stars": 10,
            "is_fork": True,
            "is_archived": False,
            "default_branch": "main",
            "owner": "user",
        },
        options_kwargs={"include_forks": True},
        expected=True,
    ),
    FilterRepoFixture(
        test_id="excludes-archived-by-default",
        repo_kwargs={
            "name": "archived",
            "clone_url": "https://github.com/user/archived.git",
            "ssh_url": "git@github.com:user/archived.git",
            "html_url": "https://github.com/user/archived",
            "description": None,
            "language": "Python",
            "topics": (),
            "stars": 5,
            "is_fork": False,
            "is_archived": True,
            "default_branch": "main",
            "owner": "user",
        },
        options_kwargs={"include_archived": False},
        expected=False,
    ),
    FilterRepoFixture(
        test_id="includes-archived-when-enabled",
        repo_kwargs={
            "name": "archived",
            "clone_url": "https://github.com/user/archived.git",
            "ssh_url": "git@github.com:user/archived.git",
            "html_url": "https://github.com/user/archived",
            "description": None,
            "language": "Python",
            "topics": (),
            "stars": 5,
            "is_fork": False,
            "is_archived": True,
            "default_branch": "main",
            "owner": "user",
        },
        options_kwargs={"include_archived": True},
        expected=True,
    ),
    FilterRepoFixture(
        test_id="filters-by-language-match",
        repo_kwargs={
            "name": "python-repo",
            "clone_url": "https://github.com/user/python-repo.git",
            "ssh_url": "git@github.com:user/python-repo.git",
            "html_url": "https://github.com/user/python-repo",
            "description": None,
            "language": "Python",
            "topics": (),
            "stars": 50,
            "is_fork": False,
            "is_archived": False,
            "default_branch": "main",
            "owner": "user",
        },
        options_kwargs={"language": "Python"},
        expected=True,
    ),
    FilterRepoFixture(
        test_id="filters-by-language-mismatch",
        repo_kwargs={
            "name": "python-repo",
            "clone_url": "https://github.com/user/python-repo.git",
            "ssh_url": "git@github.com:user/python-repo.git",
            "html_url": "https://github.com/user/python-repo",
            "description": None,
            "language": "Python",
            "topics": (),
            "stars": 50,
            "is_fork": False,
            "is_archived": False,
            "default_branch": "main",
            "owner": "user",
        },
        options_kwargs={"language": "JavaScript"},
        expected=False,
    ),
    FilterRepoFixture(
        test_id="filters-by-language-case-insensitive",
        repo_kwargs={
            "name": "python-repo",
            "clone_url": "https://github.com/user/python-repo.git",
            "ssh_url": "git@github.com:user/python-repo.git",
            "html_url": "https://github.com/user/python-repo",
            "description": None,
            "language": "Python",
            "topics": (),
            "stars": 50,
            "is_fork": False,
            "is_archived": False,
            "default_branch": "main",
            "owner": "user",
        },
        options_kwargs={"language": "python"},
        expected=True,
    ),
    FilterRepoFixture(
        test_id="filters-by-min-stars-pass",
        repo_kwargs={
            "name": "popular",
            "clone_url": "https://github.com/user/popular.git",
            "ssh_url": "git@github.com:user/popular.git",
            "html_url": "https://github.com/user/popular",
            "description": None,
            "language": "Python",
            "topics": (),
            "stars": 100,
            "is_fork": False,
            "is_archived": False,
            "default_branch": "main",
            "owner": "user",
        },
        options_kwargs={"min_stars": 50},
        expected=True,
    ),
    FilterRepoFixture(
        test_id="filters-by-min-stars-fail",
        repo_kwargs={
            "name": "unpopular",
            "clone_url": "https://github.com/user/unpopular.git",
            "ssh_url": "git@github.com:user/unpopular.git",
            "html_url": "https://github.com/user/unpopular",
            "description": None,
            "language": "Python",
            "topics": (),
            "stars": 10,
            "is_fork": False,
            "is_archived": False,
            "default_branch": "main",
            "owner": "user",
        },
        options_kwargs={"min_stars": 50},
        expected=False,
    ),
    FilterRepoFixture(
        test_id="filters-by-topics-match",
        repo_kwargs={
            "name": "cli-tool",
            "clone_url": "https://github.com/user/cli-tool.git",
            "ssh_url": "git@github.com:user/cli-tool.git",
            "html_url": "https://github.com/user/cli-tool",
            "description": None,
            "language": "Python",
            "topics": ("cli", "tool", "python"),
            "stars": 50,
            "is_fork": False,
            "is_archived": False,
            "default_branch": "main",
            "owner": "user",
        },
        options_kwargs={"topics": ["cli", "python"]},
        expected=True,
    ),
    FilterRepoFixture(
        test_id="filters-by-topics-mismatch",
        repo_kwargs={
            "name": "web-app",
            "clone_url": "https://github.com/user/web-app.git",
            "ssh_url": "git@github.com:user/web-app.git",
            "html_url": "https://github.com/user/web-app",
            "description": None,
            "language": "Python",
            "topics": ("web", "django"),
            "stars": 50,
            "is_fork": False,
            "is_archived": False,
            "default_branch": "main",
            "owner": "user",
        },
        options_kwargs={"topics": ["cli"]},
        expected=False,
    ),
]


@pytest.mark.parametrize(
    list(FilterRepoFixture._fields),
    FILTER_REPO_FIXTURES,
    ids=[f.test_id for f in FILTER_REPO_FIXTURES],
)
def test_filter_repo(
    test_id: str,
    repo_kwargs: dict[str, t.Any],
    options_kwargs: dict[str, t.Any],
    expected: bool,
) -> None:
    """Test filter_repo with various filter combinations."""
    repo = RemoteRepo(**repo_kwargs)
    options = ImportOptions(**options_kwargs)
    assert filter_repo(repo, options) == expected


def test_remote_repo_to_vcspull_url_defaults_to_ssh() -> None:
    """Test RemoteRepo.to_vcspull_url defaults to SSH URL."""
    repo = RemoteRepo(
        name="test",
        clone_url="https://github.com/user/test.git",
        ssh_url="git@github.com:user/test.git",
        html_url="https://github.com/user/test",
        description=None,
        language=None,
        topics=(),
        stars=0,
        is_fork=False,
        is_archived=False,
        default_branch="main",
        owner="user",
    )
    assert repo.to_vcspull_url() == "git+git@github.com:user/test.git"


def test_remote_repo_to_vcspull_url_https() -> None:
    """Test RemoteRepo.to_vcspull_url with use_ssh=False returns HTTPS."""
    repo = RemoteRepo(
        name="test",
        clone_url="https://github.com/user/test.git",
        ssh_url="git@github.com:user/test.git",
        html_url="https://github.com/user/test",
        description=None,
        language=None,
        topics=(),
        stars=0,
        is_fork=False,
        is_archived=False,
        default_branch="main",
        owner="user",
    )
    assert repo.to_vcspull_url(use_ssh=False) == (
        "git+https://github.com/user/test.git"
    )


def test_remote_repo_to_vcspull_url_fallback_no_ssh() -> None:
    """Test RemoteRepo.to_vcspull_url falls back to clone_url when ssh_url empty."""
    repo = RemoteRepo(
        name="test",
        clone_url="https://github.com/user/test.git",
        ssh_url="",
        html_url="https://github.com/user/test",
        description=None,
        language=None,
        topics=(),
        stars=0,
        is_fork=False,
        is_archived=False,
        default_branch="main",
        owner="user",
    )
    assert repo.to_vcspull_url() == "git+https://github.com/user/test.git"


def test_remote_repo_to_vcspull_url_already_prefixed() -> None:
    """Test RemoteRepo.to_vcspull_url doesn't double-prefix."""
    repo = RemoteRepo(
        name="test",
        clone_url="git+https://github.com/user/test.git",
        ssh_url="",
        html_url="https://github.com/user/test",
        description=None,
        language=None,
        topics=(),
        stars=0,
        is_fork=False,
        is_archived=False,
        default_branch="main",
        owner="user",
    )
    assert repo.to_vcspull_url(use_ssh=False) == (
        "git+https://github.com/user/test.git"
    )


def test_remote_repo_to_dict() -> None:
    """Test RemoteRepo.to_dict serialization."""
    repo = RemoteRepo(
        name="test",
        clone_url="https://github.com/user/test.git",
        ssh_url="git@github.com:user/test.git",
        html_url="https://github.com/user/test",
        description="A test repo",
        language="Python",
        topics=("cli", "tool"),
        stars=100,
        is_fork=False,
        is_archived=False,
        default_branch="main",
        owner="user",
    )
    d = repo.to_dict()
    assert d["name"] == "test"
    assert d["clone_url"] == "https://github.com/user/test.git"
    assert d["ssh_url"] == "git@github.com:user/test.git"
    assert d["language"] == "Python"
    assert d["topics"] == ["cli", "tool"]
    assert d["stars"] == 100
    assert d["is_fork"] is False


def test_import_options_defaults() -> None:
    """Test ImportOptions default values."""
    options = ImportOptions()
    assert options.mode == ImportMode.USER
    assert options.target == ""
    assert options.base_url is None
    assert options.token is None
    assert options.include_forks is False
    assert options.include_archived is False
    assert options.language is None
    assert options.topics == []
    assert options.min_stars == 0
    assert options.limit == 100


def test_import_mode_values() -> None:
    """Test ImportMode enum values."""
    assert ImportMode.USER.value == "user"
    assert ImportMode.ORG.value == "org"
    assert ImportMode.SEARCH.value == "search"


class InvalidLimitFixture(t.NamedTuple):
    """Fixture for invalid ImportOptions.limit test cases."""

    test_id: str
    limit: int


INVALID_LIMIT_FIXTURES: list[InvalidLimitFixture] = [
    InvalidLimitFixture(test_id="zero-limit", limit=0),
    InvalidLimitFixture(test_id="negative-limit", limit=-1),
    InvalidLimitFixture(test_id="large-negative-limit", limit=-100),
]


@pytest.mark.parametrize(
    list(InvalidLimitFixture._fields),
    INVALID_LIMIT_FIXTURES,
    ids=[f.test_id for f in INVALID_LIMIT_FIXTURES],
)
def test_import_options_rejects_invalid_limit(
    test_id: str,
    limit: int,
) -> None:
    """Test ImportOptions raises ValueError for limit < 1."""
    with pytest.raises(ValueError, match="limit must be >= 1"):
        ImportOptions(limit=limit)


def test_import_options_accepts_valid_limit() -> None:
    """Test ImportOptions accepts limit >= 1."""
    options = ImportOptions(limit=1)
    assert options.limit == 1
    options = ImportOptions(limit=500)
    assert options.limit == 500


class HandleHttpErrorFixture(t.NamedTuple):
    """Fixture for HTTPClient._handle_http_error test cases."""

    test_id: str
    status_code: int
    response_body: str
    expected_error_type: str
    expected_message_contains: str


HANDLE_HTTP_ERROR_FIXTURES: list[HandleHttpErrorFixture] = [
    HandleHttpErrorFixture(
        test_id="string-message-401",
        status_code=401,
        response_body='{"message": "Bad credentials"}',
        expected_error_type="AuthenticationError",
        expected_message_contains="Bad credentials",
    ),
    HandleHttpErrorFixture(
        test_id="dict-message-403",
        status_code=403,
        response_body='{"message": {"error": "forbidden"}}',
        expected_error_type="AuthenticationError",
        expected_message_contains="forbidden",
    ),
    HandleHttpErrorFixture(
        test_id="int-message-404",
        status_code=404,
        response_body='{"message": 42}',
        expected_error_type="NotFoundError",
        expected_message_contains="42",
    ),
    HandleHttpErrorFixture(
        test_id="rate-limit-string-403",
        status_code=403,
        response_body='{"message": "API rate limit exceeded"}',
        expected_error_type="RateLimitError",
        expected_message_contains="rate limit",
    ),
    HandleHttpErrorFixture(
        test_id="invalid-json-body-500",
        status_code=500,
        response_body="<html>Server Error</html>",
        expected_error_type="ServiceUnavailableError",
        expected_message_contains="service unavailable",
    ),
]


@pytest.mark.parametrize(
    list(HandleHttpErrorFixture._fields),
    HANDLE_HTTP_ERROR_FIXTURES,
    ids=[f.test_id for f in HANDLE_HTTP_ERROR_FIXTURES],
)
def test_handle_http_error(
    test_id: str,
    status_code: int,
    response_body: str,
    expected_error_type: str,
    expected_message_contains: str,
) -> None:
    """Test HTTPClient._handle_http_error with various response bodies."""
    import io
    import urllib.error

    from vcspull._internal.remotes.base import (
        AuthenticationError,
        HTTPClient,
        NotFoundError,
        RateLimitError,
        ServiceUnavailableError,
    )

    error_classes = {
        "AuthenticationError": AuthenticationError,
        "RateLimitError": RateLimitError,
        "NotFoundError": NotFoundError,
        "ServiceUnavailableError": ServiceUnavailableError,
    }

    client = HTTPClient("https://api.example.com")
    exc = urllib.error.HTTPError(
        url="https://api.example.com/test",
        code=status_code,
        msg="Error",
        hdrs=None,  # type: ignore[arg-type]
        fp=io.BytesIO(response_body.encode()),
    )

    with pytest.raises(error_classes[expected_error_type]) as exc_info:
        client._handle_http_error(exc, "TestService")

    assert expected_message_contains.lower() in str(exc_info.value).lower()


def test_http_client_get_merges_query_params(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test HTTPClient.get properly merges params into URLs with existing query strings.

    Naive f"{url}?{params}" would produce a double-? URL when the endpoint
    already contains query parameters. The implementation should use
    urllib.parse to merge them correctly.
    """
    import json
    import urllib.request

    from tests._internal.remotes.conftest import MockHTTPResponse
    from vcspull._internal.remotes.base import HTTPClient

    captured_urls: list[str] = []

    def mock_urlopen(
        request: urllib.request.Request,
        **kwargs: t.Any,
    ) -> MockHTTPResponse:
        captured_urls.append(request.full_url)
        return MockHTTPResponse(json.dumps({"ok": True}).encode(), {}, 200)

    # Mock urlopen: capture the request URL to verify query param merging
    monkeypatch.setattr("urllib.request.urlopen", mock_urlopen)

    client = HTTPClient("https://api.example.com")

    # Endpoint already has a query string; additional params should merge
    client.get(
        "/search?q=test",
        params={"page": 1, "per_page": 10},
        service_name="TestService",
    )

    assert len(captured_urls) == 1
    url = captured_urls[0]
    assert "??" not in url, f"Double question mark in URL: {url}"
    assert "q=test" in url
    assert "page=1" in url
    assert "per_page=10" in url


def test_http_client_warns_on_non_https_with_token(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test HTTPClient logs a warning when token is sent over non-HTTPS."""
    import logging

    from vcspull._internal.remotes.base import HTTPClient

    caplog.set_level(logging.WARNING)

    HTTPClient("http://insecure.example.com", token="secret-token")

    assert "non-HTTPS" in caplog.text
    assert "insecure.example.com" in caplog.text


def test_http_client_no_warning_on_https_with_token(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test HTTPClient does not warn when token is sent over HTTPS."""
    import logging

    from vcspull._internal.remotes.base import HTTPClient

    caplog.set_level(logging.WARNING)

    HTTPClient("https://secure.example.com", token="secret-token")

    assert "non-HTTPS" not in caplog.text
