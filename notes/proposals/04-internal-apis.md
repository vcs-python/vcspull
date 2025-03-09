# Internal APIs Proposal

> Streamlining and clarifying the internal API structure to improve code maintainability and testability.

## Current Issues

The audit identified several issues with the current internal APIs:

1. **Inconsistent API Design**: Mixture of object-oriented and functional approaches with unclear boundaries
2. **Inconsistent Return Types**: Functions return varying types (bool, ValidationResult, exceptions)
3. **Complex Data Flow**: Multiple transformations between raw config and validated models
4. **Unclear Public vs Internal Boundaries**: No clear distinction between public and internal APIs
5. **Duplicated Functionality**: Similar functions implemented multiple times in different modules

## Proposed Changes

### 1. Consistent Module Structure

1. **Clear Module Responsibilities**:
   - `vcspull.path`: Centralized path handling utilities
   - `vcspull.config`: Configuration loading and management
   - `vcspull.schemas`: Data models and validation
   - `vcspull.vcs`: VCS (Git, Mercurial, SVN) operations
   - `vcspull.cli`: Command-line interface
   - `vcspull.exceptions`: Exception hierarchy

2. **Module Organization**:
   ```
   src/vcspull/
   ├── __init__.py               # Public API exports
   ├── __about__.py              # Package metadata
   ├── exceptions.py             # Exception hierarchy
   ├── types.py                  # Type definitions
   ├── log.py                    # Logging utilities
   ├── path.py                   # Path utilities
   ├── config.py                 # Config loading and management
   ├── schemas.py                # Data models using Pydantic
   ├── vcs/                      # VCS operations
   │   ├── __init__.py           # VCS public API
   │   ├── base.py               # Base VCS handler
   │   ├── git.py                # Git handler
   │   ├── hg.py                 # Mercurial handler
   │   └── svn.py                # SVN handler
   └── cli/                      # CLI implementation
       ├── __init__.py           # CLI entry point
       ├── commands/             # Command implementations
       │   ├── __init__.py       # Commands registry
       │   ├── sync.py           # Sync command
       │   ├── detect.py         # Detect command
       │   └── lock.py           # Lock command
       └── utils.py              # CLI utilities
   ```

### 2. Consistent Return Types

1. **Error Handling Strategy**:
   - Use exceptions for error conditions
   - Return typed values for successful operations
   - Avoid boolean returns for success/failure

2. **Return Type Examples**:
   ```python
   # Before:
   def validate_config(config: dict) -> Union[bool, ValidationResult]:
       # Validation logic
       if not valid:
           return ValidationResult(valid=False, errors=[...])
       return True
   
   # After:
   def validate_config(config: dict) -> VCSPullConfig:
       """Validate configuration and return validated model.
       
       Args:
           config: Raw configuration dictionary
           
       Returns:
           Validated configuration model
           
       Raises:
           ValidationError: If validation fails
       """
       try:
           return VCSPullConfig.model_validate(config)
       except pydantic.ValidationError as e:
           raise ValidationError(e)
   ```

### 3. Dependency Injection

1. **Injectable Dependencies**:
   - Path operations
   - File system access
   - VCS operations
   - Configuration loading

2. **Example Implementation**:
   ```python
   class PathOperations(Protocol):
       """Protocol for path operations."""
       def normalize(self, path: PathLike) -> str: ...
       def expand(self, path: PathLike) -> str: ...
       def is_valid(self, path: PathLike) -> bool: ...
   
   class FileSystem(Protocol):
       """Protocol for file system operations."""
       def read_file(self, path: PathLike) -> str: ...
       def write_file(self, path: PathLike, content: str) -> None: ...
       def file_exists(self, path: PathLike) -> bool: ...
       def list_directory(self, path: PathLike) -> List[str]: ...
   
   class ConfigLoader:
       """Configuration loader with injectable dependencies."""
       def __init__(
           self,
           path_ops: PathOperations = DefaultPathOperations(),
           fs: FileSystem = DefaultFileSystem()
       ):
           self.path_ops = path_ops
           self.fs = fs
       
       def find_configs(self, *paths: PathLike) -> List[str]:
           """Find configuration files in the given paths."""
           # Implementation using self.path_ops and self.fs
   
       def load_config(self, path: PathLike) -> Dict[str, Any]:
           """Load configuration from file."""
           # Implementation using self.fs
   ```

