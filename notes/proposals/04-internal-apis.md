# Internal APIs Proposal

> Restructuring internal APIs to improve maintainability, testability, and developer experience.

## Current Issues

The audit identified several issues with the internal APIs:

1. **Inconsistent Module Structure**: Module organization is inconsistent, making navigation difficult.

2. **Mixed Responsibilities**: Many modules have mixed responsibilities, violating the single responsibility principle.

3. **Unclear Function Signatures**: Functions often have ambiguous parameters and return types.

4. **Complex Function Logic**: Many functions are too large and complex, handling multiple concerns.

5. **Limited Type Annotations**: Inconsistent or missing type annotations make it difficult to understand APIs.

6. **Global State Dependence**: Many functions depend on global state, making testing difficult.

## Proposed Changes

### 1. Consistent Module Structure

1. **Standardized Module Organization**:
   - Create a clear, consistent package structure
   - Follow standard Python project layout
   - Organize functionality into logical modules

   ```
   src/vcspull/
   ├── __init__.py             # Public API exports
   ├── __main__.py             # Entry point for direct execution
   ├── _internal/              # Internal implementation details
   │   ├── __init__.py         # Private APIs
   │   ├── fs/                 # Filesystem operations
   │   │   ├── __init__.py
   │   │   ├── paths.py        # Path utilities
   │   │   └── io.py           # File I/O operations
   │   └── vcs/                # Version control implementations
   │       ├── __init__.py     # Common VCS interfaces
   │       ├── git.py          # Git implementation
   │       ├── hg.py           # Mercurial implementation
   │       └── svn.py          # Subversion implementation
   ├── config/                 # Configuration handling
   │   ├── __init__.py         # Public API for config
   │   ├── loader.py           # Config loading
   │   ├── schemas.py          # Config data models
   │   └── validation.py       # Config validation
   ├── exceptions.py           # Exception hierarchy
   ├── types.py                # Type definitions
   ├── utils.py                # General utilities
   └── cli/                    # Command-line interface
       ├── __init__.py
       ├── main.py             # CLI entry point
       └── commands/           # CLI command implementations
           ├── __init__.py
           ├── sync.py
           └── info.py
   ```

2. **Public vs Private API Separation**:
   - Clear delineation between public and internal APIs
   - Use underscore prefixes for internal modules and functions
   - Document public APIs thoroughly

### 2. Function Design Improvements

1. **Clear Function Signatures**:
   ```python
   import typing as t
   from pathlib import Path
   import enum
   from pydantic import BaseModel, Field, ConfigDict
   
   class VCSType(enum.Enum):
       """Version control system types."""
       GIT = "git"
       HG = "hg"
       SVN = "svn"
   
   class VCSInfo(BaseModel):
       """Version control repository information.
       
       Attributes
       ----
       vcs_type : VCSType
           Type of version control system
       is_detached : bool
           Whether the repository is in a detached state
       current_rev : Optional[str]
           Current revision hash/identifier
       remotes : dict[str, str]
           Dictionary of remote names to URLs
       active_branch : Optional[str]
           Name of the active branch if any
       has_uncommitted : bool
           Whether the repository has uncommitted changes
       """
       vcs_type: VCSType
       is_detached: bool = False
       current_rev: t.Optional[str] = None
       remotes: dict[str, str] = Field(default_factory=dict)
       active_branch: t.Optional[str] = None
       has_uncommitted: bool = False
       
       model_config = ConfigDict(
           frozen=False,
           extra="forbid",
       )
   
   def detect_vcs(repo_path: t.Union[str, Path]) -> t.Optional[VCSType]:
       """Detect the version control system used by a repository.
       
       Parameters
       ----
       repo_path : Union[str, Path]
           Path to the repository directory
           
       Returns
       ----
       Optional[VCSType]
           The detected VCS type, or None if not detected
       """
       path = Path(repo_path)
       
       if (path / ".git").exists():
           return VCSType.GIT
       elif (path / ".hg").exists():
           return VCSType.HG
       elif (path / ".svn").exists():
           return VCSType.SVN
       
       return None
   
   def get_repo_info(repo_path: t.Union[str, Path], vcs_type: t.Optional[VCSType] = None) -> t.Optional[VCSInfo]:
       """Get detailed information about a repository.
       
       Parameters
       ----
       repo_path : Union[str, Path]
           Path to the repository directory
       vcs_type : Optional[VCSType], optional
           VCS type if known, otherwise will be detected, by default None
           
       Returns
       ----
       Optional[VCSInfo]
           Repository information, or None if not a valid repository
       """
       path = Path(repo_path)
       
       if not path.exists():
           return None
       
       # Detect VCS type if not provided
       detected_vcs = vcs_type or detect_vcs(path)
       if not detected_vcs:
           return None
       
       # Get repository information based on VCS type
       if detected_vcs == VCSType.GIT:
           return _get_git_info(path)
       elif detected_vcs == VCSType.HG:
           return _get_hg_info(path)
       elif detected_vcs == VCSType.SVN:
           return _get_svn_info(path)
       
       return None
   ```

