# AGENTS.md

This file provides guidance to LLM Agents such as Codex, Gemini, Claude Code (claude.ai/code), etc. when working with code in this repository.

## CRITICAL REQUIREMENTS

### Test Success
- ALL tests MUST pass for code to be considered complete and working
- Never describe code as "working as expected" if there are ANY failing tests
- Even if specific feature tests pass, failing tests elsewhere indicate broken functionality
- Changes that break existing tests must be fixed before considering implementation complete
- A successful implementation must pass linting, type checking, AND all existing tests

## Project Overview

vcspull is a Python tool for managing and synchronizing multiple git, svn, and mercurial repositories via YAML or JSON configuration files. It allows users to pull/update multiple repositories in a single command, optionally filtering by repository name, path, or VCS URL.

## Development Environment

### Setup and Installation

```bash
# Install development dependencies with uv
uv pip install -e .

# Alternative: Use uv sync to install from pyproject.toml
uv sync
```

### Common Commands

#### Testing

```bash
# Run all tests
uv run pytest

# Run specific test(s)
uv run pytest tests/test_cli.py
uv run pytest tests/test_cli.py::test_sync

# Watch mode for tests (auto re-run on file changes)
uv run ptw .
# or
just start

# Run tests with coverage
uv run py.test --cov -v
```

#### Code Quality

```bash
# Format code with ruff
uv run ruff format .
# or
just ruff-format

# Run ruff linting with auto-fixes
uv run ruff check . --fix --show-fixes
# or
just ruff

# Run mypy type checking
uv run mypy
# or
just mypy

# Watch mode for linting (using entr)
just watch-ruff
just watch-mypy
```

#### Documentation

```bash
# Build documentation
just build-docs

# Start documentation server (auto-reload)
just start-docs
```

## Development Process

Follow this workflow for code changes:

1. **Format First**: `uv run ruff format .`
2. **Run Tests**: `uv run py.test`
3. **Run Linting**: `uv run ruff check . --fix --show-fixes`
4. **Check Types**: `uv run mypy`
5. **Verify Tests Again**: `uv run py.test`

## Code Architecture

### Core Components

1. **Configuration**
   - `config.py`: Handles loading and parsing of YAML/JSON configuration files
   - `_internal/config_reader.py`: Low-level config file reading

2. **CLI**
   - `cli/__init__.py`: Main CLI entry point with argument parsing
   - `cli/sync.py`: Repository synchronization functionality
   - `cli/add.py`: Adding new repositories to configuration

3. **Repository Management**
   - Uses `libvcs` package for VCS operations (git, svn, hg)
   - Supports custom remotes and URL schemes

### Configuration Format

Configuration files are stored as YAML or JSON in either:
- `~/.vcspull.yaml`/`.json` (home directory)
- `~/.config/vcspull/` directory (XDG config)

Example format:
```yaml
~/code/:
  flask: "git+https://github.com/mitsuhiko/flask.git"
~/study/c:
  awesome: "git+git://git.naquadah.org/awesome.git"
```

## Coding Standards

### Imports

- Use namespace imports for stdlib: `import enum` instead of `from enum import Enum`; third-party packages may use `from X import Y`
- For typing, use `import typing as t` and access via namespace: `t.NamedTuple`, etc.

**For third-party packages:** Use idiomatic import styles for each library (e.g., `from pygments.token import Token` is fine).

**Always:** Use `from __future__ import annotations` at the top of all Python files.

### Docstrings

Follow NumPy docstring style for all functions and methods:

```python
"""Short description of the function or class.

Detailed description using reStructuredText format.

Parameters
----------
param1 : type
    Description of param1
param2 : type
    Description of param2

Returns
-------
type
    Description of return value
"""
```

### Doctests

**All functions and methods MUST have working doctests.** Doctests serve as both documentation and tests.