### 4. Core Services

1. **ConfigurationService**:
   ```python
   class ConfigurationService:
       """Service for loading and managing configurations."""
       def __init__(
           self,
           config_loader: ConfigLoader = ConfigLoader(),
           validator: ConfigValidator = ConfigValidator()
       ):
           self.config_loader = config_loader
           self.validator = validator
       
       def load_configs(self, *paths: PathLike) -> VCSPullConfig:
           """Load and validate configurations from multiple sources."""
           raw_configs = []
           for path in paths:
               config = self.config_loader.load_config(path)
               raw_configs.append(config)
           
           merged_config = merge_configs(raw_configs)
           return self.validator.validate(merged_config)
       
       def filter_repositories(
           self, config: VCSPullConfig, patterns: List[str] = None
       ) -> List[Repository]:
           """Filter repositories by name patterns."""
           if not patterns:
               return config.repositories
           
           filtered = []
           for repo in config.repositories:
               if any(fnmatch.fnmatch(repo.name, pattern) for pattern in patterns):
                   filtered.append(repo)
           
           return filtered
   ```

2. **RepositoryService**:
   ```python
   class RepositoryService:
       """Service for repository operations."""
       def __init__(self, vcs_factory: VCSFactory = VCSFactory()):
           self.vcs_factory = vcs_factory
       
       def sync_repository(self, repo: Repository) -> SyncResult:
           """Sync a repository.
           
           Args:
               repo: Repository configuration
               
           Returns:
               SyncResult with status and messages
               
           Raises:
               VCSError: If VCS operation fails
           """
           vcs_handler = self.vcs_factory.get_handler(repo.vcs)
           
           repo_path = Path(repo.path)
           if repo_path.exists():
               # Update existing repository
               result = vcs_handler.update(
                   repo_path=repo.path,
                   rev=repo.rev,
                   remotes=repo.remotes
               )
           else:
               # Clone new repository
               result = vcs_handler.clone(
                   repo_url=repo.url,
                   repo_path=repo.path,
                   rev=repo.rev
               )
           
           return result
   ```

### 5. VCS Handler Structure

1. **Base VCS Handler**:
   ```python
   class VCSHandler(Protocol):
       """Protocol for VCS handlers."""
       def clone(
           self, repo_url: str, repo_path: PathLike, **kwargs
       ) -> SyncResult: ...
       
       def update(
           self, repo_path: PathLike, **kwargs
       ) -> SyncResult: ...
       
       def add_remote(
           self, repo_path: PathLike, remote_name: str, remote_url: str
       ) -> bool: ...
   
   @dataclass
   class SyncResult:
       """Result of a sync operation."""
       success: bool
       message: str
       details: Dict[str, Any] = field(default_factory=dict)
   ```

2. **VCS Factory**:
   ```python
   class VCSFactory:
       """Factory for creating VCS handlers."""
       def __init__(self):
           self._handlers = {
               "git": GitHandler(),
               "hg": MercurialHandler(),
               "svn": SVNHandler()
           }
       
       def get_handler(self, vcs_type: str) -> VCSHandler:
           """Get VCS handler for the specified type.
           
           Args:
               vcs_type: VCS type ("git", "hg", "svn")
               
           Returns:
               VCS handler
               
           Raises:
               VCSError: If VCS type is not supported
           """
           handler = self._handlers.get(vcs_type.lower())
           if not handler:
               raise VCSError(f"Unsupported VCS type: {vcs_type}")
           return handler
   ```

### 6. Improved Path Handling

