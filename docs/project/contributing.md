# Development

Developing python projects associated with [git-pull.com] all use the same
structure and workflow. At a later point these will refer to that website for documentation.

[git-pull.com]: https://git-pull.com

## Bootstrap the project

Install [git] and [uv] (see uv's [installation documentation]).

Clone:

```console
$ git clone https://github.com/vcs-python/vcspull.git
```

```console
$ cd vcspull
```

Install packages:

```console
$ uv sync --all-extras --dev
```

[installation documentation]: https://docs.astral.sh/uv/getting-started/installation/
[git]: https://git-scm.com/

## Development loop

### Tests

Tests run on [pytest].

[pytest]: https://pytest.org/

#### Rerun on file change

via [pytest-watcher] (works out of the box):

```console
$ just start
```

via [entr(1)] (requires installation):

```console
$ just watch-test
```

[pytest-watcher]: https://github.com/olzhasar/pytest-watcher

#### Manual (just the command, please)

```console
$ uv run py.test
```

or:

```console
$ just test
```

#### Runtime dependency smoke test

Verify that the published wheel runs without dev/test extras:

```console
$ uvx \
    --isolated \
    --no-cache \
    --from . \
    python scripts/runtime_dep_smoketest.py
```

The script imports every ``vcspull`` module and exercises each CLI sub-command
with ``--help``. There is also a pytest wrapper guarded by a dedicated marker:

```console
$ uv run pytest \
    -m scripts__runtime_dep_smoketest \
    scripts/test_runtime_dep_smoketest.py
```

These checks are network-dependent because they rely on ``uvx`` to build the
package in an isolated environment.

#### pytest options

`PYTEST_ADDOPTS` can be set in the commands below. For more
information read [docs.pytest.com] for the latest documentation.

[docs.pytest.com]: https://docs.pytest.org/

Verbose:

```console
$ env PYTEST_ADDOPTS="-verbose" just start
```

Drop into {mod}`pdb` on first error:

```console
$ env PYTEST_ADDOPTS="-x -s --pdb" just start
```

If you have [ipython] installed:

```console
$ env PYTEST_ADDOPTS="--pdbcls=IPython.terminal.debugger:TerminalPdb" \
    just start
```

[ipython]: https://ipython.org/

### Documentation

[sphinx] generates the documentation. In the future this may change to
[docusaurus].

Default preview server: http://localhost:8022

[sphinx]: https://www.sphinx-doc.org/
[docusaurus]: https://docusaurus.io/

#### Rerun on file change

[sphinx-autobuild] will automatically build the docs, it also handles launching
a server, rebuilding file changes, and updating content in the browser:

```console
$ cd docs
```

```console
$ just start
```

If doing css adjustments:

```console
$ just design
```

[sphinx-autobuild]: https://github.com/executablebooks/sphinx-autobuild

Rebuild docs on file change (requires [entr(1)]):

```console
$ cd docs
```

```console
$ just dev
```

Use two terminals if needed:

```console
$ just watch
```

```console
$ just serve
```

#### Manual (just the command, please)

```console
$ cd docs
```

Build:

```console
$ just html
```

Launch server:

```console
$ just serve
```

## Linting

### ruff

[ruff] handles formatting, import sorting, and linting.

````{tab} Command

uv:

```console
$ uv run ruff check .
```

If you setup manually:

```console
$ ruff check .
```

````

````{tab} just

```console
$ just ruff
```

````

````{tab} Watch

```console
$ just watch-ruff
```

requires [`entr(1)`].

````

````{tab} Fix files

uv:

```console
$ uv run ruff check . --fix
```

If you setup manually:

```console
$ ruff check . --fix
```

````

#### ruff format

[ruff format] formats the code.

````{tab} Command

uv:

```console
$ uv run ruff format .
```

If you setup manually:

```console
$ ruff format .
```

````

````{tab} just

```console
$ just ruff-format
```

````

### mypy

[mypy] checks static types.

````{tab} Command

uv:

```console
$ uv run mypy .
```

If you setup manually:

```console
$ mypy .
```

````

````{tab} just

```console
$ just mypy
```

````

````{tab} Watch

```console
$ just watch-mypy
```

requires [`entr(1)`].
````

````{tab} Configuration

See `[tool.mypy]` in pyproject.toml.

```{literalinclude} ../../pyproject.toml
:language: toml
:start-at: "[tool.mypy]"
:end-before: "[tool"

```

````

## Publishing to PyPI

[uv] handles virtualenv creation, package requirements, versioning,
building, and publishing. Therefore there is no setup.py or requirements files.

Update `__version__` in `__about__.py` and `pyproject.toml`, then commit the
bump:

```console
$ git commit -m 'build(vcspull): Tag v0.1.1'
```

Tag it:

```console
$ git tag v0.1.1
```

Push the branch and the tag:

```console
$ git push
```

```console
$ git push --tags
```

[GitHub Actions](https://github.com/features/actions) will detect the new
git tag, and in its own workflow run `uv build` and push to
[PyPI](https://pypi.org/).

[uv]: https://github.com/astral-sh/uv
[entr(1)]: http://eradman.com/entrproject/
[`entr(1)`]: http://eradman.com/entrproject/
[ruff format]: https://docs.astral.sh/ruff/formatter/
[ruff]: https://ruff.rs
[mypy]: http://mypy-lang.org/
