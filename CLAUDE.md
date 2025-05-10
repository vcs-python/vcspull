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
```

#### Code Quality

```bash
# Format code with ruff
uv run ruff format .
# or
make ruff_format

# Run ruff linting
uv run ruff check .
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

### Testing

Tests use pytest and are organized by component functionality:
- `tests/test_cli.py`: Tests for CLI functionality
- `tests/test_config.py`: Tests for configuration parsing
- `tests/test_sync.py`: Tests for repository synchronization

## Best Practices

1. **Types**: The codebase uses strict typing with mypy. All new code should include proper type annotations.

2. **Docstrings**: The project follows NumPy docstring style for all functions and methods.

3. **Error Handling**: Exceptions are defined in `exc.py`. Use appropriate exception types.

4. **Testing Approach**: 
   - Tests use fixtures extensively (see `conftest.py` and `tests/fixtures/`)
   - CLI tests use parameter fixtures with clear IDs for readability