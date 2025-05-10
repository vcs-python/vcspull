# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

vcspull is a Python tool for managing and synchronizing multiple git, svn, and mercurial repositories via YAML or JSON configuration files. It allows users to pull/update multiple repositories in a single command, optionally filtering by repository name, path, or VCS URL.

## Development Environment

### Setup and Installation

```bash
# Install development dependencies with uv
uv pip install -e .
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
make start

# Run tests with coverage
uv run py.test --cov -v
```

#### Code Quality

```bash
# Format code with ruff
uv run ruff format .
# or
make ruff_format

# Run ruff linting with auto-fixes
uv run ruff check . --fix --show-fixes
# or
make ruff

# Run mypy type checking
uv run mypy
# or
make mypy

# Watch mode for linting (using entr)
make watch_ruff
make watch_mypy
```

#### Documentation

```bash
# Build documentation
make build_docs

# Start documentation server (auto-reload)
make start_docs
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
   - `cli/add_from_fs.py`: Scanning filesystem for repositories

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

- Use namespace imports: `import enum` instead of `from enum import Enum`
- For typing, use `import typing as t` and access via namespace: `t.NamedTuple`, etc.
- Use `from __future__ import annotations` at the top of all Python files

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

### Testing

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

#### Test Structure

Use `typing.NamedTuple` for parameterized tests:

```python
class SyncFixture(t.NamedTuple):
    test_id: str  # For test naming
    sync_args: list[str]
    expected_exit_code: int
    expected_in_out: ExpectedOutput = None

@pytest.mark.parametrize(
    list(SyncFixture._fields),
    SYNC_REPO_FIXTURES,
    ids=[test.test_id for test in SYNC_REPO_FIXTURES],
)
def test_sync(
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
Component/File(commit-type[Subcomponent/method]): Concise description

why: Explanation of necessity or impact.
what:
- Specific technical changes made
- Focused on a single topic

refs: #issue-number, breaking changes, or relevant links
```

Common commit types:
- **feat**: New features or enhancements
- **fix**: Bug fixes
- **refactor**: Code restructuring without functional change
- **docs**: Documentation updates
- **chore**: Maintenance (dependencies, tooling, config)
- **test**: Test-related updates
- **style**: Code style and formatting

Example:
```
cli/add(feat[add_repo]): Add support for custom remote URLs

why: Enable users to specify alternative remote URLs for repositories
what:
- Add remote_url parameter to add_repo function
- Update CLI argument parser to accept --remote-url option
- Add tests for the new functionality

refs: #123
```

## Debugging Tips

When stuck in debugging loops:

1. **Pause and acknowledge the loop**
2. **Minimize to MVP**: Remove all debugging cruft and experimental code
3. **Document the issue** comprehensively for a fresh approach
4. Format for portability (using quadruple backticks)