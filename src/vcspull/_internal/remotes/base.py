"""Base classes and utilities for remote repository importers."""

from __future__ import annotations

import dataclasses
import enum
import json
import logging
import os
import typing as t
import urllib.error
import urllib.parse
import urllib.request

log = logging.getLogger(__name__)


class ImportMode(enum.Enum):
    """Import mode for remote services."""

    USER = "user"
    ORG = "org"
    SEARCH = "search"


class RemoteImportError(Exception):
    """Base exception for remote import errors."""

    def __init__(self, message: str, service: str | None = None) -> None:
        """Initialize the error.

        Parameters
        ----------
        message : str
            Error message
        service : str | None
            Name of the service that raised the error

        Examples
        --------
        >>> err = RemoteImportError("connection failed", service="GitHub")
        >>> str(err)
        'connection failed'
        >>> err.service
        'GitHub'
        """
        super().__init__(message)
        self.service = service


class AuthenticationError(RemoteImportError):
    """Raised when authentication fails or is required."""


class RateLimitError(RemoteImportError):
    """Raised when API rate limit is exceeded."""


class NotFoundError(RemoteImportError):
    """Raised when a requested resource is not found."""


class ServiceUnavailableError(RemoteImportError):
    """Raised when the service is unavailable."""


class ConfigurationError(RemoteImportError):
    """Raised when there's a configuration error."""


class DependencyError(RemoteImportError):
    """Raised when a required dependency is missing."""


@dataclasses.dataclass(frozen=True)
class RemoteRepo:
    """Represents a repository from a remote service.

    Parameters
    ----------
    name : str
        Repository name (filesystem-safe)
    clone_url : str
        HTTPS URL for cloning the repository
    ssh_url : str
        SSH URL for cloning the repository
    html_url : str
        URL for viewing the repository in a browser
    description : str | None
        Repository description
    language : str | None
        Primary programming language
    topics : tuple[str, ...]
        Repository topics/tags
    stars : int
        Star/favorite count
    is_fork : bool
        Whether this is a fork of another repository
    is_archived : bool
        Whether the repository is archived
    default_branch : str
        Default branch name
    owner : str
        Owner username or organization name
    """

    name: str
    clone_url: str
    ssh_url: str
    html_url: str
    description: str | None
    language: str | None
    topics: tuple[str, ...]
    stars: int
    is_fork: bool
    is_archived: bool
    default_branch: str
    owner: str

    def to_vcspull_url(self, *, use_ssh: bool = True) -> str:
        """Return the URL formatted for vcspull config.

        Parameters
        ----------
        use_ssh : bool
            When True and ``ssh_url`` is non-empty, use the SSH URL.
            Falls back to ``clone_url`` when ``ssh_url`` is empty.

        Returns
        -------
        str
            Git URL with git+ prefix for vcspull config

        Examples
        --------
        >>> repo = RemoteRepo(
        ...     name="test",
        ...     clone_url="https://github.com/user/test.git",
        ...     ssh_url="git@github.com:user/test.git",
        ...     html_url="https://github.com/user/test",
        ...     description=None,
        ...     language=None,
        ...     topics=(),
        ...     stars=0,
        ...     is_fork=False,
        ...     is_archived=False,
        ...     default_branch="main",
        ...     owner="user",
        ... )
        >>> repo.to_vcspull_url()
        'git+git@github.com:user/test.git'
        >>> repo.to_vcspull_url(use_ssh=False)
        'git+https://github.com/user/test.git'
        """
        url = self.ssh_url if use_ssh and self.ssh_url else self.clone_url
        if url.startswith("git+"):
            return url
        return f"git+{url}"

    def to_dict(self) -> dict[str, t.Any]:
        """Convert to dictionary for JSON serialization.

        Returns
        -------
        dict[str, t.Any]
            Dictionary representation

        Examples
        --------
        >>> repo = RemoteRepo(
        ...     name="test",
        ...     clone_url="https://github.com/user/test.git",
        ...     ssh_url="git@github.com:user/test.git",
        ...     html_url="https://github.com/user/test",
        ...     description="A test repo",
        ...     language="Python",
        ...     topics=("cli", "tool"),
        ...     stars=100,
        ...     is_fork=False,
        ...     is_archived=False,
        ...     default_branch="main",
        ...     owner="user",
        ... )
        >>> d = repo.to_dict()
        >>> d["name"]
        'test'
        >>> d["topics"]
        ['cli', 'tool']
        """
        return {
            "name": self.name,
            "clone_url": self.clone_url,
            "ssh_url": self.ssh_url,
            "html_url": self.html_url,
            "description": self.description,
            "language": self.language,
            "topics": list(self.topics),
            "stars": self.stars,
            "is_fork": self.is_fork,
            "is_archived": self.is_archived,
            "default_branch": self.default_branch,
            "owner": self.owner,
        }


