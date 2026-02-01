"""AWS CodeCommit repository importer for vcspull."""

from __future__ import annotations

import json
import logging
import subprocess
import typing as t

from .base import (
    AuthenticationError,
    ConfigurationError,
    DependencyError,
    ImportOptions,
    RemoteRepo,
    filter_repo,
)

log = logging.getLogger(__name__)


class CodeCommitImporter:
    """Importer for AWS CodeCommit repositories.

    Uses AWS CLI to list and fetch repository information.
    Requires AWS CLI to be installed and configured.

    Examples
    --------
    >>> importer = CodeCommitImporter(region="us-east-1")
    >>> importer.service_name
    'CodeCommit'
    """

    service_name: str = "CodeCommit"

    def __init__(
        self,
        region: str | None = None,
        profile: str | None = None,
    ) -> None:
        """Initialize the CodeCommit importer.

        Parameters
        ----------
        region : str | None
            AWS region. If not provided, uses AWS CLI default.
        profile : str | None
            AWS profile name. If not provided, uses default profile.
        """
        self._region = region
        self._profile = profile
        self._check_aws_cli()

    def _check_aws_cli(self) -> None:
        """Check if AWS CLI is installed and accessible.

        Raises
        ------
        DependencyError
            When AWS CLI is not installed
        """
        try:
            result = subprocess.run(
                ["aws", "--version"],
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode != 0:
                msg = (
                    "AWS CLI not installed or not accessible. "
                    "Please install it with: pip install awscli"
                )
                raise DependencyError(msg, service=self.service_name)
        except FileNotFoundError as exc:
            msg = "AWS CLI not installed. Please install it with: pip install awscli"
            raise DependencyError(msg, service=self.service_name) from exc

    def _build_aws_command(self, *args: str) -> list[str]:
        """Build AWS CLI command with region and profile options.

        Parameters
        ----------
        *args : str
            AWS CLI arguments

        Returns
        -------
        list[str]
            Complete command list
        """
        cmd = ["aws"]
        if self._region:
            cmd.extend(["--region", self._region])
        if self._profile:
            cmd.extend(["--profile", self._profile])
        cmd.extend(args)
        return cmd

    def _run_aws_command(self, *args: str) -> dict[str, t.Any]:
        """Run an AWS CLI command and return parsed JSON output.

        Parameters
        ----------
        *args : str
            AWS CLI arguments

        Returns
        -------
        dict
            Parsed JSON output

        Raises
        ------
        AuthenticationError
            When AWS credentials are missing or invalid
        ConfigurationError
            When region is invalid or endpoint unreachable
        """
        cmd = self._build_aws_command(*args)
        log.debug("Running: %s", " ".join(cmd))

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False,
            )
        except FileNotFoundError as exc:
            msg = "AWS CLI not found"
            raise DependencyError(msg, service=self.service_name) from exc

        if result.returncode != 0:
            stderr = result.stderr.lower()
            if "unable to locate credentials" in stderr:
                msg = (
                    "AWS credentials not configured. Run 'aws configure' or "
                    "set AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY."
                )
                raise AuthenticationError(msg, service=self.service_name)
            if "could not connect to the endpoint" in stderr:
                msg = (
                    f"Could not connect to CodeCommit. Check your region setting. "
                    f"Error: {result.stderr}"
                )
                raise ConfigurationError(msg, service=self.service_name)
            if "invalid" in stderr and "region" in stderr:
                msg = f"Invalid AWS region. Error: {result.stderr}"
                raise ConfigurationError(msg, service=self.service_name)
            msg = f"AWS CLI error: {result.stderr}"
            raise ConfigurationError(msg, service=self.service_name)

        try:
            return json.loads(result.stdout) if result.stdout.strip() else {}
        except json.JSONDecodeError as exc:
            msg = f"Invalid JSON from AWS CLI: {result.stdout}"
            raise ConfigurationError(msg, service=self.service_name) from exc

    @property
    def is_authenticated(self) -> bool:
        """Check if AWS credentials are configured.

        Returns
        -------
        bool
            True if credentials appear to be configured
        """
        try:
            self._run_aws_command("sts", "get-caller-identity")
        except (AuthenticationError, ConfigurationError):
            return False
        else:
            return True

    def fetch_repos(self, options: ImportOptions) -> t.Iterator[RemoteRepo]:
        """Fetch repositories from AWS CodeCommit.

        Parameters
        ----------
        options : ImportOptions
            Import options (target is used as optional name filter)

        Yields
        ------
        RemoteRepo
            Repository information

        Raises
        ------
        AuthenticationError
            When AWS credentials are missing
        ConfigurationError
            When region is invalid
        DependencyError
            When AWS CLI is not installed
        """
        # List all repositories
        data = self._run_aws_command("codecommit", "list-repositories")
        repositories = data.get("repositories", [])

        if not repositories:
            return

        # Filter by name if target is provided
        if options.target:
            target_lower = options.target.lower()
            repositories = [
                r
                for r in repositories
                if target_lower in r.get("repositoryName", "").lower()
            ]

        # Batch get repository details (up to 25 at a time)
        count = 0
        batch_size = 25

        for i in range(0, len(repositories), batch_size):
            if count >= options.limit:
                break

            batch = repositories[i : i + batch_size]
            repo_names = [r["repositoryName"] for r in batch]

            # Get detailed info for batch
            details = self._run_aws_command(
                "codecommit",
                "batch-get-repositories",
                "--repository-names",
                *repo_names,
            )

            for repo_metadata in details.get("repositories", []):
                if count >= options.limit:
                    break

                repo = self._parse_repo(repo_metadata)
                if filter_repo(repo, options):
                    yield repo
                    count += 1

    def _parse_repo(self, data: dict[str, t.Any]) -> RemoteRepo:
        """Parse CodeCommit repository metadata into RemoteRepo.

        Parameters
        ----------
        data : dict
            CodeCommit repository metadata

        Returns
        -------
        RemoteRepo
            Parsed repository information
        """
        repo_name = data.get("repositoryName", "")
        account_id = data.get("accountId", "")

        # Build console URL
        region = self._region or "us-east-1"
        html_url = (
            f"https://{region}.console.aws.amazon.com/codesuite/codecommit/"
            f"repositories/{repo_name}/browse"
        )

        return RemoteRepo(
            name=repo_name,
            clone_url=data.get("cloneUrlHttp", ""),
            html_url=html_url,
            description=data.get("repositoryDescription"),
            language=None,  # CodeCommit doesn't track language
            topics=(),  # CodeCommit doesn't have topics
            stars=0,  # CodeCommit doesn't have stars
            is_fork=False,  # CodeCommit doesn't have forks
            is_archived=False,  # CodeCommit doesn't have archived state
            default_branch=data.get("defaultBranch", "main"),
            owner=account_id,
        )