1. **Centralized Path Module**:
   ```python
   class PathOperations:
       """Centralized path operations."""
       @staticmethod
       def normalize(path: PathLike) -> str:
           """Normalize a path to a consistent format."""
           path_obj = Path(path).expanduser().resolve()
           return str(path_obj)
       
       @staticmethod
       def expand(path: PathLike, cwd: PathLike = None) -> str:
           """Expand a path, resolving home directories and relative paths."""
           path_str = str(path)
           if cwd and not Path(path_str).is_absolute():
               path_obj = Path(cwd) / path_str
           else:
               path_obj = Path(path_str)
           
           return str(path_obj.expanduser().resolve())
       
       @staticmethod
       def is_valid(path: PathLike) -> bool:
           """Check if a path is valid."""
           try:
               # Check for basic path validity
               Path(path)
               return True
           except (TypeError, ValueError):
               return False
   ```

### 7. Event System for Extensibility

1. **Event-Based Architecture**:
   ```python
   class Event:
       """Base event class."""
       pass
   
   class ConfigLoadedEvent(Event):
       """Event fired when a configuration is loaded."""
       def __init__(self, config: VCSPullConfig):
           self.config = config
   
   class RepositorySyncStartEvent(Event):
       """Event fired when repository sync starts."""
       def __init__(self, repository: Repository):
           self.repository = repository
   
   class RepositorySyncCompleteEvent(Event):
       """Event fired when repository sync completes."""
       def __init__(self, repository: Repository, result: SyncResult):
           self.repository = repository
           self.result = result
   
   class EventBus:
       """Simple event bus for handling events."""
       def __init__(self):
           self._handlers = defaultdict(list)
       
       def subscribe(self, event_type: Type[Event], handler: Callable[[Event], None]):
           """Subscribe to an event type."""
           self._handlers[event_type].append(handler)
       
       def publish(self, event: Event):
           """Publish an event."""
           for handler in self._handlers[type(event)]:
               handler(event)
   ```

## Implementation Plan

1. **Phase 1: Module Reorganization**
   - Define new module structure
   - Move code to appropriate modules
   - Update imports

2. **Phase 2: Path Module**
   - Create centralized path handling
   - Update all code to use new path utilities
   - Add comprehensive tests

3. **Phase 3: Service Layer**
   - Implement ConfigurationService
   - Implement RepositoryService
   - Update code to use services

4. **Phase 4: VCS Abstraction**
   - Implement VCS handler protocols
   - Create VCS factory
   - Update repository operations to use VCS handlers

5. **Phase 5: Dependency Injection**
   - Add support for injectable dependencies
   - Create default implementations
   - Update services to use dependency injection

6. **Phase 6: Event System**
   - Implement event bus
   - Define core events
   - Add event handlers for core functionality

## Benefits

1. **Improved Maintainability**: Clear module structure and responsibilities
2. **Better Testability**: Dependency injection makes testing easier
3. **Consistent Error Handling**: Exception-based error handling throughout the codebase
4. **Clear API Boundaries**: Explicit public vs internal APIs
5. **Extensibility**: Event system allows for extensions without modifying core code
6. **Simplified Code Flow**: Clearer data transformations and service interactions

## Drawbacks and Mitigation

1. **Migration Effort**:
   - Phased approach to migration
   - Comprehensive test coverage to ensure correctness
   - Temporary compatibility layers

2. **Learning Curve**:
   - Improved documentation
   - Clear examples of new API usage
   - Gradually introduce new patterns

3. **Potential Over-Engineering**:
   - Start with minimal abstractions
   - Add complexity only where necessary
   - Focus on practical use cases

## Conclusion

The proposed internal API improvements will significantly enhance the maintainability and testability of the VCSPull codebase. By establishing clear module boundaries, consistent return types, and a service-based architecture, we can reduce complexity and make the code easier to understand and extend. The introduction of dependency injection and an event system will further improve testability and extensibility. 