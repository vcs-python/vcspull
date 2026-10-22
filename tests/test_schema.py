"""Published editor schema and config-loader agreement."""

from __future__ import annotations

import json
import pathlib
import random
import subprocess
import sys
import typing as t

import jsonschema
import pytest

from vcspull.config import load_configs, save_config_yaml
from vcspull.exc import VCSPullException

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "docs" / "_static" / "schemas" / "vcspull.schema.json"

CASES: list[tuple[bool, dict[str, t.Any]]] = [
    (True, {}),
    (True, {"git": {"filter": {"kind": "tree", "depth": 2**53 - 1}}}),
    (True, {"git": {"filter": "tree:18446744073709551615"}}),
    (
        True,
        {"git": {"filter": {"kind": "blob:limit", "limit": "18446744073709551615"}}},
    ),
    (False, {"git": {"filter": {"kind": "tree", "depth": 2**53}}}),
    (False, {"git": {"filter": {"kind": "blob:limit", "limit": 2**53}}}),
    (False, {"git": {"depth": 2**53}}),
    (False, {"working_copy": {"rev": 2**53}}),
    (False, {"options": {"depth": 2**53}}),
    (True, {"working_copy": {}, "rev": "main"}),
    (True, {"working_copy": {"remote": "origin"}, "options": {"rev": "main"}}),
    (True, {"working_copy": {"sync": {"dirty": "abort"}}, "rev": "main"}),
    (False, {"working_copy": {}, "rev": "main", "options": {"rev": None}}),
    (False, {"working_copy": {}, "rev": None}),
    (True, {"repo": "https://example.com/r", "git": {}}),
    (False, {"repo": "host:éx", "git": {}}),
    (True, {"repo": "host:éx", "vcs": "git", "git": {}}),
    (True, {"repo": "host:éx", "vcs": "hg", "hg": {}}),
    (False, {"repo": "host:𐌀x", "git": {}}),
    (True, {"repo": "host:x𐌀", "git": {}}),
    (True, {"repo": "junk git+file://x", "git": {}}),
    (True, {"repo": "hg+https://x/git+file://y", "vcs": "git", "git": {}}),
    (False, {"repo": "host:é", "git": {}}),
    (False, {"repo": "hg+https://x/git+file://y", "git": {}}),
    (False, {"url": ""}),
    (
        False,
        {"repo": "hg+https://example.com/r", "depth": 2, "options": {"depth": None}},
    ),
    (False, {"working_copy": {"branch": "main", "remote": "-bad"}}),
    (False, {"working_copy": {"branch": "main", "remote": "bad\0remote"}}),
    (True, {"url": "hg+https://example.com/r", "hg": {"pull": True}}),
    (
        True,
        {
            "repo": "svn+https://example.com/r",
            "svn": {"depth": "files"},
            "working_copy": {"rev": 2.0},
        },
    ),
    (True, {"git": {"depth": 2.0, "filter": "blob:none", "tls_verify": False}}),
    (
        True,
        {
            "git": {
                "filter": {
                    "kind": "combine",
                    "filters": ["blob:none", [{"kind": "tree", "depth": 2}]],
                }
            }
        },
    ),
    (True, {"git": {"filter": "sparse:oid=a+b%25"}}),
    (True, {"git": {"filter": "tree:0xFG"}}),
    (True, {"git": {"filter": "auto"}}),
    (
        True,
        {
            "options": {
                "shallow": True,
                "depth": None,
                "pin": {"fmt": True},
                "rev": "main",
            }
        },
    ),
    (True, {"git_options": {"depth": 4, "filter": "blob:none"}, "git": {"depth": 2}}),
    (True, {"metadata": {"labels": ["python", None, True, 2.5], "nested": {}}}),
    (
        True,
        {
            "remotes": {
                "upstream": {
                    "fetch_url": "git+https://example.com/up.git",
                    "push_url": "git+ssh://example.com/up.git",
                }
            }
        },
    ),
    (
        True,
        {
            "worktrees": [
                {
                    "dir": "../branch",
                    "branch": "main",
                    "sync": {"drift": "keep", "dirty": "abort"},
                }
            ]
        },
    ),
    (True, {"shell_command_after": None, "worktrees": None}),
    (False, {"git": {"deph": 2}}),
    (False, {"git": {"depth": True}}),
    (False, {"git": {"depth": 1.5}}),
    (False, {"git": {"filter": []}}),
    (False, {"git": {"filter": ["auto"]}}),
    (False, {"git": {"filter": {"kind": "combine", "filters": ["auto"]}}}),
    (False, {"git": {"filter": {"kind": "tree", "depth": -1}}}),
    (False, {"git": {"filter": {"kind": "tree", "depth": 2**64}}}),
    (False, {"git": {"filter": "tree:18446744073709551616"}}),
    (False, {"git": {"filter": "combine:blob:none+tree:1"}}),
    (False, {"git": {"filter": {"kind": "nope"}}}),
    (False, {"git": {"filter": "blob:none\n"}}),
    (False, {"options": {"depth": False}, "git": {"depth": 2}}),
    (False, {"git_options": {"depth": False}, "git": {"depth": 2}}),
    (False, {"rev": [], "working_copy": {"branch": "main"}}),
    (False, {"repo": False, "url": "git+https://example.com/r.git"}),
    (False, {"hg": {}}),
    (False, {"svn_options": {}}),
    (False, {"vcs": "svn"}),
    (False, {"working_copy": {"branch": "main", "tag": "v1"}}),
    (False, {"working_copy": {"sync": {"dirty": "preserve"}}}),
    (False, {"working_copy": {"rev": True}}),
    (False, {"working_copy": {"branch": "-invalid"}}),
    (False, {"working_copy": {"branch": "main", "sync": {"drift": "guess"}}}),
    (False, {"worktrees": [{"branch": "main"}]}),
    (False, {"remotes": {"upstream": {"fetch_url": "https://example.com/up.git"}}}),
    (False, {"remotes": {"upstream": ""}}),
    (False, {"remotes": {"upstream": "https://example.com/r\n"}}),
    (False, {"metadata": []}),
    (False, {"pin": {"sync": True}}),
    (False, {"working_coppy": {"branch": "main"}}),
]


