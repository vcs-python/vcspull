"""Validation of vcspull configuration file."""

from __future__ import annotations

import dataclasses
import pathlib
import typing as t

from libvcs import GitOptions, HgOptions, SvnOptions
from libvcs.sync.git import GitRemote
from libvcs.url import registry as url_tools

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


def validate_repo_entry(value: dict[str, t.Any], *, location: str) -> None:
    """Validate canonical repository fields before any checkout is constructed."""

    def fail(key: str, message: str) -> t.NoReturn:
        msg = f"{location}.{key}: {message}"
        raise exc.VCSPullException(msg)

    allowed = {
        "repo",
        "url",
        "name",
        "path",
        "workspace_root",
        "vcs",
        "metadata",
        "working_copy",
        "worktrees",
        "remotes",
        "shell_command_after",
        "git",
        "hg",
        "svn",
        "pin",
        "pin_reason",
        "allow_overwrite",
    }
    unknown = value.keys() - allowed
    if unknown:
        fail(min(map(str, unknown)), "unknown key")
    url = value.get("url", value.get("repo"))
    if not isinstance(url, str) or not url or "\0" in url:
        fail("repo", "expected a nonempty URL string without NUL")
    matches = url_tools.registry.match(url=url, is_explicit=True)
    inferred = matches[0].vcs if len(matches) == 1 else None
    declared = value.get("vcs")
    if declared is not None and declared not in ("git", "hg", "svn"):
        fail("vcs", "expected git, hg, or svn")
    if declared is not None and inferred is not None and declared != inferred:
        fail("vcs", "does not match the repository URL")
    backend = declared or inferred
    for name, options_type in (
        ("git", GitOptions),
        ("hg", HgOptions),
        ("svn", SvnOptions),
    ):
        if name not in value:
            continue
        if name != backend:
            fail(
                name,
                f"options do not match the repository VCS ({backend or 'unknown'})",
            )
        options = value[name]
        if not isinstance(options, dict):
            fail(name, "expected a mapping")
        fields = {field.name for field in dataclasses.fields(options_type)}
        unknown_options = options.keys() - fields
        if unknown_options:
            fail(f"{name}.{min(map(str, unknown_options))}", "unknown option")
        try:
            options_type(**options)
        except (TypeError, ValueError) as error:
            detail = str(error)
            key = next((key for key in options if detail.startswith(key)), "filter")
            field = f"{name}.{key}"
            if key == "filter" and detail.startswith("filter["):
                field = f"{name}.{detail.split(':', 1)[0]}"
            fail(field, detail)
    for key in ("name", "workspace_root"):
        if key in value and (not isinstance(value[key], str) or not value[key]):
            fail(key, "expected a nonempty string")
    if "path" in value and not isinstance(value["path"], (str, pathlib.Path)):
        fail("path", "expected a path string")
    if "metadata" in value and not isinstance(value["metadata"], dict):
        fail("metadata", "expected a mapping")
    if "shell_command_after" in value:
        commands = value["shell_command_after"]
        if (
            commands is not None
            and not isinstance(commands, str)
            and not (
                isinstance(commands, list)
                and all(isinstance(item, str) for item in commands)
            )
        ):
            fail("shell_command_after", "expected a string, list of strings, or null")
    if "pin" in value:
        pin = value["pin"]
        if isinstance(pin, dict):
            unknown_pin = pin.keys() - {"import", "add", "discover", "fmt", "merge"}
            if unknown_pin:
                fail(f"pin.{min(map(str, unknown_pin))}", "unknown operation")
            for key, enabled in pin.items():
                if not isinstance(enabled, bool):
                    fail(f"pin.{key}", "expected a boolean")
        elif not isinstance(pin, bool):
            fail("pin", "expected a boolean or operation mapping")
    if "allow_overwrite" in value and not isinstance(value["allow_overwrite"], bool):
        fail("allow_overwrite", "expected a boolean")
    if value.get("pin_reason") is not None and not isinstance(value["pin_reason"], str):
        fail("pin_reason", "expected a string or null")
    if "remotes" in value:
        remotes = value["remotes"]
        if not isinstance(remotes, dict):
            fail("remotes", "expected a mapping")
        for name, remote in remotes.items():
            if (
                not isinstance(name, str)
                or not name
                or any(c in name for c in "\r\n\0")
            ):
                fail(
                    "remotes",
                    "expected nonempty remote names without line breaks or NUL",
                )
            if isinstance(remote, GitRemote):
                continue
            if isinstance(remote, str):
                if not remote or any(c in remote for c in "\r\n\0"):
                    fail(
                        f"remotes.{name}",
                        "expected a nonempty URL without line breaks or NUL",
                    )
                continue
            if not isinstance(remote, dict):
                fail(
                    f"remotes.{name}",
                    "expected a URL string or fetch_url/push_url mapping",
                )
            for key in ("fetch_url", "push_url"):
                if (
                    key not in remote
                    or not isinstance(remote[key], str)
                    or not remote[key]
                ):
                    fail(f"remotes.{name}.{key}", "expected a nonempty URL")
                if any(c in remote[key] for c in "\r\n\0"):
                    fail(
                        f"remotes.{name}.{key}",
                        "URL must not contain line breaks or NUL",
                    )
            unknown_remote = remote.keys() - {"fetch_url", "push_url"}
            if unknown_remote:
                fail(f"remotes.{name}.{min(map(str, unknown_remote))}", "unknown key")


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
