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
cli/add(feat[add_repo]) Add support for custom remote URLs

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

**One command per code block.** This makes commands individually copyable.

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

## Debugging Tips

When stuck in debugging loops:

1. **Pause and acknowledge the loop**
2. **Minimize to MVP**: Remove all debugging cruft and experimental code
3. **Document the issue** comprehensively for a fresh approach
4. Format for portability (using quadruple backticks)
