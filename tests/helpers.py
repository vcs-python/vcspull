"""Helpers for vcspull."""
import os
import pathlib
import typing as t

from vcspull._internal.config_reader import ConfigReader


class EnvironmentVarGuard:
    """Class to help protect the environment variable properly.

    May be used as context manager.
    Vendorize to fix issue with Anaconda Python 2 not
    including test module, see #121.
    """

    def __init__(self) -> None:
        self._environ = os.environ
        self._unset: set[str] = set()
        self._reset: dict[str, str] = {}

    def set(self, envvar: str, value: str) -> None:
        """Set environmental variable."""
        if envvar not in self._environ:
            self._unset.add(envvar)
        else:
            self._reset[envvar] = self._environ[envvar]
        self._environ[envvar] = value

    def unset(self, envvar: str) -> None:
        """Unset environmental variable."""
        if envvar in self._environ:
            self._reset[envvar] = self._environ[envvar]
            del self._environ[envvar]

    def __enter__(self) -> "EnvironmentVarGuard":
        """Context manager entry for setting and resetting environmental variable."""
        return self

    def __exit__(self, *ignore_exc: object) -> None:
        """Context manager teardown for setting and resetting environmental variable."""
        for envvar, value in self._reset.items():
            self._environ[envvar] = value
        for unset in self._unset:
            del self._environ[unset]


def write_config(config_path: pathlib.Path, content: str) -> pathlib.Path:
    """Write configuration file."""
    config_path.write_text(content, encoding="utf-8")
    return config_path


def load_raw(data: str, format: t.Literal["yaml", "json"]) -> dict[str, t.Any]:
    """Load configuration data via string value. Accepts yaml or json."""
    return ConfigReader._load(format=format, content=data)
