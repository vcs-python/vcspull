import pathlib
import typing as t

from vcspull.types import RawConfigDict

if t.TYPE_CHECKING:
    from typing_extensions import TypeGuard


def is_valid_config(config: t.Dict[str, t.Any]) -> "TypeGuard[RawConfigDict]":
    if not isinstance(config, dict):
        return False

    for k, v in config.items():
        if k is None or v is None:
            return False

        if not isinstance(k, str) and not isinstance(k, pathlib.Path):
            return False

        if not isinstance(v, dict):
            return False

        for repo_name, repo in v.items():
            if not isinstance(repo, (str, dict, pathlib.Path)):
                return False

            if isinstance(repo, dict):
                if "url" not in repo and "repo" not in repo:
                    return False

    return True