**CRITICAL RULES:**
- Doctests MUST actually execute - never comment out function calls or similar
- Doctests MUST NOT be converted to `.. code-block::` as a workaround (code-blocks don't run)
- If you cannot create a working doctest, **STOP and ask for help**

**Available tools for doctests:**
- `doctest_namespace` fixtures (inherited from libvcs): `tmp_path`, `create_git_remote_repo`, `create_hg_remote_repo`, `create_svn_remote_repo`
- Ellipsis for variable output: `# doctest: +ELLIPSIS`
- Update `conftest.py` to add new fixtures to `doctest_namespace`

**`# doctest: +SKIP` is NOT permitted** - it's just another workaround that doesn't test anything. If a VCS binary might not be installed, pytest already handles skipping via `skip_if_binaries_missing`. Use the fixtures properly.

**Using fixtures in doctests:**
```python
>>> from vcspull.config import extract_repos
>>> config = {'~/code/': {'myrepo': 'git+https://github.com/user/repo'}}
>>> repos = extract_repos(config)  # doctest: +ELLIPSIS
>>> len(repos)
1
```

**When output varies, use ellipsis:**
```python
>>> repo_dir = tmp_path / 'repo'  # tmp_path from doctest_namespace
>>> repo_dir.mkdir()
>>> repo_dir  # doctest: +ELLIPSIS
PosixPath('.../repo')
```

### Logging Standards

These rules guide future logging changes; existing code may not yet conform.

#### Logger setup

- Use `logging.getLogger(__name__)` in every module
- Add `NullHandler` in library `__init__.py` files
- Never configure handlers, levels, or formatters in library code — that's the application's job

#### Structured context via `extra`

Pass structured data on every log call where useful for filtering, searching, or test assertions.

**Core keys** (stable, scalar, safe at any log level):

| Key | Type | Context |
|-----|------|---------|
| `vcs_cmd` | `str` | VCS command line |
| `vcs_type` | `str` | VCS type (git, svn, hg) |
| `vcs_url` | `str` | repository URL |
| `vcs_exit_code` | `int` | VCS process exit code |
| `vcs_repo_path` | `str` | local repository path |
| `vcspull_config_path` | `str` | workspace config file path |

**Heavy/optional keys** (DEBUG only, potentially large):

| Key | Type | Context |
|-----|------|---------|
| `vcs_stdout` | `list[str]` | VCS stdout lines (truncate or cap; `%(vcs_stdout)s` produces repr) |
| `vcs_stderr` | `list[str]` | VCS stderr lines (same caveats) |

Treat established keys as compatibility-sensitive — downstream users may build dashboards and alerts on them. Change deliberately.

#### Key naming rules

- `snake_case`, not dotted; `vcs_` prefix
- Prefer stable scalars; avoid ad-hoc objects
- Heavy keys (`vcs_stdout`, `vcs_stderr`) are DEBUG-only; consider companion `vcs_stdout_len` fields or hard truncation (e.g. `stdout[:100]`)

#### Lazy formatting

`logger.debug("msg %s", val)` not f-strings. Two rationales:
- Deferred string interpolation: skipped entirely when level is filtered
- Aggregator message template grouping: `"Running %s"` is one signature grouped ×10,000; f-strings make each line unique

When computing `val` itself is expensive, guard with `if logger.isEnabledFor(logging.DEBUG)`.

#### stacklevel for wrappers

Increment for each wrapper layer so `%(filename)s:%(lineno)d` and OTel `code.filepath` point to the real caller. Verify whenever call depth changes.

#### LoggerAdapter for persistent context

For objects with stable identity (Repository, Remote, Sync), use `LoggerAdapter` to avoid repeating the same `extra` on every call. Lead with the portable pattern (override `process()` to merge); `merge_extra=True` simplifies this on Python 3.13+.

#### Log levels

| Level | Use for | Examples |
|-------|---------|----------|
| `DEBUG` | Internal mechanics, VCS I/O | VCS command + stdout, URL parsing steps |
| `INFO` | Repository lifecycle, user-visible operations | Repository cloned, sync completed |
| `WARNING` | Recoverable issues, deprecation, user-actionable config | Deprecated VCS option, unrecognized remote |
| `ERROR` | Failures that stop an operation | VCS command failed, invalid URL |

Config discovery noise belongs in `DEBUG`; only surprising/user-actionable config issues → `WARNING`.

#### Message style

- Lowercase, past tense for events: `"repository cloned"`, `"vcs command failed"`
- No trailing punctuation
- Keep messages short; put details in `extra`, not the message string

#### Exception logging

- Use `logger.exception()` only inside `except` blocks when you are **not** re-raising
- Use `logger.error(..., exc_info=True)` when you need the traceback outside an `except` block
- Avoid `logger.exception()` followed by `raise` — this duplicates the traceback. Either add context via `extra` that would otherwise be lost, or let the exception propagate

#### Testing logs

Assert on `caplog.records` attributes, not string matching on `caplog.text`:
- Scope capture: `caplog.at_level(logging.DEBUG, logger="vcspull.cli")`
- Filter records rather than index by position: `[r for r in caplog.records if hasattr(r, "vcs_cmd")]`
- Assert on schema: `record.vcs_exit_code == 0` not `"exit code 0" in caplog.text`
- `caplog.record_tuples` cannot access extra fields — always use `caplog.records`

#### Avoid

- f-strings/`.format()` in log calls
- Unguarded logging in hot loops (guard with `isEnabledFor()`)
- Catch-log-reraise without adding new context
- `print()` for diagnostics
- Logging secret env var values (log key names only)
- Non-scalar ad-hoc objects in `extra`
- Requiring custom `extra` fields in format strings without safe defaults (missing keys raise `KeyError`)

### Testing

**Use functional tests only**: Write tests as standalone functions (`test_*`), not classes. Avoid `class TestFoo:` groupings - use descriptive function names and file organization instead. This applies to pytest tests, not doctests.

#### Using libvcs Fixtures

When writing tests, leverage libvcs's pytest plugin fixtures:

- `create_git_remote_repo`, `create_svn_remote_repo`, `create_hg_remote_repo`: Factory fixtures
- `git_repo`, `svn_repo`, `hg_repo`: Pre-made repository instances
- `set_home`, `gitconfig`, `hgconfig`, `git_commit_envvars`: Environment fixtures

Example:
```python
def test_vcspull_sync(git_repo):
    # git_repo is already a GitSync instance with a clean repository
    # Use it directly in your tests
```
#### Release commits

Never create tags. Never push tags. The user handles tagging and tag
pushes (tags trigger the CI publish workflow).

Release commit subjects are plain and short: `Tag v<version>`. Put
the detailed why/what in the commit body. Don't use the
`Scope(type[detail]):` format for releases — don't bury the lede.

For multi-line commits, use heredoc to preserve formatting:
```bash
git commit -m "$(cat <<'EOF'
feat(Component[method]) add feature description

why: Explanation of the change.

what:
- First change
- Second change
EOF
)"
```

#### Test Structure

Use `typing.NamedTuple` for parameterized tests:

```python
class CLIFixture(t.NamedTuple):
    test_id: str  # For test naming
    cli_args: list[str]
    expected_exit_code: int
    expected_in_out: ExpectedOutput = None

@pytest.mark.parametrize(
    list(CLIFixture._fields),
    CLI_FIXTURES,
    ids=[test.test_id for test in CLI_FIXTURES],
)
def test_cli_subcommands(
    # Parameters and fixtures...
):
    # Test implementation
```

#### Mocking Strategy

- Use `monkeypatch` for environment, globals, attributes
- Use `mocker` (from pytest-mock) for application code
- Document every mock with comments explaining WHAT is being mocked and WHY

#### Configuration File Testing

- Use project helper functions like `vcspull.tests.helpers.write_config` or `save_config_yaml`
- Avoid direct `yaml.dump` or `file.write_text` for config creation

### Git Commit Standards

Format commit messages as:
```
Scope(type[detail]): concise description

why: Explanation of necessity or impact.

what:
- Specific technical changes made
- Focused on a single topic
```

Keep the subject ≤50 chars (excluding any trailing `(#NN)` PR ref); wrap
body lines at ≤72 chars. Separate the `why:` and `what:` blocks with a
blank line.

The `why:` must be the pragmatic, contextual reason behind the change — never cite AGENTS.md, CLAUDE.md, or other rule files as the justification. If you feel compelled to write "AGENTS.md says..." or "CLAUDE.md requires...", look at `git log -n 10 -p`, the PR description, and the ticket for the real engineering reason (e.g., "function had no doctest coverage" not "CLAUDE.md requires doctests").

Common commit types:
- **feat**: New features or enhancements
- **fix**: Bug fixes
- **refactor**: Code restructuring without functional change
- **docs**: Documentation updates
- **chore**: Maintenance (dependencies, tooling, config)
- **test**: Test-related updates
- **style**: Code style and formatting
- **ai(rules[AGENTS])**: AI rule updates
- **ai(claude[rules])**: Claude Code rules (CLAUDE.md)
- **ai(claude[command])**: Claude Code command changes

Examples:
```
cli(add[repo]) Add support for custom remote URLs

why: Enable users to specify alternative remote URLs for repositories

what:
- Add remote_url parameter to add_repo function
- Update CLI argument parser to accept --remote-url option
- Add tests for the new functionality
```

For docs/_ext changes, use `docs` as the top-level component:
```
docs(sphinx_argparse_neo[renderer]) Escape asterisks in quoted strings

why: Glob patterns like "django-*" cause RST emphasis issues

what:
- Add _escape_glob_asterisks() helper method
- Call it before RST parsing in _parse_text()
```

## Documentation Standards

### Code Blocks in Documentation

When writing documentation (README, CHANGES, docs/), follow these rules for code blocks:

**One command per code block.** This makes commands individually copyable. For sequential commands, either use separate code blocks or chain them with `&&` or `;` and `\` continuations (keeping it one logical command).

**Put explanations outside the code block**, not as comments inside.

Good:

Search for a term across all fields:

```console
$ vcspull search django
```

Search by repository name:

```console
$ vcspull search "name:flask"
```

Bad:

```console
# Search for a term across all fields
$ vcspull search django

# Search by repository name
$ vcspull search "name:flask"
```

### Shell Command Formatting

These rules apply to shell commands in documentation (README, CHANGES, docs/), **not** to Python doctests.

**Use `console` language tag with `$ ` prefix.** This distinguishes interactive commands from scripts and enables prompt-aware copy in many terminals.

Good:

```console
$ uv run pytest
```

Bad:

```bash
uv run pytest
```

**Split long commands with `\` for readability.** Each flag or flag+value pair gets its own continuation line, indented. Positional parameters go on the final line.

Good:

```console
$ pipx install \
    --suffix=@next \
    --pip-args '\--pre' \
    --force \
    'vcspull'
```

Bad:

```console
$ pipx install --suffix=@next --pip-args '\--pre' --force 'vcspull'
```

**Prefer longform flags** — use `--workspace` not `-w`, `--file` not `-f`.

**Split multi-flag commands** — when a command has 2+ flags/options, place each on its own `\`-continuation line, indented by 4 spaces.

Good:

```console
$ vcspull import gh my-org \
    --mode org \
    --workspace ~/code/
```

Bad:

```console
$ vcspull import gh my-org --mode org -w ~/code/
```

### Changelog Conventions

These rules apply when authoring entries in `CHANGES`, which is rendered as the Sphinx changelog page. Modeled on Django's release-notes shape — deliverables get titles and prose, not bullets. Older entries used a flat `### Section` + bullet shape; new entries follow the Django shape below.

**Release entry boilerplate.** Every release header is `## vcspull vX.Y.Z (YYYY-MM-DD)` (note the `v` prefix on the version). The file opens with a `## vcspull vX.Y.Z (unreleased)` placeholder block fenced by `<!-- KEEP THIS PLACEHOLDER ... -->` and `<!-- END PLACEHOLDER ... -->` HTML comments — new release entries land immediately below the END marker, never above it.

**Open with a multi-sentence lead paragraph.** Plain prose, no italic. Open with the version as sentence subject (*"vcspull vX.Y.Z ships …"*) so the lead is self-contained when excerpted. Two to four sentences telling the reader what shipped and who cares — user-visible takeaways, not internal mechanism. Cross-reference detail docs with `{ref}` to keep the lead compact.

**Lead paragraphs are release-time material — off-limits to branches and PRs.** The unreleased entry carries no lead paragraph and no version summary: sections only (`### Breaking changes`, `### What's new` deliverables, `### Fixes`, …). Speaking for the release — what the version "is", "ships", or "focuses on" — is presumptuous before its scope is final; only the person cutting the release writes that, and only when the user explicitly asks to release. Never write or edit a lead from a feature branch, and never ask or imply that a release should happen.

**Each deliverable is a section, not a bullet.** Inside `### What's new`, every distinct deliverable gets a `#### Deliverable title (#NN)` heading naming it in user vocabulary, followed by 1-3 prose paragraphs explaining what shipped. Don't wrap a paragraph in `- ` — bullets are for enumerable lists, not paragraph containers. Cross-link detail docs (`See {ref}\`foo\` for details.`) so prose stays focused.

**The deliverable test.** Before writing an entry, ask: "What's the deliverable, in user vocabulary?" If you can't answer in one sentence, the entry isn't ready. Mechanism (helper internals, byte counters, schema-validation locations) belongs in PR descriptions and code comments, not the changelog.

**Fixed subheadings**, in this order when present: `### Breaking changes`, `### Dependencies`, `### What's new`, `### Fixes`, `### Documentation`, `### Development`. Dev tooling (helper scripts, internal automation) lives under `### Development`. For breaking changes, show the migration path with concrete inline code (e.g. a `# Before` / `# After` fenced code block). Dependency floor bumps use the form ``Minimum `pkg>=X.Y.Z` (was `>=X.Y.W`)``.

**PR refs `(#NN)`** sit in each deliverable's `####` heading.

**When bullets are appropriate.** Catch-all sections (`### Fixes`, occasionally `### Documentation`) with 3+ genuinely small items use bullets — one line each, never paragraphs. If a bullet swells past two lines, promote it to a `#### Title (#NN)` heading with prose body.

**Anti-patterns.**

- Fragile metrics: token ceilings, third-party version pins, percent benchmarks, exact byte counts. Describe the *capability*, not the math.
- Internal jargon: private symbols (leading-underscore identifiers), algorithm names exposed for the first time, backend scaffolding.
- Walls of text dressed up as bullets.
- Buried breaking changes — they get their own subheading at the top of the entry.

**Always link autodoc'd APIs.** Any class, method, function, exception, or attribute that has its own rendered page must be cited via the appropriate role (`{class}`, `{meth}`, `{func}`, `{exc}`, `{attr}`) — never with plain backticks. Doc pages without explicit ref labels use `{doc}`. Plain backticks are correct for code syntax, env vars, parameter names, and file paths that aren't doc pages — anything without an autodoc destination.

**MyST roles.** Class references use `{class}` (e.g. `{class}\`~vcspull.config.ConfigReader\``), methods use `{meth}`, functions use `{func}`, exceptions use `{exc}`, attributes use `{attr}`, internal anchors use `{ref}`, doc-path links use `{doc}`.

**Summarization style.** When a user asks "what changed in the latest version?" or similar, lead with the entry's lead paragraph (paraphrased if needed), followed by each `####` deliverable heading under `### What's new` with a one-sentence summary. Cite `(#NN)` only if the user asks for source links. Don't invent versions, dates, or numbers not present in `CHANGES`. Don't quote line numbers or file offsets — those shift as the file evolves.

## Debugging Tips

When stuck in debugging loops:

1. **Pause and acknowledge the loop**
2. **Minimize to MVP**: Remove all debugging cruft and experimental code
3. **Document the issue** comprehensively for a fresh approach
4. Format for portability (using quadruple backticks)

## AI Slop Prevention

Treat AI slop as **review-hostile noise**, not as proof that text or
code is wrong. The goal is to maximize information density by removing
artifacts that make the repository harder to trust or navigate.

### The Anti-Slop Rubric

Before committing, audit all AI-assisted changes for these noise
patterns:

- **AI Signatures:** Remove "Generated by", footers, conversational
  filler ("Certainly!", "Here is..."), unexplained emojis (🤖, ✨), and
  AI-tool metadata.
- **Brittle References:** Avoid hard-coded line numbers, fragile
  file/test counts, dated "as of" claims, bare SHAs, and local
  absolute paths unless they are strict evidentiary artifacts (e.g.,
  benchmark logs).
- **Diff Narration:** Do not restate what moved, was renamed, or was
  removed in artifacts the downstream reader holds: code, docstrings,
  README, CHANGES, PR descriptions, or release notes. The diff and
  commit message already carry this history.
- **Branch-Internal Narrative:** Do not mention intermediate branch
  states, abandoned approaches, or "no longer" behavior unless users
  of a published release actually experienced the old state (**The
  Published-Release Test**).
- **Low-Value Scaffolding:** Remove ownerless TODOs (`TODO: revisit`),
  unused future-proofing, debug artifacts, and defensive wrappers that
  do not protect a currently reachable failure mode.
- **Prose Inflation:** Replace generic AI "tells" like *comprehensive,
  robust, seamless, production-ready, leverage, delve, tapestry,* and
  *best practices* with concrete descriptions of behavior,
  constraints, or trade-offs.
- **Coded Labels:** Write rules, options, and findings as plain
  imperatives. Don't tag them with codes like `[R1]`, `A1`, or
  `Option B` in artifacts a human reads — the reader shouldn't have to
  decode an index. Internal agent bookkeeping may use ids; shipped text
  may not.

### Preservation & Context

**When unsure, leave the text in place and ask.** Subjective cleanup
must never be a reason to remove load-bearing rationale.

- **Preserve the "Why":** You MUST NOT delete comments that document
  invariants, protocol constraints, platform quirks, security
  boundaries, and upstream workarounds.
- **Evidence is Immune:** Preserve exact counts, dates, and SHAs when
  they serve as evidence in benchmark results, release notes, stack
  traces, or lockfiles.
- **Behavior Over Inventory:** A useful description explains what
  changed for the *system or user*; it does not provide an inventory
  of files or functions the diff already shows.

### The Published-Release Test

Long-running branches accumulate tactical decisions — renames,
refactors, attempts-then-reverts. When deciding what counts as
branch-internal, use trunk or the parent branch as the baseline — not
intermediate states inside the current branch. Ask:

> Did users of the most recently published release ever experience
> this old name, old behavior, or bug?

If the answer is **no**, it is branch-internal narrative. Move it to
the commit message and describe only the final state in the artifact.

**Keep in shipped artifacts:**
- Deprecations and migration guides for symbols that actually shipped.
- `### Fixes` entries for bugs that affected users of a published
  release.
- Comments explaining *why the current code looks this way*
  (invariants, platform quirks) that make sense to a reader who never
  saw the previous version.

### Cleanup in Hindsight

When applying these rules retroactively from inside a feature branch,
first establish scope by diffing against the parent branch (or trunk)
to identify which commits this branch actually introduced. Then:

- **In-branch commits:** Prompt the user with two options: `fixup!`
  commits with `git rebase --autosquash` to address each causal commit
  at its source, or a single cleanup commit at branch tip.
- **Trunk/Parent commits:** Default to leaving them alone. Act only on
  explicit user instruction. If the user opts in, fold the cleanup
  into a single commit at branch tip; do not rewrite shared history.
- **Scope guard:** If cleaning prior slop would touch a colleague's
  work or expand the branch beyond its stated goal, stay in lane:
  protect the current goal and leave prior slop alone.

### Change Discipline

- Make the smallest coherent change that solves the verified problem;
  keep unrelated cleanup out of it.
- Reuse an existing file, component, helper, API, or test before adding
  a new one. Modify in place when the change fits the file's
  responsibility.
- Keep new APIs private until a caller outside the module needs them.
- Add a file only for a durable boundary — a distinct responsibility,
  independent reuse, or splitting an oversized high-touch module — not
  for a single-use helper or a one-line re-export.

### Keep Instructions Lean

Treat this file like code and prune it.

- Delete a line whose removal would not cause a mistake.
- Move multi-step procedures into skills, path-specific rules into
  nested AGENTS.md files, and hard limits into hooks or CI.
- Keep only non-obvious, broadly applicable defaults here. Anything a
  reader can infer from the code, a manifest, or a linter does not
  belong.
