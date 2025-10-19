"""Utility functions for vcspull."""

from __future__ import annotations

import os
import pathlib
import typing as t
from collections.abc import Mapping

LEGACY_CONFIG_DIR = pathlib.Path("~/.vcspull/").expanduser()  # remove dupes of this


def get_config_dir() -> pathlib.Path:
    """
    Return vcspull configuration directory.

    ``VCSPULL_CONFIGDIR`` environmental variable has precedence if set. We also
    evaluate XDG default directory from XDG_CONFIG_HOME environmental variable
    if set or its default. Then the old default ~/.vcspull is returned for
    compatibility.

    Returns
    -------
    str :
        absolute path to tmuxp config directory
    """
    paths: list[pathlib.Path] = []
    if "VCSPULL_CONFIGDIR" in os.environ:
        paths.append(pathlib.Path(os.environ["VCSPULL_CONFIGDIR"]))
    if "XDG_CONFIG_HOME" in os.environ:
        paths.append(pathlib.Path(os.environ["XDG_CONFIG_HOME"]) / "vcspull")
    else:
        paths.append(pathlib.Path("~/.config/vcspull/"))
    paths.append(LEGACY_CONFIG_DIR)

    for path in paths:
        path = path.expanduser()
        if path.is_dir():
            return path

    # Return last path as default if none of the previous ones matched
    return path


def contract_user_home(path: str | pathlib.Path) -> str:
    """Contract user home directory to ~ for display purposes.

    Parameters
    ----------
    path : str | pathlib.Path
        Path to contract

    Returns
    -------
    str
        Path with $HOME contracted to ~

    Examples
    --------
    >>> contract_user_home("/home/user/code/repo")
    '~/code/repo'
    >>> contract_user_home("/opt/project")
    '/opt/project'
    """
    path_str = str(path)
    home_str = str(pathlib.Path.home())

    # Replace home directory with ~ if path starts with it
    if path_str.startswith(home_str):
        # Handle both /home/user and /home/user/ cases
        relative = path_str[len(home_str) :]
        if relative.startswith(os.sep):
            relative = relative[1:]
        return f"~/{relative}" if relative else "~"

    return path_str


T = t.TypeVar("T", bound=dict[str, t.Any])


def update_dict(
    d: T,
    u: T,
) -> T:
    """Return updated dict.

    Parameters
    ----------
    d : dict
    u : dict

    Returns
    -------
    dict :
        Updated dictionary

    Notes
    -----
    Thanks: http://stackoverflow.com/a/3233356
    """
    for k, v in u.items():
        if isinstance(v, Mapping):
            r = update_dict(d.get(k, {}), v)
            d[k] = r
        else:
            d[k] = v
    return d
