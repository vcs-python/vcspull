# VCSPull Test Improvement Plan

This plan outlines strategies for improving the test coverage and test quality for VCSPull, focusing on addressing the gaps identified in the test audit.

## Type Safety and Static Analysis

Throughout this plan, we'll ensure all code follows these standards:

1. **Strict Type Annotations**
   - All function parameters and return types must be annotated
   - Use the most specific type possible (avoid `t.Any` when possible)
   - Use `t.Optional` for parameters that might be `None`
   - Use `t.Union` when a value could be multiple distinct types
   - Use `t.Literal` for values restricted to a set of constants
   - Always import typing as a namespace: `import typing as t`

2. **Import Guidelines**
   - Prefer namespace imports over importing specific symbols
   - For all standard library modules like `enum`, `pathlib`, `os`, etc.:
     - Use `import enum` and access via `enum.Enum` (not `from enum import Enum`)
     - Use `import pathlib` and access via `pathlib.Path` (not `from pathlib import Path`)
   - For typing, always use `import typing as t` and access via namespace:
     - Use `t.NamedTuple`, `t.TypedDict`, etc. via the namespace
     - For primitive types, use built-in notation: `list[str]`, `dict[str, int]`
     - For unions, use the pipe syntax: `str | None` instead of `t.Optional[str]`

3. **Mypy Configuration**
   - ✓ Strict mode is already enabled in `pyproject.toml` under `[tool.mypy]`
   - ✓ The project uses the following mypy configuration:
     ```toml
     [tool.mypy]
     python_version = 3.9
     warn_unused_configs = true
     files = [
       "src",
       "tests",
     ]
     strict = true
     ```
   - All necessary error checks are enabled via the `strict = true` setting
   - Remaining task: Add CI checks for type validation

4. **Python 3.9+ Features**
   - Use built-in generic types when possible (but always access typing via namespace)
   - Use the new dictionary merge operators (`|` and `|=`)
   - Use the more precise `t.Annotated` for complex annotations
   - Use `t.Protocol` for structural subtyping

5. **Type Documentation**
   - Document complex type behavior in docstrings
   - Type function parameters using the NumPy docstring format
   - Use descriptive variable names that make types obvious
   - When using complex types, define type aliases for better readability

All code examples in this plan follow these guidelines and must be maintained throughout the implementation.

## 1. Improving Testability in Source Code

### A. Enhance Exception Handling

1. **Create Specific Exception Types**
   - ✓ Create a hierarchy of exceptions with specific subtypes in `src/vcspull/exc.py`:
     ```python
     import enum
     import typing as t
     
     class VCSPullException(Exception):
         """Base exception for vcspull."""
     
     class ConfigurationError(VCSPullException):
         """Error in configuration format or content."""
     
     class ValidationError(ConfigurationError):
         """Error validating configuration."""
         
         def __init__(
             self, 
             message: str, 
             *,
             config_type: t.Optional[str] = None,
             path: t.Optional[str] = None,
             url: t.Optional[str] = None,
             suggestion: t.Optional[str] = None,
             risk: t.Optional[t.Literal["security", "performance", "reliability"]] = None
         ) -> None:
             self.config_type = config_type
             self.path = path
             self.url = url
             self.suggestion = suggestion
             self.risk = risk
             
             details = []
             if config_type:
                 details.append(f"Type: {config_type}")
             if path:
                 details.append(f"Path: {path}")
             if url:
                 details.append(f"URL: {url}")
             if risk:
                 details.append(f"Risk: {risk}")
                 
             error_msg = message
             if details:
                 error_msg = f"{message} [{', '.join(details)}]"
             if suggestion:
                 error_msg = f"{error_msg}\nSuggestion: {suggestion}"
                 
             super().__init__(error_msg)
     
     class VCSOperationError(VCSPullException):
         """Error performing VCS operation."""
         
         def __init__(
             self, 
             message: str, 
             *, 
             vcs_type: t.Optional[t.Literal["git", "hg", "svn"]] = None, 
             operation: t.Optional[str] = None, 
             repo_path: t.Optional[str] = None,
             error_code: t.Optional["ErrorCode"] = None
         ) -> None:
             self.vcs_type = vcs_type
             self.operation = operation
             self.repo_path = repo_path
             self.error_code = error_code
             
             details = []
             if vcs_type:
                 details.append(f"VCS: {vcs_type}")
             if operation:
                 details.append(f"Op: {operation}")
             if repo_path:
                 details.append(f"Path: {repo_path}")
             if error_code:
                 details.append(f"Code: {error_code.name}")
                 
             error_msg = message
             if details:
                 error_msg = f"{message} [{', '.join(details)}]"
                 
             super().__init__(error_msg)
     
     class NetworkError(VCSPullException):
         """Network-related errors."""
         
         def __init__(
             self, 
             message: str, 
             *, 
             url: t.Optional[str] = None, 
             status_code: t.Optional[int] = None, 
             retry_count: t.Optional[int] = None,
             suggestion: t.Optional[str] = None,
             error_code: t.Optional["ErrorCode"] = None
         ) -> None:
             self.url = url
             self.status_code = status_code
             self.retry_count = retry_count
             self.suggestion = suggestion
             self.error_code = error_code
             
             details = []
             if url:
                 details.append(f"URL: {url}")
             if status_code:
                 details.append(f"Status: {status_code}")
             if retry_count is not None:
                 details.append(f"Retries: {retry_count}")
             if error_code:
                 details.append(f"Code: {error_code.name}")
                 
             error_msg = message
             if details:
                 error_msg = f"{message} [{', '.join(details)}]"
             if suggestion:
                 error_msg = f"{error_msg}\nSuggestion: {suggestion}"
                 
             super().__init__(error_msg)
     
     class AuthenticationError(NetworkError):
         """Authentication failures."""
         
         def __init__(
             self, 
             message: str, 
             *, 
             url: t.Optional[str] = None, 
             auth_method: t.Optional[t.Literal["ssh-key", "username/password", "token"]] = None,
             error_code: t.Optional["ErrorCode"] = None
         ) -> None:
             self.auth_method = auth_method
             details = []
             if auth_method:
                 details.append(f"Auth: {auth_method}")
                 
             super().__init__(
                 message, 
                 url=url, 
                 error_code=error_code
             )
     
     class RepositoryStateError(VCSPullException):
         """Error with repository state."""
         
         def __init__(
             self, 
             message: str, 
             *, 
             repo_path: t.Optional[str] = None, 
             current_state: t.Optional[t.Dict[str, t.Any]] = None, 
             expected_state: t.Optional[str] = None,
             error_code: t.Optional["ErrorCode"] = None
         ) -> None:
             self.repo_path = repo_path
             self.current_state = current_state
             self.expected_state = expected_state
             self.error_code = error_code
             
             details = []
             if repo_path:
                 details.append(f"Path: {repo_path}")
             if current_state:
                 state_str = ", ".join(f"{k}={v}" for k, v in current_state.items())
                 details.append(f"Current: {{{state_str}}}")
             if expected_state:
                 details.append(f"Expected: {expected_state}")
             if error_code:
                 details.append(f"Code: {error_code.name}")
                 
             error_msg = message
             if details:
                 error_msg = f"{message} [{', '.join(details)}]"
                 
             super().__init__(error_msg)
             
     class ErrorCode(enum.Enum):
         """Error codes for VCSPull exceptions."""
         # Network errors (100-199)
         NETWORK_UNREACHABLE = 100
         CONNECTION_REFUSED = 101
         TIMEOUT = 102
         SSL_ERROR = 103
         DNS_ERROR = 104
         RATE_LIMITED = 105
         
         # Authentication errors (200-299)
         AUTHENTICATION_FAILED = 200
         SSH_KEY_ERROR = 201
         CREDENTIALS_ERROR = 202
         TOKEN_ERROR = 203
         PERMISSION_DENIED = 204
         
         # Repository state errors (300-399)
         REPOSITORY_CORRUPT = 300
         DETACHED_HEAD = 301
         MERGE_CONFLICT = 302
         UNCOMMITTED_CHANGES = 303
         UNTRACKED_FILES = 304
         
         # Configuration errors (400-499)
         INVALID_CONFIGURATION = 400
         MALFORMED_YAML = 401
         MALFORMED_JSON = 402
         PATH_TRAVERSAL = 403
         INVALID_URL = 404
         DUPLICATE_REPOSITORY = 405
     ```

