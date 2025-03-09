# Configuration Format & Structure Proposal

> Streamlining the configuration system to reduce complexity and improve user experience.

## Current Issues

The audit identified several issues with the current configuration system:

1. **Complex Path Handling**: Multiple functions for path expansion, normalization, and validation spread across `config.py`, `schemas.py`, and `validator.py`.
2. **Multiple Configuration Sources**: Complex merging logic for config files from multiple sources.
3. **Duplicate Detection**: Inefficient O(n²) approach for detecting and merging duplicate repositories.
4. **Complex Configuration Loading Pipeline**: Multiple transformation stages from discovery to validated configurations.

## Proposed Changes

### 1. Standardized Configuration Format

1. **Simplified Schema**:
   - Use a standard, well-documented YAML/JSON format
   - Leverage Pydantic v2 models for validation and documentation
   - Provide complete JSON Schema for configuration validation

2. **Example Configuration**:
   ```yaml
   # VCSPull Configuration
   settings:
     sync_remotes: true
     default_vcs: git
     depth: 1
   
   repositories:
     - name: vcspull
       url: https://github.com/vcs-python/vcspull.git
       path: ~/code/python/vcspull
       vcs: git
       rev: main
     
     - name: myrepo
       url: git@github.com:username/myrepo.git
       path: ~/code/myrepo
       remotes:
         upstream: https://github.com/upstream/myrepo.git
   
   includes:
     - ~/.config/vcspull/work.yaml
     - ~/.config/vcspull/personal.yaml
   ```

3. **Schema Definition**:
   ```python
   import typing as t
   from pathlib import Path
   from pydantic import BaseModel, Field, field_validator, model_validator
   
   class Settings(BaseModel):
       """Global settings for VCSPull."""
       sync_remotes: bool = True
       default_vcs: t.Optional[str] = None
       depth: t.Optional[int] = None
   
   class Repository(BaseModel):
       """Repository configuration."""
       name: t.Optional[str] = None
       url: str
       path: str
       vcs: t.Optional[str] = None
       rev: t.Optional[str] = None
       remotes: t.Dict[str, str] = Field(default_factory=dict)
       
       model_config = {
           "json_schema_extra": {
               "examples": [
                   {
                       "name": "vcspull",
                       "url": "https://github.com/vcs-python/vcspull.git",
                       "path": "~/code/python/vcspull",
                       "vcs": "git",
                       "rev": "main"
                   }
               ]
           }
       }
       
       @field_validator('path')
       @classmethod
       def validate_and_normalize_path(cls, v: str) -> str:
           """Validate and normalize repository path."""
           path = Path(v).expanduser()
           return str(path.resolve() if path.exists() else path.absolute())
       
       @model_validator(mode='after')
       def infer_name_if_missing(self) -> 'Repository':
           """Infer name from URL or path if not provided."""
           if not self.name:
               # Try to extract name from URL
               if '/' in self.url:
                   self.name = self.url.split('/')[-1].split('.')[0]
               else:
                   # Use directory name from path
                   self.name = Path(self.path).name
           return self
   
   class ConfigFile(BaseModel):
       """Root configuration model."""
       settings: Settings = Field(default_factory=Settings)
       repositories: t.List[Repository] = Field(default_factory=list)
       includes: t.List[str] = Field(default_factory=list)
   ```

### 2. Unified Path Handling

1. **Path Utility Module**:
   - Create a dedicated utility module for path operations
   - Use modern pathlib features consistently
   - Centralize all path-related functions

2. **Path Utilities Implementation**:
   ```python
   import typing as t
   import os
   from pathlib import Path
   from typing_extensions import Annotated
   from pydantic import AfterValidator, BeforeValidator
   
   def expand_path(path_str: str) -> Path:
       """Expand user home directory and resolve path."""
       path = Path(path_str).expanduser()
       return path.resolve() if path.exists() else path.absolute()
   
   def normalize_path(path_str: str) -> str:
       """Normalize path to string representation."""
       return str(expand_path(path_str))
   
   def validate_path_exists(path: Path) -> Path:
       """Validate that a path exists."""
       if not path.exists():
           raise ValueError(f"Path does not exist: {path}")
       return path
   
   def validate_path_is_dir(path: Path) -> Path:
       """Validate that a path is a directory."""
       if not path.is_dir():
           raise ValueError(f"Path is not a directory: {path}")
       return path
   
   # Define reusable path types using Annotated
   ExpandedPath = Annotated[str, BeforeValidator(normalize_path)]
   ExistingPath = Annotated[Path, BeforeValidator(expand_path), AfterValidator(validate_path_exists)]
   ExistingDir = Annotated[Path, BeforeValidator(expand_path), AfterValidator(validate_path_exists), AfterValidator(validate_path_is_dir)]
   ```

