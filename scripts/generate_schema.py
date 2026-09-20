"""Generate the published schema without adding runtime validation dependencies.

Run with the project's pinned Python version for reproducible type generation.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import typing as t

from libvcs.url.registry import registry
from pydantic import ConfigDict, TypeAdapter

from vcspull.types import RepoEntryDict

if t.TYPE_CHECKING:
    from libvcs.url.base import RuleMap

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "_static" / "schemas" / "vcspull.schema.json"
SCHEMA_ID = "https://vcspull.git-pull.com/_static/schemas/vcspull.schema.json"

DIGITS = "0123456789abcdef"
MAX_UINT = 2**64 - 1
MAX_JSON_INTEGER = 2**53 - 1
STRICT_END = r"(?![\s\S])"


def digit_atom(chars: str) -> str:
    """Accept both cases of each hexadecimal digit.

    >>> digit_atom("af")
    '[aAfF]'
    """
    chars = "".join(c + c.upper() if c.isalpha() else c for c in chars)
    return chars if len(chars) == 1 else "[" + chars + "]"


def bounded_number(maximum: int, base: int) -> str:
    """Match canonical unsigned numerals no greater than a positive maximum."""
    digits = ""
    while maximum:
        digits = DIGITS[maximum % base] + digits
        maximum //= base
    digits = digits or "0"
    parts = ["0"]
    any_digit = digit_atom(DIGITS[:base])
    nonzero = digit_atom(DIGITS[1:base])
    for length in range(1, len(digits)):
        tail = any_digit + f"{{{length - 1}}}" if length > 1 else ""
        parts.append(nonzero + tail)
    prefix = ""
    for position, character in enumerate(digits):
        lower = DIGITS[1 if position == 0 else 0 : DIGITS.index(character)]
        remaining = len(digits) - position - 1
        if lower:
            tail = any_digit + f"{{{remaining}}}" if remaining else ""
            parts.append(prefix + digit_atom(lower) + tail)
        prefix += digit_atom(character)
    parts.append(prefix)
    return "(?:" + "|".join(parts) + ")"


def unsigned_long_fragment() -> str:
    """Bound every base/unit combination before multiplication."""
    parts = []
    for power, suffix in enumerate(("", "[kK]", "[mM]", "[gG]")):
        bound = MAX_UINT // 1024**power
        number = "(?:" + bounded_number(bound, 10)
        number += "|0[xX]0*" + bounded_number(bound, 16)
        number += "|0+" + bounded_number(bound, 8) + ")"
        parts.append(number + suffix)
    return r"[\t\u000B\f ]*\+?(?:" + "|".join(parts) + ")"


def unsigned_long_pattern() -> str:
    """Anchor native unsigned-long syntax without accepting a final newline."""
    return "^" + unsigned_long_fragment() + STRICT_END


def atomic_filter_pattern(*, allow_auto: bool = True) -> str:
    """Match atomic native filters; combinations use structured config."""
    parts = [
        "blob:none",
        "object:type=(?:blob|tree|commit|tag)",
        r"sparse:oid=[^\u0000\r\n]+",
        "(?:tree:|blob:limit=)" + unsigned_long_fragment(),
    ]
    if allow_auto:
        parts.append("auto")
    return "^(?:" + "|".join(parts) + ")" + STRICT_END


def compact_verbose(pattern: re.Pattern[str]) -> str:
    """Strip only verbose syntax, preserving character classes and escapes."""
    assert pattern.flags == re.UNICODE | re.VERBOSE, pattern.flags
    source = pattern.pattern
    result = []
    inside_class = False
    index = 0
    while index < len(source):
        character = source[index]
        if character == "\\":
            result.append(source[index : index + 2])
            index += 2
            continue
        if character == "[":
            inside_class = True
        elif character == "]":
            inside_class = False
        if not inside_class and character == "#":
            end = source.find("\n", index)
            index = end if end >= 0 else len(source)
            continue
        if not inside_class and character in " \t\r\n\v\f":
            index += 1
            continue
        if not inside_class and source.startswith("(?P<", index):
            end = source.index(">", index + 4)
            result.append("(?:")
            index = end + 1
            continue
        result.append(character)
        index += 1
    compacted = "".join(result)
    assert "(?P" not in compacted
    return compacted


def url_predicates() -> dict[str, list[str]]:
    """Translate the bundled rules with the loader's ASCII word/digit contract."""
    output = {}
    for backend, parser in registry.parser_map.items():
        patterns = []
        rules: RuleMap = t.cast("t.Any", parser).rule_map
        for rule in rules.values():
            if not rule.is_explicit:
                continue
            pattern = compact_verbose(rule.pattern)
            pattern = pattern.replace(r"\w", "[A-Za-z0-9_]")
            pattern = pattern.replace(r"\d", "[0-9]")
            patterns.append(pattern)
        output[backend] = patterns
    return output


def ref(name: str) -> dict[str, str]:
    """Refer to a shared definition in the published document."""
    return {"$ref": f"#/$defs/{name}"}


