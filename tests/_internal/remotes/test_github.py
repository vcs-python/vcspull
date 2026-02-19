"""Tests for vcspull._internal.remotes.github module."""

from __future__ import annotations

import json
import typing as t

import pytest

from vcspull._internal.remotes.base import ImportMode, ImportOptions
from vcspull._internal.remotes.github import GitHubImporter


class GitHubUserFixture(t.NamedTuple):
    """Fixture for GitHub user import test cases."""

    test_id: str
    response_json: list[dict[str, t.Any]]
    options_kwargs: dict[str, t.Any]
    expected_count: int
    expected_names: list[str]


GITHUB_USER_FIXTURES: list[GitHubUserFixture] = [
    GitHubUserFixture(
        test_id="single-repo-user",
        response_json=[
            {
                "name": "repo1",
                "clone_url": "https://github.com/testuser/repo1.git",
                "ssh_url": "git@github.com:testuser/repo1.git",
                "html_url": "https://github.com/testuser/repo1",
                "description": "Test repo",
                "language": "Python",
                "topics": [],
                "stargazers_count": 10,
                "fork": False,
                "archived": False,
                "default_branch": "main",
                "owner": {"login": "testuser"},
            }
        ],
        options_kwargs={"mode": ImportMode.USER, "target": "testuser"},
        expected_count=1,
        expected_names=["repo1"],
    ),
    GitHubUserFixture(
        test_id="multiple-repos-forks-excluded",
        response_json=[
            {
                "name": "original",
                "clone_url": "https://github.com/testuser/original.git",
                "ssh_url": "git@github.com:testuser/original.git",
                "html_url": "https://github.com/testuser/original",
                "description": "Original repo",
                "language": "Python",
                "topics": [],
                "stargazers_count": 100,
                "fork": False,
                "archived": False,
                "default_branch": "main",
                "owner": {"login": "testuser"},
            },
            {
                "name": "forked",
                "clone_url": "https://github.com/testuser/forked.git",
                "ssh_url": "git@github.com:testuser/forked.git",
                "html_url": "https://github.com/testuser/forked",
                "description": "Forked repo",
                "language": "Python",
                "topics": [],
                "stargazers_count": 5,
                "fork": True,
                "archived": False,
                "default_branch": "main",
                "owner": {"login": "testuser"},
            },
        ],
        options_kwargs={
            "mode": ImportMode.USER,
            "target": "testuser",
            "include_forks": False,
        },
        expected_count=1,
        expected_names=["original"],
    ),
    GitHubUserFixture(
        test_id="multiple-repos-forks-included",
        response_json=[
            {
                "name": "original",
                "clone_url": "https://github.com/testuser/original.git",
                "ssh_url": "git@github.com:testuser/original.git",
                "html_url": "https://github.com/testuser/original",
                "description": "Original repo",
                "language": "Python",
                "topics": [],
                "stargazers_count": 100,
                "fork": False,
                "archived": False,
                "default_branch": "main",
                "owner": {"login": "testuser"},
            },
            {
                "name": "forked",
                "clone_url": "https://github.com/testuser/forked.git",
                "ssh_url": "git@github.com:testuser/forked.git",
                "html_url": "https://github.com/testuser/forked",
                "description": "Forked repo",
                "language": "Python",
                "topics": [],
                "stargazers_count": 5,
                "fork": True,
                "archived": False,
                "default_branch": "main",
                "owner": {"login": "testuser"},
            },
        ],
        options_kwargs={
            "mode": ImportMode.USER,
            "target": "testuser",
            "include_forks": True,
        },
        expected_count=2,
        expected_names=["original", "forked"],
    ),
    GitHubUserFixture(
        test_id="archived-excluded-by-default",
        response_json=[
            {
                "name": "active",
                "clone_url": "https://github.com/testuser/active.git",
                "ssh_url": "git@github.com:testuser/active.git",
                "html_url": "https://github.com/testuser/active",
                "description": "Active repo",
                "language": "Python",
                "topics": [],
                "stargazers_count": 50,
                "fork": False,
                "archived": False,
                "default_branch": "main",
                "owner": {"login": "testuser"},
            },
            {
                "name": "archived",
                "clone_url": "https://github.com/testuser/archived.git",
                "ssh_url": "git@github.com:testuser/archived.git",
                "html_url": "https://github.com/testuser/archived",
                "description": "Archived repo",
                "language": "Python",
                "topics": [],
                "stargazers_count": 10,
                "fork": False,
                "archived": True,
                "default_branch": "main",
                "owner": {"login": "testuser"},
            },
        ],
        options_kwargs={
            "mode": ImportMode.USER,
            "target": "testuser",
            "include_archived": False,
        },
        expected_count=1,
        expected_names=["active"],
    ),
    GitHubUserFixture(
        test_id="language-filter-applied",
        response_json=[
            {
                "name": "python-repo",
                "clone_url": "https://github.com/testuser/python-repo.git",
                "ssh_url": "git@github.com:testuser/python-repo.git",
                "html_url": "https://github.com/testuser/python-repo",
                "description": "Python repo",
                "language": "Python",
                "topics": [],
                "stargazers_count": 50,
                "fork": False,
                "archived": False,
                "default_branch": "main",
                "owner": {"login": "testuser"},
            },
            {
                "name": "js-repo",
                "clone_url": "https://github.com/testuser/js-repo.git",
                "ssh_url": "git@github.com:testuser/js-repo.git",
                "html_url": "https://github.com/testuser/js-repo",
                "description": "JavaScript repo",
                "language": "JavaScript",
                "topics": [],
                "stargazers_count": 30,
                "fork": False,
                "archived": False,
                "default_branch": "main",
                "owner": {"login": "testuser"},
            },
        ],
        options_kwargs={
            "mode": ImportMode.USER,
            "target": "testuser",
            "language": "Python",
        },
        expected_count=1,
        expected_names=["python-repo"],
    ),
    GitHubUserFixture(
        test_id="empty-response-returns-empty-list",
        response_json=[],
        options_kwargs={"mode": ImportMode.USER, "target": "emptyuser"},
        expected_count=0,
        expected_names=[],
    ),
]