3. **Path Resolution Strategy**:
   - Consistent handling for relative and absolute paths
   - Clear documentation on how paths are resolved
   - Unified approach to path expansion and normalization

### 3. Configuration Loading System

1. **Discovery**:
   ```python
   import typing as t
   from pathlib import Path
   
   def find_config_files(search_paths: t.List[t.Union[str, Path]] = None) -> t.List[Path]:
       """Find configuration files in standard locations.
       
       Args:
           search_paths: Optional list of paths to search
           
       Returns:
           List of discovered configuration files
       """
       if search_paths is None:
           search_paths = [
               Path.home() / ".vcspull.yaml",
               Path.home() / ".config" / "vcspull" / "config.yaml",
               Path.home() / ".config" / "vcspull.yaml",
               Path.cwd() / ".vcspull.yaml",
           ]
       
       found_files = []
       for path_str in search_paths:
           path = Path(path_str).expanduser()
           if path.is_file():
               found_files.append(path)
           elif path.is_dir():
               # Search for YAML/JSON files in directory
               found_files.extend(list(path.glob("*.yaml")))
               found_files.extend(list(path.glob("*.yml")))
               found_files.extend(list(path.glob("*.json")))
       
       return found_files
   ```

2. **Loading**:
   ```python
   import yaml
   import json
   from pydantic import TypeAdapter
   
   def load_config_file(config_path: Path) -> dict:
       """Load configuration from a file.
       
       Args:
           config_path: Path to configuration file
           
       Returns:
           Parsed configuration dictionary
           
       Raises:
           ConfigError: If file cannot be loaded or parsed
       """
       try:
           with open(config_path, 'r') as f:
               if config_path.suffix.lower() in ('.yaml', '.yml'):
                   return yaml.safe_load(f) or {}
               elif config_path.suffix.lower() == '.json':
                   return json.load(f)
               else:
                   raise ConfigError(f"Unsupported file format: {config_path.suffix}")
       except (yaml.YAMLError, json.JSONDecodeError) as e:
           raise ConfigError(f"Failed to parse {config_path}: {e}")
       except OSError as e:
           raise ConfigError(f"Failed to read {config_path}: {e}")
   ```

3. **Merging Strategy**:
   ```python
   def merge_configs(configs: t.List[dict]) -> dict:
       """Merge multiple configuration dictionaries.
       
       Args:
           configs: List of configuration dictionaries
           
       Returns:
           Merged configuration dictionary
       """
       merged = {"settings": {}, "repositories": [], "includes": []}
       
       for config in configs:
           # Merge settings (shallow merge)
           if config.get("settings"):
               merged["settings"].update(config["settings"])
           
           # Append repositories (will detect duplicates later)
           if config.get("repositories"):
               merged["repositories"].extend(config["repositories"])
           
           # Append includes
           if config.get("includes"):
               merged["includes"].extend(config["includes"])
       
       return merged
   ```

4. **Duplicate Repository Handling**:
   ```python
   def detect_and_merge_duplicate_repos(repositories: t.List[dict]) -> t.List[dict]:
       """Detect and merge duplicate repositories using optimized algorithm.
       
       Args:
           repositories: List of repository dictionaries
           
       Returns:
           List with duplicates merged
       """
       # Use dictionary with repo path as key for O(n) performance
       unique_repos = {}
       
       for repo in repositories:
           path = normalize_path(repo["path"])
           
           if path in unique_repos:
               # Merge with existing repository
               existing = unique_repos[path]
               
               # Priority: Keep the most specific configuration
               for key, value in repo.items():
                   if key not in existing or not existing[key]:
                       existing[key] = value
                   
                   # Special handling for remotes
                   if key == "remotes" and value:
                       if not existing.get("remotes"):
                           existing["remotes"] = {}
                       existing["remotes"].update(value)
           else:
               # New unique repository
               unique_repos[path] = repo.copy()
       
       return list(unique_repos.values())
   ```

