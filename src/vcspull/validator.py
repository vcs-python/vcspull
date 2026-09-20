"""Validation of vcspull configuration file."""

from __future__ import annotations

import dataclasses
import math
import pathlib
import re
import typing as t

from libvcs import GitOptions, HgOptions, SvnOptions
from libvcs._internal.types import VCSLiteral
from libvcs.sync.git import GitRemote
from libvcs.url import registry as url_tools

from vcspull import exc
from vcspull.types import RawConfigDict


def match_vcs_url(url: str) -> tuple[VCSLiteral, ...]:
    """Match explicit backend rules using stable ASCII word/digit semantics.

    Unicode hostnames and paths remain supported. For an unprefixed SCP URL
    whose path starts with a non-ASCII character, declare the backend.

    >>> match_vcs_url("git@host:project")
    ('git',)
    >>> match_vcs_url("host:éx")
    ()
    >>> match_vcs_url("git+ssh://host/éx")
    ('git',)
    """
    matches = []
    for backend, parser in url_tools.registry.parser_map.items():
        rules = t.cast("t.Any", parser).rule_map
        if any(
            rule.is_explicit
            and re.search(
                rule.pattern.pattern,
                url,
                (rule.pattern.flags & ~re.UNICODE) | re.ASCII,
            )
            for rule in rules.values()
        ):
            matches.append(t.cast("VCSLiteral", backend))
    return tuple(matches)


def _config_integer(value: t.Any, *, location: str = "value") -> t.Any:
    """Normalize mathematical integers from JSON or YAML numeric values.

    >>> _config_integer(2.0)
    2
    >>> _config_integer(2.5)
    2.5
    """
    normalized = (
        int(value) if isinstance(value, float) and value.is_integer() else value
    )
    if type(normalized) is int and abs(normalized) > 2**53 - 1:
        msg = f"{location}: integer exceeds the exact JSON number range"
        raise exc.VCSPullException(msg)
    return normalized


def _is_json_value(value: t.Any, ancestors: frozenset[int] = frozenset()) -> bool:
    """Reject non-JSON YAML values and recursive aliases in metadata.

    >>> _is_json_value({"labels": ["python", None, True]})
    True
    >>> _is_json_value({1: "invalid key"})
    False
    """
    if value is None or isinstance(value, (str, bool, int)):
        return True
    if isinstance(value, float):
        return math.isfinite(value)
    if id(value) in ancestors:
        return False
    parents = ancestors | {id(value)}
    if isinstance(value, list):
        return all(_is_json_value(item, parents) for item in value)
    if isinstance(value, dict):
        return all(
            isinstance(key, str) and _is_json_value(item, parents)
            for key, item in value.items()
        )
    return False


def validate_metadata(value: t.Any, *, location: str = "metadata") -> None:
    """Require a finite JSON mapping before copying or comparing entries.

    >>> validate_metadata({"imported_from": "github:example"})
    """
    if not isinstance(value, dict) or not _is_json_value(value):
        msg = f"{location}: expected a JSON-compatible mapping"
        raise exc.VCSPullException(msg)


def _normalize_filter(
    value: t.Any, *, location: str, depth: int = 0, outer: bool = True
) -> t.Any:
    """Normalize numeric filter fields and require structured combinations.

    >>> _normalize_filter({"kind": "tree", "depth": 2.0}, location="filter")
    {'kind': 'tree', 'depth': 2}
    """
    if depth > 32:
        msg = f"{location}: filter nesting exceeds 32 levels"
        raise exc.VCSPullException(msg)
    if isinstance(value, str) and value.startswith("combine:"):
        msg = f"{location}: use a kind: combine mapping with filters, or a list"
        raise exc.VCSPullException(msg)
    if isinstance(value, list):
        return [
            _normalize_filter(
                item,
                location=f"{location}[{idx}]",
                depth=depth if outer else depth + 1,
                outer=False,
            )
            for idx, item in enumerate(value)
        ]
    if isinstance(value, dict):
        result = value.copy()
        for key in ("limit", "depth"):
            if key in result:
                result[key] = _config_integer(result[key], location=f"{location}.{key}")
        children = result.get("filters")
        if result.get("kind") == "combine" and isinstance(children, list):
            result["filters"] = [
                _normalize_filter(
                    item,
                    location=f"{location}.filters[{idx}]",
                    depth=depth + 1,
                    outer=False,
                )
                for idx, item in enumerate(children)
            ]
        return result
    return value


