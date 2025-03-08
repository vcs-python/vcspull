# VCSPull Test Improvement Plan

This plan outlines strategies for improving the test coverage and test quality for VCSPull, focusing on addressing the gaps identified in the test audit.

## 1. Improving Testability in Source Code

### A. Enhance Exception Handling

1. **Create Specific Exception Types**
   - Create a hierarchy of exceptions with specific subtypes in `src/vcspull/exc.py`:
     ```python
     class VCSPullException(Exception):
         """Base exception for vcspull."""
     
     class ConfigurationError(VCSPullException):
         """Error in configuration format or content."""
     
     class ValidationError(ConfigurationError):
         """Error validating configuration."""
     
     class VCSOperationError(VCSPullException):
         """Error performing VCS operation."""
         
         def __init__(self, message, vcs_type=None, operation=None, repo_path=None):
             self.vcs_type = vcs_type  # git, hg, svn
             self.operation = operation  # clone, pull, checkout
             self.repo_path = repo_path
             super().__init__(f"{message} [VCS: {vcs_type}, Op: {operation}, Path: {repo_path}]")
     
     class NetworkError(VCSPullException):
         """Network-related errors."""
         
         def __init__(self, message, url=None, status_code=None, retry_count=None):
             self.url = url
             self.status_code = status_code
             self.retry_count = retry_count
             super().__init__(f"{message} [URL: {url}, Status: {status_code}, Retries: {retry_count}]")
     
     class AuthenticationError(NetworkError):
         """Authentication failures."""
         
         def __init__(self, message, url=None, auth_method=None):
             self.auth_method = auth_method  # ssh-key, username/password, token
             super().__init__(message, url=url)
     
     class RepositoryStateError(VCSPullException):
         """Error with repository state."""
         
         def __init__(self, message, repo_path=None, current_state=None, expected_state=None):
             self.repo_path = repo_path
             self.current_state = current_state
             self.expected_state = expected_state
             super().__init__(f"{message} [Path: {repo_path}, Current: {current_state}, Expected: {expected_state}]")
     ```

2. **Refactor Validator Module**
   - Update `src/vcspull/validator.py` to use the specific exception types:
     ```python
     def is_valid_config(config):
         """Check if configuration is valid."""
         if not isinstance(config, (dict, Mapping)):
             raise ValidationError("Configuration must be a dictionary", 
                                 config_type=type(config).__name__)
     ```
   
   - Add detailed error messages with context information:
     ```python
     def validate_url(url):
         """Validate repository URL."""
         vcs_types = ['git+', 'svn+', 'hg+']
         
         if not any(url.startswith(prefix) for prefix in vcs_types):
             raise ValidationError(
                 f"URL must start with one of {vcs_types}",
                 url=url,
                 suggestion=f"Try adding a prefix like 'git+' to the URL"
             )
             
         # Additional URL validation
     ```
   
   - Add validation for URL schemes, special characters, and path traversal:
     ```python
     def validate_path(path):
         """Validate repository path."""
         if '..' in path:
             raise ValidationError(
                 "Path contains potential directory traversal",
                 path=path,
                 risk="security"
             )
             
         # Check for invalid characters, length limits, etc.
     ```

3. **Enhance Error Reporting**
   - Add context information to all exceptions in `src/vcspull/cli/sync.py`:
     ```python
     try:
         repo.update()
     except Exception as e:
         # Replace with specific exception handling
         raise VCSOperationError(
             f"Failed to update repository: {str(e)}",
             vcs_type=repo.vcs,
             operation="update",
             repo_path=repo.path
         ) from e
     ```
   
   - Include recovery suggestions in error messages:
     ```python
     def handle_network_error(e, repo):
         """Handle network errors with recovery suggestions."""
         if isinstance(e, requests.ConnectionError):
             raise NetworkError(
                 "Network connection failed",
                 url=repo.url,
                 suggestion="Check network connection and try again"
             ) from e
         elif isinstance(e, requests.Timeout):
             raise NetworkError(
                 "Request timed out",
                 url=repo.url,
                 retry_count=0,
                 suggestion="Try again with a longer timeout"
             ) from e
     ```
   
   - Add error codes for programmatic handling:
     ```python
     # In src/vcspull/exc.py
     class ErrorCode(enum.Enum):
         """Error codes for VCSPull exceptions."""
         NETWORK_UNREACHABLE = 100
         AUTHENTICATION_FAILED = 101
         REPOSITORY_CORRUPT = 200
         MERGE_CONFLICT = 201
         INVALID_CONFIGURATION = 300
         PATH_TRAVERSAL = 301
     
     # Usage:
     raise NetworkError(
         "Failed to connect",
         url=repo.url,
         error_code=ErrorCode.NETWORK_UNREACHABLE
     )
     ```

### B. Add Testability Hooks