@pytest.mark.parametrize(
    list(GitHubUserFixture._fields),
    GITHUB_USER_FIXTURES,
    ids=[f.test_id for f in GITHUB_USER_FIXTURES],
)
def test_github_fetch_user(
    test_id: str,
    response_json: list[dict[str, t.Any]],
    options_kwargs: dict[str, t.Any],
    expected_count: int,
    expected_names: list[str],
    mock_urlopen: t.Callable[..., None],
) -> None:
    """Test GitHub user repository fetching with various scenarios."""
    mock_urlopen(
        [
            (
                json.dumps(response_json).encode(),
                {"x-ratelimit-remaining": "100", "x-ratelimit-limit": "60"},
                200,
            )
        ]
    )
    importer = GitHubImporter()
    options = ImportOptions(**options_kwargs)
    repos = list(importer.fetch_repos(options))
    assert len(repos) == expected_count
    assert [r.name for r in repos] == expected_names


def test_github_fetch_org(
    mock_urlopen: t.Callable[..., None],
) -> None:
    """Test GitHub org repository fetching."""
    response_json = [
        {
            "name": "org-repo",
            "clone_url": "https://github.com/testorg/org-repo.git",
            "ssh_url": "git@github.com:testorg/org-repo.git",
            "html_url": "https://github.com/testorg/org-repo",
            "description": "Org repo",
            "language": "Python",
            "topics": [],
            "stargazers_count": 200,
            "fork": False,
            "archived": False,
            "default_branch": "main",
            "owner": {"login": "testorg"},
        }
    ]
    mock_urlopen(
        [
            (
                json.dumps(response_json).encode(),
                {"x-ratelimit-remaining": "100", "x-ratelimit-limit": "60"},
                200,
            )
        ]
    )
    importer = GitHubImporter()
    options = ImportOptions(mode=ImportMode.ORG, target="testorg")
    repos = list(importer.fetch_repos(options))
    assert len(repos) == 1
    assert repos[0].name == "org-repo"
    assert repos[0].owner == "testorg"