2. **Benefits**:
   - Consistent parameter naming and ordering
   - Clear return types with appropriate models
   - Documentation for function behavior
   - Type hints for better IDE support
   - Enumerated types for constants

### 3. Module Responsibility Separation

1. **Single Responsibility Principle**:
   - Each module has a clear, focused purpose
   - Functions have single responsibilities
   - Avoid side effects and global state

2. **Examples**:
   ```python
   # src/vcspull/_internal/fs/paths.py
   import typing as t
   from pathlib import Path
   import os
   
   def normalize_path(path: t.Union[str, Path]) -> Path:
       """Normalize a path to an absolute Path object.
       
       Parameters
       ----
       path : Union[str, Path]
           Path to normalize
           
       Returns
       ----
       Path
           Normalized path object
       """
       path_obj = Path(path).expanduser()
       return path_obj.resolve() if path_obj.exists() else path_obj.absolute()
   
   def is_subpath(path: Path, parent: Path) -> bool:
       """Check if a path is a subpath of another.
       
       Parameters
       ----
       path : Path
           Path to check
       parent : Path
           Potential parent path
           
       Returns
       ----
       bool
           True if path is a subpath of parent
       """
       try:
           path.relative_to(parent)
           return True
       except ValueError:
           return False
   
   # src/vcspull/_internal/vcs/git.py
   import typing as t
   from pathlib import Path
   import subprocess
   from ...types import VCSInfo, VCSType
   
   def is_git_repo(path: Path) -> bool:
       """Check if a directory is a Git repository.
       
       Parameters
       ----
       path : Path
           Path to check
           
       Returns
       ----
       bool
           True if the directory is a Git repository
       """
       return (path / ".git").exists()
   
   def get_git_info(path: Path) -> VCSInfo:
       """Get Git repository information.
       
       Parameters
       ----
       path : Path
           Path to the Git repository
           
       Returns
       ----
       VCSInfo
           Git repository information
       """
       # Git-specific implementation
       return VCSInfo(
           vcs_type=VCSType.GIT,
           current_rev=_get_git_revision(path),
           remotes=_get_git_remotes(path),
           active_branch=_get_git_branch(path),
           is_detached=_is_git_detached(path),
           has_uncommitted=_has_git_uncommitted(path)
       )
   ```

3. **Benefits**:
   - Clear module and function responsibilities
   - Easier to understand and maintain
   - Better testability through focused components
   - Improved code reuse

### 4. Dependency Injection and Inversion of Control

1. **Dependency Injection Pattern**:
   ```python
   import typing as t
   from pathlib import Path
   from pydantic import BaseModel
   
   class GitOptions(BaseModel):
       """Options for Git operations."""
       depth: t.Optional[int] = None
       branch: t.Optional[str] = None
       quiet: bool = False
   
   class GitClient:
       """Git client implementation."""
       
       def __init__(self, executor: t.Optional[t.Callable] = None):
           """Initialize Git client.
           
           Parameters
           ----
           executor : Optional[Callable], optional
               Command execution function, by default subprocess.run
           """
           self.executor = executor or self._default_executor
       
       def _default_executor(self, cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
           """Default command executor using subprocess.
           
           Parameters
           ----
           cmd : list[str]
               Command to execute
               
           Returns
           ----
           subprocess.CompletedProcess
               Command execution result
           """
           import subprocess
           return subprocess.run(cmd, check=False, capture_output=True, text=True, **kwargs)
       
       def clone(self, url: str, target_path: Path, options: t.Optional[GitOptions] = None) -> bool:
           """Clone a Git repository.
           
           Parameters
           ----
           url : str
               Repository URL to clone
           target_path : Path
               Target directory for the clone
           options : Optional[GitOptions], optional
               Clone options, by default None
               
           Returns
           ----
           bool
               True if clone was successful
           """
           opts = options or GitOptions()
           cmd = ["git", "clone", url, str(target_path)]
           
           if opts.depth:
               cmd.extend(["--depth", str(opts.depth)])
           
           if opts.branch:
               cmd.extend(["--branch", opts.branch])
           
           if opts.quiet:
               cmd.append("--quiet")
           
           result = self.executor(cmd)
           return result.returncode == 0
   ```

