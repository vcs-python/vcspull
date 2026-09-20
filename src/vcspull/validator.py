"""Validation of vcspull configuration file."""

from __future__ import annotations

import pathlib
import typing as t

from vcspull import exc
from vcspull.types import RawConfigDict


def validate_working_copy(
    value: object,
    *,
    location: str = "working_copy",
    worktree: bool = False,
) -> None:
    """Require one target and validate its drift/dirty policy without VCS I/O."""

    def fail(key: str, message: str) -> t.NoReturn:
        prefix = f"{location}.{key}" if key else location
        msg = f"{prefix}: {message}"
        raise exc.VCSPullException(msg)

    if not isinstance(value, dict):
        fail("", "expected a mapping")
    ref_keys = ("branch", "tag", "commit", "rev")
    allowed = {*ref_keys, "remote", "sync"}
    if worktree:
        allowed.update(("dir", "detach", "lock", "lock_reason"))
        if not value.get("dir"):
            fail("", "missing required 'dir' field")
        if not isinstance(value["dir"], str):
            fail("dir", "'dir' must be a string")
    unknown = value.keys() - allowed
    if unknown:
        fail(min(map(str, unknown)), "unknown key")

    refs = [key for key in ref_keys if key in value]
    if not refs:
        fail("", "must specify one of: branch, tag, commit, or rev")
    if len(refs) > 1:
        fail("", "cannot specify multiple refs (branch, tag, commit, rev)")
    ref = refs[0]
    selected = value[ref]
    if ref == "rev" and type(selected) is int:
        if selected < 0:
            fail(ref, "revision must be nonnegative")
    else:
        if not isinstance(selected, str):
            fail(ref, f"'{ref}' must be a string")
        if not selected:
            fail(ref, "empty ref value")
        if selected.startswith("-") or "\0" in selected:
            fail(ref, "ref must not begin with '-' or contain NUL")

    if "remote" in value and (
        not isinstance(value["remote"], str) or not value["remote"]
    ):
        fail("remote", "expected a nonempty remote name")
    if "sync" in value:
        policy = value["sync"]
        if not isinstance(policy, dict):
            fail("sync", "expected a mapping")
        unknown_policy = policy.keys() - {"drift", "dirty"}
        if unknown_policy:
            fail(f"sync.{min(map(str, unknown_policy))}", "unknown key")
        for key, choices in (
            ("drift", ("keep", "follow", "warn")),
            ("dirty", ("abort", "preserve", "discard")),
        ):
            if key in policy and policy[key] not in choices:
                fail(f"sync.{key}", f"expected one of {', '.join(choices)}")
    if worktree:
        for key in ("detach", "lock"):
            if key in value and not isinstance(value[key], bool):
                fail(key, "expected a boolean")
        if "lock_reason" in value and not isinstance(value["lock_reason"], str):
            fail("lock_reason", "expected a string")


def is_valid_config(config: dict[str, t.Any]) -> t.TypeGuard[RawConfigDict]:
    """Return true and upcast if vcspull configuration file is valid."""
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