2. **Refactor Validator Module**
   - Update `src/vcspull/validator.py` to use the specific exception types:
     ```python
     import typing as t
     import re
     from pathlib import Path
     
     from .exc import ValidationError, ErrorCode
     
     def is_valid_config(config: t.Any) -> bool:
         """
         Check if configuration is valid.
         
         Parameters
         ----------
         config : Any
             Configuration object to validate
             
         Returns
         -------
         bool
             True if configuration is valid
             
         Raises
         ------
         ValidationError
             If configuration is invalid
         """
         if not isinstance(config, (dict, t.Mapping)):
             raise ValidationError(
                 "Configuration must be a dictionary", 
                 config_type=type(config).__name__,
                 error_code=ErrorCode.INVALID_CONFIGURATION
             )
         
         # Additional validation logic...
         return True
     ```
   
   - Add detailed error messages with context information:
     ```python
     def validate_url(url: str) -> bool:
         """
         Validate repository URL.
         
         Parameters
         ----------
         url : str
             URL to validate
             
         Returns
         -------
         bool
             True if URL is valid
             
         Raises
         ------
         ValidationError
             If URL is invalid
         """
         vcs_types = ['git+', 'svn+', 'hg+']
         
         if not isinstance(url, str):
             raise ValidationError(
                 f"URL must be a string",
                 config_type=type(url).__name__,
                 error_code=ErrorCode.INVALID_URL
             )
         
         if not any(url.startswith(prefix) for prefix in vcs_types):
             raise ValidationError(
                 f"URL must start with one of {vcs_types}",
                 url=url,
                 suggestion=f"Try adding a prefix like 'git+' to the URL",
                 error_code=ErrorCode.INVALID_URL
             )
         
         # Check URL for spaces or invalid characters
         if ' ' in url or re.search(r'[<>"{}|\\^`]', url):
             raise ValidationError(
                 "URL contains invalid characters",
                 url=url,
                 suggestion="Encode special characters in URL",
                 error_code=ErrorCode.INVALID_URL
             )
             
         # Check URL length
         if len(url) > 2048:
             raise ValidationError(
                 "URL exceeds maximum length of 2048 characters",
                 url=f"{url[:50]}...",
                 error_code=ErrorCode.INVALID_URL
             )
             
         return True
     ```
   
   - Add validation for URL schemes, special characters, and path traversal:
     ```python
     def validate_path(path: t.Union[str, Path]) -> bool:
         """
         Validate repository path.
         
         Parameters
         ----------
         path : Union[str, Path]
             Repository path to validate
             
         Returns
         -------
         bool
             True if path is valid
             
         Raises
         ------
         ValidationError
             If path is invalid
         """
         path_str = str(path)
         
         # Check for path traversal
         if '..' in path_str:
             raise ValidationError(
                 "Path contains potential directory traversal",
                 path=path_str,
                 risk="security",
                 error_code=ErrorCode.PATH_TRAVERSAL
             )
         
         # Check for invalid characters in path
         if re.search(r'[<>:"|?*]', path_str):
             raise ValidationError(
                 "Path contains characters invalid on some file systems",
                 path=path_str,
                 risk="reliability",
                 error_code=ErrorCode.INVALID_CONFIGURATION
             )
             
         # Check path length
         if len(path_str) > 255:
             raise ValidationError(
                 "Path exceeds maximum length of 255 characters",
                 path=f"{path_str[:50]}...",
                 risk="reliability",
                 error_code=ErrorCode.INVALID_CONFIGURATION
             )
             
         return True
     ```

3. **Enhance Error Reporting**
   - Add context information to all exceptions in `src/vcspull/cli/sync.py`:
     ```python
     import typing as t
     import logging
     
     from vcspull.exc import VCSOperationError, ErrorCode
     
     # Logger setup
     log = logging.getLogger(__name__)
     
     def update_repo(repo: t.Dict[str, t.Any]) -> t.Any:
         """Update a repository."""
         try:
             # Assuming repo.update() is the operation
             result = repo.get("sync_object").update()
             return result
         except Exception as e:
             # More specific exception handling
             raise VCSOperationError(
                 f"Failed to update repository: {str(e)}",
                 vcs_type=t.cast(str, repo.get("vcs")),
                 operation="update",
                 repo_path=t.cast(str, repo.get("path")),
                 error_code=ErrorCode.REPOSITORY_CORRUPT
             ) from e
     ```
   
   - Include recovery suggestions in error messages:
     ```python
     import requests
     import typing as t
     
     from vcspull.exc import NetworkError, ErrorCode
     
     def handle_network_error(e: Exception, repo: t.Dict[str, t.Any]) -> None:
         """
         Handle network errors with recovery suggestions.
         
         Parameters
         ----------
         e : Exception
             The original exception
         repo : Dict[str, Any]
             Repository information
             
         Raises
         ------
         NetworkError
             A more specific network error with recovery suggestions
         """
         repo_url = t.cast(str, repo.get("url"))
         
         if isinstance(e, requests.ConnectionError):
             raise NetworkError(
                 "Network connection failed",
                 url=repo_url,
                 suggestion="Check network connection and try again",
                 error_code=ErrorCode.NETWORK_UNREACHABLE
             ) from e
         elif isinstance(e, requests.Timeout):
             raise NetworkError(
                 "Request timed out",
                 url=repo_url,
                 retry_count=0,
                 suggestion="Try again with a longer timeout",
                 error_code=ErrorCode.TIMEOUT
             ) from e
         elif isinstance(e, requests.exceptions.SSLError):
             raise NetworkError(
                 "SSL certificate verification failed",
                 url=repo_url,
                 suggestion="Check SSL certificates or use --no-verify-ssl option",
                 error_code=ErrorCode.SSL_ERROR
             ) from e
         else:
             # Generic network error
             raise NetworkError(
                 f"Network error: {str(e)}",
                 url=repo_url,
                 error_code=ErrorCode.NETWORK_UNREACHABLE
             ) from e
     ```

### B. Add Testability Hooks

1. **Dependency Injection**
   - Refactor VCS operations in `src/vcspull/cli/sync.py` to accept injectable dependencies:
     ```python
     import typing as t
     from pathlib import Path
     
     # Define protocol for VCS factories
     class VCSFactory(t.Protocol):
         """Protocol for VCS factory functions."""
         def __call__(
             self, 
             *, 
             vcs: str, 
             url: str, 
             path: str, 
             **kwargs: t.Any
         ) -> t.Any: ...
     
     # Define protocol for network managers
     class NetworkManager(t.Protocol):
         """Protocol for network managers."""
         def request(
             self, 
             method: str, 
             url: str, 
             **kwargs: t.Any
         ) -> t.Any: ...
         
         def get(
             self, 
             url: str, 
             **kwargs: t.Any
         ) -> t.Any: ...
     
     # Define protocol for filesystem managers
     class FilesystemManager(t.Protocol):
         """Protocol for filesystem managers."""
         def ensure_directory(
             self, 
             path: t.Union[str, Path], 
             mode: int = 0o755
         ) -> Path: ...
         
         def is_writable(
             self, 
             path: t.Union[str, Path]
         ) -> bool: ...
     
     def update_repo(
         repo: t.Dict[str, t.Any], 
         *, 
         vcs_factory: t.Optional[VCSFactory] = None, 
         network_manager: t.Optional[NetworkManager] = None, 
         fs_manager: t.Optional[FilesystemManager] = None,
         **kwargs: t.Any
     ) -> t.Any:
         """
         Update a repository with injectable dependencies.
         
         Parameters
         ----------
         repo : dict
             Repository configuration dictionary
         vcs_factory : VCSFactory, optional
             Factory function to create VCS objects
         network_manager : NetworkManager, optional
             Network handling manager for HTTP operations
         fs_manager : FilesystemManager, optional
             Filesystem manager for disk operations
         **kwargs : Any
             Additional parameters to pass to VCS object
             
         Returns
         -------
         Any
             Result of the update operation
             
         Raises
         ------
         VCSOperationError
             If update operation fails
         """
         vcs_factory = vcs_factory or get_default_vcs_factory()
         network_manager = network_manager or get_default_network_manager()
         fs_manager = fs_manager or get_default_fs_manager()
         
         # Repository creation with dependency injection
         vcs_obj = vcs_factory(
             vcs=t.cast(str, repo.get('vcs')),
             url=t.cast(str, repo.get('url')),
             path=t.cast(str, repo.get('path')),
             network_manager=network_manager,
             fs_manager=fs_manager,
             **kwargs
         )
         
         return vcs_obj.update()
     ```

   - Create factory functions that can be mocked/replaced:
     ```python
     import typing as t
     from pathlib import Path
     import logging
     
     from libvcs.sync.git import GitSync
     from libvcs.sync.hg import HgSync
     from libvcs.sync.svn import SvnSync
     
     from vcspull.exc import VCSOperationError, ErrorCode
     
     log = logging.getLogger(__name__)
     
     # Type variable for VCS sync classes
     VCSType = t.Union[GitSync, HgSync, SvnSync]
     
     class FactoryRegistry:
         """Registry for factory functions."""
         
         _instance: t.ClassVar[t.Optional["FactoryRegistry"]] = None
         
         def __init__(self) -> None:
             self.vcs_factories: t.Dict[str, t.Callable[..., VCSType]] = {}
             self.network_manager: t.Optional[NetworkManager] = None
             self.fs_manager: t.Optional[FilesystemManager] = None
             
         @classmethod
         def get_instance(cls) -> "FactoryRegistry":
             """Get the singleton instance."""
             if cls._instance is None:
                 cls._instance = cls()
             return cls._instance
             
         def register_vcs_factory(
             self, 
             vcs_type: str, 
             factory: t.Callable[..., VCSType]
         ) -> None:
             """Register a VCS factory function."""
             self.vcs_factories[vcs_type] = factory
             log.debug(f"Registered VCS factory for {vcs_type}")
             
         def get_vcs_factory(
             self, 
             vcs_type: str
         ) -> t.Callable[..., VCSType]:
             """Get a VCS factory function."""
             if vcs_type not in self.vcs_factories:
                 raise ValueError(f"No factory registered for VCS type: {vcs_type}")
             return self.vcs_factories[vcs_type]
             
         def set_network_manager(
             self, 
             manager: NetworkManager
         ) -> None:
             """Set the network manager."""
             self.network_manager = manager
             
         def set_fs_manager(
             self, 
             manager: FilesystemManager
         ) -> None:
             """Set the filesystem manager."""
             self.fs_manager = manager
     
     
     def default_vcs_factory(
         *, 
         vcs: str, 
         url: str, 
         path: str, 
         **kwargs: t.Any
     ) -> VCSType:
         """
         Create a VCS object based on the specified type.
         
         Parameters
         ----------
         vcs : str
             Type of VCS ('git', 'hg', 'svn')
         url : str
             Repository URL
         path : str
             Repository path
         **kwargs : Any
             Additional parameters for VCS object
             
         Returns
         -------
         Union[GitSync, HgSync, SvnSync]
             VCS object
             
         Raises
         ------
         ValueError
             If VCS type is not supported
         """
         if vcs == 'git':
             return GitSync(url=url, path=path, **kwargs)
         elif vcs == 'hg':
             return HgSync(url=url, path=path, **kwargs)
         elif vcs == 'svn':
             return SvnSync(url=url, path=path, **kwargs)
         else:
             raise ValueError(f"Unsupported VCS type: {vcs}")
             
     
     def get_default_vcs_factory() -> VCSFactory:
         """
         Get the default VCS factory function.
         
         Returns
         -------
         VCSFactory
             Factory function to create VCS objects
         """
         registry = FactoryRegistry.get_instance()
         
         # Register default factories if not already registered
         if not registry.vcs_factories:
             registry.register_vcs_factory('git', lambda **kwargs: GitSync(**kwargs))
             registry.register_vcs_factory('hg', lambda **kwargs: HgSync(**kwargs))
             registry.register_vcs_factory('svn', lambda **kwargs: SvnSync(**kwargs))
             
         return default_vcs_factory
         
     
     def get_default_network_manager() -> NetworkManager:
         """
         Get the default network manager.
         
         Returns
         -------
         NetworkManager
             Network manager for HTTP operations
         """
         registry = FactoryRegistry.get_instance()
         
         if registry.network_manager is None:
             from vcspull._internal.network import NetworkManager
             registry.network_manager = NetworkManager()
             
         return t.cast(NetworkManager, registry.network_manager)
         
     
     def get_default_fs_manager() -> FilesystemManager:
         """
         Get the default filesystem manager.
         
         Returns
         -------
         FilesystemManager
             Filesystem manager for disk operations
         """
         registry = FactoryRegistry.get_instance()
         
         if registry.fs_manager is None:
             from vcspull._internal.fs import FilesystemManager
             registry.fs_manager = FilesystemManager()
             
         return t.cast(FilesystemManager, registry.fs_manager)
     ```

2. **Add State Inspection Methods**
   - Create new module `src/vcspull/_internal/repo_inspector.py` for repository state inspection:
     ```python
     import typing as t
     import logging
     import subprocess
     from pathlib import Path
     import os
     
     from vcspull.exc import RepositoryStateError, ErrorCode
     
     log = logging.getLogger(__name__)
     
     # Type alias for VCS types
     VCSType = t.Literal["git", "hg", "svn"]
     
     # Type alias for repository state
     RepoState = t.Dict[str, t.Any]
     
     
     def detect_repo_type(repo_path: t.Union[str, Path]) -> VCSType:
         """
         Detect repository type.
         
         Parameters
         ----------
         repo_path : Union[str, Path]
             Path to repository
             
         Returns
         -------
         Literal["git", "hg", "svn"]
             Repository type
             
         Raises
         ------
         RepositoryStateError
             If repository type cannot be detected
         """
         repo_path = Path(repo_path).expanduser().resolve()
         
         if (repo_path / '.git').exists():
             return "git"
         elif (repo_path / '.hg').exists():
             return "hg"
         elif (repo_path / '.svn').exists():
             return "svn"
         else:
             raise RepositoryStateError(
                 "Cannot detect repository type",
                 repo_path=str(repo_path),
                 expected_state="git, hg, or svn repository",
                 error_code=ErrorCode.REPOSITORY_CORRUPT
             )
     
     
     def get_repository_state(
         repo_path: t.Union[str, Path], 
         vcs_type: t.Optional[VCSType] = None
     ) -> RepoState:
         """
         Return detailed repository state information.
         
         Parameters
         ----------
         repo_path : Union[str, Path]
             Path to the repository
         vcs_type : Literal["git", "hg", "svn"], optional
             VCS type - will auto-detect if not specified
             
         Returns
         -------
         Dict[str, Any]
             Dictionary containing repository state information
             
         Raises
         ------
         RepositoryStateError
             If repository state cannot be determined
         ValueError
             If VCS type is not supported
         """
         if vcs_type is None:
             vcs_type = detect_repo_type(repo_path)
             
         if vcs_type == 'git':
             return get_git_repository_state(repo_path)
         elif vcs_type == 'hg':
             return get_hg_repository_state(repo_path)
         elif vcs_type == 'svn':
             return get_svn_repository_state(repo_path)
         else:
             raise ValueError(f"Unsupported VCS type: {vcs_type}")
     
     
     def get_git_repository_state(repo_path: t.Union[str, Path]) -> RepoState:
         """
         Get detailed state information for Git repository.
         
         Parameters
         ----------
         repo_path : Union[str, Path]
             Path to repository
             
         Returns
         -------
         Dict[str, Any]
             Repository state information
             
         Raises
         ------
         RepositoryStateError
             If repository state cannot be determined
         """
         repo_path = Path(repo_path).expanduser().resolve()
         
         # Check for .git directory
         if not (repo_path / '.git').exists():
             return {'exists': False, 'is_repo': False, 'vcs_type': 'git'}
             
         # Get current branch
         branch: t.Optional[str] = None
         try:
             branch = subprocess.check_output(
                 ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
                 cwd=repo_path,
                 universal_newlines=True,
                 stderr=subprocess.PIPE
             ).strip()
         except subprocess.CalledProcessError:
             log.warning(f"Failed to get current branch for {repo_path}")
             
         # Check if HEAD is detached
         is_detached = branch == 'HEAD'
         
         # Check for uncommitted changes
         has_changes = False
         try:
             changes = subprocess.check_output(
                 ['git', 'status', '--porcelain'],
                 cwd=repo_path,
                 universal_newlines=True,
                 stderr=subprocess.PIPE
             )
             has_changes = bool(changes.strip())
         except subprocess.CalledProcessError:
             log.warning(f"Failed to check for uncommitted changes in {repo_path}")
             
         # Get current commit
         commit: t.Optional[str] = None
         try:
             commit = subprocess.check_output(
                 ['git', 'rev-parse', 'HEAD'],
                 cwd=repo_path,
                 universal_newlines=True,
                 stderr=subprocess.PIPE
             ).strip()
         except subprocess.CalledProcessError:
             log.warning(f"Failed to get current commit for {repo_path}")
             
         # Check for merge conflicts
         has_conflicts = False
         try:
             conflicts = subprocess.check_output(
                 ['git', 'diff', '--name-only', '--diff-filter=U'],
                 cwd=repo_path,
                 universal_newlines=True,
                 stderr=subprocess.PIPE
             )
             has_conflicts = bool(conflicts.strip())
         except subprocess.CalledProcessError:
             log.warning(f"Failed to check for merge conflicts in {repo_path}")
             
         # Check for untracked files
         has_untracked = False
         try:
             # Find untracked files (start with ?? in git status)
             untracked = subprocess.check_output(
                 ['git', 'status', '--porcelain'],
                 cwd=repo_path,
                 universal_newlines=True,
                 stderr=subprocess.PIPE
             )
             has_untracked = any(line.startswith('??') for line in untracked.splitlines())
         except subprocess.CalledProcessError:
             log.warning(f"Failed to check for untracked files in {repo_path}")
             
         return {
             'exists': True,
             'is_repo': True,
             'vcs_type': 'git',
             'branch': branch,
             'is_detached': is_detached,
             'has_changes': has_changes,
             'has_conflicts': has_conflicts,
             'has_untracked': has_untracked,
             'commit': commit
         }
     
     
     def get_hg_repository_state(repo_path: t.Union[str, Path]) -> RepoState:
         """
         Get detailed state information for Mercurial repository.
         
         Parameters
         ----------
         repo_path : Union[str, Path]
             Path to repository
             
         Returns
         -------
         Dict[str, Any]
             Repository state information
         """
         repo_path = Path(repo_path).expanduser().resolve()
         
         # Implementation for Mercurial repositories
         # This is a placeholder - full implementation would be similar to Git's
         
         if not (repo_path / '.hg').exists():
             return {'exists': False, 'is_repo': False, 'vcs_type': 'hg'}
             
         return {
             'exists': True,
             'is_repo': True,
             'vcs_type': 'hg',
             # Additional Mercurial-specific state information would go here
         }
     
     
     def get_svn_repository_state(repo_path: t.Union[str, Path]) -> RepoState:
         """
         Get detailed state information for Subversion repository.
         
         Parameters
         ----------
         repo_path : Union[str, Path]
             Path to repository
             
         Returns
         -------
         Dict[str, Any]
             Repository state information
         """
         repo_path = Path(repo_path).expanduser().resolve()
         
         # Implementation for Subversion repositories
         # This is a placeholder - full implementation would be similar to Git's
         
         if not (repo_path / '.svn').exists():
             return {'exists': False, 'is_repo': False, 'vcs_type': 'svn'}
             
         return {
             'exists': True,
             'is_repo': True,
             'vcs_type': 'svn',
             # Additional SVN-specific state information would go here
         }
     
     
     def is_detached_head(repo_path: t.Union[str, Path]) -> bool:
         """
         Check if Git repository is in detached HEAD state.
         
         Parameters
         ----------
         repo_path : Union[str, Path]
             Path to repository
             
         Returns
         -------
         bool
             True if repository is in detached HEAD state
             
         Raises
         ------
         RepositoryStateError
             If repository is not a Git repository or state cannot be determined
         """
         try:
             state = get_git_repository_state(repo_path)
             return state.get('is_detached', False)
         except Exception as e:
             raise RepositoryStateError(
                 f"Failed to check detached HEAD state: {str(e)}",
                 repo_path=str(repo_path),
                 error_code=ErrorCode.REPOSITORY_CORRUPT
             ) from e
     
     
     def has_uncommitted_changes(repo_path: t.Union[str, Path]) -> bool:
         """
         Check if repository has uncommitted changes.
         
         Parameters
         ----------
         repo_path : Union[str, Path]
             Path to repository
             
         Returns
         -------
         bool
             True if repository has uncommitted changes
             
         Raises
         ------
         RepositoryStateError
             If repository state cannot be determined
         """
         try:
             vcs_type = detect_repo_type(repo_path)
             state = get_repository_state(repo_path, vcs_type=vcs_type)
             return state.get('has_changes', False)
         except Exception as e:
             raise RepositoryStateError(
                 f"Failed to check uncommitted changes: {str(e)}",
                 repo_path=str(repo_path),
                 error_code=ErrorCode.REPOSITORY_CORRUPT
             ) from e
     ```

3. **Add Test Mode Flag**
   - Update the primary synchronization function in `src/vcspull/cli/sync.py`:
     ```python
     import typing as t
     import logging
     
     from vcspull.exc import VCSOperationError, ErrorCode
     
     log = logging.getLogger(__name__)
     
     def sync_repositories(
         repos: t.List[t.Dict[str, t.Any]], 
         *, 
         test_mode: bool = False, 
         **kwargs: t.Any
     ) -> t.List[t.Dict[str, t.Any]]:
         """
         Sync repositories with test mode support.
         
         Parameters
         ----------
         repos : List[Dict[str, Any]]
             List of repository dictionaries
         test_mode : bool, optional
             Enable test mode
         **kwargs : Any
             Additional parameters to pass to update_repo
             
         Returns
         -------
         List[Dict[str, Any]]
             List of updated repositories with status information
             
         Raises
         ------
         VCSOperationError
             If repository update fails and raise_exceptions is True
         """
         if test_mode:
             # Configure for testing
             kwargs.setdefault('timeout', 5)  # Short timeout for faster tests
             kwargs.setdefault('retries', 1)  # Fewer retries for faster tests
             kwargs.setdefault('verbose', True)  # More detailed output
             
             # Log operations instead of executing them if requested
             if kwargs.get('dry_run'):
                 log.info("Running in dry run test mode")
                 
             # Set up test hooks
             from vcspull._internal.testing.hooks import register_test_hooks
             register_test_hooks()
         
         results: t.List[t.Dict[str, t.Any]] = []
         for repo in repos:
             try:
                 result = update_repo(repo, **kwargs)
                 results.append({
                     'name': t.cast(str, repo['name']), 
                     'status': 'success', 
                     'result': result
                 })
             except Exception as e:
                 if test_mode:
                     # In test mode, capture the exception for verification
                     results.append({
                         'name': t.cast(str, repo['name']), 
                         'status': 'error', 
                         'exception': e
                     })
                     if kwargs.get('raise_exceptions', True):
                         raise
                 else:
                     # In normal mode, log and continue
                     log.error(f"Error updating {repo['name']}: {str(e)}")
                     results.append({
                         'name': t.cast(str, repo['name']), 
                         'status': 'error', 
                         'message': str(e)
                     })
         
         return results
     ```

   - Create test hooks module `src/vcspull/_internal/testing/hooks.py`:
     ```python
     """Hooks for testing VCSPull."""
     
     import logging
     import typing as t
     from functools import wraps
     
     log = logging.getLogger(__name__)
     
     # Type variables for hook functions
     T = t.TypeVar('T')
     R = t.TypeVar('R')
     
     # Type for hook functions
     HookFunction = t.Callable[[t.Any, t.Callable[..., R], t.Any, t.Any], R]
     
     # Global registry for test hooks
     _test_hooks: t.Dict[str, HookFunction] = {}
     
     
     def register_test_hook(name: str, hook_function: HookFunction) -> None:
         """
         Register a test hook function.
         
         Parameters
         ----------
         name : str
             Hook name (usually Class.method_name)
         hook_function : Callable
             Hook function to call
         """
         _test_hooks[name] = hook_function
         log.debug(f"Registered test hook: {name}")
         
     
     def get_test_hook(name: str) -> t.Optional[HookFunction]:
         """
         Get a registered test hook function.
         
         Parameters
         ----------
         name : str
             Hook name
             
         Returns
         -------
         Optional[Callable]
             Hook function if registered, None otherwise
         """
         return _test_hooks.get(name)
         
     
     def hook_method(cls: type, method_name: str) -> None:
         """
         Decorator to hook a method for testing.
         
         Parameters
         ----------
         cls : type
             Class to hook
         method_name : str
             Method name to hook
         """
         original_method = getattr(cls, method_name)
         
         @wraps(original_method)
         def wrapped(self: t.Any, *args: t.Any, **kwargs: t.Any) -> t.Any:
             hook_name = f"{cls.__name__}.{method_name}"
             hook = get_test_hook(hook_name)
             
             if hook:
                 log.debug(f"Calling test hook: {hook_name}")
                 return hook(self, original_method, *args, **kwargs)
             else:
                 return original_method(self, *args, **kwargs)
                 
         setattr(cls, method_name, wrapped)
         log.debug(f"Hooked method: {cls.__name__}.{method_name}")
         
     
     def register_test_hooks() -> None:
         """Register all test hooks."""
         # Example: Hook GitSync update method
         from libvcs.sync.git import GitSync
         hook_method(GitSync, 'update')
         
         # Example: Hook network operations
         from vcspull._internal.network import NetworkManager
         hook_method(NetworkManager, 'request')
     ```

### C. Separate Concerns for Better Testability

1. **Extract Network Operations**
   - Create a separate module for network operations in `src/vcspull/_internal/network.py`:
     ```python
     """Network operations for VCSPull."""
     
     import logging
     import time
     import typing as t
     from urllib.parse import urlparse
     import dataclasses
     
     import requests
     from requests.exceptions import ConnectionError, Timeout
     
     from vcspull.exc import NetworkError, ErrorCode
     
     log = logging.getLogger(__name__)
     
     
     @dataclasses.dataclass
     class RetryStrategy:
         """Strategy for retrying network operations."""
         
         max_retries: int = 3
         initial_delay: float = 1.0
         backoff_factor: float = 2.0
         
         def get_delay(self, attempt: int) -> float:
             """
             Get delay for a specific retry attempt.
             
             Parameters
             ----------
             attempt : int
                 Current attempt number (1-based)
                 
             Returns
             -------
             float
                 Delay in seconds
             """
             return self.initial_delay * (self.backoff_factor ** (attempt - 1))
     
     
     ResponseType = t.TypeVar('ResponseType')
     
     
     class NetworkManager:
         """Manager for network operations."""
         
         def __init__(
             self, 
             *, 
             session: t.Optional[requests.Session] = None, 
             retry_strategy: t.Optional[RetryStrategy] = None
         ) -> None:
             """
             Initialize network manager.
             
             Parameters
             ----------
             session : requests.Session, optional
                 Session to use for requests
             retry_strategy : RetryStrategy, optional
                 Strategy for retrying failed requests
             """
             self.session = session or requests.Session()
             self.retry_strategy = retry_strategy or RetryStrategy()
             
         def request(
             self, 
             method: str, 
             url: str, 
             **kwargs: t.Any
         ) -> requests.Response:
             """
             Perform HTTP request with retry logic.
             
             Parameters
             ----------
             method : str
                 HTTP method (GET, POST, etc.)
             url : str
                 URL to request
             **kwargs : Any
                 Additional parameters for requests
                 
             Returns
             -------
             requests.Response
                 Response object
                 
             Raises
             ------
             NetworkError
                 If the request fails after all retries
             """
             parsed_url = urlparse(url)
             log.debug(f"Requesting {method} {parsed_url.netloc}{parsed_url.path}")
             
             # Get retry settings
             max_retries = kwargs.pop('max_retries', self.retry_strategy.max_retries)
             
             # Initialize retry counter
             attempt = 0
             last_exception: t.Optional[NetworkError] = None
             
             while attempt < max_retries:
                 attempt += 1
                 try:
                     response = self.session.request(method, url, **kwargs)
                     
                     # Check for HTTP errors
                     if response.status_code >= 400:
                         log.warning(f"HTTP error {response.status_code} for {url}")
                         if 500 <= response.status_code < 600:
                             # Server errors might be temporary, keep retrying
                             last_exception = NetworkError(
                                 f"Server error: {response.status_code}",
                                 url=url,
                                 status_code=response.status_code,
                                 retry_count=attempt,
                                 error_code=ErrorCode.NETWORK_UNREACHABLE
                             )
                             continue
                         elif response.status_code == 429:
                             # Rate limiting - wait longer
                             last_exception = NetworkError(
                                 "Rate limited",
                                 url=url,
                                 status_code=429,
                                 retry_count=attempt,
                                 error_code=ErrorCode.RATE_LIMITED
                             )
                             # Get retry-after header if available
                             retry_after = response.headers.get('Retry-After')
                             if retry_after:
                                 try:
                                     delay = float(retry_after)
                                 except (ValueError, TypeError):
                                     delay = self.retry_strategy.get_delay(attempt)
                             else:
                                 delay = self.retry_strategy.get_delay(attempt)
                             log.info(f"Rate limited, waiting {delay}s before retry {attempt}/{max_retries}")
                             time.sleep(delay)
                             continue
                         else:
                             # Client errors are not likely to be resolved by retrying
                             raise NetworkError(
                                 f"Client error: {response.status_code}",
                                 url=url,
                                 status_code=response.status_code,
                                 error_code=ErrorCode.NETWORK_UNREACHABLE
                             )
                     
                     # Success
                     return response
                     
                 except (ConnectionError, Timeout) as e:
                     # Network errors might be temporary
                     log.warning(f"Network error on attempt {attempt}/{max_retries}: {str(e)}")
                     last_exception = NetworkError(
                         f"Network error: {str(e)}",
                         url=url,
                         retry_count=attempt,
                         error_code=(
                             ErrorCode.TIMEOUT if isinstance(e, Timeout) 
                             else ErrorCode.CONNECTION_REFUSED
                         )
                     )
                     
                     # Wait before retrying
                     if attempt < max_retries:
                         delay = self.retry_strategy.get_delay(attempt)
                         log.info(f"Retrying in {delay}s ({attempt}/{max_retries})")
                         time.sleep(delay)
             
             # If we get here, all retries failed
             if last_exception:
                 raise last_exception
             else:
                 raise NetworkError(
                     f"Failed after {max_retries} attempts", 
                     url=url,
                     error_code=ErrorCode.NETWORK_UNREACHABLE
                 )
                 
         def get(
             self, 
             url: str, 
             **kwargs: t.Any
         ) -> requests.Response:
             """
             Perform HTTP GET request.
             
             Parameters
             ----------
             url : str
                 URL to request
             **kwargs : Any
                 Additional parameters for requests
                 
             Returns
             -------
             requests.Response
                 Response object
             """
             return self.request('GET', url, **kwargs)
             
         def post(
             self, 
             url: str, 
             **kwargs: t.Any
         ) -> requests.Response:
             """
             Perform HTTP POST request.
             
             Parameters
             ----------
             url : str
                 URL to request
             **kwargs : Any
                 Additional parameters for requests
                 
             Returns
             -------
             requests.Response
                 Response object
             """
             return self.request('POST', url, **kwargs)
     
     
     def perform_request(
         url: str, 
         *, 
         auth: t.Optional[t.Tuple[str, str]] = None, 
         retry_strategy: t.Optional[RetryStrategy] = None, 
         **kwargs: t.Any
     ) -> requests.Response:
         """
         Perform HTTP request with configurable retry strategy.
         
         Parameters
         ----------
         url : str
             URL to request
         auth : Tuple[str, str], optional
             Authentication credentials (username, password)
         retry_strategy : RetryStrategy, optional
             Strategy for retrying failed requests
         **kwargs : Any
             Additional parameters for requests
             
         Returns
         -------
         requests.Response
             Response object
         """
         manager = NetworkManager(retry_strategy=retry_strategy)
         return manager.get(url, auth=auth, **kwargs)
     ```

2. **Extract Shell Command Execution**
   - Create a separate module for shell command execution in `src/vcspull/_internal/shell.py`:
     ```python
     """Shell command execution for VCSPull."""
     
     import logging
     import os
     import shlex
     import subprocess
     import typing as t
     from pathlib import Path
     
     from vcspull.exc import VCSPullException
     
     log = logging.getLogger(__name__)
     
     
     class CommandResult:
         """Result of a shell command execution."""
         
         def __init__(
             self, 
             returncode: int, 
             stdout: str, 
             stderr: str, 
             command: str,
             cwd: t.Optional[str] = None
         ) -> None:
             self.returncode = returncode
             self.stdout = stdout
             self.stderr = stderr
             self.command = command
             self.cwd = cwd
             
         def __bool__(self) -> bool:
             """Return True if command succeeded (returncode == 0)."""
             return self.returncode == 0
             
         def __str__(self) -> str:
             """Return string representation."""
             return f"CommandResult(returncode={self.returncode}, command={self.command!r})"
             
         @property
         def success(self) -> bool:
             """Return True if command succeeded."""
             return self.returncode == 0
     
     
     class ShellCommandError(VCSPullException):
         """Error executing shell command."""
         
         def __init__(self, message: str, result: CommandResult) -> None:
             self.result = result
             super().__init__(f"{message}\nCommand: {result.command}\nExit code: {result.returncode}\nStderr: {result.stderr}")
     
     
     def execute_command(
         command: str, 
         *, 
         env: t.Optional[t.Dict[str, str]] = None, 
         cwd: t.Optional[str] = None, 
         timeout: t.Optional[float] = None,
         check: bool = False,
         shell: bool = False
     ) -> CommandResult:
         """
         Execute shell command with configurable parameters.
         
         Parameters
         ----------
         command : str
             Command to execute
         env : dict, optional
             Environment variables
         cwd : str, optional
             Working directory
         timeout : float, optional
             Timeout in seconds
         check : bool, optional
             Raise exception if command fails
         shell : bool, optional
             Run command in shell
             
         Returns
         -------
         CommandResult
             Result of command execution
             
         Raises
         ------
         ShellCommandError
             If command fails and check=True
         """
         log.debug(f"Executing command: {command}, cwd={cwd}")
         
         # Prepare environment
         cmd_env = os.environ.copy()
         if env:
             cmd_env.update(env)
             
         # Prepare arguments
         if shell:
             args = command
         else:
             args = shlex.split(command)
             
         try:
             result = subprocess.run(
                 args,
                 env=cmd_env,
                 cwd=cwd,
                 capture_output=True,
                 text=True,
                 timeout=timeout,
                 shell=shell,
             )
             
             command_result = CommandResult(
                 returncode=result.returncode,
                 stdout=result.stdout,
                 stderr=result.stderr,
                 command=command,
                 cwd=cwd
             )
             
             if result.returncode != 0:
                 log.warning(f"Command failed: {command}, exit_code={result.returncode}")
                 log.debug(f"Stderr: {result.stderr}")
                 if check:
                     raise ShellCommandError("Command failed", command_result)
             else:
                 log.debug(f"Command succeeded: {command}")
                 
             return command_result
             
         except subprocess.TimeoutExpired as e:
             log.error(f"Command timed out: {command}, timeout={timeout}s")
             result = CommandResult(
                 returncode=-1,  # Use -1 for timeout as it has no returncode
                 stdout="",
                 stderr=f"Timeout expired after {timeout}s",
                 command=command,
                 cwd=cwd
             )
             
             if check:
                 raise ShellCommandError("Command timed out", result) from e
                 
             return result
     ```

3. **Extract Filesystem Operations**
   - Create a separate module for filesystem operations in `src/vcspull/_internal/fs.py`:
     ```python
     """Filesystem operations for VCSPull."""
     
     import logging
     import os
     import shutil
     import stat
     import typing as t
     from pathlib import Path
     
     from vcspull.exc import VCSPullException
     
     log = logging.getLogger(__name__)
     
     
     class FilesystemError(VCSPullException):
         """Error performing filesystem operation."""
         
         def __init__(self, message: str, path: t.Optional[str] = None, operation: t.Optional[str] = None):
             self.path = path
             self.operation = operation
             super().__init__(f"{message} [Path: {path}, Operation: {operation}]")
     
     
     class FilesystemManager:
         """Manager for filesystem operations."""
         
         def ensure_directory(self, path: t.Union[str, Path], mode: int = 0o755) -> Path:
             """Ensure directory exists with proper permissions.
             
             Parameters
             ----------
             path : str or Path
                 Directory path
             mode : int, optional
                 Directory permissions mode
                 
             Returns
             -------
             Path
                 Path object for the directory
                 
             Raises
             ------
             FilesystemError
                 If directory cannot be created
             """
             path = Path(path).expanduser().resolve()
             
             try:
                 if not path.exists():
                     log.debug(f"Creating directory: {path}")
                     path.mkdir(mode=mode, parents=True, exist_ok=True)
                 elif not path.is_dir():
                     raise FilesystemError(
                         f"Path exists but is not a directory",
                         path=str(path),
                         operation="ensure_directory"
                     )
                     
                 return path
                 
             except (PermissionError, OSError) as e:
                 raise FilesystemError(
                     f"Failed to create directory: {str(e)}",
                     path=str(path),
                     operation="ensure_directory"
                 ) from e
                 
         def remove_directory(self, path: t.Union[str, Path], recursive: bool = False) -> None:
             """Remove directory.
             
             Parameters
             ----------
             path : str or Path
                 Directory path
             recursive : bool, optional
                 Remove directory and contents recursively
                 
             Raises
             ------
             FilesystemError
                 If directory cannot be removed
             """
             path = Path(path).expanduser().resolve()
             
             if not path.exists():
                 return
                 
             if not path.is_dir():
                 raise FilesystemError(
                     "Path is not a directory",
                     path=str(path),
                     operation="remove_directory"
                 )
                 
             try:
                 if recursive:
                     log.debug(f"Removing directory recursively: {path}")
                     shutil.rmtree(path)
                 else:
                     log.debug(f"Removing empty directory: {path}")
                     path.rmdir()
                     
             except (PermissionError, OSError) as e:
                 raise FilesystemError(
                     f"Failed to remove directory: {str(e)}",
                     path=str(path),
                     operation="remove_directory"
                 ) from e
                 
         def is_writable(self, path: t.Union[str, Path]) -> bool:
             """Check if path is writable.
             
             Parameters
             ----------
             path : str or Path
                 Path to check
                 
             Returns
             -------
             bool
                 True if path is writable
             """
             path = Path(path).expanduser().resolve()
             
             if path.exists():
                 return os.access(path, os.W_OK)
                 
             # Path doesn't exist, check parent directory
             return os.access(path.parent, os.W_OK)
     
     
     def ensure_directory(path: t.Union[str, Path], mode: int = 0o755) -> Path:
         """Ensure directory exists with proper permissions."""
         manager = FilesystemManager()
         return manager.ensure_directory(path, mode)
     ```

### D. Add Simulation Capabilities

1. **Add Network Simulation**
   - Create a network simulation module in `src/vcspull/_internal/testing/network.py`:
     ```python
     """Network simulation for testing."""
     
     import logging
     import random
     import threading
     import time
     import typing as t
     
     from vcspull.exc import NetworkError
     
     log = logging.getLogger(__name__)
     
     
     class NetworkCondition:
         """Base class for network conditions."""
         
         def __init__(self, probability: float = 1.0, duration: t.Optional[float] = None):
             """Initialize network condition.
             
             Parameters
             ----------
             probability : float
                 Probability (0.0-1.0) of condition applying
             duration : float, optional
                 Duration of condition in seconds, None for persistent
             """
             self.probability = max(0.0, min(1.0, probability))
             self.duration = duration
             self.start_time = None
             
         def start(self):
             """Start the condition."""
             self.start_time = time.time()
             log.debug(f"Started network condition: {self.__class__.__name__}")
             
         def is_active(self) -> bool:
             """Check if condition is active."""
             if self.start_time is None:
                 return False
                 
             if self.duration is None:
                 return True
                 
             elapsed = time.time() - self.start_time
             return elapsed < self.duration
             
         def should_apply(self) -> bool:
             """Check if condition should be applied."""
             if not self.is_active():
                 return False
                 
             return random.random() < self.probability
             
         def apply(self, request_func, *args, **kwargs):
             """Apply the condition."""
             raise NotImplementedError("Subclasses must implement apply()")
     
     
     class NetworkOutage(NetworkCondition):
         """Simulate complete network outage."""
         
         def apply(self, request_func, *args, **kwargs):
             """Apply the network outage."""
             if self.should_apply():
                 log.debug("Simulating network outage")
                 raise NetworkError(
                     "Simulated network outage",
                     url=kwargs.get('url', None)
                 )
             
             return request_func(*args, **kwargs)
     
     
     class NetworkLatency(NetworkCondition):
         """Simulate network latency."""
         
         def __init__(self, min_delay: float = 0.5, max_delay: float = 2.0, **kwargs):
             """Initialize network latency.
             
             Parameters
             ----------
             min_delay : float
                 Minimum delay in seconds
             max_delay : float
                 Maximum delay in seconds
             **kwargs
                 Additional parameters for NetworkCondition
             """
             super().__init__(**kwargs)
             self.min_delay = min_delay
             self.max_delay = max_delay
             
         def apply(self, request_func, *args, **kwargs):
             """Apply the network latency."""
             if self.should_apply():
                 delay = random.uniform(self.min_delay, self.max_delay)
                 log.debug(f"Simulating network latency: {delay:.2f}s")
                 time.sleep(delay)
             
             return request_func(*args, **kwargs)
     
     
     class RateLimiting(NetworkCondition):
         """Simulate rate limiting."""
         
         def __init__(self, status_code: int = 429, retry_after: t.Optional[float] = None, **kwargs):
             """Initialize rate limiting.
             
             Parameters
             ----------
             status_code : int
                 HTTP status code to return
             retry_after : float, optional
                 Value for Retry-After header
             **kwargs
                 Additional parameters for NetworkCondition
             """
             super().__init__(**kwargs)
             self.status_code = status_code
             self.retry_after = retry_after
             
         def apply(self, request_func, *args, **kwargs):
             """Apply the rate limiting."""
             if self.should_apply():
                 log.debug(f"Simulating rate limiting: status={self.status_code}")
                 
                 # Create response-like object with status code
                 class MockResponse:
                     def __init__(self, status_code, headers=None):
                         self.status_code = status_code
                         self.headers = headers or {}
                         
                 headers = {}
                 if self.retry_after is not None:
                     headers['Retry-After'] = str(self.retry_after)
                     
                 return MockResponse(self.status_code, headers)
             
             return request_func(*args, **kwargs)
     
     
     class NetworkSimulator:
         """Network condition simulator."""
         
         def __init__(self):
             self.conditions = []
             self.lock = threading.RLock()
             
         def add_condition(self, condition: NetworkCondition) -> NetworkCondition:
             """Add a network condition.
             
             Parameters
             ----------
             condition : NetworkCondition
                 Network condition to add
                 
             Returns
             -------
             NetworkCondition
                 The added condition
             """
             with self.lock:
                 condition.start()
                 self.conditions.append(condition)
                 return condition
                 
         def remove_condition(self, condition: NetworkCondition) -> None:
             """Remove a network condition."""
             with self.lock:
                 if condition in self.conditions:
                     self.conditions.remove(condition)
                     
         def clear_conditions(self) -> None:
             """Remove all network conditions."""
             with self.lock:
                 self.conditions.clear()
                 
         def wrap_request(self, request_func):
             """Wrap a request function with network conditions."""
             def wrapped(*args, **kwargs):
                 current_func = request_func
                 
                 # Apply conditions in reverse order (newest first)
                 with self.lock:
                     active_conditions = [c for c in self.conditions if c.is_active()]
                     
                 for condition in reversed(active_conditions):
                     # Create a closure over the current function
                     prev_func = current_func
                     condition_func = lambda *a, **kw: condition.apply(prev_func, *a, **kw)
                     current_func = condition_func
                     
                 return current_func(*args, **kwargs)
                 
             return wrapped
     
     
     # Global network simulator instance
     _network_simulator = NetworkSimulator()
     
     
     def get_network_simulator():
         """Get the global network simulator."""
         return _network_simulator
     
     
     def simulate_network_condition(condition_type: str, duration: t.Optional[float] = None, **kwargs):
         """Simulate network condition.
         
         Parameters
         ----------
         condition_type : str
             Type of condition ('outage', 'latency', 'rate_limit')
         duration : float, optional
             Duration of condition in seconds
         **kwargs
             Additional parameters for specific condition type
             
         Returns
         -------
         NetworkCondition
             The created network condition
         """
         simulator = get_network_simulator()
         
         if condition_type == 'outage':
             condition = NetworkOutage(duration=duration, **kwargs)
         elif condition_type == 'latency':
             condition = NetworkLatency(duration=duration, **kwargs)
         elif condition_type == 'rate_limit':
             condition = RateLimiting(duration=duration, **kwargs)
         else:
             raise ValueError(f"Unknown network condition type: {condition_type}")
             
         return simulator.add_condition(condition)
     
     
     # Monkey-patching functions for testing
     def patch_network_manager():
         """Patch the NetworkManager class for simulation."""
         from vcspull._internal.network import NetworkManager
         
         # Store original request method
         original_request = NetworkManager.request
         
         # Replace with wrapped version
         def patched_request(self, *args, **kwargs):
             simulator = get_network_simulator()
             wrapped = simulator.wrap_request(original_request)
             return wrapped(self, *args, **kwargs)
             
         NetworkManager.request = patched_request
         log.debug("Patched NetworkManager.request for network simulation")
     ```

2. **Add Repository State Simulation**
   - Create a repository state simulation module in `src/vcspull/_internal/testing/repo.py`:
     ```python
     """Repository state simulation for testing."""
     
     import logging
     import os
     import random
     import string
     import subprocess
     import typing as t
     from pathlib import Path
     
     from vcspull.exc import RepositoryStateError
     from vcspull._internal.shell import execute_command
     
     log = logging.getLogger(__name__)
     
     
     def create_random_content(size: int = 100) -> str:
         """Create random text content.
         
         Parameters
         ----------
         size : int
             Size of content in characters
             
         Returns
         -------
         str
             Random content
         """
         return ''.join(random.choices(
             string.ascii_letters + string.digits + string.whitespace,
             k=size
         ))
     
     
     def simulate_repository_state(repo_path: t.Union[str, Path], state_type: str, **kwargs):
         """Simulate repository state.
         
         Parameters
         ----------
         repo_path : str or Path
             Path to repository
         state_type : str
             Type of state to simulate
         **kwargs
             Additional parameters for specific state type
             
         Returns
         -------
         dict
             Information about the simulated state
         """
         repo_path = Path(repo_path).expanduser().resolve()
         
         # Validate repository
         if not (repo_path / '.git').is_dir():
             raise RepositoryStateError(
                 "Not a Git repository",
                 repo_path=str(repo_path),
                 expected_state="git repository"
             )
             
         if state_type == 'detached_head':
             return simulate_detached_head(repo_path, **kwargs)
         elif state_type == 'uncommitted_changes':
             return simulate_uncommitted_changes(repo_path, **kwargs)
         elif state_type == 'merge_conflict':
             return simulate_merge_conflict(repo_path, **kwargs)
         elif state_type == 'corrupt':
             return simulate_corrupt_repo(repo_path, **kwargs)
         elif state_type == 'empty':
             return simulate_empty_repo(repo_path, **kwargs)
         else:
             raise ValueError(f"Unknown repository state type: {state_type}")
     
     
     def simulate_detached_head(repo_path: Path, commit: t.Optional[str] = None) -> dict:
         """Simulate detached HEAD state.
         
         Parameters
         ----------
         repo_path : Path
             Path to repository
         commit : str, optional
             Specific commit to checkout, defaults to a random previous commit
             
         Returns
         -------
         dict
             Information about the simulated state
         """
         log.debug(f"Simulating detached HEAD state for {repo_path}")
         
         # Get commit if not specified
         if commit is None:
             # Get a commit from history (not the latest)
             result = execute_command(
                 "git log --format=%H -n 10",
                 cwd=str(repo_path),
                 check=True
             )
             commits = result.stdout.strip().split('\n')
             if len(commits) > 1:
                 # Use a commit that's not the latest
                 commit = commits[min(1, len(commits) - 1)]
             else:
                 commit = commits[0]
             
         # Checkout the commit
         result = execute_command(
             f"git checkout {commit}",
             cwd=str(repo_path),
             check=True
         )
         
         return {
             'state_type': 'detached_head',
             'commit': commit,
             'output': result.stdout
         }
     
     
     def simulate_uncommitted_changes(repo_path: Path, 
                                    num_files: int = 3, 
                                    staged: bool = False) -> dict:
         """Simulate uncommitted changes.
         
         Parameters
         ----------
         repo_path : Path
             Path to repository
         num_files : int
             Number of files to modify
         staged : bool
             Whether to stage the changes
             
         Returns
         -------
         dict
             Information about the simulated state
         """
         log.debug(f"Simulating uncommitted changes for {repo_path}")
         
         # Find existing files to modify
         result = execute_command(
             "git ls-files",
             cwd=str(repo_path),
             check=True
         )
         existing_files = result.stdout.strip().split('\n')
         
         if not existing_files or existing_files[0] == '':
             # No existing files, create new ones
             modified_files = []
             for i in range(num_files):
                 filename = f"file_{i}.txt"
                 file_path = repo_path / filename
                 file_path.write_text(create_random_content())
                 modified_files.append(filename)
         else:
             # Modify existing files
             modified_files = []
             for i in range(min(num_files, len(existing_files))):
                 filename = random.choice(existing_files)
                 file_path = repo_path / filename
                 
                 if file_path.exists() and file_path.is_file():
                     # Append content to file
                     with open(file_path, 'a') as f:
                         f.write(f"\n\n# Modified for testing at {time.time()}\n")
                         f.write(create_random_content())
                         
                     modified_files.append(filename)
                     
         # Stage changes if requested
         if staged and modified_files:
             files_arg = ' '.join(modified_files)
             execute_command(
                 f"git add {files_arg}",
                 cwd=str(repo_path)
             )
             
         return {
             'state_type': 'uncommitted_changes',
             'modified_files': modified_files,
             'staged': staged
         }
     
     
     def simulate_merge_conflict(repo_path: Path, branch_name: t.Optional[str] = None) -> dict:
         """Simulate merge conflict.
         
         Parameters
         ----------
         repo_path : Path
             Path to repository
         branch_name : str, optional
             Name of branch to create and merge, defaults to a random name
             
         Returns
         -------
         dict
             Information about the simulated state
         """
         log.debug(f"Simulating merge conflict for {repo_path}")
         
         if branch_name is None:
             branch_name = f"test-branch-{random.randint(1000, 9999)}"
             
         # Create a new branch
         execute_command(
             f"git checkout -b {branch_name}",
             cwd=str(repo_path),
             check=True
         )
         
         # Find a file to modify
         result = execute_command(
             "git ls-files",
             cwd=str(repo_path),
             check=True
         )
         existing_files = result.stdout.strip().split('\n')
         
         if not existing_files or existing_files[0] == '':
             # No existing files, create a new one
             filename = "README.md"
             file_path = repo_path / filename
             file_path.write_text("# Test Repository\n\nThis is a test file.\n")
             execute_command(
                 f"git add {filename}",
                 cwd=str(repo_path),
                 check=True
             )
             execute_command(
                 'git commit -m "Add README.md"',
                 cwd=str(repo_path),
                 check=True
             )
         else:
             filename = existing_files[0]
             
         # Modify the file on the branch
         file_path = repo_path / filename
         with open(file_path, 'a') as f:
             f.write("\n\n# Branch modification\n")
             f.write(create_random_content())
             
         # Commit the change
         execute_command(
             f"git add {filename}",
             cwd=str(repo_path),
             check=True
         )
         execute_command(
             'git commit -m "Modify file on branch"',
             cwd=str(repo_path),
             check=True
         )
         
         # Go back to main branch
         execute_command(
             "git checkout main || git checkout master",
             cwd=str(repo_path),
             shell=True,
             check=True
         )
         
         # Modify the same file on main
         with open(file_path, 'a') as f:
             f.write("\n\n# Main branch modification\n")
             f.write(create_random_content())
             
         # Commit the change
         execute_command(
             f"git add {filename}",
             cwd=str(repo_path),
             check=True
         )
         execute_command(
             'git commit -m "Modify file on main"',
             cwd=str(repo_path),
             check=True
         )
         
         # Try to merge, which should cause a conflict
         try:
             execute_command(
                 f"git merge {branch_name}",
                 cwd=str(repo_path),
                 check=False
             )
         except Exception as e:
             log.debug(f"Expected merge conflict: {str(e)}")
             
         return {
             'state_type': 'merge_conflict',
             'branch_name': branch_name,
             'conflicted_file': filename
         }
     ```

## 2. Additional Tests to Add

### A. Configuration and Validation Tests

1. **Malformed Configuration Tests**
   - Test with invalid YAML syntax:
     ```python
     def test_invalid_yaml_syntax():
         """Test handling of invalid YAML syntax."""
         invalid_yaml = """
         /home/user/repos:
           repo1: git+https://github.com/user/repo1
           # Missing colon
           repo2 git+https://github.com/user/repo2
         """
         
         with pytest.raises(ConfigurationError) as excinfo:
             ConfigReader._load(fmt="yaml", content=invalid_yaml)
             
         assert "YAML syntax error" in str(excinfo.value)
     ```
   
   - Test with invalid JSON syntax:
     ```python
     def test_invalid_json_syntax():
         """Test handling of invalid JSON syntax."""
         invalid_json = """
         {
             "/home/user/repos": {
                 "repo1": "git+https://github.com/user/repo1",
                 "repo2": "git+https://github.com/user/repo2"
             }, // Invalid trailing comma
         }
         """
         
         with pytest.raises(ConfigurationError) as excinfo:
             ConfigReader._load(fmt="json", content=invalid_json)
             
         assert "JSON syntax error" in str(excinfo.value)
     ```
   
   - Test with incorrect indentation in YAML:
     ```python
     def test_yaml_indentation_error():
         """Test handling of incorrect YAML indentation."""
         bad_indentation = """
         /home/user/repos:
           repo1: git+https://github.com/user/repo1
          repo2: git+https://github.com/user/repo2  # Wrong indentation
         """
         
         with pytest.raises(ConfigurationError) as excinfo:
             ConfigReader._load(fmt="yaml", content=bad_indentation)
             
         assert "indentation" in str(excinfo.value).lower()
     ```
   
   - Test with duplicate keys:
     ```python
     def test_duplicate_keys():
         """Test handling of duplicate keys in configuration."""
         duplicate_keys = """
         /home/user/repos:
           repo1: git+https://github.com/user/repo1
           repo1: git+https://github.com/user/another-repo1  # Duplicate key
         """
         
         # YAML parser might overwrite the first value, but we should detect this
         with pytest.warns(UserWarning):
             config = ConfigReader._load(fmt="yaml", content=duplicate_keys)
             
         assert is_valid_config(config)
         
         # Check that we have the correct repository (second one should win)
         repos = extract_repos(config)
         assert len(repos) == 1
         assert repos[0]['url'] == "git+https://github.com/user/another-repo1"
     ```

2. **URL Validation Tests**
   - Test with invalid URL schemes:
     ```python
     def test_invalid_url_scheme():
         """Test handling of invalid URL schemes."""
         invalid_scheme = """
         /home/user/repos:
           repo1: github+https://github.com/user/repo1  # Invalid scheme
         """
         
         config = ConfigReader._load(fmt="yaml", content=invalid_scheme)
         
         with pytest.raises(ValidationError) as excinfo:
             validate_repos(config)
             
         assert "Invalid URL scheme" in str(excinfo.value)
         assert "github+" in str(excinfo.value)
         assert "git+, svn+, hg+" in str(excinfo.value)
     ```
   
   - Test with missing protocol prefixes:
     ```python
     def test_missing_protocol_prefix():
         """Test handling of URLs with missing protocol prefixes."""
         missing_prefix = """
         /home/user/repos:
           repo1: https://github.com/user/repo1  # Missing git+ prefix
         """
         
         config = ConfigReader._load(fmt="yaml", content=missing_prefix)
         
         with pytest.raises(ValidationError) as excinfo:
             validate_repos(config)
             
         assert "Missing protocol prefix" in str(excinfo.value)
         assert "Try adding a prefix like 'git+'" in str(excinfo.value)
     ```
   
   - Test with special characters in URLs:
     ```python
     def test_special_chars_in_url():
         """Test handling of URLs with special characters."""
         special_chars = """
         /home/user/repos:
           repo1: git+https://github.com/user/repo with spaces
           repo2: git+https://github.com/user/repo%20with%20encoded%20spaces
         """
         
         config = ConfigReader._load(fmt="yaml", content=special_chars)
         
         # First repo should fail validation
         with pytest.raises(ValidationError) as excinfo:
             validate_repos(config)
             
         assert "Invalid URL" in str(excinfo.value)
         assert "spaces" in str(excinfo.value)
         
         # Second repo with encoded spaces should be valid
         valid_config = """
         /home/user/repos:
           repo2: git+https://github.com/user/repo%20with%20encoded%20spaces
         """
         
         config = ConfigReader._load(fmt="yaml", content=valid_config)
         assert validate_repos(config)
     ```
   
   - Test with extremely long URLs:
     ```python
     def test_extremely_long_url():
         """Test handling of extremely long URLs."""
         # Create a URL that exceeds normal length limits
         very_long_path = "x" * 2000
         long_url = f"""
         /home/user/repos:
           repo1: git+https://github.com/user/{very_long_path}
         """
         
         config = ConfigReader._load(fmt="yaml", content=long_url)
         
         with pytest.raises(ValidationError) as excinfo:
             validate_repos(config)
             
         assert "URL exceeds maximum length" in str(excinfo.value)
     ```

3. **Path Validation Tests**
   - Test with path traversal attempts:
     ```python
     def test_path_traversal():
         """Test handling of path traversal attempts."""
         traversal_path = """
         /home/user/repos:
           ../etc/passwd: git+https://github.com/user/repo  # Path traversal
         """
         
         config = ConfigReader._load(fmt="yaml", content=traversal_path)
         
         with pytest.raises(ValidationError) as excinfo:
             validate_repos(config)
             
         assert "Path traversal attempt" in str(excinfo.value)
         assert "security risk" in str(excinfo.value)
     ```
   
   - Test with invalid characters in paths:
     ```python
     def test_invalid_path_chars():
         """Test handling of invalid characters in paths."""
         invalid_chars = """
         /home/user/repos:
           "repo*with*stars": git+https://github.com/user/repo
           "repo:with:colons": git+https://github.com/user/repo
         """
         
         config = ConfigReader._load(fmt="yaml", content=invalid_chars)
         
         with pytest.raises(ValidationError) as excinfo:
             validate_repos(config)
             
         assert "Invalid characters in path" in str(excinfo.value)
     ```
   
   - Test with unicode characters in paths:
     ```python
     def test_unicode_path_chars():
         """Test handling of unicode characters in paths."""
         unicode_paths = """
         /home/user/repos:
           "репозиторий": git+https://github.com/user/repo  # Cyrillic
           "リポジトリ": git+https://github.com/user/repo  # Japanese
         """
         
         config = ConfigReader._load(fmt="yaml", content=unicode_paths)
         
         # This should be valid in modern systems
         assert validate_repos(config)
         
         # Extract and verify
         repos = extract_repos(config)
         assert len(repos) == 2
         repo_names = [r['name'] for r in repos]
         assert "репозиторий" in repo_names
         assert "リポジトリ" in repo_names
     ```
   
   - Test with extremely long paths:
     ```python
     def test_extremely_long_path():
         """Test handling of extremely long paths."""
         # Create a path that exceeds normal length limits
         very_long_name = "x" * 255  # Most filesystems have a 255 char limit
         long_path = f"""
         /home/user/repos:
           "{very_long_name}": git+https://github.com/user/repo
         """
         
         config = ConfigReader._load(fmt="yaml", content=long_path)
         
         with pytest.raises(ValidationError) as excinfo:
             validate_repos(config)
             
         assert "Path exceeds maximum length" in str(excinfo.value)
     ```

### B. VCS-Specific Operation Tests

1. **Git Branch and Tag Tests**
   - Test checkout of specific branches:
     ```python
     def test_checkout_specific_branch(tmp_path, git_remote_repo_with_branches):
         """Test checkout of a specific branch."""
         # Set up config with branch specification
         config = f"""
         {tmp_path}/repos:
           myrepo:
             url: git+file://{git_remote_repo_with_branches}
             branch: feature-branch
         """
         
         conf_obj = ConfigReader._load(fmt="yaml", content=config)
         repos = extract_repos(conf_obj)
         
         # Sync the repository
         result = sync_repositories(repos, test_mode=True)
         
         # Verify the correct branch was checked out
         repo_path = tmp_path / "repos" / "myrepo"
         branch = subprocess.check_output(
             ["git", "branch", "--show-current"],
             cwd=repo_path,
             universal_newlines=True
         ).strip()
         
         assert branch == "feature-branch"
         assert result[0]["status"] == "success"
     ```
   
   - Test checkout of specific tags:
     ```python
     def test_checkout_specific_tag(tmp_path, git_remote_repo_with_tags):
         """Test checkout of a specific tag."""
         # Set up config with tag specification
         config = f"""
         {tmp_path}/repos:
           myrepo:
             url: git+file://{git_remote_repo_with_tags}
             tag: v1.0.0
         """
         
         conf_obj = ConfigReader._load(fmt="yaml", content=config)
         repos = extract_repos(conf_obj)
         
         # Sync the repository
         result = sync_repositories(repos, test_mode=True)
         
         # Verify the correct tag was checked out
         repo_path = tmp_path / "repos" / "myrepo"
         
         # Should be in detached HEAD state
         is_detached = subprocess.call(
             ["git", "symbolic-ref", "-q", "HEAD"],
             cwd=repo_path,
             stderr=subprocess.DEVNULL,
             stdout=subprocess.DEVNULL
         ) != 0
         
         assert is_detached
         
         # Should be at the tag commit
         tag_commit = subprocess.check_output(
             ["git", "rev-parse", "v1.0.0"],
             cwd=repo_path,
             universal_newlines=True
         ).strip()
         
         head_commit = subprocess.check_output(
             ["git", "rev-parse", "HEAD"],
             cwd=repo_path,
             universal_newlines=True
         ).strip()
         
         assert head_commit == tag_commit
         assert result[0]["status"] == "success"
     ```
   
   - Test checkout of specific commits:
     ```python
     def test_checkout_specific_commit(tmp_path, git_remote_repo):
         """Test checkout of a specific commit."""
         # Get a specific commit from the remote
         commit = subprocess.check_output(
             ["git", "rev-parse", "HEAD"],
             cwd=git_remote_repo,
             universal_newlines=True
         ).strip()
         
         # Set up config with commit specification
         config = f"""
         {tmp_path}/repos:
           myrepo:
             url: git+file://{git_remote_repo}
             rev: {commit[:8]}  # Short commit hash
         """
         
         conf_obj = ConfigReader._load(fmt="yaml", content=config)
         repos = extract_repos(conf_obj)
         
         # Sync the repository
         result = sync_repositories(repos, test_mode=True)
         
         # Verify the correct commit was checked out
         repo_path = tmp_path / "repos" / "myrepo"
         head_commit = subprocess.check_output(
             ["git", "rev-parse", "HEAD"],
             cwd=repo_path,
             universal_newlines=True
         ).strip()
         
         assert head_commit.startswith(commit[:8])
         assert result[0]["status"] == "success"
     ```
   
   - Test handling of non-existent branches/tags:
     ```python
     def test_nonexistent_branch(tmp_path, git_remote_repo):
         """Test handling of non-existent branch."""
         # Set up config with non-existent branch
         config = f"""
         {tmp_path}/repos:
           myrepo:
             url: git+file://{git_remote_repo}
             branch: non-existent-branch
         """
         
         conf_obj = ConfigReader._load(fmt="yaml", content=config)
         repos = extract_repos(conf_obj)
         
         # Sync should fail with appropriate error
         with pytest.raises(VCSOperationError) as excinfo:
             sync_repositories(repos, test_mode=True)
             
         assert "non-existent-branch" in str(excinfo.value)
         assert "branch not found" in str(excinfo.value).lower()
     ```

2. **Git Submodule Tests**
   - Test repositories with submodules:
     ```python
     def test_repo_with_submodules(tmp_path, git_remote_repo_with_submodules):
         """Test handling of repository with submodules."""
         # Set up config
         config = f"""
         {tmp_path}/repos:
           myrepo:
             url: git+file://{git_remote_repo_with_submodules}
             init_submodules: true
         """
         
         conf_obj = ConfigReader._load(fmt="yaml", content=config)
         repos = extract_repos(conf_obj)
         
         # Sync the repository
         result = sync_repositories(repos, test_mode=True)
         
         # Verify the submodules were initialized
         repo_path = tmp_path / "repos" / "myrepo"
         submodule_path = repo_path / "submodule"
         
         assert submodule_path.is_dir()
         assert (submodule_path / ".git").exists()
         assert result[0]["status"] == "success"
     ```
   
   - Test submodule initialization and update:
     ```python
     def test_submodule_update(tmp_path, git_remote_repo_with_submodules):
         """Test updating submodules to latest version."""
         # Set up config
         config = f"""
         {tmp_path}/repos:
           myrepo:
             url: git+file://{git_remote_repo_with_submodules}
             init_submodules: true
             update_submodules: true
         """
         
         conf_obj = ConfigReader._load(fmt="yaml", content=config)
         repos = extract_repos(conf_obj)
         
         # Sync the repository
         result = sync_repositories(repos, test_mode=True)
         
         # Verify the submodules were updated
         repo_path = tmp_path / "repos" / "myrepo"
         
         # Check if submodule is at the correct commit
         submodule_commit = subprocess.check_output(
             ["git", "submodule", "status", "submodule"],
             cwd=repo_path,
             universal_newlines=True
         ).strip()
         
         # Submodule should not be prefixed with + (which indicates not updated)
         assert not submodule_commit.startswith("+")
         assert result[0]["status"] == "success"
     ```
   
   - Test handling of missing submodules:
     ```python
     def test_missing_submodule(tmp_path, git_remote_repo_with_missing_submodule):
         """Test handling of repository with missing submodule."""
         # Set up config
         config = f"""
         {tmp_path}/repos:
           myrepo:
             url: git+file://{git_remote_repo_with_missing_submodule}
             init_submodules: true
         """
         
         conf_obj = ConfigReader._load(fmt="yaml", content=config)
         repos = extract_repos(conf_obj)
         
         # Sync should fail with appropriate error
         with pytest.raises(VCSOperationError) as excinfo:
             sync_repositories(repos, test_mode=True)
             
         assert "submodule" in str(excinfo.value).lower()
         assert "not found" in str(excinfo.value).lower()
     ```
   
   - Test nested submodules:
     ```python
     def test_nested_submodules(tmp_path, git_remote_repo_with_nested_submodules):
         """Test handling of repository with nested submodules."""
         # Set up config with recursive submodule initialization
         config = f"""
         {tmp_path}/repos:
           myrepo:
             url: git+file://{git_remote_repo_with_nested_submodules}
             init_submodules: true
             recursive_submodules: true
         """
         
         conf_obj = ConfigReader._load(fmt="yaml", content=config)
         repos = extract_repos(conf_obj)
         
         # Sync the repository
         result = sync_repositories(repos, test_mode=True)
         
         # Verify the nested submodules were initialized
         repo_path = tmp_path / "repos" / "myrepo"
         submodule_path = repo_path / "submodule"
         nested_submodule_path = submodule_path / "nested-submodule"
         
         assert submodule_path.is_dir()
         assert nested_submodule_path.is_dir()
         assert (nested_submodule_path / ".git").exists()
         assert result[0]["status"] == "success"
     ```

3. **Repository State Tests**
   - Test handling of detached HEAD state:
     ```python
     @pytest.fixture
     def git_repo_detached_head(tmp_path, git_remote_repo):
         """Create a repository in detached HEAD state."""
         # Clone the repository
         repo_path = tmp_path / "detached-repo"
         subprocess.run(
             ["git", "clone", git_remote_repo, str(repo_path)],
             check=True
         )
         
         # Get a commit that's not HEAD
         commits = subprocess.check_output(
             ["git", "log", "--format=%H", "-n", "2"],
             cwd=repo_path,
             universal_newlines=True
         ).strip().split("\n")
         
         if len(commits) > 1:
             # Check out the previous commit (not HEAD)
             subprocess.run(
                 ["git", "checkout", commits[1]],
                 cwd=repo_path,
                 check=True
             )
             
         return repo_path
     
     def test_detached_head_recovery(git_repo_detached_head):
         """Test recovery from detached HEAD state."""
         # Set up config for existing repo
         config = f"""
         {git_repo_detached_head.parent}:
           detached-repo:
             url: file://{git_repo_detached_head}
         """
         
         conf_obj = ConfigReader._load(fmt="yaml", content=config)
         repos = extract_repos(conf_obj)
         
         # Sync the repository
         result = sync_repositories(repos, test_mode=True)
         
         # Verify HEAD is no longer detached
         is_detached = subprocess.call(
             ["git", "symbolic-ref", "-q", "HEAD"],
             cwd=git_repo_detached_head,
             stderr=subprocess.DEVNULL,
             stdout=subprocess.DEVNULL
         ) != 0
         
         assert not is_detached
         assert result[0]["status"] == "success"
     ```
   
   - Test handling of merge conflicts:
     ```python
     @pytest.fixture
     def git_repo_merge_conflict(tmp_path, git_remote_repo):
         """Create a repository with merge conflict."""
         # Clone the repository
         repo_path = tmp_path / "conflict-repo"
         subprocess.run(
             ["git", "clone", git_remote_repo, str(repo_path)],
             check=True
         )
         
         # Create and switch to a new branch
         subprocess.run(
             ["git", "checkout", "-b", "test-branch"],
             cwd=repo_path,
             check=True
         )
         
         # Find a file to modify
         files = subprocess.check_output(
             ["git", "ls-files"],
             cwd=repo_path,
             universal_newlines=True
         ).strip().split("\n")
         
         if not files:
             # Create a file if none exists
             readme = repo_path / "README.md"
             readme.write_text("# Test Repository\n")
             subprocess.run(
                 ["git", "add", "README.md"],
                 cwd=repo_path,
                 check=True
             )
             subprocess.run(
                 ["git", "commit", "-m", "Add README"],
                 cwd=repo_path,
                 check=True
             )
         else:
             filename = files[0]
             
         # Modify a file in the branch
         file_path = repo_path / filename
         with open(file_path, "a") as f:
             f.write("\n\n# Branch modification\n")
             
         subprocess.run(
             ["git", "add", filename],
             cwd=repo_path,
             check=True
         )
         subprocess.run(
             ["git", "commit", "-m", "Branch change"],
             cwd=repo_path,
             check=True
         )
         
         # Switch back to main/master
         subprocess.run(
             ["git", "checkout", "master"],
             cwd=repo_path,
             stderr=subprocess.DEVNULL,
             check=False
         ) or subprocess.run(
             ["git", "checkout", "main"],
             cwd=repo_path,
             check=True
         )
         
         # Modify the same file in main
         with open(file_path, "a") as f:
             f.write("\n\n# Main branch modification\n")
             
         subprocess.run(
             ["git", "add", filename],
             cwd=repo_path,
             check=True
         )
         subprocess.run(
             ["git", "commit", "-m", "Main change"],
             cwd=repo_path,
             check=True
         )
         
         # Attempt to merge, which will cause conflict
         subprocess.run(
             ["git", "merge", "test-branch"],
             cwd=repo_path,
             stderr=subprocess.DEVNULL,
             stdout=subprocess.DEVNULL,
             check=False
         )
         
         return repo_path
     
     def test_merge_conflict_detection(git_repo_merge_conflict):
         """Test detection of merge conflict during sync."""
         # Set up config for existing repo
         config = f"""
         {git_repo_merge_conflict.parent}:
           conflict-repo:
             url: file://{git_repo_merge_conflict}
         """
         
         conf_obj = ConfigReader._load(fmt="yaml", content=config)
         repos = extract_repos(conf_obj)
         
         # Sync should detect the conflict
         with pytest.raises(RepositoryStateError) as excinfo:
             sync_repositories(repos, test_mode=True)
             
         assert "merge conflict" in str(excinfo.value).lower()
         assert "requires manual resolution" in str(excinfo.value).lower()
     ```
   
   - Test handling of uncommitted changes:
     ```python
     @pytest.fixture
     def git_repo_uncommitted_changes(tmp_path, git_remote_repo):
         """Create a repository with uncommitted changes."""
         # Clone the repository
         repo_path = tmp_path / "uncommitted-repo"
         subprocess.run(
             ["git", "clone", git_remote_repo, str(repo_path)],
             check=True
         )
         
         # Make a change without committing
         readme = repo_path / "README.md"
         if readme.exists():
             with open(readme, "a") as f:
                 f.write("\n# Uncommitted change\n")
         else:
             readme.write_text("# Test Repository\n\n# Uncommitted change\n")
             
         return repo_path
     
     def test_uncommitted_changes_handling(git_repo_uncommitted_changes):
         """Test handling of uncommitted changes during sync."""
         # Set up config for existing repo
         config = f"""
         {git_repo_uncommitted_changes.parent}:
           uncommitted-repo:
             url: file://{git_repo_uncommitted_changes}
             # Options: stash, reset, fail
             uncommitted: fail
         """
         
         conf_obj = ConfigReader._load(fmt="yaml", content=config)
         repos = extract_repos(conf_obj)
         
         # Sync should fail due to uncommitted changes
         with pytest.raises(RepositoryStateError) as excinfo:
             sync_repositories(repos, test_mode=True)
             
         assert "uncommitted changes" in str(excinfo.value).lower()
         
         # Try with stash option
         config = f"""
         {git_repo_uncommitted_changes.parent}:
           uncommitted-repo:
             url: file://{git_repo_uncommitted_changes}
             uncommitted: stash
         """
         
         conf_obj = ConfigReader._load(fmt="yaml", content=config)
         repos = extract_repos(conf_obj)
         
         # Sync should succeed with stashing
         result = sync_repositories(repos, test_mode=True)
         
         # Verify changes were stashed
         has_changes = subprocess.check_output(
             ["git", "status", "--porcelain"],
             cwd=git_repo_uncommitted_changes,
             universal_newlines=True
         ).strip()
         
         assert not has_changes  # Working directory should be clean
         assert result[0]["status"] == "success"
     ```
   
   - Test handling of untracked files:
     ```python
     @pytest.fixture
     def git_repo_untracked_files(tmp_path, git_remote_repo):
         """Create a repository with untracked files."""
         # Clone the repository
         repo_path = tmp_path / "untracked-repo"
         subprocess.run(
             ["git", "clone", git_remote_repo, str(repo_path)],
             check=True
         )
         
         # Add untracked file
         untracked = repo_path / "untracked.txt"
         untracked.write_text("This is an untracked file")
             
         return repo_path
     
     def test_untracked_files_handling(git_repo_untracked_files):
         """Test handling of untracked files during sync."""
         # Set up config for existing repo
         config = f"""
         {git_repo_untracked_files.parent}:
           untracked-repo:
             url: file://{git_repo_untracked_files}
             # Options: keep, remove, fail
             untracked: keep
         """
         
         conf_obj = ConfigReader._load(fmt="yaml", content=config)
         repos = extract_repos(conf_obj)
         
         # Sync should succeed and keep untracked files
         result = sync_repositories(repos, test_mode=True)
         
         # Verify untracked file is still there
         untracked = git_repo_untracked_files / "untracked.txt"
         assert untracked.exists()
         assert result[0]["status"] == "success"
         
         # Try with remove option
         config = f"""
         {git_repo_untracked_files.parent}:
           untracked-repo:
             url: file://{git_repo_untracked_files}
             untracked: remove
         """
         
         conf_obj = ConfigReader._load(fmt="yaml", content=config)
         repos = extract_repos(conf_obj)
         
         # Sync should succeed and remove untracked files
         result = sync_repositories(repos, test_mode=True)
         
         # Verify untracked file is gone
         untracked = git_repo_untracked_files / "untracked.txt"
         assert not untracked.exists()
         assert result[0]["status"] == "success"
     ```

## 3. Tests Requiring Source Code Changes

### A. Tests Depending on Enhanced Exception Handling

1. **Configuration Validation Error Tests**
   - Requires specific `ValidationError` exceptions in validator module
   - Needs detailed error information in exceptions
   - Depends on new validation rules for URL schemes and paths

2. **Network Error Recovery Tests**
   - Requires `NetworkError` hierarchy
   - Needs retry mechanism in network operations
   - Depends on error recovery enhancements

3. **Authentication Failure Tests**
   - Requires `AuthenticationError` exception type
   - Needs authentication state tracking
   - Depends on credential management enhancements

### B. Tests Depending on Testability Hooks

1. **Repository State Simulation Tests**
   - Requires repository state inspection methods
   - Needs hooks to create specific repository states
   - Depends on state tracking enhancements

2. **Network Condition Simulation Tests**
   - Requires network simulation capabilities
   - Needs hooks to inject network behaviors
   - Depends on network operation abstraction

3. **Dependency Injection Tests**
   - Requires refactored code with injectable dependencies
   - Needs mock objects for VCS operations, network, etc.
   - Depends on decoupled components

### C. Tests Depending on Separated Concerns

1. **Shell Command Execution Tests**
   - Requires extracted shell command execution module
   - Needs ability to mock command execution
   - Depends on command execution abstraction

2. **Filesystem Operation Tests**
   - Requires extracted filesystem operation module
   - Needs ability to mock filesystem operations
   - Depends on filesystem abstraction

### D. Implementation Priority

1. **High Priority (Immediate Impact)**
   - Enhance exception hierarchy
   - Add repository state inspection methods
   - Create validation error tests
   - Add basic network error tests

2. **Medium Priority (Important but Less Urgent)**
   - Implement dependency injection
   - Extract shell command execution
   - Create submodule handling tests
   - Add authentication tests

3. **Lower Priority (Future Improvements)**
   - Add simulation capabilities
   - Create performance tests
   - Add platform-specific tests
   - Implement advanced feature tests

## Implementation Timeline

1. **Phase 1 (1-2 weeks)**
   - Enhance exception handling in source code
   - Add basic testability hooks
   - Create initial validation tests
   - Add repository state tests

2. **Phase 2 (2-4 weeks)**
   - Separate concerns in source code
   - Add dependency injection
   - Create network error tests
   - Add authentication tests

3. **Phase 3 (4-8 weeks)**
   - Add simulation capabilities
   - Create performance tests
   - Add platform-specific tests
   - Implement advanced feature tests

## Success Metrics

1. **Coverage Metrics**
   - Increase overall coverage to 90%+
   - Achieve 100% coverage for critical paths
   - Ensure all exception handlers are tested

2. **Quality Metrics**
   - Reduce bug reports related to error handling
   - Improve reliability in unstable network conditions
   - Support all target platforms reliably
   - Eliminate type-related runtime errors

3. **Maintenance Metrics**
   - Reduce time to diagnose issues
   - Improve speed of adding new features
   - Increase confidence in code changes

4. **Type Safety Metrics**
   - Pass mypy in strict mode with zero warnings
   - Every function has proper type annotations
   - Properly handle typed errors with specificity
   - Document complex types with aliases for readability

5. **Documentation Metrics**
   - All public APIs have comprehensive docstrings with type information
   - Examples demonstrate correct type usage
   - Error scenarios are documented with error type information
   - Exception hierarchies are clearly documented

## 2. Pydantic Integration for Enhanced Validation

VCSPull will use Pydantic for improved type safety, validation, and error handling. This section outlines the comprehensive plan for implementing Pydantic models throughout the codebase.

### A. Current Progress

#### Completed Tasks

1. **Core Pydantic Models**
   - ✅ Implemented `RepositoryModel` for repository configuration
   - ✅ Implemented `ConfigSectionModel` and `ConfigModel` for complete configuration
   - ✅ Added raw models (`RawRepositoryModel`, `RawConfigSectionModel`, `RawConfigModel`) for initial parsing
   - ✅ Implemented field validators for VCS types, paths, and URLs

2. **Validator Module Updates**
   - ✅ Replaced manual validators with Pydantic-based validation
   - ✅ Integrated Pydantic validation errors with VCSPull exceptions
   - ✅ Created utilities for formatting Pydantic error messages
   - ✅ Maintained the same API for existing validation functions

3. **Validator Module Tests**
   - ✅ Updated test cases to use Pydantic models
   - ✅ Added tests for Pydantic-specific validation features
   - ✅ Enhanced test coverage for edge cases

### B. Model Architecture

The Pydantic models follow a hierarchical structure aligned with the configuration data:

```
ConfigModel
└── ConfigSectionModel (for each section)
    └── RepositoryModel (for each repository)
        └── GitRemote (for Git remotes)