2. **Factory Functions**:
   ```python
   import typing as t
   from pathlib import Path
   import enum
   
   from .git import GitClient
   from .hg import HgClient
   from .svn import SvnClient
   
   class VCSType(enum.Enum):
       """Version control system types."""
       GIT = "git"
       HG = "hg"
       SVN = "svn"
   
   class VCSClientFactory:
       """Factory for creating VCS clients."""
       
       def __init__(self):
           """Initialize the VCS client factory."""
           self._clients = {
               VCSType.GIT: self._create_git_client,
               VCSType.HG: self._create_hg_client,
               VCSType.SVN: self._create_svn_client
           }
       
       def _create_git_client(self) -> GitClient:
           """Create a Git client.
           
           Returns
           ----
           GitClient
               Git client instance
           """
           return GitClient()
       
       def _create_hg_client(self) -> HgClient:
           """Create a Mercurial client.
           
           Returns
           ----
           HgClient
               Mercurial client instance
           """
           return HgClient()
       
       def _create_svn_client(self) -> SvnClient:
           """Create a Subversion client.
           
           Returns
           ----
           SvnClient
               Subversion client instance
           """
           return SvnClient()
       
       def get_client(self, vcs_type: VCSType):
           """Get a VCS client for the specified type.
           
           Parameters
           ----
           vcs_type : VCSType
               Type of VCS client to create
               
           Returns
           ----
           VCS client instance
               
           Raises
           ----
           ValueError
               If the VCS type is not supported
           """
           creator = self._clients.get(vcs_type)
           if not creator:
               raise ValueError(f"Unsupported VCS type: {vcs_type}")
           return creator()
   ```

3. **Benefits**:
   - Improved testability through mock injection
   - Clear dependencies between components
   - Easier to extend and modify
   - Better separation of concerns

### 5. Enhanced Type System

1. **Comprehensive Type Definitions**:
   ```python
   # src/vcspull/types.py
   import typing as t
   import enum
   from pathlib import Path
   import os
   from typing_extensions import TypeAlias, Protocol, runtime_checkable
   from pydantic import BaseModel, Field
   
   # Path types
   PathLike: TypeAlias = t.Union[str, os.PathLike, Path]
   
   # VCS types
   class VCSType(enum.Enum):
       """Version control system types."""
       GIT = "git"
       HG = "hg"
       SVN = "svn"
       
       @classmethod
       def from_string(cls, value: t.Optional[str]) -> t.Optional["VCSType"]:
           """Convert string to VCSType.
           
           Parameters
           ----
           value : Optional[str]
               String value to convert
               
           Returns
           ----
           Optional[VCSType]
               VCS type or None if not found
           """
           if not value:
               return None
           
           try:
               return cls(value.lower())
           except ValueError:
               return None
   
   # Repository info
   class VCSInfo(BaseModel):
       """Version control repository information."""
       vcs_type: VCSType
       is_detached: bool = False
       current_rev: t.Optional[str] = None
       remotes: dict[str, str] = Field(default_factory=dict)
       active_branch: t.Optional[str] = None
       has_uncommitted: bool = False
   
   # Command result
   class CommandResult(BaseModel):
       """Result of a command execution."""
       success: bool
       output: str = ""
       error: str = ""
       exit_code: int = 0
   
   # VCS client protocol
   @runtime_checkable
   class VCSClient(Protocol):
       """Protocol for VCS client implementations."""
       def clone(self, url: str, target_path: PathLike, **kwargs) -> CommandResult: ...
       def update(self, repo_path: PathLike, **kwargs) -> CommandResult: ...
       def get_info(self, repo_path: PathLike) -> VCSInfo: ...
   ```

2. **Benefits**:
   - Consistent type definitions across the codebase
   - Better IDE support and code completion
   - Improved static type checking with mypy
   - Self-documenting code structure

### 6. Error Handling Strategy

