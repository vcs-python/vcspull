"""Shared test helpers for vcspull CLI tests."""

from __future__ import annotations

import typing as t

from vcspull._internal.remotes import (
    ImportOptions,
    RemoteRepo,
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