@dataclasses.dataclass
class ImportOptions:
    """Options for importing repositories from a remote service.

    Parameters
    ----------
    mode : ImportMode
        The importing mode (user, org, or search)
    target : str
        Target user, org, or search query
    base_url : str | None
        Base URL for self-hosted instances
    token : str | None
        API token for authentication
    include_forks : bool
        Whether to include forked repositories
    include_archived : bool
        Whether to include archived repositories
    language : str | None
        Filter by programming language
    topics : list[str]
        Filter by topics
    min_stars : int
        Minimum star count (for search mode)
    limit : int
        Maximum number of repositories to return
    """

    mode: ImportMode = ImportMode.USER
    target: str = ""
    base_url: str | None = None
    token: str | None = None
    include_forks: bool = False
    include_archived: bool = False
    language: str | None = None
    topics: list[str] = dataclasses.field(default_factory=list)
    min_stars: int = 0
    limit: int = 100

    def __post_init__(self) -> None:
        """Validate options after initialization.

        Examples
        --------
        >>> opts = ImportOptions(limit=10)
        >>> opts.limit
        10

        >>> ImportOptions(limit=0)
        Traceback (most recent call last):
            ...
        ValueError: limit must be >= 1, got 0
        """
        if self.limit < 1:
            msg = f"limit must be >= 1, got {self.limit}"
            raise ValueError(msg)


class HTTPClient:
    """Simple HTTP client using urllib for making API requests."""

    def __init__(
        self,
        base_url: str,
        *,
        token: str | None = None,
        auth_header: str = "Authorization",
        auth_prefix: str = "Bearer",
        user_agent: str = "vcspull",
        timeout: int = 30,
    ) -> None:
        """Initialize the HTTP client.

        Parameters
        ----------
        base_url : str
            Base URL for API requests
        token : str | None
            Authentication token
        auth_header : str
            Header name for authentication
        auth_prefix : str
            Prefix for the token in the auth header
        user_agent : str
            User-Agent header value
        timeout : int
            Request timeout in seconds

        Examples
        --------
        >>> client = HTTPClient("https://api.example.com/")
        >>> client.base_url
        'https://api.example.com'
        """
        self.base_url = base_url.rstrip("/")
        self.token = token
        if token and not self.base_url.startswith("https://"):
            log.warning(
                "Authentication token will be sent over non-HTTPS connection "
                "to %s — consider using HTTPS to protect credentials",
                self.base_url,
            )
        self.auth_header = auth_header
        self.auth_prefix = auth_prefix
        self.user_agent = user_agent
        self.timeout = timeout

    def _build_headers(self) -> dict[str, str]:
        """Build request headers.

        Returns
        -------
        dict[str, str]
            Request headers

        Examples
        --------
        >>> client = HTTPClient("https://api.example.com", token="tok123")
        >>> headers = client._build_headers()
        >>> headers["Authorization"]
        'Bearer tok123'

        >>> client = HTTPClient("https://api.example.com")
        >>> "Authorization" not in client._build_headers()
        True
        """
        headers = {
            "User-Agent": self.user_agent,
            "Accept": "application/json",
        }
        if self.token:
            if self.auth_prefix:
                headers[self.auth_header] = f"{self.auth_prefix} {self.token}"
            else:
                headers[self.auth_header] = self.token
        return headers

    def get(
        self,
        endpoint: str,
        *,
        params: dict[str, str | int] | None = None,
        service_name: str = "remote",
    ) -> tuple[t.Any, dict[str, str]]:
        """Make a GET request to the API.

        Parameters
        ----------
        endpoint : str
            API endpoint (will be appended to base_url)
        params : dict | None
            Query parameters
        service_name : str
            Service name for error messages

        Returns
        -------
        tuple[Any, dict[str, str]]
            Parsed JSON response and response headers

        Raises
        ------
        AuthenticationError
            When authentication fails (401)
        RateLimitError
            When rate limit is exceeded (403/429)
        NotFoundError
            When resource is not found (404)
        ServiceUnavailableError
            When service is unavailable (5xx)
        """
        url = f"{self.base_url}{endpoint}"

        if params:
            parts = urllib.parse.urlsplit(url)
            existing_qs = urllib.parse.parse_qs(parts.query)
            existing_qs.update({k: [str(v)] for k, v in params.items()})
            new_query = urllib.parse.urlencode(
                {k: v[0] for k, v in existing_qs.items()},
            )
            url = urllib.parse.urlunsplit(
                (parts.scheme, parts.netloc, parts.path, new_query, parts.fragment),
            )

        headers = self._build_headers()
        request = urllib.request.Request(url, headers=headers)

        log.debug("GET %s", url)

        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                body = response.read().decode("utf-8")
                response_headers = {k.lower(): v for k, v in response.getheaders()}
                return json.loads(body), response_headers
        except urllib.error.HTTPError as exc:
            self._handle_http_error(exc, service_name)
        except urllib.error.URLError as exc:
            msg = f"Connection error: {exc.reason}"
            raise ServiceUnavailableError(msg, service=service_name) from exc
        except json.JSONDecodeError as exc:
            msg = f"Invalid JSON response from {service_name}"
            raise ServiceUnavailableError(msg, service=service_name) from exc

        # Should never reach here, but for type checker
        msg = "Unexpected error"
        raise ServiceUnavailableError(msg, service=service_name)

    def _handle_http_error(
        self,
        exc: urllib.error.HTTPError,
        service_name: str,
    ) -> t.NoReturn:
        """Handle HTTP error responses.

        Parameters
        ----------
        exc : urllib.error.HTTPError
            The HTTP error
        service_name : str
            Service name for error messages

        Raises
        ------
        AuthenticationError
            When authentication fails (401)
        RateLimitError
            When rate limit is exceeded (403/429)
        NotFoundError
            When resource is not found (404)
        ServiceUnavailableError
            When service is unavailable (5xx)
        """
        try:
            body = exc.read().decode("utf-8")
            error_data = json.loads(body)
            message = str(error_data.get("message", exc))
        except (json.JSONDecodeError, UnicodeDecodeError):
            message = str(exc)

        if exc.code == 401:
            msg = f"Authentication failed for {service_name}: {message}"
            raise AuthenticationError(msg, service=service_name) from exc

        if exc.code == 403:
            if "rate limit" in message.lower():
                msg = f"Rate limit exceeded for {service_name}: {message}"
                raise RateLimitError(msg, service=service_name) from exc
            msg = f"Access denied for {service_name}: {message}"
            raise AuthenticationError(msg, service=service_name) from exc

        if exc.code == 404:
            msg = f"Resource not found on {service_name}: {message}"
            raise NotFoundError(msg, service=service_name) from exc

        if exc.code == 429:
            msg = f"Rate limit exceeded for {service_name}: {message}"
            raise RateLimitError(msg, service=service_name) from exc

        if exc.code >= 500:
            msg = f"{service_name} service unavailable: {message}"
            raise ServiceUnavailableError(msg, service=service_name) from exc

        msg = f"HTTP {exc.code} from {service_name}: {message}"
        raise ServiceUnavailableError(msg, service=service_name) from exc