1. **Exception Hierarchy**:
   ```python
   # src/vcspull/exceptions.py
   class VCSPullError(Exception):
       """Base exception for all VCSPull errors."""
       pass
   
   class ConfigError(VCSPullError):
       """Configuration related errors."""
       pass
   
   class ValidationError(ConfigError):
       """Validation errors for configuration."""
       pass
   
   class VCSError(VCSPullError):
       """Version control system related errors."""
       pass
   
   class GitError(VCSError):
       """Git specific errors."""
       pass
   
   class HgError(VCSError):
       """Mercurial specific errors."""
       pass
   
   class SvnError(VCSError):
       """Subversion specific errors."""
       pass
   
   class RepositoryError(VCSPullError):
       """Repository related errors."""
       pass
   
   class RepositoryNotFoundError(RepositoryError):
       """Repository not found error."""
       pass
   
   class RepositoryExistsError(RepositoryError):
       """Repository already exists error."""
       
       def __init__(self, path: str, message: t.Optional[str] = None):
           """Initialize repository exists error.
           
           Parameters
           ----
           path : str
               Repository path
           message : Optional[str], optional
               Custom error message, by default None
           """
           self.path = path
           super().__init__(message or f"Repository already exists at {path}")
   ```

2. **Consistent Error Handling**:
   ```python
   from pathlib import Path
   from .exceptions import RepositoryNotFoundError, GitError
   
   def get_git_revision(repo_path: Path) -> str:
       """Get current Git revision.
       
       Parameters
       ----
       repo_path : Path
           Repository path
           
       Returns
       ----
       str
           Current revision
           
       Raises
       ----
       RepositoryNotFoundError
           If the repository does not exist
       GitError
           If there is an error getting the revision
       """
       if not repo_path.exists():
           raise RepositoryNotFoundError(f"Repository not found at {repo_path}")
       
       if not (repo_path / ".git").exists():
           raise GitError(f"Not a Git repository: {repo_path}")
       
       try:
           result = subprocess.run(
               ["git", "rev-parse", "HEAD"],
               cwd=repo_path,
               check=True,
               capture_output=True,
               text=True
           )
           return result.stdout.strip()
       except subprocess.CalledProcessError as e:
           raise GitError(f"Failed to get Git revision: {e.stderr.strip()}")
   ```

3. **Benefits**:
   - Clear error boundaries and responsibilities
   - Structured error information
   - Consistent error handling across codebase
   - Improved error reporting for users

### 7. Event-Based Architecture

1. **Event System for Cross-Component Communication**:
   ```python
   import typing as t
   import enum
   from dataclasses import dataclass
   
   class EventType(enum.Enum):
       """Types of events in the system."""
       REPO_CLONED = "repo_cloned"
       REPO_UPDATED = "repo_updated"
       REPO_SYNC_STARTED = "repo_sync_started"
       REPO_SYNC_COMPLETED = "repo_sync_completed"
       REPO_SYNC_FAILED = "repo_sync_failed"
   
   @dataclass
   class Event:
       """Base event class."""
       type: EventType
       timestamp: float
       
       @classmethod
       def create(cls, event_type: EventType, **kwargs) -> "Event":
           """Create an event.
           
           Parameters
           ----
           event_type : EventType
               Type of event
               
           Returns
           ----
           Event
               Created event
           """
           import time
           return cls(type=event_type, timestamp=time.time(), **kwargs)
   
   @dataclass
   class RepositoryEvent(Event):
       """Repository related event."""
       repo_path: str
       repo_url: str
   
   class EventListener(Protocol):
       """Protocol for event listeners."""
       def on_event(self, event: Event) -> None: ...
   
   class EventEmitter:
       """Event emitter for publishing events."""
       
       def __init__(self):
           """Initialize the event emitter."""
           self._listeners: dict[EventType, list[EventListener]] = {}
       
       def add_listener(self, event_type: EventType, listener: EventListener) -> None:
           """Add an event listener.
           
           Parameters
           ----
           event_type : EventType
               Type of event to listen for
           listener : EventListener
               Listener to add
           """
           if event_type not in self._listeners:
               self._listeners[event_type] = []
           self._listeners[event_type].append(listener)
       
       def remove_listener(self, event_type: EventType, listener: EventListener) -> None:
           """Remove an event listener.
           
           Parameters
           ----
           event_type : EventType
               Type of event to stop listening for
           listener : EventListener
               Listener to remove
           """
           if event_type in self._listeners and listener in self._listeners[event_type]:
               self._listeners[event_type].remove(listener)
       
       def emit(self, event: Event) -> None:
           """Emit an event.
           
           Parameters
           ----
           event : Event
               Event to emit
           """
           for listener in self._listeners.get(event.type, []):
               listener.on_event(event)
   ```