def nullable(schema: dict[str, t.Any]) -> dict[str, t.Any]:
    """Retain an explicitly disabled configuration field."""
    return {"anyOf": [schema, {"type": "null"}]}


def selected_url(schema: dict[str, t.Any]) -> dict[str, t.Any]:
    """Apply URL inference to the alias selected by the loader."""
    return {
        "if": {"required": ["url"]},
        "then": {"properties": {"url": schema}},
        "else": {"required": ["repo"], "properties": {"repo": schema}},
    }


def backend_selected(name: str) -> dict[str, t.Any]:
    """Use a declared backend, or unique URL inference when undeclared."""
    return {
        "anyOf": [
            {"required": ["vcs"], "properties": {"vcs": {"const": name}}},
            {
                "allOf": [
                    {"properties": {"vcs": {"type": "null"}}},
                    selected_url(ref(f"Unique{name.title()}URL")),
                ]
            },
        ]
    }


def sort_enums(value: t.Any) -> None:
    """Stabilize Literal order, which can vary with interpreter type caching.

    >>> value = {"nested": [{"enum": ["svn", None, "git"]}]}
    >>> sort_enums(value)
    >>> value
    {'nested': [{'enum': ['git', 'svn', None]}]}
    """
    if isinstance(value, dict):
        if "enum" in value:
            value["enum"].sort(key=lambda item: json.dumps(item, sort_keys=True))
        for child in value.values():
            sort_enums(child)
    elif isinstance(value, list):
        for child in value:
            sort_enums(child)