```

For initial parsing without validation, a parallel hierarchy is used:

```
RawConfigModel
└── RawConfigSectionModel (for each section)
    └── RawRepositoryModel (for each repository)
```

### C. Implementation Plan

#### Phase 1: Core Model Implementation

1. **Model Definitions**
   - Define core Pydantic models to replace TypedDict definitions
   - Add field validators with meaningful error messages
   - Implement serialization and deserialization methods
   - Example implementation:

```python
import enum
import pathlib
import typing as t
import pydantic

class VCSType(str, enum.Enum):
    """Valid version control system types."""
    GIT = "git"
    MERCURIAL = "hg"
    SUBVERSION = "svn"

class RawRepositoryModel(pydantic.BaseModel):
    """Raw repository configuration before validation."""
    
    class Config:
        """Pydantic model configuration."""
        extra = pydantic.Extra.allow
    
    # Required fields
    url: t.Optional[str] = None
    repo_name: t.Optional[str] = None
    vcs: t.Optional[str] = None
    
    # Optional fields with defaults
    remotes: t.Dict[str, str] = {}
    rev: t.Optional[str] = None

class RepositoryModel(pydantic.BaseModel):
    """Validated repository configuration."""
    
    class Config:
        """Pydantic model configuration."""
        extra = pydantic.Extra.forbid
    
    # Required fields with validation
    url: pydantic.HttpUrl
    repo_name: str
    vcs: VCSType
    
    # Optional fields with defaults
    remotes: t.Dict[str, pydantic.HttpUrl] = {}
    rev: t.Optional[str] = None
    path: pathlib.Path
    
    @pydantic.validator("repo_name")
    def validate_repo_name(cls, value: str) -> str:
        """Validate repository name."""
        if not value:
            raise ValueError("Repository name cannot be empty")
        if "/" in value or "\\" in value:
            raise ValueError("Repository name cannot contain path separators")
        return value
    
    @pydantic.root_validator
    def validate_remotes(cls, values: t.Dict[str, t.Any]) -> t.Dict[str, t.Any]:
        """Validate remotes against the main URL."""
        url = values.get("url")
        remotes = values.get("remotes", {})
        
        if "origin" in remotes and url != remotes["origin"]:
            raise ValueError(
                "When 'origin' remote is specified, it must match the main URL"
            )
        
        return values