1. **Dependency Injection**
   - Refactor VCS operations in `src/vcspull/cli/sync.py` to accept injectable dependencies:
     ```python
     def update_repo(repo, vcs_factory=None, network_manager=None, fs_manager=None):
         """Update a repository with injectable dependencies.
         
         Parameters
         ----------
         repo : dict
             Repository configuration dictionary
         vcs_factory : callable, optional
             Factory function to create VCS objects
         network_manager : object, optional
             Network handling manager for HTTP operations
         fs_manager : object, optional
             Filesystem manager for disk operations
         """
         vcs_factory = vcs_factory or default_vcs_factory
         network_manager = network_manager or get_default_network_manager()
         fs_manager = fs_manager or get_default_fs_manager()
         
         # Repository creation with dependency injection
         vcs_obj = vcs_factory(
             vcs=repo['vcs'],
             url=repo['url'],
             path=repo['path'],
             network_manager=network_manager,
             fs_manager=fs_manager
         )
         
         return vcs_obj.update()
     ```

   - Create factory functions that can be mocked/replaced:
     ```python
     # In src/vcspull/_internal/factories.py
     def default_vcs_factory(vcs, url, path, **kwargs):
         """Create a VCS object based on the specified type."""
         if vcs == 'git':
             return GitSync(url=url, path=path, **kwargs)
         elif vcs == 'hg':
             return HgSync(url=url, path=path, **kwargs)
         elif vcs == 'svn':
             return SvnSync(url=url, path=path, **kwargs)
         else:
             raise ValueError(f"Unsupported VCS type: {vcs}")
             
     # Network manager factory
     def get_default_network_manager():
         """Get the default network manager."""
         from vcspull._internal.network import NetworkManager
         return NetworkManager()
         
     # Filesystem manager factory
     def get_default_fs_manager():
         """Get the default filesystem manager."""
         from vcspull._internal.fs import FilesystemManager
         return FilesystemManager()
     ```

2. **Add State Inspection Methods**
   - Create new module `src/vcspull/_internal/repo_inspector.py` for repository state inspection:
     ```python
     def get_repository_state(repo_path, vcs_type=None):
         """Return detailed repository state information.
         
         Parameters
         ----------
         repo_path : str or pathlib.Path
             Path to the repository
         vcs_type : str, optional
             VCS type (git, hg, svn) - will auto-detect if not specified
             
         Returns
         -------
         dict
             Dictionary containing repository state information
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
     
     def get_git_repository_state(repo_path):
         """Get detailed state information for Git repository."""
         import subprocess
         from pathlib import Path
         
         repo_path = Path(repo_path)
         
         # Check for .git directory
         if not (repo_path / '.git').exists():
             return {'exists': False, 'is_repo': False}
             
         # Get current branch
         try:
             branch = subprocess.check_output(
                 ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
                 cwd=repo_path,
                 universal_newlines=True
             ).strip()
         except subprocess.CalledProcessError:
             branch = None
             
         # Check if HEAD is detached
         is_detached = branch == 'HEAD'
         
         # Check for uncommitted changes
         has_changes = False
         try:
             changes = subprocess.check_output(
                 ['git', 'status', '--porcelain'],
                 cwd=repo_path,
                 universal_newlines=True
             )
             has_changes = bool(changes.strip())
         except subprocess.CalledProcessError:
             pass
             
         # Get current commit
         try:
             commit = subprocess.check_output(
                 ['git', 'rev-parse', 'HEAD'],
                 cwd=repo_path,
                 universal_newlines=True
             ).strip()
         except subprocess.CalledProcessError:
             commit = None
             
         return {
             'exists': True,
             'is_repo': True,
             'vcs_type': 'git',
             'branch': branch,
             'is_detached': is_detached,
             'has_changes': has_changes,
             'commit': commit
         }
     
     def is_detached_head(repo_path):
         """Check if Git repository is in detached HEAD state."""
         state = get_git_repository_state(repo_path)
         return state.get('is_detached', False)
     ```

