"""Utility functions for vcspull."""

from __future__ import annotations

import os
import pathlib
import typing as t
from collections.abc import Mapping, MutableMapping

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


T = t.TypeVar("T", bound=MutableMapping[str, object])


def update_dict(
    d: T,
    u: Mapping[str, object],
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
            current = d.get(k)
            if isinstance(current, MutableMapping):
                r = update_dict(current, t.cast("Mapping[str, object]", v))
            elif isinstance(current, Mapping):
                r = update_dict(dict(current), t.cast("Mapping[str, object]", v))
            else:
                r = update_dict({}, t.cast("Mapping[str, object]", v))
            d[k] = r
        else:
            d[k] = v
    return d