```

2. **Exception Integration**
   - Adapt Pydantic validation errors to VCSPull exception hierarchy
   - Add context and suggestions to validation errors
   - Implement improved error messages for end users

```python
import typing as t
import pydantic

from vcspull import exc

def convert_pydantic_error(
    error: pydantic.ValidationError, 
    config_type: str = "repository"
) -> exc.ValidationError:
    """Convert Pydantic validation error to VCSPull validation error."""
    # Extract the first error for a focused message
    error_details = error.errors()[0]
    location = ".".join(str(loc) for loc in error_details["loc"])
    message = f"Invalid {config_type} configuration at '{location}': {error_details['msg']}"
    
    # Determine field-specific context
    path = None
    url = None
    suggestion = None
    
    if "url" in error_details["loc"]:
        url = error_details.get("input")
        suggestion = "Ensure the URL is properly formatted with scheme (e.g., https://)"
    elif "path" in error_details["loc"]:
        path = error_details.get("input")
        suggestion = "Ensure the path exists and is accessible"
    
    return exc.ValidationError(
        message,
        config_type=config_type,
        path=path,
        url=url,
        suggestion=suggestion
    )
```

#### Phase 2: Configuration Module Updates

1. **Config Processing**
   - Update config.py to use Pydantic models
   - Implement conversion between raw and validated models
   - Ensure backward compatibility with existing code
   - Example implementation:

```python
import os
import pathlib
import typing as t
import pydantic

