"""Helpers for vcspull."""
import os
import pathlib
import textwrap
from typing import Literal

import kaptan


class EnvironmentVarGuard:

    """Class to help protect the environment variable properly.

    May be used as context manager.
    Vendorize to fix issue with Anaconda Python 2 not
    including test module, see #121.
    """

    def __init__(self):
        self._environ = os.environ
        self._unset = set()
        self._reset = dict()

    def set(self, envvar, value):
        if envvar not in self._environ:
            self._unset.add(envvar)
        else:
            self._reset[envvar] = self._environ[envvar]
        self._environ[envvar] = value

    def unset(self, envvar):
        if envvar in self._environ:
            self._reset[envvar] = self._environ[envvar]
            del self._environ[envvar]

    def __enter__(self):
        return self

    def __exit__(self, *ignore_exc):
        for envvar, value in self._reset.items():
            self._environ[envvar] = value
        for unset in self._unset:
            del self._environ[unset]


def write_config(config_path: pathlib.Path, content: str) -> pathlib.Path:
    config_path.write_text(content, encoding="utf-8")
    return config_path


def import_raw(data: str, format: Literal["yaml", "json"]) -> kaptan.Kaptan:
    return kaptan.Kaptan(handler=format).import_config(textwrap.dedent(data))


def load_raw(data: str, format: Literal["yaml", "json"]) -> dict:
    return import_raw(data=data, format=format).export("dict")