def get_token_from_env(*env_vars: str) -> str | None:
    """Get an API token from environment variables.

    Parameters
    ----------
    *env_vars : str
        Environment variable names to check in order

    Returns
    -------
    str | None
        The token if found, None otherwise

    Examples
    --------
    >>> import os
    >>> os.environ["TEST_TOKEN"] = "secret"
    >>> get_token_from_env("TEST_TOKEN", "OTHER_TOKEN")
    'secret'
    >>> get_token_from_env("NONEXISTENT_TOKEN")
    >>> del os.environ["TEST_TOKEN"]
    """
    for var in env_vars:
        token = os.environ.get(var)
        if token:
            return token
    return None


def filter_repo(
    repo: RemoteRepo,
    options: ImportOptions,
) -> bool:
    """Check if a repository passes the filter criteria.

    Parameters
    ----------
    repo : RemoteRepo
        The repository to check
    options : ImportOptions
        Filter options

    Returns
    -------
    bool
        True if the repository passes all filters

    Examples
    --------
    >>> repo = RemoteRepo(
    ...     name="test",
    ...     clone_url="https://github.com/user/test.git",
    ...     ssh_url="git@github.com:user/test.git",
    ...     html_url="https://github.com/user/test",
    ...     description=None,
    ...     language="Python",
    ...     topics=("cli",),
    ...     stars=50,
    ...     is_fork=False,
    ...     is_archived=False,
    ...     default_branch="main",
    ...     owner="user",
    ... )
    >>> options = ImportOptions(include_forks=False, include_archived=False)
    >>> filter_repo(repo, options)
    True
    >>> options = ImportOptions(language="JavaScript")
    >>> filter_repo(repo, options)
    False
    """
    # Check fork filter
    if repo.is_fork and not options.include_forks:
        return False

    # Check archived filter
    if repo.is_archived and not options.include_archived:
        return False

    # Check language filter
    if options.language and (
        not repo.language or repo.language.lower() != options.language.lower()
    ):
        return False

    # Check topics filter
    if options.topics:
        repo_topics_lower = {topic.lower() for topic in repo.topics}
        required_topics_lower = {topic.lower() for topic in options.topics}
        if not required_topics_lower.issubset(repo_topics_lower):
            return False

    # Check minimum stars
    return not (options.min_stars > 0 and repo.stars < options.min_stars)
