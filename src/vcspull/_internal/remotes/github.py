"""GitHub repository importer for vcspull."""

from __future__ import annotations

import logging
import typing as t

from .base import (
    HTTPClient,
    ImportMode,
    ImportOptions,
    RemoteRepo,
    filter_repo,
    get_token_from_env,
)

log = logging.getLogger(__name__)

GITHUB_API_URL = "https://api.github.com"
DEFAULT_PER_PAGE = 100


class GitHubImporter:
    """Importer for GitHub repositories.

    Supports three modes:
    - USER: Fetch repositories for a user
    - ORG: Fetch repositories for an organization
    - SEARCH: Search for repositories by query

    Examples
    --------
    >>> importer = GitHubImporter()
    >>> importer.service_name
    'GitHub'
    """

    service_name: str = "GitHub"

    def __init__(
        self,
        token: str | None = None,
        base_url: str | None = None,
    ) -> None:
        """Initialize the GitHub importer.

        Parameters
        ----------
        token : str | None
            GitHub API token. If not provided, will try GITHUB_TOKEN env var.
        base_url : str | None
            Base URL for GitHub Enterprise. Defaults to api.github.com.
        """
        self._token = token or get_token_from_env("GITHUB_TOKEN", "GH_TOKEN")
        self._base_url = (base_url or GITHUB_API_URL).rstrip("/")
        self._client = HTTPClient(
            self._base_url,
            token=self._token,
            auth_header="Authorization",
            auth_prefix="Bearer",
            user_agent="vcspull",
        )

    @property
    def is_authenticated(self) -> bool:
        """Check if the importer has authentication configured.

        Returns
        -------
        bool
            True if a token is configured
        """
        return self._token is not None

    def fetch_repos(self, options: ImportOptions) -> t.Iterator[RemoteRepo]:
        """Fetch repositories from GitHub.

        Parameters
        ----------
        options : ImportOptions
            Scraping options

        Yields
        ------
        RemoteRepo
            Repository information

        Raises
        ------
        AuthenticationError
            When authentication fails
        RateLimitError
            When rate limit is exceeded
        NotFoundError
            When user/org is not found
        """
        if options.mode == ImportMode.USER:
            yield from self._fetch_user(options)
        elif options.mode == ImportMode.ORG:
            yield from self._fetch_org(options)
        elif options.mode == ImportMode.SEARCH:
            yield from self._fetch_search(options)

    def _fetch_user(self, options: ImportOptions) -> t.Iterator[RemoteRepo]:
        """Fetch repositories for a user.

        Parameters
        ----------
        options : ImportOptions
            Scraping options

        Yields
        ------
        RemoteRepo
            Repository information
        """
        endpoint = f"/users/{options.target}/repos"
        yield from self._paginate_repos(endpoint, options)

    def _fetch_org(self, options: ImportOptions) -> t.Iterator[RemoteRepo]:
        """Fetch repositories for an organization.

        Parameters
        ----------
        options : ImportOptions
            Scraping options

        Yields
        ------
        RemoteRepo
            Repository information
        """
        endpoint = f"/orgs/{options.target}/repos"
        yield from self._paginate_repos(endpoint, options)

    def _fetch_search(self, options: ImportOptions) -> t.Iterator[RemoteRepo]:
        """Search for repositories.

        Parameters
        ----------
        options : ImportOptions
            Scraping options

        Yields
        ------
        RemoteRepo
            Repository information
        """
        query_parts = [options.target]

        if options.language:
            query_parts.append(f"language:{options.language}")

        if options.min_stars > 0:
            query_parts.append(f"stars:>={options.min_stars}")

        query = " ".join(query_parts)
        endpoint = "/search/repositories"
        page = 1
        count = 0

        while count < options.limit:
            # Always use DEFAULT_PER_PAGE to maintain consistent pagination offset.
            # Changing per_page between pages causes offset misalignment and duplicates.
            params: dict[str, str | int] = {
                "q": query,
                "per_page": DEFAULT_PER_PAGE,
                "page": page,
                "sort": "stars",
                "order": "desc",
            }

            data, headers = self._client.get(
                endpoint,
                params=params,
                service_name=self.service_name,
            )

            self._log_rate_limit(headers)

            items = data.get("items", [])
            if not items:
                break

            for item in items:
                if count >= options.limit:
                    break

                repo = self._parse_repo(item)
                if filter_repo(repo, options):
                    yield repo
                    count += 1

            # Check if there are more pages
            if len(items) < DEFAULT_PER_PAGE:
                break

            page += 1

    def _paginate_repos(
        self,
        endpoint: str,
        options: ImportOptions,
    ) -> t.Iterator[RemoteRepo]:
        """Paginate through repository listing endpoints.

        Parameters
        ----------
        endpoint : str
            API endpoint
        options : ImportOptions
            Scraping options

        Yields
        ------
        RemoteRepo
            Repository information
        """
        page = 1
        count = 0

        while count < options.limit:
            # Always use DEFAULT_PER_PAGE to maintain consistent pagination offset.
            # Changing per_page between pages causes offset misalignment and duplicates.
            params: dict[str, str | int] = {
                "per_page": DEFAULT_PER_PAGE,
                "page": page,
                "sort": "updated",
                "direction": "desc",
            }

            data, headers = self._client.get(
                endpoint,
                params=params,
                service_name=self.service_name,
            )

            self._log_rate_limit(headers)

            if not data:
                break

            for item in data:
                if count >= options.limit:
                    break

                repo = self._parse_repo(item)
                if filter_repo(repo, options):
                    yield repo
                    count += 1

            # Check if there are more pages
            if len(data) < DEFAULT_PER_PAGE:
                break

            page += 1

    def _parse_repo(self, data: dict[str, t.Any]) -> RemoteRepo:
        """Parse GitHub API response into RemoteRepo.

        Parameters
        ----------
        data : dict
            GitHub API repository data

        Returns
        -------
        RemoteRepo
            Parsed repository information
        """
        return RemoteRepo(
            name=data["name"],
            clone_url=data["clone_url"],
            html_url=data["html_url"],
            description=data.get("description"),
            language=data.get("language"),
            topics=tuple(data.get("topics", [])),
            stars=data.get("stargazers_count", 0),
            is_fork=data.get("fork", False),
            is_archived=data.get("archived", False),
            default_branch=data.get("default_branch", "main"),
            owner=data.get("owner", {}).get("login", ""),
        )

    def _log_rate_limit(self, headers: dict[str, str]) -> None:
        """Log rate limit information from response headers.

        Parameters
        ----------
        headers : dict[str, str]
            Response headers
        """
        remaining = headers.get("x-ratelimit-remaining")
        limit = headers.get("x-ratelimit-limit")

        if remaining is not None and limit is not None:
            remaining_int = int(remaining)
            if remaining_int < 10:
                log.warning(
                    "GitHub API rate limit low: %s/%s remaining",
                    remaining,
                    limit,
                )
            else:
                log.debug(
                    "GitHub API rate limit: %s/%s remaining",
                    remaining,
                    limit,
                )
