# Development

## Setup the project

Install and [git] and [poetry]. After:

    git clone https://github.com/vcs-python/vcspull.git
    cd vcspull
    poetry install -E "docs test coverage lint format"

[installation documentation]: https://python-poetry.org/docs/#installation
[poetry]: https://python-poetry.org/

## Tests

    poetry run py.test

or:

    make test

## Automatically run tests on file save

via [pytest-watcher] (works out of the box):

    make start

via [entr(1)] (requires installation):

    make watch_test

[pytest-watcher]: https://github.com/olzhasar/pytest-watcher

## Documentation

Default preview server: http://localhost:8022

[sphinx-autobuild] will automatically build the docs, watch for file changes and launch a server.

    cd docs
    make start

If doing css adjustments:

    cd docs
    make design

[sphinx-autobuild]: https://github.com/executablebooks/sphinx-autobuild

### Manual documentation (the hard way)

    cd docs
    make html

To launch in server:

    cd docs
    make serve

Rebuild docs on file change (requires [entr(1)]):

    cd docs
    make watch_docs

Rebuild docs and run server via one terminal: `make dev_docs` (requires above, and a
`make(1)` with `-J` support, e.g. GNU Make)

## Formatting code

The project uses [black] and [isort] (one after the other) and runs [flake8] via
CI. See the configuration in `pyproject.toml` and `setup.cfg`:

Run `black` first, then `isort` to handle import nuances:

    make black isort

[black]: https://github.com/psf/black
[isort]: https://pypi.org/project/isort/
[flake8]: https://flake8.pycqa.org/

## Lint

    make flake8

to watch (requires `entr(1)`)

    make watch_flake8

## Releasing to PyPI

As of 0.10, [poetry] handles virtualenv creation, package requirements, versioning,
building, and publishing. Therefore there is no setup.py or requirements files.

Update `__version__` in `__about__.py` and `pyproject.toml`::

    git commit -m 'build(vcspull): Tag v0.1.1'
    git tag v0.1.1
    git push
    git push --tags
    poetry build
    poetry publish

[entr(1)]: http://eradman.com/entrproject/