def _validate_backend_options(
    value: t.Any,
    options_type: type[GitOptions | HgOptions | SvnOptions],
    *,
    location: str,
) -> dict[str, t.Any]:
    """Validate backend fields at their original configuration location.

    >>> _validate_backend_options({"depth": 2.0}, GitOptions, location="git")
    {'depth': 2}
    """
    if not isinstance(value, dict):
        msg = f"{location}: expected a mapping"
        raise exc.VCSPullException(msg)
    options = value.copy()
    fields = {field.name for field in dataclasses.fields(options_type)}
    unknown = options.keys() - fields
    if unknown:
        msg = f"{location}.{min(map(str, unknown))}: unknown option"
        raise exc.VCSPullException(msg)
    if options_type is GitOptions:
        if "depth" in options:
            options["depth"] = _config_integer(
                options["depth"], location=f"{location}.depth"
            )
        if "filter" in options:
            options["filter"] = _normalize_filter(
                options["filter"], location=f"{location}.filter"
            )
    try:
        options_type(**options)
    except (TypeError, ValueError) as error:
        detail = str(error)
        key = next((key for key in options if detail.startswith(key)), "filter")
        if key == "filter" and detail.startswith("filter["):
            key = detail.split(":", 1)[0]
        msg = f"{location}.{key}: {detail}"
        raise exc.VCSPullException(msg) from error
    return options


def validate_legacy_options(value: dict[str, t.Any]) -> None:
    """Validate supplied legacy settings before precedence can hide errors.

    >>> validate_legacy_options({"repo": "git+https://example.com/r.git", "depth": 2})
    """
    options = value.get("options", {})
    if not isinstance(options, dict):
        msg = "options: expected a mapping"
        raise exc.VCSPullException(msg)
    allowed = {"rev", "shallow", "depth", "pin", "pin_reason", "allow_overwrite"}
    unknown = options.keys() - allowed
    if unknown:
        msg = f"options.{min(map(str, unknown))}: unknown legacy option"
        raise exc.VCSPullException(msg)
    context: dict[str, t.Any] = {
        key: value[key] for key in ("repo", "url", "vcs") if key in value
    }
    for prefix, fields in (("", value), ("options.", options)):
        if fields.get("rev") is not None:
            validate_working_copy(
                {"rev": fields["rev"]}, location=prefix.rstrip(".") or "repository"
            )
        if fields.get("shallow") is not None and not isinstance(
            fields["shallow"], bool
        ):
            msg = f"{prefix}shallow: expected a boolean"
            raise exc.VCSPullException(msg)
        if fields.get("depth") is not None:
            _validate_backend_options(
                {"depth": fields["depth"]},
                GitOptions,
                location=prefix.rstrip(".") or "repository",
            )
        if fields.get("depth") is not None or fields.get("shallow") is True:
            validate_repo_entry(
                {**context, "git": {}}, location=prefix.rstrip(".") or "repository"
            )
        if prefix:
            for key in ("pin", "pin_reason", "allow_overwrite"):
                if key in fields:
                    validate_repo_entry(
                        {**context, key: fields[key]}, location="options"
                    )
    for name, options_type in (
        ("git", GitOptions),
        ("hg", HgOptions),
        ("svn", SvnOptions),
    ):
        alias = f"{name}_options"
        if alias in value:
            _validate_backend_options(value[alias], options_type, location=alias)
            validate_repo_entry({**context, name: {}}, location=alias)


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
    if ref == "rev":
        value[ref] = _config_integer(value[ref], location=f"{location}.{ref}")
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
    if "remote" in value and (
        value["remote"].startswith("-") or "\0" in value["remote"]
    ):
        fail("remote", "remote must not begin with '-' or contain NUL")
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
    for alias in ("repo", "url"):
        if alias in value and (
            not isinstance(value[alias], str)
            or not value[alias]
            or "\0" in value[alias]
        ):
            fail(alias, "expected a nonempty URL string without NUL")
    url = value.get("url", value.get("repo"))
    if not isinstance(url, str) or not url or "\0" in url:
        fail("repo", "expected a nonempty URL string without NUL")
    matches = match_vcs_url(url)
    inferred = matches[0] if len(matches) == 1 else None
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
        value[name] = _validate_backend_options(
            value[name], options_type, location=f"{location}.{name}"
        )
    for key in ("name", "workspace_root"):
        if key in value and (not isinstance(value[key], str) or not value[key]):
            fail(key, "expected a nonempty string")
    if "path" in value and not isinstance(value["path"], (str, pathlib.Path)):
        fail("path", "expected a path string")
    if "metadata" in value:
        validate_metadata(value["metadata"], location=f"{location}.metadata")
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
