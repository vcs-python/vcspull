# External APIs Proposal

> Defining a clean, user-friendly public API for VCSPull to enable programmatic usage and easier integration with other tools.

## Current Issues

The audit identified several issues with the current external API:

1. **Limited Public API**: No clear definition of what constitutes the public API
2. **Inconsistent Function Signatures**: Public functions have varying parameter styles and return types
3. **Lack of Documentation**: Public interfaces lack comprehensive documentation
4. **No Versioning Strategy**: No clear versioning for the public API to maintain compatibility
5. **No Type Hints**: Incomplete or missing type hints for public interfaces

## Proposed Changes

### 1. Clearly Defined Public API

1. **API Module Structure**:
   ```
   src/vcspull/
   ├── __init__.py               # Public API exports
   ├── api/                      # Dedicated public API module
   │   ├── __init__.py           # API exports
   │   ├── config.py             # Configuration API
   │   ├── repositories.py       # Repository operations API
   │   └── exceptions.py         # Public exceptions
   ```

2. **Public API Declaration**:
   ```python
   # src/vcspull/__init__.py
   """VCSPull - a multiple repository management tool for Git, SVN and Mercurial."""

   from vcspull.api import (
       load_config,
       sync_repositories,
       detect_repositories,
       lock_repositories,
       ConfigurationError,
       RepositoryError,
       VCSError,
   )

   __all__ = [
       "load_config",
       "sync_repositories",
       "detect_repositories",
       "lock_repositories",
       "ConfigurationError",
       "RepositoryError",
       "VCSError",
   ]
   ```

### 2. Configuration API

1. **API for Configuration Operations**:
   ```python
   # src/vcspull/api/config.py
   """Configuration API for VCSPull."""

   from pathlib import Path
   from typing import List, Optional, Union, Dict, Any

   from vcspull.schemas import VCSPullConfig, Repository
   from vcspull.exceptions import ConfigurationError

   def load_config(
       *paths: Union[str, Path], search_home: bool = True
   ) -> VCSPullConfig:
       """Load configuration from specified paths.
       
       Args:
           *paths: Configuration file paths. If not provided, default locations will be searched.
           search_home: Whether to also search for config files in user's home directory.
           
       Returns:
           Validated configuration object.
           
       Raises:
           ConfigurationError: If configuration cannot be loaded or validated.
       """
       # Implementation details

   def save_config(
       config: VCSPullConfig, path: Union[str, Path], format: str = "yaml"
   ) -> None:
       """Save configuration to a file.
       
       Args:
           config: Configuration object to save.
           path: Path to save the configuration to.
           format: Format to save the configuration in (yaml or json).
           
       Raises:
           ConfigurationError: If configuration cannot be saved.
       """
       # Implementation details

   def get_repository(
       config: VCSPullConfig, name_or_path: str
   ) -> Optional[Repository]:
       """Get a repository from the configuration by name or path.
       
       Args:
           config: Configuration object.
           name_or_path: Repository name or path.
           
       Returns:
           Repository if found, None otherwise.
       """
       # Implementation details

   def add_repository(
       config: VCSPullConfig,
       url: str,
       path: Union[str, Path],
       name: Optional[str] = None,
       vcs: Optional[str] = None,
       **kwargs
   ) -> Repository:
       """Add a repository to the configuration.
       
       Args:
           config: Configuration object.
           url: Repository URL.
           path: Repository path.
           name: Repository name (optional, defaults to extracted name from URL).
           vcs: Version control system (optional, defaults to inferred from URL).
           **kwargs: Additional repository options.
           
       Returns:
           Added repository.
           
       Raises:
           ConfigurationError: If repository cannot be added.
       """
       # Implementation details
   ```

### 3. Repository API

