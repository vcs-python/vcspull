"""Sphinx configuration for vcspull documentation."""

# flake8: noqa: E501
import inspect
import pathlib
import sys
import typing as t
from os.path import relpath

import vcspull

if t.TYPE_CHECKING:
    from sphinx.application import Sphinx

# Get the project root dir, which is the parent dir of this
cwd = pathlib.Path.cwd()
project_root = cwd.parent
src_root = project_root / "src"

sys.path.insert(0, str(src_root))
sys.path.insert(0, str(cwd / "_ext"))

# package data
about: dict[str, str] = {}
with (src_root / "vcspull" / "__about__.py").open() as fp:
    exec(fp.read(), about)

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.intersphinx",
    "sphinx_autodoc_typehints",
    "sphinx.ext.todo",
    "sphinx.ext.napoleon",
    "sphinx.ext.linkcode",
    "sphinxarg.ext",  # sphinx-argparse
    "sphinx_inline_tabs",
    "sphinx_copybutton",
    "sphinxext.opengraph",
    "sphinxext.rediraffe",
    "myst_parser",
    "linkify_issues",
]
myst_enable_extensions = [
    "colon_fence",
    "substitution",
    "replacements",
    "strikethrough",
]

templates_path = ["_templates"]

source_suffix = {".rst": "restructuredtext", ".md": "markdown"}

master_doc = "index"

project = about["__title__"]
project_copyright = about["__copyright__"]

version = "%s" % (".".join(about["__version__"].split("."))[:2])
release = "%s" % (about["__version__"])

exclude_patterns = ["_build"]

pygments_style = "monokai"
pygments_dark_style = "monokai"

html_favicon = "_static/favicon.ico"
html_static_path = ["_static"]
html_css_files = ["css/custom.css"]
html_extra_path = ["manifest.json"]
html_theme = "furo"
html_theme_path: list[str] = []
html_theme_options = {
    "light_logo": "img/vcspull.svg",
    "dark_logo": "img/vcspull-dark.svg",
    "footer_icons": [
        {
            "name": "GitHub",
            "url": about["__github__"],
            "html": """
                <svg stroke="currentColor" fill="currentColor" stroke-width="0" viewBox="0 0 16 16">
                    <path fill-rule="evenodd" d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0 0 16 8c0-4.42-3.58-8-8-8z"></path>
                </svg>
            """,
            "class": "",
        },
    ],
    "source_repository": f"{about['__github__']}/",
    "source_branch": "master",
    "source_directory": "docs/",
}
html_sidebars = {
    "**": [
        "sidebar/scroll-start.html",
        "sidebar/brand.html",
        "sidebar/search.html",
        "sidebar/navigation.html",
        "sidebar/projects.html",
        "sidebar/scroll-end.html",
    ],
}

# linkify_issues
issue_url_tpl = about["__github__"] + "/issues/{issue_id}"

# sphinx.ext.autodoc
autoclass_content = "both"
autodoc_member_order = "bysource"
toc_object_entries_show_parents = "hide"
autodoc_default_options = {
    "undoc-members": True,
    "members": True,
    "private-members": True,
    "show-inheritance": True,
    "member-order": "bysource",
}

# sphinx-autodoc-typehints
autodoc_typehints = "description"  # show type hints in doc body instead of signature
simplify_optional_unions = True

# sphinx.ext.napoleon
napoleon_google_docstring = True
napoleon_include_init_with_doc = True

# sphinx-copybutton
copybutton_prompt_text = (
    r">>> |\.\.\. |> |\$ |\# | In \[\d*\]: | {2,5}\.\.\.: | {5,8}: "
)
copybutton_prompt_is_regexp = True
copybutton_remove_prompts = True

# sphinxext-rediraffe
rediraffe_redirects = "redirects.txt"
rediraffe_branch = "master~1"

# sphinxext.opengraph
ogp_site_url = about["__docs__"]
ogp_image = "_static/img/icons/icon-192x192.png"
ogp_site_name = about["__title__"]

intersphinx_mapping = {
    "py": ("https://docs.python.org/", None),
    "libvcs": ("http://libvcs.git-pull.com/", None),
}


def linkcode_resolve(domain: str, info: dict[str, str]) -> t.Union[None, str]:
    """
    Determine the URL corresponding to Python object.

    Notes
    -----
    From https://github.com/numpy/numpy/blob/v1.15.1/doc/source/conf.py, 7c49cfa
    on Jul 31. License BSD-3. https://github.com/numpy/numpy/blob/v1.15.1/LICENSE.txt
    """
    if domain != "py":
        return None

    modname = info["module"]
    fullname = info["fullname"]

    submod = sys.modules.get(modname)
    if submod is None:
        return None

    obj = submod
    for part in fullname.split("."):
        try:
            obj = getattr(obj, part)
        except Exception:  # noqa: PERF203
            return None

    # strip decorators, which would resolve to the source of the decorator
    # possibly an upstream bug in getsourcefile, bpo-1764286
    try:
        unwrap = inspect.unwrap
    except AttributeError:
        pass
    else:
        if callable(obj):
            obj = unwrap(obj)

    try:
        fn = inspect.getsourcefile(obj)
    except Exception:
        fn = None
    if not fn:
        return None

    try:
        source, lineno = inspect.getsourcelines(obj)
    except Exception:
        lineno = None

    linespec = "#L%d-L%d" % (lineno, lineno + len(source) - 1) if lineno else ""

    fn = relpath(fn, start=pathlib.Path(vcspull.__file__).parent)

    if "dev" in about["__version__"]:
        return "{}/blob/master/{}/{}/{}{}".format(
            about["__github__"],
            "src",
            about["__package_name__"],
            fn,
            linespec,
        )
    return "{}/blob/v{}/{}/{}/{}{}".format(
        about["__github__"],
        about["__version__"],
        "src",
        about["__package_name__"],
        fn,
        linespec,
    )


def remove_tabs_js(app: "Sphinx", exc: Exception) -> None:
    """Fix for sphinx-inline-tabs#18."""
    if app.builder.format == "html" and not exc:
        tabs_js = pathlib.Path(app.builder.outdir) / "_static" / "tabs.js"
        tabs_js.unlink(missing_ok=True)


def setup(app: "Sphinx") -> None:
    """Sphinx setup hook."""
    app.connect("build-finished", remove_tabs_js)