def build_schema() -> dict[str, t.Any]:
    """Generate structural types and the loader's semantic constraints.

    Generation requires Python 3.12 or newer; the published schema validates
    configurations on every supported Python version.

    >>> import sys
    >>> if sys.version_info >= (3, 12):
    ...     assert build_schema()["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    """
    schema = TypeAdapter(
        dict[str, dict[str, str | RepoEntryDict]],
        config=ConfigDict(use_attribute_docstrings=True),
    ).json_schema()
    schema.update(
        {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "$id": SCHEMA_ID,
            "title": "vcspull workspace configuration",
        }
    )
    definitions = schema["$defs"]
    for definition in definitions.values():
        if definition.get("type") == "object":
            definition["additionalProperties"] = False
    nonempty = {"type": "string", "minLength": 1}
    no_nul = {"type": "string", "pattern": r"^[^\u0000]*(?![\s\S])"}
    url = {**no_nul, "minLength": 1}
    native_ref = {
        "type": "string",
        "minLength": 1,
        "pattern": r"^(?!-)[^\u0000]+(?![\s\S])",
    }
    revision = {
        "anyOf": [
            native_ref,
            {"type": "integer", "minimum": 0, "maximum": MAX_JSON_INTEGER},
        ]
    }
    remote_url = {
        "type": "string",
        "minLength": 1,
        "pattern": r"^[^\u0000\r\n]+(?![\s\S])",
    }
    schema["additionalProperties"]["additionalProperties"] = {
        "anyOf": [url, ref("RepoEntryDict")]
    }

    definitions["JsonValue"] = {
        "anyOf": [
            {"type": ["null", "boolean", "string", "number"]},
            {"type": "array", "items": ref("JsonValue")},
            {"type": "object", "additionalProperties": ref("JsonValue")},
        ]
    }
    repo = definitions["RepoEntryDict"]
    props = repo["properties"]
    props["repo"] = props["url"] = url
    repo.pop("required", None)
    repo["anyOf"] = [{"required": ["repo"]}, {"required": ["url"]}]
    for key in ("name", "workspace_root"):
        props[key] = nonempty
    props["metadata"] = {"type": "object", "additionalProperties": ref("JsonValue")}
    props["rev"] = nullable(revision)
    props["depth"] = nullable(
        {"type": "integer", "minimum": 1, "maximum": MAX_JSON_INTEGER}
    )
    for key in ("fetch_url", "push_url"):
        definitions["RemoteURLsDict"]["properties"][key] = remote_url
    props["remotes"]["propertyNames"] = remote_url
    props["remotes"]["additionalProperties"] = {
        "anyOf": [remote_url, ref("RemoteURLsDict")]
    }
    definitions["RepoOptionsDict"]["properties"]["rev"] = nullable(revision)
    definitions["RepoOptionsDict"]["properties"]["depth"] = props["depth"]
    for name in ("WorkingCopyConfigDict", "WorktreeConfigDict"):
        target = definitions[name]
        for key in ("branch", "tag", "commit"):
            target["properties"][key] = native_ref
        target["properties"]["rev"] = revision
        target["properties"]["remote"] = native_ref
        target["oneOf"] = [
            {"required": [key]} for key in ("branch", "tag", "commit", "rev")
        ]
    target_keys = [{"required": [key]} for key in ("branch", "tag", "commit", "rev")]
    no_target = {"not": {"anyOf": target_keys}}
    definitions["WorkingCopyConfigDict"]["oneOf"].append(no_target)
    definitions["WorktreeConfigDict"]["properties"]["dir"] = nonempty
    definitions["GitOptionsDict"]["properties"]["depth"] = props["depth"]
    for name, keys in (
        ("HgOptionsDict", ("ssh", "remote_cmd")),
        ("SvnOptionsDict", ("username", "password")),
    ):
        for key in keys:
            definitions[name]["properties"][key] = nullable(no_nul)

    definitions["AtomicFilter"] = {
        "type": "string",
        "pattern": atomic_filter_pattern(allow_auto=False),
    }
    uint = {"type": "integer", "minimum": 0, "maximum": MAX_JSON_INTEGER}
    atoms: dict[str, dict[str, t.Any]] = {
        "blob:none": {},
        "blob:limit": {
            "limit": {
                "anyOf": [uint, {"type": "string", "pattern": unsigned_long_pattern()}]
            }
        },
        "tree": {"depth": uint},
        "object:type": {"type": {"enum": ["blob", "tree", "commit", "tag"]}},
        "sparse:oid": {"oid": remote_url},
    }
    definitions["AtomicFilterMapping"] = {
        "oneOf": [
            {
                "type": "object",
                "properties": {"kind": {"const": kind}, **fields},
                "required": ["kind", *fields],
                "additionalProperties": False,
            }
            for kind, fields in atoms.items()
        ]
    }
    for depth in range(33):
        alternatives: list[dict[str, t.Any]] = [
            ref("AtomicFilter"),
            ref("AtomicFilterMapping"),
        ]
        if depth < 32:
            children = {
                "type": "array",
                "minItems": 1,
                "items": ref(f"FilterDepth{depth + 1}"),
            }
            alternatives.extend(
                [
                    children,
                    {
                        "type": "object",
                        "required": ["kind", "filters"],
                        "properties": {
                            "kind": {"const": "combine"},
                            "filters": children,
                        },
                        "additionalProperties": False,
                    },
                ]
            )
        definitions[f"FilterDepth{depth}"] = {"anyOf": alternatives}
    definitions["GitOptionsDict"]["properties"]["filter"] = {
        "anyOf": [
            {"type": "null"},
            {"const": "auto"},
            {
                "type": "object",
                "properties": {"kind": {"const": "auto"}},
                "required": ["kind"],
                "additionalProperties": False,
            },
            ref("FilterDepth0"),
            {"type": "array", "minItems": 1, "items": ref("FilterDepth0")},
        ]
    }

    backend_names = ("git", "hg", "svn")
    for name, patterns in url_predicates().items():
        definitions[f"{name.title()}URL"] = {
            "type": "string",
            "anyOf": [{"pattern": pattern} for pattern in patterns],
        }
        definitions[f"Unique{name.title()}URL"] = {
            "allOf": [
                ref(f"{name.title()}URL"),
                {
                    "not": {
                        "anyOf": [
                            ref(f"{other.title()}URL")
                            for other in backend_names
                            if other != name
                        ]
                    }
                },
            ]
        }
    rules = []
    for name in backend_names:
        rules.append(
            {
                "if": selected_url(ref(f"Unique{name.title()}URL")),
                "then": {"properties": {"vcs": {"enum": [name, None]}}},
            }
        )
        rules.append(
            {
                "if": {
                    "anyOf": [{"required": [name]}, {"required": [f"{name}_options"]}]
                },
                "then": backend_selected(name),
            }
        )
    legacy_git = {
        "anyOf": [
            {"required": ["depth"], "properties": {"depth": {"type": "integer"}}},
            {"required": ["shallow"], "properties": {"shallow": {"const": True}}},
        ]
    }
    rules.append(
        {
            "if": {
                "anyOf": [
                    legacy_git,
                    {"required": ["options"], "properties": {"options": legacy_git}},
                ]
            },
            "then": backend_selected("git"),
        }
    )
    # Migration fills an absent canonical target from options.rev, then rev.
    # A supplied null options.rev disables the top-level fallback.
    rules.append(
        {
            "if": {
                "required": ["working_copy"],
                "properties": {"working_copy": no_target},
            },
            "then": {
                "if": {
                    "required": ["options"],
                    "properties": {"options": {"required": ["rev"]}},
                },
                "then": {
                    "properties": {
                        "options": {
                            "properties": {"rev": revision},
                        }
                    }
                },
                "else": {"required": ["rev"], "properties": {"rev": revision}},
            },
        }
    )
    repo["allOf"] = rules
    sort_enums(schema)
    return schema


def main() -> int:
    """Write the schema, or fail when its committed bytes are stale."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="check the committed schema without writing",
    )
    args = parser.parse_args()
    content = json.dumps(build_schema(), indent=2, ensure_ascii=False) + "\n"
    if args.check:
        if not OUTPUT.exists() or OUTPUT.read_text() != content:
            print("Schema is stale; run python scripts/generate_schema.py")
            return 1
        return 0
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(content)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