1. **API for Repository Operations**:
   ```python
   # src/vcspull/api/repositories.py
   """Repository operations API for VCSPull."""

   from pathlib import Path
   from typing import List, Optional, Union, Dict, Any, Callable

   from vcspull.schemas import Repository, VCSPullConfig
   from vcspull.exceptions import RepositoryError, VCSError

   def sync_repositories(
       config: VCSPullConfig,
       patterns: Optional[List[str]] = None,
       dry_run: bool = False,
       progress_callback: Optional[Callable[[str, int, int], None]] = None
   ) -> Dict[str, Dict[str, Any]]:
       """Synchronize repositories according to configuration.
       
       Args:
           config: Configuration object.
           patterns: Optional list of repository name patterns to filter.
           dry_run: If True, only show what would be done without making changes.
           progress_callback: Optional callback for progress updates.
           
       Returns:
           Dictionary mapping repository names to sync results.
           
       Raises:
           RepositoryError: If repository operations fail.
       """
       # Implementation details

   def detect_repositories(
       directory: Union[str, Path],
       recursive: bool = True,
       include_submodules: bool = False
   ) -> List[Repository]:
       """Detect existing repositories in a directory.
       
       Args:
           directory: Directory to scan for repositories.
           recursive: Whether to recursively scan subdirectories.
           include_submodules: Whether to include Git submodules.
           
       Returns:
           List of detected repositories.
           
       Raises:
           RepositoryError: If repository detection fails.
       """
       # Implementation details

   def lock_repositories(
       config: VCSPullConfig,
       patterns: Optional[List[str]] = None,
       lock_file: Optional[Union[str, Path]] = None
   ) -> Dict[str, Dict[str, str]]:
       """Lock repositories to their current revision.
       
       Args:
           config: Configuration object.
           patterns: Optional list of repository name patterns to filter.
           lock_file: Optional path to save lock information.
           
       Returns:
           Dictionary mapping repository names to lock information.
           
       Raises:
           RepositoryError: If repository locking fails.
       """
       # Implementation details

   def apply_locks(
       config: VCSPullConfig,
       lock_file: Union[str, Path],
       patterns: Optional[List[str]] = None,
       dry_run: bool = False
   ) -> Dict[str, Dict[str, Any]]:
       """Apply locked revisions to repositories.
       
       Args:
           config: Configuration object.
           lock_file: Path to lock file.
           patterns: Optional list of repository name patterns to filter.
           dry_run: If True, only show what would be done without making changes.
           
       Returns:
           Dictionary mapping repository names to application results.
           
       Raises:
           RepositoryError: If applying locks fails.
       """
       # Implementation details
   ```

### 4. Exceptions Hierarchy

1. **Public Exception Classes**:
   ```python
   # src/vcspull/api/exceptions.py
   """Public exceptions for VCSPull API."""

   class VCSPullError(Exception):
       """Base exception for all VCSPull errors."""
       pass

   class ConfigurationError(VCSPullError):
       """Error related to configuration loading or validation."""
       pass

   class RepositoryError(VCSPullError):
       """Error related to repository operations."""
       pass

   class VCSError(VCSPullError):
       """Error related to version control operations."""
       def __init__(self, message: str, vcs_type: str, command: str = None, output: str = None):
           self.vcs_type = vcs_type
           self.command = command
           self.output = output
           super().__init__(message)
   ```

### 5. Progress Reporting

1. **Callback-Based Progress Reporting**:
   ```python
   # Example usage with progress callback
   def progress_callback(repo_name: str, current: int, total: int):
       print(f"Syncing {repo_name}: {current}/{total}")

   results = sync_repositories(
       config=config,
       patterns=["myrepo*"],
       progress_callback=progress_callback
   )
   ```

2. **Structured Progress Information**:
   ```python
   # Example of structured progress reporting
   class ProgressReporter:
       def __init__(self):
           self.total_repos = 0
           self.processed_repos = 0
           self.current_repo = None
           self.current_operation = None
       
       def on_progress(self, repo_name: str, current: int, total: int):
           self.current_repo = repo_name
           self.processed_repos = current
           self.total_repos = total
           print(f"[{current}/{total}] Processing {repo_name}")

   reporter = ProgressReporter()
   results = sync_repositories(
       config=config,
       progress_callback=reporter.on_progress
   )
   ```

### 6. Lock File Format

1. **JSON Lock File Format**:
   ```json
   {
     "created_at": "2023-03-15T12:34:56Z",
     "repositories": {
       "myrepo": {
         "url": "git+https://github.com/user/myrepo.git",
         "path": "/home/user/myproject/",
         "vcs": "git",
         "rev": "a1b2c3d4e5f6",
         "branch": "main"
       },
       "another-repo": {
         "url": "git+https://github.com/user/another-repo.git",
         "path": "/home/user/projects/another-repo",
         "vcs": "git",
         "rev": "f6e5d4c3b2a1",
         "branch": "develop"
       }
     }
   }
   ```

2. **Lock API Example**:
   ```python
   # Lock repositories to their current revisions
   lock_info = lock_repositories(
       config=config,
       patterns=["*"],
       lock_file="vcspull.lock.json"
   )

   # Later, apply the locked revisions
   apply_results = apply_locks(
       config=config,
       lock_file="vcspull.lock.json"
   )
   ```

### 7. API Versioning Strategy

1. **Semantic Versioning**:
   - Major version changes for breaking API changes
   - Minor version changes for new features or non-breaking changes
   - Patch version changes for bug fixes