def test_github_fetch_search(
    mock_urlopen: t.Callable[..., None],
) -> None:
    """Test GitHub search repository fetching."""
    search_response = {
        "total_count": 1,
        "items": [
            {
                "name": "search-result",
                "clone_url": "https://github.com/user/search-result.git",
                "ssh_url": "git@github.com:user/search-result.git",
                "html_url": "https://github.com/user/search-result",
                "description": "Found by search",
                "language": "Python",
                "topics": ["machine-learning"],
                "stargazers_count": 1000,
                "fork": False,
                "archived": False,
                "default_branch": "main",
                "owner": {"login": "user"},
            }
        ],
    }
    mock_urlopen(
        [
            (
                json.dumps(search_response).encode(),
                {"x-ratelimit-remaining": "100", "x-ratelimit-limit": "60"},
                200,
            )
        ]
    )
    importer = GitHubImporter()
    options = ImportOptions(mode=ImportMode.SEARCH, target="machine learning")
    repos = list(importer.fetch_repos(options))
    assert len(repos) == 1
    assert repos[0].name == "search-result"
    assert repos[0].stars == 1000


def test_github_importer_is_authenticated_without_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test is_authenticated returns False without token."""
    # Clear environment variables that could provide a token
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GH_TOKEN", raising=False)
    importer = GitHubImporter(token=None)
    assert importer.is_authenticated is False


def test_github_importer_is_authenticated_with_token() -> None:
    """Test is_authenticated returns True with token."""
    importer = GitHubImporter(token="test-token")
    assert importer.is_authenticated is True


def test_github_importer_service_name() -> None:
    """Test service_name property."""
    importer = GitHubImporter()
    assert importer.service_name == "GitHub"


def test_github_enterprise_url_normalized() -> None:
    """Test that GitHub Enterprise URLs get /api/v3 appended."""
    importer = GitHubImporter(token="fake", base_url="https://ghe.example.com")
    assert importer._client.base_url == "https://ghe.example.com/api/v3"


def test_github_enterprise_url_already_has_api() -> None:
    """Test that GHE URLs with /api/v3 are not double-suffixed."""
    importer = GitHubImporter(token="fake", base_url="https://ghe.example.com/api/v3")
    assert importer._client.base_url == "https://ghe.example.com/api/v3"


def test_github_public_url_not_modified() -> None:
    """Test that default api.github.com URL is not modified."""
    importer = GitHubImporter(token="fake")
    assert importer._client.base_url == "https://api.github.com"


def test_github_handles_null_topics(
    mock_urlopen: t.Callable[..., None],
) -> None:
    """Test GitHub handles null topics in API response.

    GitHub API can return "topics": null instead of an empty array.
    dict.get("topics", []) returns None when the key exists with null value,
    causing tuple(None) to crash with TypeError.
    """
    response_json = [
        {
            "name": "null-topics-repo",
            "clone_url": "https://github.com/user/null-topics-repo.git",
            "ssh_url": "git@github.com:user/null-topics-repo.git",
            "html_url": "https://github.com/user/null-topics-repo",
            "description": "Repo with null topics",
            "language": "Python",
            "topics": None,
            "stargazers_count": 10,
            "fork": False,
            "archived": False,
            "default_branch": "main",
            "owner": {"login": "user"},
        }
    ]
    mock_urlopen(
        [
            (
                json.dumps(response_json).encode(),
                {"x-ratelimit-remaining": "100", "x-ratelimit-limit": "60"},
                200,
            )
        ]
    )
    importer = GitHubImporter()
    options = ImportOptions(mode=ImportMode.USER, target="user")
    repos = list(importer.fetch_repos(options))
    assert len(repos) == 1
    assert repos[0].topics == ()


def test_github_limit_respected(
    mock_urlopen: t.Callable[..., None],
) -> None:
    """Test that limit option is respected."""
    # Create response with 5 repos
    response_json = [
        {
            "name": f"repo{i}",
            "clone_url": f"https://github.com/user/repo{i}.git",
            "ssh_url": f"git@github.com:user/repo{i}.git",
            "html_url": f"https://github.com/user/repo{i}",
            "description": f"Repo {i}",
            "language": "Python",
            "topics": [],
            "stargazers_count": 10,
            "fork": False,
            "archived": False,
            "default_branch": "main",
            "owner": {"login": "user"},
        }
        for i in range(5)
    ]
    mock_urlopen(
        [
            (
                json.dumps(response_json).encode(),
                {"x-ratelimit-remaining": "100", "x-ratelimit-limit": "60"},
                200,
            )
        ]
    )
    importer = GitHubImporter()
    options = ImportOptions(mode=ImportMode.USER, target="user", limit=3)
    repos = list(importer.fetch_repos(options))
    assert len(repos) == 3


class LogRateLimitFixture(t.NamedTuple):
    """Fixture for _log_rate_limit test cases."""

    test_id: str
    headers: dict[str, str]
    expected_log_level: str | None
    expected_message_fragment: str | None


LOG_RATE_LIMIT_FIXTURES: list[LogRateLimitFixture] = [
    LogRateLimitFixture(
        test_id="valid-headers-low-remaining",
        headers={"x-ratelimit-remaining": "5", "x-ratelimit-limit": "60"},
        expected_log_level="warning",
        expected_message_fragment="rate limit low",
    ),
    LogRateLimitFixture(
        test_id="valid-headers-sufficient-remaining",
        headers={"x-ratelimit-remaining": "50", "x-ratelimit-limit": "60"},
        expected_log_level="debug",
        expected_message_fragment="rate limit",
    ),
    LogRateLimitFixture(
        test_id="non-numeric-remaining-header",
        headers={"x-ratelimit-remaining": "unlimited", "x-ratelimit-limit": "60"},
        expected_log_level=None,
        expected_message_fragment=None,
    ),
    LogRateLimitFixture(
        test_id="missing-remaining-header",
        headers={"x-ratelimit-limit": "60"},
        expected_log_level=None,
        expected_message_fragment=None,
    ),
    LogRateLimitFixture(
        test_id="missing-both-headers",
        headers={},
        expected_log_level=None,
        expected_message_fragment=None,
    ),
]


@pytest.mark.parametrize(
    list(LogRateLimitFixture._fields),
    LOG_RATE_LIMIT_FIXTURES,
    ids=[f.test_id for f in LOG_RATE_LIMIT_FIXTURES],
)
def test_log_rate_limit(
    test_id: str,
    headers: dict[str, str],
    expected_log_level: str | None,
    expected_message_fragment: str | None,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test _log_rate_limit handles various header scenarios."""
    import logging

    caplog.set_level(logging.DEBUG)
    importer = GitHubImporter()
    # Should not raise on any input
    importer._log_rate_limit(headers)

    if expected_message_fragment is not None:
        assert expected_message_fragment in caplog.text.lower()
    else:
        # No rate limit message should appear
        assert "rate limit" not in caplog.text.lower()