from vcspull import models
from vcspull import exc

def load_config(
    config_file: t.Union[str, pathlib.Path]
) -> models.ConfigModel:
    """Load and validate configuration file using Pydantic."""
    config_path = pathlib.Path(os.path.expanduser(config_file))
    
    if not config_path.exists():
        raise exc.ConfigurationError(f"Config file not found: {config_path}")
    
    try:
        # First pass: load raw config with minimal validation
        with open(config_path, "r") as f:
            raw_data = yaml.safe_load(f)
        
        # Parse with raw model allowing extra fields
        raw_config = models.RawConfigModel.parse_obj(raw_data)
        
        # Process raw config (expand variables, resolve paths, etc.)
        processed_data = process_raw_config(raw_config, base_path=config_path.parent)
        
        # Final validation with strict model
        return models.ConfigModel.parse_obj(processed_data)
    except yaml.YAMLError as e:
        raise exc.ConfigurationError(f"Invalid YAML in config: {e}")
    except pydantic.ValidationError as e:
        raise convert_pydantic_error(e, config_type="config")
```

2. **Config Reader Updates**
   - Update internal config reader to use Pydantic models
   - Implement path normalization and environment variable expansion
   - Add serialization for different output formats
   - Add more robust validation for complex configurations

#### Phase 3: CLI and Sync Operations Updates

1. **CLI Module**
   - Update CLI commands to work with Pydantic models
   - Enhance error reporting with validation details
   - Add schema validation for command line options

2. **Sync Operations**
   - Update sync operations to use validated models
   - Improve error handling with model validation
   - Add type safety to repository operations

### D. Testing Strategy

1. **Model Tests**
   - Unit tests for model instantiation and validation
   - Tests for all field validators and constraints
   - Property-based testing for model validation
   - Example test:

```python
import pathlib
import typing as t
import pytest
import pydantic

