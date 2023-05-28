# Development

Developing python projects associated with [git-pull.com] all use the same
structure and workflow. At a later point these will refer to that website for documentation.

[git-pull.com]: https://git-pull.com

## Bootstrap the project

Install and [git] and [poetry]

Clone:

```console
$ git clone https://github.com/vcs-python/vcspull.git
```

```console
$ cd vcspull
```

Install packages:

```console
$ poetry install -E "docs test coverage lint"
```

[installation documentation]: https://python-poetry.org/docs/#installation
[git]: https://git-scm.com/

## Development loop

### Tests

[pytest] is used for tests.

[pytest]: https://pytest.org/

#### Rerun on file change

via [pytest-watcher] (works out of the box):

```console
$ make start
```

via [entr(1)] (requires installation):

```console
$ make watch_test
```

[pytest-watcher]: https://github.com/olzhasar/pytest-watcher

#### Manual (just the command, please)

```console
$ poetry run py.test
```

or:

```console
$ make test
```

#### pytest options

`PYTEST_ADDOPTS` can be set in the commands below. For more
information read [docs.pytest.com] for the latest documentation.

[docs.pytest.com]: https://docs.pytest.org/

Verbose:

```console
$ env PYTEST_ADDOPTS="-verbose" make start
```

Drop into `pdb` on first error:

```console
$ env PYTEST_ADDOPTS="-x -s --pdb" make start
```

If you have [ipython] installed:

```console
$ env PYTEST_ADDOPTS="--pdbcls=IPython.terminal.debugger:TerminalPdb" \
    make start
```

[ipython]: https://ipython.org/

### Documentation

[sphinx] is used for documentation generation. In the future this may change to
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
$ make start
```

If doing css adjustments:

```console
$ make design
```

[sphinx-autobuild]: https://github.com/executablebooks/sphinx-autobuild

Rebuild docs on file change (requires [entr(1)]):

```console
$ cd docs
```

```console
$ make dev
```

If not GNU Make / no -J support, use two terminals:

```console
$ make watch
```

```console
$ make serve
```

#### Manual (just the command, please)

```console
$ cd docs
```

Build:

```console
$ make html
```

Launch server:

```console
$ make serve
```

## Linting

### black

[black] is used for formatting.

````{tab} Command

poetry:

```console
$ poetry run black .
```

If you setup manually:

```console
$ black .
```

````

````{tab} make

```console
$ make black
```

````

In the future, `ruff` (below) may replace black as formatter.

### ruff

The project uses [ruff] to handles formatting, sorting imports and linting.

````{tab} Command

poetry:

```console
$ poetry run ruff
```

If you setup manually:

```console
$ ruff .
```

````

````{tab} make

```console
$ make ruff
```

````

````{tab} Watch

```console
$ make watch_ruff
```

requires [`entr(1)`].

````

````{tab} Fix files

poetry:

```console
$ poetry run ruff . --fix
```

If you setup manually:

```console
$ ruff . --fix
```

````

### mypy

[mypy] is used for static type checking.

````{tab} Command

poetry:

```console
$ poetry run mypy .
```

If you setup manually:

```console
$ mypy .
```

````

````{tab} make

```console
$ make mypy
```

````

````{tab} Watch

```console
$ make watch_mypy
```

requires [`entr(1)`].
````

````{tab} Configuration

See `[tool.mypy]` in pyproject.toml.

```{literalinclude} ../pyproject.toml
:language: toml
:start-at: "[tool.mypy]"
:end-before: "[tool"

```

````

## Publishing to PyPI

[poetry] handles virtualenv creation, package requirements, versioning,
building, and publishing. Therefore there is no setup.py or requirements files.

Update `__version__` in `__about__.py` and `pyproject.toml`::

    git commit -m 'build(vcspull): Tag v0.1.1'
    git tag v0.1.1
    git push
    git push --tags
    poetry build
    poetry publish

[poetry]: https://python-poetry.org/
[entr(1)]: http://eradman.com/entrproject/
[`entr(1)`]: http://eradman.com/entrproject/
[black]: https://github.com/psf/black
[ruff]: https://ruff.rs
[mypy]: http://mypy-lang.org/