def test_github_parse_repo_missing_keys(
    mock_urlopen: t.Callable[..., None],
) -> None:
    """Test GitHub _parse_repo handles incomplete API responses gracefully.

    GitHub API responses may lack keys like 'name', 'clone_url', or 'html_url'
    in edge cases (partial responses, API changes). Using .get() with defaults
    prevents KeyError crashes.
    """
    response_json = [
        {
            # Missing: name, clone_url, html_url, ssh_url
            "description": "Incomplete repo data",
            "language": "Python",
            "topics": ["test"],
            "stargazers_count": 5,
            "fork": False,
            "archived": False,
            "default_branch": "main",
            "owner": {"login": "user"},
        }
    ]
    mock_urlopen(
        [
            (
                json.dumps(response_json).encode(),
                {"x-ratelimit-remaining": "100", "x-ratelimit-limit": "60"},
                200,
            )
        ]
    )
    importer = GitHubImporter()
    options = ImportOptions(mode=ImportMode.USER, target="user")
    repos = list(importer.fetch_repos(options))
    assert len(repos) == 1
    assert repos[0].name == ""
    assert repos[0].clone_url == ""
    assert repos[0].html_url == ""
    assert repos[0].ssh_url == ""


def test_github_parse_repo_null_owner(
    mock_urlopen: t.Callable[..., None],
) -> None:
    """Test GitHub _parse_repo handles null owner without crashing.

    JSON APIs may return ``"owner": null`` for deleted/suspended accounts.
    The importer must not raise AttributeError when this happens.
    """
    response_json = [
        {
            "name": "repo",
            "clone_url": "https://github.com/ghost/repo.git",
            "ssh_url": "git@github.com:ghost/repo.git",
            "html_url": "https://github.com/ghost/repo",
            "description": "Orphaned repo",
            "language": "Python",
            "topics": [],
            "stargazers_count": 1,
            "fork": False,
            "archived": False,
            "default_branch": "main",
            "owner": None,
        }
    ]
    mock_urlopen(
        [
            (
                json.dumps(response_json).encode(),
                {"x-ratelimit-remaining": "100", "x-ratelimit-limit": "60"},
                200,
            )
        ]
    )
    importer = GitHubImporter()
    options = ImportOptions(mode=ImportMode.USER, target="ghost")
    repos = list(importer.fetch_repos(options))
    assert len(repos) == 1
    assert repos[0].owner == ""


