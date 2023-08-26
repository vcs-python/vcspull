import pathlib
import typing as t

if t.TYPE_CHECKING:
    from typing_extensions import TypeGuard

    from vcspull.types import RawConfigDict


def is_valid_config(config: dict[str, t.Any]) -> "TypeGuard[RawConfigDict]":
    if not isinstance(config, dict):
        return False

    for k, v in config.items():
        if k is None or v is None:
            return False

        if not isinstance(k, str) and not isinstance(k, pathlib.Path):
            return False

        if not isinstance(v, dict):
            return False

        for repo in v.values():
            if not isinstance(repo, (str, dict, pathlib.Path)):
                return False

            if isinstance(repo, dict) and "url" not in repo and "repo" not in repo:
                return False

    return True
