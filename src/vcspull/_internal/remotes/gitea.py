"""Gitea/Forgejo/Codeberg repository importer for vcspull."""

from __future__ import annotations

import logging
import typing as t
import urllib.parse

from .base import (
    HTTPClient,
    ImportMode,
    ImportOptions,
    RemoteRepo,
    filter_repo,
    get_token_from_env,
)

log = logging.getLogger(__name__)

CODEBERG_API_URL = "https://codeberg.org"
DEFAULT_PER_PAGE = 50  # Gitea's default is 50


class GiteaImporter:
    """Importer for Gitea, Forgejo, and Codeberg repositories.

    Supports three modes:
    - USER: Fetch repositories for a user
    - ORG: Fetch repositories for an organization
    - SEARCH: Search for repositories by query

    Examples
    --------
    >>> importer = GiteaImporter(base_url="https://codeberg.org")
    >>> importer.service_name
    'Gitea'
    """

    service_name: str = "Gitea"

    def __init__(
        self,
        token: str | None = None,
        base_url: str | None = None,
    ) -> None:
        """Initialize the Gitea/Forgejo/Codeberg importer.

        Parameters
        ----------
        token : str | None
            API token. If not provided, will try service-specific env vars.
        base_url : str | None
            Base URL for the Gitea instance. Required for generic Gitea.
            Defaults to Codeberg if not specified.

        Notes
        -----
        Token lookup is hostname-aware:

        - Codeberg (codeberg.org): ``CODEBERG_TOKEN``, falls back to
          ``GITEA_TOKEN``
        - Forgejo (hostname contains "forgejo"): ``FORGEJO_TOKEN``, falls back
          to ``GITEA_TOKEN``
        - Other Gitea instances: ``GITEA_TOKEN``

        Create a scoped token with at least ``read:repository`` permission at
        ``https://<instance>/user/settings/applications``.

        Examples
        --------
        >>> importer = GiteaImporter(token="fake", base_url="https://codeberg.org")
        >>> importer.service_name
        'Gitea'
        """
        self._base_url = (base_url or CODEBERG_API_URL).rstrip("/")

        # Determine token from environment based on service.
        # Use proper URL parsing to extract hostname to avoid substring attacks.
        parsed_url = urllib.parse.urlparse(self._base_url.lower())
        hostname = parsed_url.netloc

        self._token: str | None
        if token:
            self._token = token
        elif hostname == "codeberg.org":
            self._token = get_token_from_env("CODEBERG_TOKEN", "GITEA_TOKEN")
        elif "forgejo" in hostname:
            self._token = get_token_from_env("FORGEJO_TOKEN", "GITEA_TOKEN")
        else:
            self._token = get_token_from_env("GITEA_TOKEN")

        self._client = HTTPClient(
            f"{self._base_url}/api/v1",
            token=self._token,
            auth_header="Authorization",
            auth_prefix="token",  # Gitea uses "token <token>"
            user_agent="vcspull",
        )

    @property
    def is_authenticated(self) -> bool:
        """Check if the importer has authentication configured.

        Returns
        -------
        bool
            True if a token is configured

        Examples
        --------
        >>> GiteaImporter(token="fake", base_url="https://codeberg.org").is_authenticated
        True
        """
        return self._token is not None

    def fetch_repos(self, options: ImportOptions) -> t.Iterator[RemoteRepo]:
        """Fetch repositories from Gitea/Forgejo/Codeberg.

        Parameters
        ----------
        options : ImportOptions
            Import options

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
            Import options

        Yields
        ------
        RemoteRepo
            Repository information
        """
        target = urllib.parse.quote(options.target, safe="")
        endpoint = f"/users/{target}/repos"
        yield from self._paginate_repos(endpoint, options)

    def _fetch_org(self, options: ImportOptions) -> t.Iterator[RemoteRepo]:
        """Fetch repositories for an organization.

        Parameters
        ----------
        options : ImportOptions
            Import options

        Yields
        ------
        RemoteRepo
            Repository information
        """
        target = urllib.parse.quote(options.target, safe="")
        endpoint = f"/orgs/{target}/repos"
        yield from self._paginate_repos(endpoint, options)

    def _fetch_search(self, options: ImportOptions) -> t.Iterator[RemoteRepo]:
        """Search for repositories.

        Parameters
        ----------
        options : ImportOptions
            Import options

        Yields
        ------
        RemoteRepo
            Repository information
        """
        endpoint = "/repos/search"
        page = 1
        count = 0

        while count < options.limit:
            # Always use DEFAULT_PER_PAGE to maintain consistent pagination offset.
            # Changing limit between pages causes offset misalignment and duplicates.
            params: dict[str, str | int] = {
                "q": options.target,
                "limit": DEFAULT_PER_PAGE,
                "page": page,
                "sort": "stars",
                "order": "desc",
            }

            if not options.include_archived:
                params["archived"] = "false"

            if not options.include_forks:
                params["fork"] = "false"

            data, _headers = self._client.get(
                endpoint,
                params=params,
                service_name=self.service_name,
            )

            # Gitea search returns {"ok": true, "data": [...]} or just [...]
            items = data.get("data", []) if isinstance(data, dict) else data

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
            Import options

        Yields
        ------
        RemoteRepo
            Repository information
        """
        page = 1
        count = 0

        while count < options.limit:
            # Always use DEFAULT_PER_PAGE to maintain consistent pagination offset.
            # Changing limit between pages causes offset misalignment and duplicates.
            params: dict[str, str | int] = {
                "limit": DEFAULT_PER_PAGE,
                "page": page,
            }

            data, _headers = self._client.get(
                endpoint,
                params=params,
                service_name=self.service_name,
            )

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
        """Parse Gitea API response into RemoteRepo.

        Parameters
        ----------
        data : dict
            Gitea API repository data

        Returns
        -------
        RemoteRepo
            Parsed repository information
        """
        owner_data = data.get("owner") or {}

        return RemoteRepo(
            name=data.get("name", ""),
            clone_url=data.get("clone_url", ""),
            ssh_url=data.get("ssh_url", ""),
            html_url=data.get("html_url", ""),
            description=data.get("description"),
            language=data.get("language"),
            topics=tuple(data.get("topics") or []),
            stars=data.get("stars_count", 0),  # Note: Gitea uses stars_count
            is_fork=data.get("fork", False),
            is_archived=data.get("archived", False),
            default_branch=data.get("default_branch", "main"),
            owner=owner_data.get("login", owner_data.get("username", "")),
        )