from vcspull.models import RepositoryModel, VCSType

class TestRepositoryModel:
    """Tests for the RepositoryModel."""
    
    def test_valid_repository(self) -> None:
        """Test that a valid repository configuration passes validation."""
        repo = RepositoryModel(
            url="https://github.com/example/repo.git",
            repo_name="repo",
            vcs=VCSType.GIT,
            path=pathlib.Path("/tmp/repos/repo")
        )
        
        assert repo.url == "https://github.com/example/repo.git"
        assert repo.repo_name == "repo"
        assert repo.vcs == VCSType.GIT
        assert repo.path == pathlib.Path("/tmp/repos/repo")
    
    def test_invalid_url(self) -> None:
        """Test that invalid URLs are rejected."""
        with pytest.raises(pydantic.ValidationError) as exc_info:
            RepositoryModel(
                url="not-a-url",
                repo_name="repo",
                vcs=VCSType.GIT,
                path=pathlib.Path("/tmp/repos/repo")
            )
        
        error_msg = str(exc_info.value)
        assert "url" in error_msg
        assert "invalid or missing URL scheme" in error_msg
    
    def test_invalid_repo_name(self) -> None:
        """Test that invalid repository names are rejected."""
        with pytest.raises(pydantic.ValidationError) as exc_info:
            RepositoryModel(
                url="https://github.com/example/repo.git",
                repo_name="invalid/name",
                vcs=VCSType.GIT,
                path=pathlib.Path("/tmp/repos/repo")
            )
        
        error_msg = str(exc_info.value)
        assert "repo_name" in error_msg
        assert "cannot contain path separators" in error_msg
