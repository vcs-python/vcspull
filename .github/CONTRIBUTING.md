# Contributing

Thanks for looking. A bug report with a reproduction, or a pull request that
fixes a verified problem, is the most useful contribution right now. Discuss
a substantial change via an issue before making it.

How this project writes prose — README, `CHANGES`, release notes, commit
messages, docstrings, and source comments — is set out separately in
[WRITING.md](WRITING.md). Read that before changing any of it. The constraints
every change is held to, and the map of what is where, are in
[AGENTS.md](../AGENTS.md).

## Getting set up

Install [git](https://git-scm.com/) and
[uv](https://docs.astral.sh/uv/getting-started/installation/), clone the
repository, then install the dependency groups:

```console
$ uv sync --all-extras --dev
```

## The gates

CI is the order of record; every gate it runs has to pass before a change is
done (see `.github/workflows/tests.yml`).

Format:

```console
$ uv run ruff format .
```

Lint:

```console
$ uv run ruff check . --fix --show-fixes
```

Type-check:

```console
$ uv run mypy .
```

`mypy` runs in strict mode (`[tool.mypy]` in `pyproject.toml`).

Test:

```console
$ uv run py.test
```

Documentation is a gate, not a courtesy. Doctests under `src/vcspull`,
`docs/_ext`, and `scripts` are executed by `pytest`; `vcspull …` commands
shown in `docs/*.md` and in the CLI's help text are checked against the real
argument parser by the same test run. `README.md` is verified by neither
mechanism and stays honest by hand. Which check applies to which file, and
the one edit that silently deletes a doctest, are in
[WRITING.md](WRITING.md#documented-examples-that-run).

Before claiming a test or a gate works, show it failing. A gate that has
never been red is an assumption.

### Imports and typing

- `from __future__ import annotations` at the top of every file — `ruff`'s
  isort configuration (`required-imports` in `[tool.ruff.lint.isort]`)
  enforces this; a missing one is a lint failure, not a style note.
- Namespace imports for the standard library: `import pathlib`, not
  `from pathlib import Path`. Third-party packages may use idiomatic
  `from X import Y` imports.
- `import typing as t`, accessed via the namespace: `t.NamedTuple`,
  `t.TYPE_CHECKING`, and so on.

Docstring conventions (NumPy style, doctest requirements) are in
[WRITING.md](WRITING.md#docstrings) — they are prose policy, not a workflow
step.

## Tests

Tests are written as standalone functions (`test_*`), not grouped into
`class TestFoo:` blocks — use descriptive function names and file
organization instead. This applies to pytest tests, not doctests.

**libvcs fixtures.** The suite leans on libvcs's pytest plugin:
`create_git_remote_repo`, `create_svn_remote_repo`, `create_hg_remote_repo`
(factory fixtures), `git_repo`, `svn_repo`, `hg_repo` (pre-made repository
instances), and `set_home`, `gitconfig`, `hgconfig`, `git_commit_envvars`
(environment fixtures). Reach for these before writing a new one.

**Parametrized CLI tests** use `typing.NamedTuple` fixtures:

```python
class CLIFixture(t.NamedTuple):
    test_id: str
    cli_args: list[str]
    expected_exit_code: int


@pytest.mark.parametrize(
    list(CLIFixture._fields),
    CLI_FIXTURES,
    ids=[test.test_id for test in CLI_FIXTURES],
)
def test_cli_subcommands(...):
    ...
```

**Mocking.** `monkeypatch` for environment variables, globals, and
attributes; `mocker` (from `pytest-mock`) for application code. Document
every mock with a comment explaining what is mocked and why.

**Configuration file tests** go through the project's own helpers —
`vcspull.tests.helpers.write_config` or `save_config_yaml` — rather than a
direct `yaml.dump` or `file.write_text`.

**Logging assertions** read `caplog.records`, not `caplog.text`: scope
capture with `caplog.at_level(logging.DEBUG, logger="vcspull.cli")`, filter
records rather than index by position
(`[r for r in caplog.records if hasattr(r, "vcs_cmd")]`), and assert on the
structured fields (`record.vcs_exit_code == 0`) instead of string-matching
the rendered message. `caplog.record_tuples` cannot see `extra` fields — use
`caplog.records`.

**Runtime dependency smoke test.** Verifies the published wheel runs without
the dev/test extras by importing every `vcspull` module and exercising each
CLI subcommand with `--help` in an isolated environment:

```console
$ uvx \
    --isolated \
    --no-cache \
    --from . \
    python scripts/runtime_dep_smoketest.py
```

The same check has a pytest wrapper behind a dedicated marker, and both are
network-dependent because `uvx` builds the package in an isolated
environment:

```console
$ uv run pytest \
    -m scripts__runtime_dep_smoketest \
    scripts/test_runtime_dep_smoketest.py
```

**Debugging a failing test.** Rerun on every file change with `just start`
(wraps [pytest-watcher](https://github.com/olzhasar/pytest-watcher)). Drop
into `pdb` on the first failure by setting `PYTEST_ADDOPTS`:

```console
$ env PYTEST_ADDOPTS="-x -s --pdb" just start
```

With [ipython](https://ipython.org/) installed, use its debugger instead:

```console
$ env PYTEST_ADDOPTS="--pdbcls=IPython.terminal.debugger:TerminalPdb" \
    just start
```

## Logging conventions

These rules guide new and changed logging code; existing code may not yet
conform.

- `logging.getLogger(__name__)` in every module; a `NullHandler` in library
  `__init__.py` files. Never configure handlers, levels, or formatters in
  library code — that is the application's job. The CLI's own configuration
  is in `vcspull.log.setup_logger`.
- Pass structured context via `extra` rather than folding it into the message
  string. Core keys are stable, scalar, and safe at any level: `vcs_cmd`,
  `vcs_type`, `vcs_url`, `vcs_exit_code`, `vcs_repo_path`,
  `vcspull_config_path`. Treat them as compatibility-sensitive — downstream
  users build dashboards and alerts on them. Heavy keys (`vcs_stdout`,
  `vcs_stderr`, both `list[str]`) are DEBUG-only and should be capped or
  truncated.
- `snake_case`, `vcs_`-prefixed keys; prefer stable scalars over ad-hoc
  objects.
- Lazy formatting: `logger.debug("msg %s", val)`, not an f-string. This skips
  the interpolation entirely when the level is filtered, and keeps
  aggregator grouping intact (an f-string makes every call site a unique
  message). Guard an expensive `val` with
  `if logger.isEnabledFor(logging.DEBUG)`.
- Increment `stacklevel` for each wrapper layer so `%(filename)s:%(lineno)d`
  and OTel's `code.filepath` point at the real caller; re-check whenever call
  depth changes.
- For an object with stable identity (a repository, a remote, a sync run),
  use `LoggerAdapter` instead of repeating the same `extra` on every call.
- Level by audience, not severity of code path:

  | Level | Use for | Examples |
  | ----- | ------- | -------- |
  | `DEBUG` | Internal mechanics, VCS I/O | VCS command + stdout, URL parsing steps |
  | `INFO` | Repository lifecycle, user-visible operations | Repository cloned, sync completed |
  | `WARNING` | Recoverable issues, deprecation, user-actionable config | Deprecated VCS option, unrecognized remote |
  | `ERROR` | Failures that stop an operation | VCS command failed, invalid URL |

  Config discovery noise belongs in `DEBUG`; only a surprising or
  user-actionable config issue rises to `WARNING`.
- `logger.exception()` only inside an `except` block you are not
  re-raising from. `logger.error(..., exc_info=True)` when the traceback is
  needed outside an `except` block. Avoid `logger.exception()` followed by
  `raise` — it duplicates the traceback.
- Avoid: f-strings/`.format()` in log calls; unguarded logging in hot loops;
  catch-log-reraise without adding context; `print()` for diagnostics;
  logging a secret env var's value (log the key name only); non-scalar
  ad-hoc objects in `extra`; requiring custom `extra` fields in a format
  string without a safe default (a missing key raises `KeyError`).

Message wording — lowercase, past tense, no trailing punctuation — and the
stdout/stderr split are prose policy, not a workflow step:
[WRITING.md](WRITING.md#cli-output-and-error-messages).

## Documentation

[Sphinx](https://www.sphinx-doc.org/) generates the documentation. Build it:

```console
$ just build-docs
```

Preview with live reload while editing:

```console
$ cd docs
```

```console
$ just start
```

`just build-docs` is also the only check that catches a broken MyST
cross-reference — build the docs before committing a change under `docs/`.
See [MyST roles](WRITING.md#markdown-and-cross-references) for the role and
anchor conventions the build enforces.

## Releasing

Never create tags. Never push tags. The owner handles tagging and tag
pushes, because a tag triggers the publish workflow. See
[Release commits](WRITING.md#release-commits).

1. Update `CHANGES`: add the `## vcspull vX.Y.Z (YYYY-MM-DD)` header below
   the unreleased placeholder's `END PLACEHOLDER` marker.
2. Bump `version` in `pyproject.toml` and `__version__` in
   `src/vcspull/__about__.py` — both are hardcoded and must match; neither is
   derived from the other.
3. Commit the bump, then create a signed tag: `git tag -s v<version>`.
4. Push the branch, then push the tag: `git push --tags`.

Pushing the tag is what starts the release: `.github/workflows/tests.yml`'s
`release` job runs on `push` to a `refs/tags/*` ref, builds the package, and
publishes it to PyPI via trusted publishing. There is no separate manual
`uv build` / `uv publish` step.

## Pull requests

One subject per pull request. Unrelated cleanup found along the way belongs
in its own commit, and usually in its own pull request.

Discuss a substantial change via an issue before making it.

Commit format is in [WRITING.md](WRITING.md#commits).

You may merge the pull request once you have the sign-off of one other
developer. If you do not have permission to do that, request a reviewer to
merge it for you.

## Decorum

- Participants will be tolerant of opposing views.
- Participants must ensure that their language and actions are free of
  personal attacks and disparaging personal remarks.
- When interpreting the words and actions of others, participants should
  always assume good intentions.
- Behaviour which can be reasonably considered harassment will not be
  tolerated.

Based on [Ruby's Community Conduct Guideline](https://www.ruby-lang.org/en/conduct/).

## Security

Please do not open a public issue for a vulnerability. Report it privately
through the repository's
[Security tab](https://github.com/vcs-python/vcspull/security/advisories/new)
on GitHub.
