"""Sphinx configuration for vcspull documentation."""

from __future__ import annotations

import pathlib
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
        "sphinx_argparse_neo.exemplar",
    ],
    intersphinx_mapping={
        "py": ("https://docs.python.org/", None),
        "libvcs": ("https://libvcs.git-pull.com/", None),
    },
    linkcode_resolve=make_linkcode_resolve(vcspull, about["__github__"]),
    html_favicon="_static/favicon.ico",
    html_extra_path=["manifest.json"],
    rediraffe_redirects="redirects.txt",
)

_gp_setup = conf.pop("setup")


def setup(app: Sphinx) -> None:
    """Configure Sphinx app hooks and register vcspull-specific lexers."""
    _gp_setup(app)

    from vcspull_console_lexer import VcspullConsoleLexer
    from vcspull_output_lexer import VcspullOutputLexer

    app.add_lexer("vcspull-output", VcspullOutputLexer)
    app.add_lexer("vcspull-console", VcspullConsoleLexer)


globals().update(conf)