```

2. **Integration Tests**
   - Tests for loading configurations from files
   - End-to-end tests for validation and error handling
   - Performance testing for model validation

### E. Code Style and Import Guidelines

When implementing Pydantic models, follow these guidelines:

1. **Namespace Imports**:
   ```python
   # DO:
   import enum
   import pathlib
   import typing as t
   import pydantic
   
   # DON'T: 
   from enum import Enum
   from pathlib import Path
   from typing import List, Dict, Optional
   from pydantic import BaseModel, Field
   ```

2. **Accessing via Namespace**:
   ```python
   # DO:
   class ErrorCode(enum.Enum):
       ...
       
   repo_path = pathlib.Path("~/repos").expanduser()
   
   class RepositoryModel(pydantic.BaseModel):
       vcs: t.Literal["git", "hg", "svn"]
       url: str
       remotes: t.Dict[str, str] = {}
   ```

3. **For Primitive Types**:
   ```python
   # Preferred Python 3.9+ syntax:
   paths: list[pathlib.Path]
   settings: dict[str, str | int]
   maybe_url: str | None
   ```

### F. Expected Benefits

1. **Improved Type Safety**
   - Runtime validation with proper error messages
   - Static type checking integration with mypy
   - Self-documenting data models

2. **Better Error Messages**
   - Field-specific error details
   - Context-rich validation errors
   - Suggestions for resolving issues

3. **Reduced Boilerplate**
   - Automatic serialization and deserialization
   - Built-in validation rules
   - Simplified configuration handling

4. **Enhanced Maintainability**
   - Clear separation of validation concerns
   - Centralized data model definitions
   - Better IDE support with type hints

### G. Success Metrics

- **Type Safety**
  - Pass mypy in strict mode with zero warnings
  - 100% of functions have type annotations
  - All configuration types defined as Pydantic models

- **Test Coverage**
  - Overall test coverage > 90%
  - Core modules coverage > 95%
  - All public APIs have tests

- **Documentation**
  - All public APIs documented
  - All Pydantic models documented
  - Examples for all major features

## 3. Additional Tests to Add

### 11. Testing Pydantic Models and Validators

1. **✓ Basic Model Validation Tests**
   - ✓ Add tests for `RepositoryModel` validation:
     ```python
     import pytest
     import typing as t
     
     from vcspull.schemas import RepositoryModel
     
     def test_repository_model_valid():
         """Test valid repository model."""
         # Create a valid model
         repo = RepositoryModel(
             vcs="git",
             name="test-repo",
             path="/path/to/repo",
             url="https://github.com/user/repo",
         )
         
         # Verify basic attributes
         assert repo.vcs == "git"
         assert repo.name == "test-repo"
         assert str(repo.path).endswith("/path/to/repo")
         assert repo.url == "https://github.com/user/repo"
         
     def test_repository_model_invalid_vcs():
         """Test invalid VCS type."""
         with pytest.raises(ValueError) as excinfo:
             RepositoryModel(
                 vcs="invalid",
                 name="test-repo", 
                 path="/path/to/repo",
                 url="https://github.com/user/repo",
             )
         
         # Verify error message
         assert "Invalid VCS type" in str(excinfo.value)
     ```

2. **Pending: Path Validation Tests**
   - Create tests for path validation and normalization:
     ```python
     import os
     import pathlib
     
     def test_repository_model_path_expansion():
         """Test path expansion in repository model."""
         # Test with environment variables
         os.environ["TEST_PATH"] = "/test/path"
         repo = RepositoryModel(
             vcs="git",
             name="test-repo",
             path="${TEST_PATH}/repo",
             url="https://github.com/user/repo",
         )
         
         # Verify path expansion
         assert str(repo.path) == "/test/path/repo"
         
         # Test with tilde expansion
         repo = RepositoryModel(
             vcs="git", 
             name="test-repo",
             path="~/repo",
             url="https://github.com/user/repo",
         )
         
         # Verify tilde expansion
         assert str(repo.path) == str(pathlib.Path.home() / "repo")
     ```

3. **Pending: URL Validation Tests**
   - Test different URL formats and validation:
     ```python
     def test_repository_model_url_validation():
         """Test URL validation in repository model."""
         # Test valid URLs
         valid_urls = [
             "https://github.com/user/repo",
             "git@github.com:user/repo.git",
             "file:///path/to/repo",
         ]
         
         for url in valid_urls:
             repo = RepositoryModel(
                 vcs="git",
                 name="test-repo",
                 path="/path/to/repo",
                 url=url,
             )
             assert repo.url == url
         
         # Test invalid URLs
         invalid_urls = ["", "   "]
         
         for url in invalid_urls:
             with pytest.raises(ValueError) as excinfo:
                 RepositoryModel(
                     vcs="git",
                     name="test-repo",
                     path="/path/to/repo",
                     url=url,
                 )
             assert "URL cannot be empty" in str(excinfo.value)
     ```

4. **Pending: Configuration Dict Model Tests**
   - Test the dictionary-like behavior of config models:
     ```python
     from vcspull.schemas import ConfigSectionDictModel, RepositoryModel
     
     def test_config_section_dict_model():
         """Test ConfigSectionDictModel behavior."""
         # Create repository models
         repo1 = RepositoryModel(
             vcs="git",
             name="repo1",
             path="/path/to/repo1",
             url="https://github.com/user/repo1",
         )
         
         repo2 = RepositoryModel(
             vcs="git",
             name="repo2", 
             path="/path/to/repo2",
             url="https://github.com/user/repo2",
         )
         
         # Create section model
         section = ConfigSectionDictModel(root={"repo1": repo1, "repo2": repo2})
         
         # Test dictionary-like access
         assert section["repo1"] == repo1
         assert section["repo2"] == repo2
         
         # Test keys, values, items
         assert set(section.keys()) == {"repo1", "repo2"}
         assert list(section.values()) == [repo1, repo2]
         assert dict(section.items()) == {"repo1": repo1, "repo2": repo2}
     ```

5. **Pending: Raw to Validated Conversion Tests**
   - Test conversion from raw to validated models:
     ```python
     from vcspull.schemas import (
         RawConfigDictModel,
         convert_raw_to_validated,
     )
     
     def test_convert_raw_to_validated():
         """Test conversion from raw to validated models."""
         # Create raw config
         raw_config = RawConfigDictModel(root={
             "section1": {
                 "repo1": {
                     "vcs": "git",
                     "name": "repo1",
                     "path": "/path/to/repo1",
                     "url": "https://github.com/user/repo1",
                 },
                 "repo2": "https://github.com/user/repo2",  # Shorthand URL
             }
         })
         
         # Convert to validated config
         validated = convert_raw_to_validated(raw_config)
         
         # Verify structure
         assert "section1" in validated.root
         assert "repo1" in validated["section1"].root
         assert "repo2" in validated["section1"].root
         
         # Verify expanded shorthand URL
         assert validated["section1"]["repo2"].url == "https://github.com/user/repo2"
         assert validated["section1"]["repo2"].name == "repo2"
     ```

6. **Pending: Integration with CLI Tests**
   - Test CLI commands with Pydantic models:
     ```python
     def test_cli_with_pydantic_models(runner, tmp_path):
         """Test CLI commands with Pydantic models."""
         # Create a test config file with valid and invalid entries
         config_file = tmp_path / "config.yaml"
         config_file.write_text("""
         section1:
           repo1:
             vcs: git
             name: repo1
             path: {tmp_path}/repo1
             url: https://github.com/user/repo1
           repo2:
             vcs: invalid  # Invalid VCS type
             name: repo2
             path: {tmp_path}/repo2
             url: https://github.com/user/repo2
         """.format(tmp_path=tmp_path))
         
         # Run CLI command with the config file
         result = runner.invoke(cli, ["sync", "--config", str(config_file)])
         
         # Verify that the valid repository is processed
         assert "Processing repository repo1" in result.output
         
         # Verify that the invalid repository is reported with a Pydantic error
         assert "Invalid VCS type: invalid" in result.output
     ```

7. **Pending: Error Handling in Models**
   - Test error handling and error formatting:
     ```python
     from vcspull.validator import format_pydantic_errors
     from pydantic import ValidationError
     
     def test_format_pydantic_errors():
         """Test formatting of Pydantic validation errors."""
         try:
             RepositoryModel(
                 vcs="invalid",
                 name="",  # Empty name
                 path="",  # Empty path
                 url="",   # Empty URL
             )
         except ValidationError as e:
             # Format the error
             error_msg = format_pydantic_errors(e)
             
             # Verify formatted error message
             assert "vcs: Invalid VCS type" in error_msg
             assert "name: " in error_msg
             assert "path: " in error_msg
             assert "url: URL cannot be empty" in error_msg
     ```

8. **Pending: Advanced Validation Tests**
   - Create tests for more complex validation scenarios:
     ```python
     def test_repository_model_with_remotes():
         """Test repository model with Git remotes."""
         from vcspull.schemas import GitRemote
         
         # Create Git remotes
         remotes = {
             "origin": GitRemote(
                 name="origin",
                 url="https://github.com/user/repo",
                 fetch="+refs/heads/*:refs/remotes/origin/*",
                 push="refs/heads/*:refs/heads/*",
             ),
             "upstream": GitRemote(
                 name="upstream",
                 url="https://github.com/upstream/repo",
             ),
         }
         
         # Create repository with remotes
         repo = RepositoryModel(
             vcs="git",
             name="test-repo",
             path="/path/to/repo",
             url="https://github.com/user/repo",
             remotes=remotes,
         )
         
         # Verify remotes
         assert repo.remotes is not None
         assert "origin" in repo.remotes
         assert "upstream" in repo.remotes
         assert repo.remotes["origin"].url == "https://github.com/user/repo"
         assert repo.remotes["upstream"].url == "https://github.com/upstream/repo"
     ```

## 12. Performance Testing
