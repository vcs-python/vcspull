"""Sphinx configuration for vcspull documentation."""

from __future__ import annotations

import pathlib
import re
import sys
import typing as t

from gp_sphinx.config import make_linkcode_resolve, merge_sphinx_config

import vcspull

if t.TYPE_CHECKING:
    from sphinx.application import Sphinx

# Get the project root dir, which is the parent dir of this
cwd = pathlib.Path(__file__).parent
project_root = cwd.parent
src_root = project_root / "src"

sys.path.insert(0, str(src_root))
sys.path.insert(0, str(cwd / "_ext"))

# package data
about: dict[str, str] = {}
with (src_root / "vcspull" / "__about__.py").open() as fp:
    exec(fp.read(), about)

conf = merge_sphinx_config(
    project=about["__title__"],
    version=about["__version__"],
    copyright=about["__copyright__"],
    source_repository=f"{about['__github__']}/",
    docs_url=about["__docs__"],
    source_branch="master",
    light_logo="img/vcspull.svg",
    dark_logo="img/vcspull-dark.svg",
    extra_extensions=[
        "sphinx_autodoc_api_style",
        "sphinx_autodoc_argparse.exemplar",
    ],
    intersphinx_mapping={
        "py": ("https://docs.python.org/", None),
        "libvcs": ("https://libvcs.git-pull.com/", None),
    },
    linkcode_resolve=make_linkcode_resolve(vcspull, about["__github__"]),
    html_favicon="_static/favicon.ico",
    html_extra_path=["manifest.json"],
    rediraffe_redirects="redirects.txt",
    # AGENTS.md is agent guidance, not a site page; keep Sphinx from
    # treating it as an orphan document.
    exclude_patterns=["_build", "AGENTS.md", "CLAUDE.md"],
)

_gp_setup = conf.pop("setup")

_NUMPY_UNDERLINE = re.compile(r"^\s*-{2,}\s*$")


def _numpy_attribute_names(doc: str | None) -> frozenset[str]:
    """Return field names a NumPy ``Attributes`` section of *doc* documents."""
    if not doc:
        return frozenset()

    lines = doc.expandtabs().splitlines()
    names: set[str] = set()
    index = 0
    while index + 1 < len(lines):
        heading = lines[index].strip() == "Attributes"
        if not (heading and _NUMPY_UNDERLINE.match(lines[index + 1])):
            index += 1
            continue

        indent = len(lines[index]) - len(lines[index].lstrip())
        cursor = index + 2
        while cursor < len(lines):
            entry = lines[cursor]
            if not entry.strip():
                cursor += 1
                continue
            entry_indent = len(entry) - len(entry.lstrip())
            if entry_indent < indent:
                break
            if entry_indent == indent:
                # The next NumPy section header is underlined; stop before it.
                if cursor + 1 < len(lines) and _NUMPY_UNDERLINE.match(
                    lines[cursor + 1]
                ):
                    break
                names.add(entry.split(":", 1)[0].strip())
            cursor += 1
        index = cursor

    return frozenset(names)


def _skip_documented_namedtuple_fields(
    app: Sphinx,
    what: str,
    name: str,
    obj: object,
    skip: bool,
    options: object,
) -> bool | None:
    """Drop NamedTuple field stubs the class docstring already documents.

    ``typing.NamedTuple`` fields are descriptors whose ``__doc__`` is
    ``"Alias for field number N"``. Autodoc counts that boilerplate as a real
    docstring, so the field is documented no matter how ``undoc-members`` is
    set. When the class docstring carries a NumPy ``Attributes`` section, the
    docstring preprocessor has already emitted an ``.. attribute::`` block for
    the same dotted name, and the Python domain warns about the duplicate.
    """
    if skip or what != "class":
        return None

    current = app.env.current_document
    module = sys.modules.get(getattr(current, "autodoc_module", "") or "")
    owner_name = (getattr(current, "autodoc_class", "") or "").partition(".")[0]
    owner = getattr(module, owner_name, None)

    fields = getattr(owner, "_fields", None)
    if not isinstance(fields, tuple) or name not in fields:
        return None

    return name in _numpy_attribute_names(owner.__doc__)


def setup(app: Sphinx) -> None:
    """Configure Sphinx app hooks and register vcspull-specific lexers."""
    _gp_setup(app)
    app.connect("autodoc-skip-member", _skip_documented_namedtuple_fields)

    from vcspull_console_lexer import VcspullConsoleLexer
    from vcspull_output_lexer import VcspullOutputLexer

    app.add_lexer("vcspull-output", VcspullOutputLexer)
    app.add_lexer("vcspull-console", VcspullConsoleLexer)


globals().update(conf)
