"""GitLab repository importer for vcspull."""

from __future__ import annotations

import logging
import typing as t
import urllib.parse

from .base import (
    AuthenticationError,
    HTTPClient,
    ImportMode,
    ImportOptions,
    RemoteRepo,
    filter_repo,
    get_token_from_env,
)

log = logging.getLogger(__name__)

GITLAB_API_URL = "https://gitlab.com"
DEFAULT_PER_PAGE = 100


class GitLabImporter:
    """Importer for GitLab repositories.

    Supports three modes:
    - USER: Fetch repositories for a user
    - ORG: Fetch repositories for a group (organization)
    - SEARCH: Search for repositories (requires authentication)

    Examples
    --------
    >>> importer = GitLabImporter()
    >>> importer.service_name
    'GitLab'
    """

    service_name: str = "GitLab"

    def __init__(
        self,
        token: str | None = None,
        base_url: str | None = None,
    ) -> None:
        """Initialize the GitLab importer.

        Parameters
        ----------
        token : str | None
            GitLab API token. If not provided, will try GITLAB_TOKEN env var.
        base_url : str | None
            Base URL for self-hosted GitLab instances. Defaults to gitlab.com.

        Examples
        --------
        >>> importer = GitLabImporter(token="fake")
        >>> importer.service_name
        'GitLab'
        """
        self._token = token or get_token_from_env("GITLAB_TOKEN", "GL_TOKEN")
        self._base_url = (base_url or GITLAB_API_URL).rstrip("/")
        self._client = HTTPClient(
            f"{self._base_url}/api/v4",
            token=self._token,
            auth_header="PRIVATE-TOKEN",
            auth_prefix="",  # GitLab uses token directly without prefix
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
        >>> GitLabImporter(token="fake").is_authenticated
        True
        """
        return self._token is not None

    def fetch_repos(self, options: ImportOptions) -> t.Iterator[RemoteRepo]:
        """Fetch repositories from GitLab.

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
            When authentication fails or is required for search
        RateLimitError
            When rate limit is exceeded
        NotFoundError
            When user/group is not found
        """
        if options.mode == ImportMode.USER:
            yield from self._fetch_user(options)
        elif options.mode == ImportMode.ORG:
            yield from self._fetch_group(options)
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
        endpoint = f"/users/{target}/projects"
        yield from self._paginate_repos(endpoint, options)

    def _fetch_group(self, options: ImportOptions) -> t.Iterator[RemoteRepo]:
        """Fetch repositories for a group (organization).

        Parameters
        ----------
        options : ImportOptions
            Import options

        Yields
        ------
        RemoteRepo
            Repository information
        """
        # URL-encode the group name (handles slashes in subgroups, etc.)
        target = urllib.parse.quote(options.target, safe="")
        endpoint = f"/groups/{target}/projects"
        yield from self._paginate_repos(endpoint, options, include_subgroups=True)

    def _fetch_search(self, options: ImportOptions) -> t.Iterator[RemoteRepo]:
        """Search for repositories.

        Note: GitLab search API requires authentication.

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
            When not authenticated (GitLab search requires auth)
        """
        if not self.is_authenticated:
            msg = (
                "GitLab search API requires authentication. Please provide "
                "a token via --token or GITLAB_TOKEN environment variable."
            )
            raise AuthenticationError(msg, service=self.service_name)

        endpoint = "/search"
        page = 1
        count = 0

        while count < options.limit:
            # Always use DEFAULT_PER_PAGE to maintain consistent pagination offset.
            # Changing per_page between pages causes offset misalignment and duplicates.
            params: dict[str, str | int] = {
                "scope": "projects",
                "search": options.target,
                "per_page": DEFAULT_PER_PAGE,
                "page": page,
            }

            if not options.include_archived:
                params["archived"] = "false"

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

    def _paginate_repos(
        self,
        endpoint: str,
        options: ImportOptions,
        *,
        include_subgroups: bool = False,
    ) -> t.Iterator[RemoteRepo]:
        """Paginate through project listing endpoints.

        Parameters
        ----------
        endpoint : str
            API endpoint
        options : ImportOptions
            Import options
        include_subgroups : bool
            Whether to include projects from subgroups

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
                "order_by": "last_activity_at",
                "sort": "desc",
            }

            if include_subgroups:
                params["include_subgroups"] = "true"

            if not options.include_archived:
                params["archived"] = "false"
            # When include_archived=True, omit the param to get all projects

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
        """Parse GitLab API response into RemoteRepo.

        Parameters
        ----------
        data : dict
            GitLab API project data

        Returns
        -------
        RemoteRepo
            Parsed repository information
        """
        # Use 'path' instead of 'name' for filesystem-safe name
        name = data.get("path", data.get("name", ""))

        # Prefer the full namespace path for subgroup-aware import behavior.
        namespace = data.get("namespace", {})
        owner = namespace.get("full_path")
        if not owner:
            path_with_namespace = data.get("path_with_namespace")
            if isinstance(path_with_namespace, str) and "/" in path_with_namespace:
                owner = path_with_namespace.rsplit("/", 1)[0]
            else:
                owner = namespace.get("path", namespace.get("name", ""))

        # Check if it's a fork
        is_fork = data.get("forked_from_project") is not None

        return RemoteRepo(
            name=name,
            clone_url=data.get("http_url_to_repo", ""),
            ssh_url=data.get("ssh_url_to_repo", ""),
            html_url=data.get("web_url", ""),
            description=data.get("description"),
            language=None,  # GitLab doesn't return language in list endpoints
            topics=tuple(data.get("topics") or data.get("tag_list") or []),
            stars=data.get("star_count", 0),
            is_fork=is_fork,
            is_archived=data.get("archived", False),
            default_branch=data.get("default_branch", "main"),
            owner=owner,
        )