def test_github_search_caps_at_1000_results(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test GitHub search stops paginating at 1000 results.

    GitHub's search API returns HTTP 422 beyond offset 1000.
    The importer must stop before requesting page 11 (with per_page=100).
    """
    from tests._internal.remotes.conftest import MockHTTPResponse

    call_count = 0

    def make_search_page() -> dict[str, t.Any]:
        """Create a full page of 100 search results."""
        return {
            "total_count": 5000,
            "items": [
                {
                    "name": f"repo-{i}",
                    "clone_url": f"https://github.com/user/repo-{i}.git",
                    "ssh_url": f"git@github.com:user/repo-{i}.git",
                    "html_url": f"https://github.com/user/repo-{i}",
                    "description": f"Repo {i}",
                    "language": "Python",
                    "topics": [],
                    "stargazers_count": 100,
                    "fork": False,
                    "archived": False,
                    "default_branch": "main",
                    "owner": {"login": "user"},
                }
                for i in range(100)
            ],
        }

    def urlopen_side_effect(
        request: t.Any,
        timeout: int | None = None,
    ) -> MockHTTPResponse:
        nonlocal call_count
        call_count += 1
        page_data = make_search_page()
        return MockHTTPResponse(
            json.dumps(page_data).encode(),
            {"x-ratelimit-remaining": "100", "x-ratelimit-limit": "60"},
            200,
        )

    # Mock urlopen: track how many API requests are made
    monkeypatch.setattr("urllib.request.urlopen", urlopen_side_effect)

    importer = GitHubImporter()
    options = ImportOptions(
        mode=ImportMode.SEARCH,
        target="test",
        limit=5000,
    )
    repos = list(importer.fetch_repos(options))

    # Should have fetched at most 10 pages (1000 results)
    assert call_count <= 10, f"Expected at most 10 API calls, got {call_count}"
    assert len(repos) <= 1000


# ---------------------------------------------------------------------------
# Truncation warnings
# ---------------------------------------------------------------------------


def _make_github_repo(idx: int) -> dict[str, t.Any]:
    """Create a minimal GitHub repo API object for testing."""
    return {
        "name": f"repo-{idx}",
        "clone_url": f"https://github.com/user/repo-{idx}.git",
        "ssh_url": f"git@github.com:user/repo-{idx}.git",
        "html_url": f"https://github.com/user/repo-{idx}",
        "description": f"Repo {idx}",
        "language": "Python",
        "topics": [],
        "stargazers_count": 10,
        "fork": False,
        "archived": False,
        "default_branch": "main",
        "owner": {"login": "user"},
    }


class GitHubTruncationFixture(t.NamedTuple):
    """Fixture for GitHub truncation warning test cases."""

    test_id: str
    mode: ImportMode
    limit: int
    num_repos_on_server: int
    total_count: int | None  # for search mode, total_count in JSON body
    expect_warning: bool
    expected_warning_fragment: str | None


GITHUB_TRUNCATION_FIXTURES: list[GitHubTruncationFixture] = [
    GitHubTruncationFixture(
        test_id="search-truncated-with-total-count",
        mode=ImportMode.SEARCH,
        limit=2,
        num_repos_on_server=5,
        total_count=5,
        expect_warning=True,
        expected_warning_fragment="showing 2 of 5",
    ),
    GitHubTruncationFixture(
        test_id="search-not-truncated",
        mode=ImportMode.SEARCH,
        limit=100,
        num_repos_on_server=3,
        total_count=3,
        expect_warning=False,
        expected_warning_fragment=None,
    ),
    GitHubTruncationFixture(
        test_id="user-truncated-full-page",
        mode=ImportMode.USER,
        limit=3,
        num_repos_on_server=5,
        total_count=None,
        expect_warning=True,
        expected_warning_fragment="more may be available",
    ),
    GitHubTruncationFixture(
        test_id="user-not-truncated",
        mode=ImportMode.USER,
        limit=100,
        num_repos_on_server=3,
        total_count=None,
        expect_warning=False,
        expected_warning_fragment=None,
    ),
]


@pytest.mark.parametrize(
    list(GitHubTruncationFixture._fields),
    GITHUB_TRUNCATION_FIXTURES,
    ids=[f.test_id for f in GITHUB_TRUNCATION_FIXTURES],
)
def test_github_truncation_warning(
    test_id: str,
    mode: ImportMode,
    limit: int,
    num_repos_on_server: int,
    total_count: int | None,
    expect_warning: bool,
    expected_warning_fragment: str | None,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test truncation warnings when results exceed --limit."""
    import logging

    from tests._internal.remotes.conftest import MockHTTPResponse

    caplog.set_level(logging.WARNING)

    repos = [_make_github_repo(i) for i in range(num_repos_on_server)]
    rate_headers = {"x-ratelimit-remaining": "100", "x-ratelimit-limit": "60"}

    if mode == ImportMode.SEARCH:
        body = json.dumps({"total_count": total_count, "items": repos}).encode()
    else:
        body = json.dumps(repos).encode()

    def urlopen_side_effect(
        request: t.Any,
        timeout: int | None = None,
    ) -> MockHTTPResponse:
        return MockHTTPResponse(body, rate_headers, 200)

    # Mock urlopen: return all repos in one page
    monkeypatch.setattr("urllib.request.urlopen", urlopen_side_effect)

    importer = GitHubImporter()
    options = ImportOptions(mode=mode, target="user", limit=limit)
    list(importer.fetch_repos(options))

    if expect_warning:
        assert expected_warning_fragment is not None
        assert expected_warning_fragment in caplog.text.lower()
    else:
        assert "--limit" not in caplog.text.lower()


def test_github_truncation_at_page_boundary(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Truncation warning fires when limit equals a full page of results."""
    import logging

    from tests._internal.remotes.conftest import MockHTTPResponse

    # Return exactly DEFAULT_PER_PAGE (100) repos on page 1;
    # the while loop should detect this boundary and warn
    page1_repos = [_make_github_repo(i) for i in range(100)]
    page2_repos = [_make_github_repo(i) for i in range(100, 105)]
    rate_headers = {"x-ratelimit-remaining": "100", "x-ratelimit-limit": "60"}

    call_count = 0

    def urlopen_side_effect(
        request: t.Any,
        timeout: int | None = None,
    ) -> MockHTTPResponse:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            body = json.dumps(page1_repos).encode()
        else:
            body = json.dumps(page2_repos).encode()
        return MockHTTPResponse(body, rate_headers, 200)

    monkeypatch.setattr("urllib.request.urlopen", urlopen_side_effect)
    caplog.set_level(logging.WARNING)

    importer = GitHubImporter()
    options = ImportOptions(mode=ImportMode.USER, target="user", limit=100)
    repos = list(importer.fetch_repos(options))

    assert len(repos) == 100
    assert call_count == 1, "Should not fetch page 2 when limit already reached"
    assert "more may be available" in caplog.text.lower()
