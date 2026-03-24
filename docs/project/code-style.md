(code-style)=

# Code Style

## Formatting and linting

vcspull uses [ruff](https://docs.astral.sh/ruff/) for formatting and linting.

```console
$ uv run ruff format .
```

```console
$ uv run ruff check . --fix --show-fixes
```

## Type checking

[mypy](https://mypy-lang.org/) runs in strict mode.

```console
$ uv run mypy
```

## Docstrings

Follow [NumPy docstring convention](https://numpydoc.readthedocs.io/en/latest/format.html).

## Imports

- Use `from __future__ import annotations` in every file.
- Prefer namespace imports for stdlib: `import pathlib` not `from pathlib import Path`.
- Use `import typing as t` and access via `t.NamedTuple`, `t.TYPE_CHECKING`, etc.