5. **Validation Pipeline**:
   ```python
   def process_configuration(config_paths: t.List[Path] = None) -> ConfigFile:
       """Process and validate configuration from multiple files.
       
       Args:
           config_paths: Optional list of configuration file paths
           
       Returns:
           Validated configuration object
           
       Raises:
           ConfigError: If configuration cannot be loaded or validated
       """
       # Discover config files if not provided
       if config_paths is None:
           config_paths = find_config_files()
       
       if not config_paths:
           return ConfigFile()  # Return default empty configuration
       
       # Load all config files
       raw_configs = []
       for path in config_paths:
           raw_config = load_config_file(path)
           raw_configs.append(raw_config)
       
       # Merge raw configs
       merged_config = merge_configs(raw_configs)
       
       # Handle duplicate repositories
       if merged_config.get("repositories"):
           merged_config["repositories"] = detect_and_merge_duplicate_repos(
               merged_config["repositories"]
           )
       
       # Validate through Pydantic model
       try:
           config = ConfigFile.model_validate(merged_config)
       except ValidationError as e:
           raise ConfigValidationError(e)
       
       # Process includes if any
       if config.includes:
           included_paths = [Path(path).expanduser() for path in config.includes]
           included_config = process_configuration(included_paths)
           
           # Merge with current config (main config takes precedence)
           # Settings from main config override included configs
           new_config = ConfigFile(
               settings=config.settings,
               repositories=detect_and_merge_duplicate_repos(
                   [repo.model_dump() for repo in config.repositories] +
                   [repo.model_dump() for repo in included_config.repositories]
               ),
               includes=[]  # Clear includes to avoid circular references
           )
           return new_config
       
       return config
   ```

### 4. Enhanced Configuration Management

1. **Environment Variable Support**:
   ```python
   from pydantic import field_validator
   import os
   
   class EnvAwareSettings(BaseModel):
       """Settings model with environment variable support."""
       sync_remotes: bool = Field(default=True)
       default_vcs: t.Optional[str] = Field(default=None)
       depth: t.Optional[int] = Field(default=None)
       
       model_config = {
           "env_prefix": "VCSPULL_",
           "env_nested_delimiter": "__",
       }
   
   class EnvAwareConfigFile(BaseModel):
       """Configuration model with environment variable support."""
       settings: EnvAwareSettings = Field(default_factory=EnvAwareSettings)
       repositories: t.List[Repository] = Field(default_factory=list)
       includes: t.List[str] = Field(default_factory=list)
       
       @field_validator('includes')
       @classmethod
       def expand_env_vars_in_includes(cls, v: t.List[str]) -> t.List[str]:
           """Expand environment variables in include paths."""
           return [os.path.expandvars(path) for path in v]
   ```

2. **Configuration Profiles**:
   - Support for multiple configuration profiles (e.g., "work", "personal")
   - Profile selection via environment variable or command line flag
   - Simplified management of multiple repository sets

3. **Self-documenting Configuration**:
   - JSON Schema generation from Pydantic models
   - Automatic documentation generation
   - Example configurations for common scenarios

## Implementation Plan

1. **Phase 1: Path Utilities Refactoring**
   - Create a dedicated path module
   - Refactor existing path handling functions
   - Add comprehensive tests for path handling
   - Update code to use the new utilities

2. **Phase 2: Configuration Model Updates**
   - Create new Pydantic v2 models for configuration
   - Add model validators
   - Define JSON schema for documentation
   - Add model serialization/deserialization

3. **Phase 3: Configuration Loading Pipeline**
   - Implement the new loading and discovery functions
   - Implement the optimized duplicate detection
   - Add tests for configuration loading
   - Document the configuration loading process

4. **Phase 4: Environment and Profile Support**
   - Add environment variable support
   - Implement configuration profiles
   - Add test cases for environment handling
   - Update documentation with environment variable details

5. **Phase 5: Migration and Compatibility**
   - Ensure backward compatibility with existing configs
   - Provide migration guide for users
   - Add deprecation warnings for old formats
   - Create migration tool if necessary

## Benefits

1. **Simplified Configuration**: Clearer, more intuitive format for users
2. **Reduced Complexity**: Fewer lines of code, simplified loading process
3. **Better Performance**: Optimized duplicate detection and merging
4. **Improved Validation**: Comprehensive validation with better error messages
5. **Enhanced Extensibility**: Easier to add new configuration options
6. **Better User Experience**: Environment variable support and profiles
7. **Self-documenting**: Automatic schema generation for documentation
8. **Type Safety**: Better type checking with Pydantic models

## Drawbacks and Mitigation

1. **Migration Effort**:
   - Provide backward compatibility for existing configurations
   - Offer migration tools to convert old formats
   - Document migration process clearly
   - Support both formats during transition period

2. **Learning Curve**:
   - Comprehensive documentation of new format
   - Examples of common configuration patterns
   - Clear error messages for validation issues
   - Command to generate example configuration

## Conclusion

The proposed configuration format and structure will significantly improve the user experience and reduce the complexity of the VCSPull codebase. By leveraging Pydantic v2 for validation and documentation, we can ensure configurations are both easy to understand and rigorously validated. The optimized loading pipeline and duplicate detection will provide better performance, while environment variable support and profiles will enhance flexibility for users with complex repository management needs.

By centralizing path handling and defining a clear configuration loading strategy, we address several key issues identified in the audit. The new implementation will be more maintainable, easier to test, and provide a better foundation for future features. 