2. **Usage Example**:
   ```python
   class SyncProgressReporter(EventListener):
       """Repository sync progress reporter."""
       
       def on_event(self, event: Event) -> None:
           """Handle an event.
           
           Parameters
           ----
           event : Event
               Event to handle
           """
           if event.type == EventType.REPO_SYNC_STARTED and isinstance(event, RepositoryEvent):
               print(f"Started syncing: {event.repo_path}")
           elif event.type == EventType.REPO_SYNC_COMPLETED and isinstance(event, RepositoryEvent):
               print(f"Completed syncing: {event.repo_path}")
           elif event.type == EventType.REPO_SYNC_FAILED and isinstance(event, RepositoryEvent):
               print(f"Failed to sync: {event.repo_path}")
   
   class SyncManager:
       """Repository synchronization manager."""
       
       def __init__(self, event_emitter: EventEmitter):
           """Initialize sync manager.
           
           Parameters
           ----
           event_emitter : EventEmitter
               Event emitter to use
           """
           self.event_emitter = event_emitter
       
       def sync_repo(self, repo_path: str, repo_url: str) -> bool:
           """Synchronize a repository.
           
           Parameters
           ----
           repo_path : str
               Repository path
           repo_url : str
               Repository URL
               
           Returns
           ----
           bool
               True if sync was successful
           """
           # Emit sync started event
           self.event_emitter.emit(RepositoryEvent.create(
               EventType.REPO_SYNC_STARTED,
               repo_path=repo_path,
               repo_url=repo_url
           ))
           
           try:
               # Perform sync operation
               success = self._perform_sync(repo_path, repo_url)
               
               # Emit appropriate event based on result
               event_type = EventType.REPO_SYNC_COMPLETED if success else EventType.REPO_SYNC_FAILED
               self.event_emitter.emit(RepositoryEvent.create(
                   event_type,
                   repo_path=repo_path,
                   repo_url=repo_url
               ))
               
               return success
           except Exception:
               # Emit sync failed event on exception
               self.event_emitter.emit(RepositoryEvent.create(
                   EventType.REPO_SYNC_FAILED,
                   repo_path=repo_path,
                   repo_url=repo_url
               ))
               return False
   ```

3. **Benefits**:
   - Decoupled components
   - Extensible architecture
   - Easier to add new features
   - Improved testability

## Implementation Plan

1. **Phase 1: Module Reorganization**
   - Restructure modules according to new layout
   - Separate public and private APIs
   - Update import statements
   - Ensure backward compatibility during transition

2. **Phase 2: Type System Enhancement**
   - Create comprehensive type definitions
   - Define protocols for interfaces
   - Add type hints to function signatures
   - Validate with mypy

3. **Phase 3: Function Signature Standardization**
   - Standardize parameter names and ordering
   - Add clear return type annotations
   - Document parameters and return values
   - Create data models for complex returns

4. **Phase 4: Error Handling Implementation**
   - Define exception hierarchy
   - Update error handling throughout codebase
   - Add specific error types for different scenarios
   - Improve error messages and reporting

5. **Phase 5: Dependency Injection**
   - Refactor global state to injectable dependencies
   - Create factory functions for component creation
   - Implement protocols for interface contracts
   - Update tests to use dependency injection

6. **Phase 6: Event System**
   - Implement event emitter and listener pattern
   - Define standard event types
   - Update components to use events
   - Add progress reporting via events

## Benefits

1. **Improved Maintainability**: Clearer code structure and organization
2. **Better Testability**: Dependency injection and focused modules
3. **Enhanced Developer Experience**: Consistent interfaces and documentation
4. **Reduced Complexity**: Smaller, focused components
5. **Type Safety**: Comprehensive type checking
6. **Extensibility**: Easier to add new features and components
7. **Error Handling**: Consistent and informative error reporting

## Drawbacks and Mitigation

1. **Migration Effort**:
   - Implement changes incrementally
   - Maintain backward compatibility during transition
   - Provide tooling to assist with migration

2. **Learning Curve**:
   - Document new API patterns and organization
   - Provide examples for common use cases
   - Clear migration guides for contributors

## Conclusion

The proposed internal API restructuring will significantly improve the maintainability, testability, and developer experience of the VCSPull codebase. By adopting consistent module organization, clear function signatures, dependency injection, and enhanced type definitions, we can create a more robust and extensible codebase.

These changes align with modern Python best practices and will provide a strong foundation for future enhancements. The improved API structure will also make the codebase more intuitive for both users and contributors, reducing the learning curve and improving productivity. 