2. **API Version Declaration**:
   ```python
   # src/vcspull/api/__init__.py
   """VCSPull Public API."""

   __api_version__ = "1.0.0"

   from .config import load_config, save_config, get_repository, add_repository
   from .repositories import (
       sync_repositories, detect_repositories, lock_repositories, apply_locks
   )
   from .exceptions import ConfigurationError, RepositoryError, VCSError

   __all__ = [
       "__api_version__",
       "load_config",
       "save_config",
       "get_repository",
       "add_repository",
       "sync_repositories",
       "detect_repositories",
       "lock_repositories",
       "apply_locks",
       "ConfigurationError",
       "RepositoryError",
       "VCSError",
   ]
   ```

### 8. Documentation Standards

1. **API Documentation Format**:
   - Use Google-style docstrings
   - Document all parameters, return values, and exceptions
   - Include examples for common usage patterns

2. **Example Documentation**:
   ```python
   def sync_repositories(
       config: VCSPullConfig,
       patterns: Optional[List[str]] = None,
       dry_run: bool = False,
       progress_callback: Optional[Callable[[str, int, int], None]] = None
   ) -> Dict[str, Dict[str, Any]]:
       """Synchronize repositories according to configuration.
       
       This function synchronizes repositories defined in the configuration.
       For existing repositories, it updates them to the latest version.
       For non-existing repositories, it clones them.
       
       Args:
           config: Configuration object containing repository definitions.
           patterns: Optional list of repository name patterns to filter.
               If provided, only repositories matching these patterns will be synchronized.
               Patterns support Unix shell-style wildcards (e.g., "project*").
           dry_run: If True, only show what would be done without making changes.
           progress_callback: Optional callback for progress updates.
               The callback receives three arguments:
               - repository name (str)
               - current repository index (int, 1-based)
               - total number of repositories (int)
           
       Returns:
           Dictionary mapping repository names to sync results.
           Each result contains:
           - 'success': bool indicating if the sync was successful
           - 'message': str describing the result
           - 'details': dict with operation-specific details
           
       Raises:
           RepositoryError: If repository operations fail.
           ConfigurationError: If the provided configuration is invalid.
           
       Examples:
           >>> config = load_config("~/.config/vcspull/config.yaml")
           >>> results = sync_repositories(config)
           >>> for repo, result in results.items():
           ...     print(f"{repo}: {'Success' if result['success'] else 'Failed'}")
           
           # Sync only repositories matching a pattern
           >>> results = sync_repositories(config, patterns=["project*"])
           
           # Use a progress callback
           >>> def show_progress(repo, current, total):
           ...     print(f"[{current}/{total}] Processing {repo}")
           >>> sync_repositories(config, progress_callback=show_progress)
       """
       # Implementation details
   ```

## Implementation Plan

1. **Phase 1: API Design**
   - Design and document the public API
   - Define exception hierarchy
   - Establish versioning strategy

2. **Phase 2: Configuration API**
   - Implement configuration loading and saving
   - Add repository management functions
   - Write comprehensive tests

3. **Phase 3: Repository Operations API**
   - Implement sync, detect, lock, and apply functions
   - Add progress reporting
   - Write comprehensive tests

4. **Phase 4: Documentation**
   - Create API documentation
   - Add usage examples
   - Update existing docs to reference the API

5. **Phase 5: Integration**
   - Update CLI to use the public API
   - Ensure backward compatibility
   - Release with proper versioning

## Benefits

1. **Improved Usability**: Clean, well-documented API for programmatic usage
2. **Better Integration**: Easier to integrate with other tools and scripts
3. **Clear Contracts**: Well-defined function signatures and return types
4. **Comprehensive Documentation**: Clear documentation with examples
5. **Forward Compatibility**: Versioning strategy for future changes
6. **Enhanced Error Handling**: Structured exceptions for better error handling

## Drawbacks and Mitigation

1. **Breaking Changes**:
   - Provide clear migration guides
   - Maintain backward compatibility where possible
   - Use deprecation warnings before removing old functionality

2. **Maintenance Overhead**:
   - Clear ownership of public API
   - Comprehensive test coverage
   - API documentation reviews

3. **Learning Curve**:
   - Clear examples for common use cases
   - Comprehensive error messages
   - Tutorials for new users

## Conclusion

The proposed external API will provide a clean, well-documented interface for programmatic usage of VCSPull. By establishing clear boundaries, consistent function signatures, and a proper versioning strategy, we can make VCSPull more accessible to users who want to integrate it with their own tools and workflows. The addition of lock file functionality will also enhance VCSPull's capabilities for reproducible environments. 