@pytest.fixture(scope="module")
def validator() -> jsonschema.Draft202012Validator:
    """Validate the committed schema before using it as an oracle."""
    schema = json.loads(SCHEMA.read_text())
    jsonschema.Draft202012Validator.check_schema(schema)
    return jsonschema.Draft202012Validator(schema)


@pytest.mark.parametrize(("expected", "fields"), CASES)
def test_schema_and_loader_agree(
    expected: bool,
    fields: dict[str, t.Any],
    tmp_path: pathlib.Path,
    validator: jsonschema.Draft202012Validator,
) -> None:
    """Both validators see the original document without custom validators."""
    document = {"./": {"project": {"repo": "git+https://example.com/r.git", **fields}}}
    path = tmp_path / "config.yaml"
    save_config_yaml(path, document)
    try:
        load_configs([path], warn_legacy_options=False)
    except VCSPullException:
        loaded = False
    else:
        loaded = True
    assert loaded is expected
    assert validator.is_valid(document) is expected


@pytest.mark.skipif(
    sys.version_info < (3, 12),
    reason="Pydantic requires Python 3.12 for typing.TypedDict generation",
)
def test_committed_schema_is_current() -> None:
    """The generator checks the same artifact that the docs publish."""
    subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "generate_schema.py"), "--check"],
        cwd=ROOT,
        check=True,
    )


def test_cli_does_not_import_schema_dependencies() -> None:
    """Development-only schema dependencies stay out of CLI startup."""
    subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys; import vcspull.cli; "
                "assert not {'pydantic', 'jsonschema'} & sys.modules.keys()"
            ),
        ],
        check=True,
    )


@pytest.mark.parametrize("depth", [31, 32, 33])
@pytest.mark.parametrize("outer_list", [False, True])
def test_schema_filter_depth_matches_loader(
    depth: int,
    outer_list: bool,
    tmp_path: pathlib.Path,
    validator: jsonschema.Draft202012Validator,
) -> None:
    """The repeated outer list does not consume a combination nesting level."""
    filter_value: t.Any = "blob:none"
    for _ in range(depth):
        filter_value = {"kind": "combine", "filters": [filter_value]}
    if outer_list:
        filter_value = [filter_value]
    test_schema_and_loader_agree(
        depth <= 32, {"git": {"filter": filter_value}}, tmp_path, validator
    )


def numeric_filter_cases() -> list[tuple[bool, dict[str, t.Any]]]:
    """Exercise native base/unit limits with independently calculated verdicts."""
    values = [
        (True, "0xFG"),
        (True, "  +077K"),
        (False, "08"),
        (False, "1KB"),
        (False, "1\n"),
        (False, "\u00a01"),
    ]
    maximum = 2**64 - 1
    for power, unit in enumerate(("", "k", "M", "g")):
        bound = maximum // 1024**power
        for number in (bound - 1, bound, bound + 1):
            values.extend(
                (number <= bound, form + unit)
                for form in (str(number), hex(number), "0" + format(number, "o"))
            )
    rng = random.Random(576)
    for _ in range(32):
        number = rng.randrange(2**66)
        power = rng.randrange(4)
        values.append(
            (number <= maximum // 1024**power, hex(number) + ("", "k", "M", "g")[power])
        )
    return [
        (expected, {"git": {"filter": prefix + value}})
        for expected, value in values
        for prefix in ("tree:", "blob:limit=")
    ]


def test_schema_numeric_filter_boundaries(
    tmp_path: pathlib.Path,
    validator: jsonschema.Draft202012Validator,
) -> None:
    """Every native uint64 base/unit boundary agrees before any normalization."""
    for expected, fields in numeric_filter_cases():
        test_schema_and_loader_agree(expected, fields, tmp_path, validator)
