# VCSPull Package Structure

This document outlines the structure of the modernized VCSPull package.

## Directory Structure

```
src/vcspull/
├── __about__.py       # Package metadata
├── __init__.py        # Package initialization
├── _internal/         # Internal utilities
│   ├── __init__.py
│   └── logger.py      # Logging utilities
├── cli/               # Command-line interface
│   ├── __init__.py
│   └── commands.py    # CLI command implementations
├── config/            # Configuration handling
│   ├── __init__.py
│   ├── loader.py      # Configuration loading functions
│   └── models.py      # Configuration models
└── vcs/               # Version control system interfaces
    ├── __init__.py
    ├── base.py        # Base VCS interface
    ├── git.py         # Git implementation
    ├── mercurial.py   # Mercurial implementation
    └── svn.py         # Subversion implementation
```

## Module Responsibilities

### Configuration (`config/`)

- **models.py**: Defines Pydantic models for configuration
- **loader.py**: Provides functions for loading and resolving configuration files

### Version Control Systems (`vcs/`)

- **base.py**: Defines the abstract interface for VCS operations
- **git.py**, **mercurial.py**, **svn.py**: Implementations for specific VCS types

### Command-line Interface (`cli/`)

- **commands.py**: Implements CLI commands and argument parsing

### Internal Utilities (`_internal/`)

- **logger.py**: Logging utilities for the package

## Configuration Format

VCSPull uses a YAML or JSON configuration format with the following structure:

```yaml
settings:
  sync_remotes: true
  default_vcs: git
  depth: 1

repositories:
  - name: example-repo
    url: https://github.com/user/repo.git
    path: ~/code/repo
    vcs: git
    rev: main
    remotes:
      upstream: https://github.com/upstream/repo.git
    web_url: https://github.com/user/repo

includes:
  - ~/other-config.yaml
```

## Usage

```python
from vcspull import load_config

# Load configuration
config = load_config("~/.config/vcspull/vcspull.yaml")

# Access repositories
for repo in config.repositories:
    print(f"{repo.name}: {repo.url} -> {repo.path}")
```

## Implemented Features

The following features have been implemented according to the modernization plan:

1. **Configuration Format & Structure**
   - Defined Pydantic v2 models for configuration
   - Implemented comprehensive validation logic
   - Created configuration loading functions
   - Added include resolution logic
   - Implemented configuration merging functions

2. **Validation System**
   - Migrated all validation to Pydantic v2 models
   - Used Pydantic's built-in validation capabilities
   - Created clear type aliases
   - Implemented path expansion and normalization

3. **Testing System**
   - Reorganized tests to mirror source code structure
   - Created separate unit test directories
   - Implemented test fixtures for configuration files

4. **Internal APIs**
   - Reorganized codebase according to proposed structure
   - Separated public and private API components
   - Created logical module organization
   - Standardized function signatures
   - Implemented clear parameter and return types
   - Added comprehensive docstrings with type information

5. **External APIs**
   - Created dedicated API module
   - Implemented load_config function
   - Defined public interfaces

6. **CLI System**
   - Implemented basic CLI commands
   - Added configuration handling in CLI
   - Created command structure

## Next Steps

The following features are planned for future implementation:

1. **VCS Operations**
   - Implement full synchronization logic
   - Add support for remote management
   - Implement revision locking

2. **CLI Enhancements**
   - Add progress reporting
   - Implement rich output formatting
   - Add repository detection command

3. **Documentation**
   - Generate JSON schema documentation
   - Create example configuration files
   - Update user documentation with new format 