3. **Add Test Mode Flag**
   - Update the primary synchronization function in `src/vcspull/cli/sync.py`:
     ```python
     def sync_repositories(repos, test_mode=False, **kwargs):
         """Sync repositories with test mode support.
         
         Parameters
         ----------
         repos : list
             List of repository dictionaries
         test_mode : bool, optional
             Enable test mode
         **kwargs
             Additional parameters to pass to update_repo
             
         Returns
         -------
         list
             List of updated repositories
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
         
         results = []
         for repo in repos:
             try:
                 result = update_repo(repo, **kwargs)
                 results.append({'name': repo['name'], 'status': 'success', 'result': result})
             except Exception as e:
                 if test_mode:
                     # In test mode, capture the exception for verification
                     results.append({'name': repo['name'], 'status': 'error', 'exception': e})
                     if kwargs.get('raise_exceptions', True):
                         raise
                 else:
                     # In normal mode, log and continue
                     log.error(f"Error updating {repo['name']}: {str(e)}")
                     results.append({'name': repo['name'], 'status': 'error', 'message': str(e)})
         
         return results
     ```

   - Create test hooks module `src/vcspull/_internal/testing/hooks.py`:
     ```python
     """Hooks for testing VCSPull."""
     
     import logging
     from functools import wraps
     
     log = logging.getLogger(__name__)
     
     # Global registry for test hooks
     _test_hooks = {}
     
     def register_test_hook(name, hook_function):
         """Register a test hook function."""
         _test_hooks[name] = hook_function
         log.debug(f"Registered test hook: {name}")
         
     def get_test_hook(name):
         """Get a registered test hook function."""
         return _test_hooks.get(name)
         
     def hook_method(cls, method_name):
         """Decorator to hook a method for testing."""
         original_method = getattr(cls, method_name)
         
         @wraps(original_method)
         def wrapped(self, *args, **kwargs):
             hook_name = f"{cls.__name__}.{method_name}"
             hook = get_test_hook(hook_name)
             
             if hook:
                 log.debug(f"Calling test hook: {hook_name}")
                 return hook(self, original_method, *args, **kwargs)
             else:
                 return original_method(self, *args, **kwargs)
                 
         setattr(cls, method_name, wrapped)
         log.debug(f"Hooked method: {cls.__name__}.{method_name}")
         
     def register_test_hooks():
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
     
     import requests
     from requests.exceptions import ConnectionError, Timeout
     
     from vcspull.exc import NetworkError
     
     log = logging.getLogger(__name__)
     
     
     class RetryStrategy:
         """Strategy for retrying network operations."""
         
         def __init__(self, max_retries=3, initial_delay=1.0, backoff_factor=2.0):
             self.max_retries = max_retries
             self.initial_delay = initial_delay
             self.backoff_factor = backoff_factor
             
         def get_delay(self, attempt):
             """Get delay for a specific retry attempt."""
             return self.initial_delay * (self.backoff_factor ** (attempt - 1))
     
     
     class NetworkManager:
         """Manager for network operations."""
         
         def __init__(self, session=None, retry_strategy=None):
             self.session = session or requests.Session()
             self.retry_strategy = retry_strategy or RetryStrategy()
             
         def request(self, method, url, **kwargs):
             """Perform HTTP request with retry logic.
             
             Parameters
             ----------
             method : str
                 HTTP method (GET, POST, etc.)
             url : str
                 URL to request
             **kwargs
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
             last_exception = None
             
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
                                 retry_count=attempt
                             )
                             continue
                         elif response.status_code == 429:
                             # Rate limiting - wait longer
                             last_exception = NetworkError(
                                 "Rate limited",
                                 url=url,
                                 status_code=429,
                                 retry_count=attempt
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
                                 status_code=response.status_code
                             )
                     
                     # Success
                     return response
                     
                 except (ConnectionError, Timeout) as e:
                     # Network errors might be temporary
                     log.warning(f"Network error on attempt {attempt}/{max_retries}: {str(e)}")
                     last_exception = NetworkError(
                         f"Network error: {str(e)}",
                         url=url,
                         retry_count=attempt
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
                 raise NetworkError(f"Failed after {max_retries} attempts", url=url)
                 
         def get(self, url, **kwargs):
             """Perform HTTP GET request."""
             return self.request('GET', url, **kwargs)
             
         def post(self, url, **kwargs):
             """Perform HTTP POST request."""
             return self.request('POST', url, **kwargs)
     
     
     def perform_request(url, auth=None, retry_strategy=None, **kwargs):
         """Perform HTTP request with configurable retry strategy."""
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
         
         def __init__(self, 
                     returncode: int, 
                     stdout: str, 
                     stderr: str, 
                     command: str,
                     cwd: t.Optional[str] = None):
             self.returncode = returncode
             self.stdout = stdout
             self.stderr = stderr
             self.command = command
             self.cwd = cwd
             
         def __bool__(self):
             """Return True if command succeeded (returncode == 0)."""
             return self.returncode == 0
             
         def __str__(self):
             """Return string representation."""
             return f"CommandResult(returncode={self.returncode}, command={self.command!r})"
             
         @property
         def success(self) -> bool:
             """Return True if command succeeded."""
             return self.returncode == 0
     
     
     class ShellCommandError(VCSPullException):
         """Error executing shell command."""
         
         def __init__(self, message: str, result: CommandResult):
             self.result = result
             super().__init__(f"{message}\nCommand: {result.command}\nExit code: {result.returncode}\nStderr: {result.stderr}")
     
     
     def execute_command(command: str, 
                        env: t.Optional[dict] = None, 
                        cwd: t.Optional[str] = None, 
                        timeout: t.Optional[float] = None,
                        check: bool = False,
                        shell: bool = False) -> CommandResult:
         """Execute shell command with configurable parameters.
         
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
                 returncode=None,  # timeout has no returncode
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
             f.write("\n# Branch modification\n")
             
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
             f.write("\n# Main modification\n")
             
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
   - Implement advanced concurrency tests
   - Create performance testing framework
   - Add platform-specific tests

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

3. **Maintenance Metrics**
   - Reduce time to diagnose issues
   - Improve speed of adding new features
   - Increase confidence in code changes
