# Configuration Format & Structure Proposal

> Simplifying the configuration format and structure to improve maintainability and user experience.

## Current Issues

The audit identified several issues with the current configuration format:

1. **Complex Configuration Handling**: The codebase has intricate configuration handling spread across multiple files, including:
   - `config.py` (2200+ lines)
   - `types.py` 
   - Multiple configuration loaders and handlers

2. **Redundant Validation**: Similar validation logic is duplicated across the codebase, leading to inconsistencies.

3. **Complex File Resolution**: File path handling and resolution is overly complex, making debugging difficult.

4. **Nested Configuration Structure**: Current YAML configuration has deeply nested structures that are difficult to maintain.

5. **No Schema Definition**: Lack of a formal schema makes configuration validation and documentation difficult.

## Proposed Changes

### 1. Simplified Configuration Format

1. **Flatter Configuration Structure**:
   ```yaml
   # Current format (complex and nested)
   sync_remotes: true
   projects:
     projectgroup:
       repo1:
         url: https://github.com/user/repo1.git
         path: ~/code/repo1
       repo2:
         url: https://github.com/user/repo2.git
         path: ~/code/repo2
   
   # Proposed format (flatter and more consistent)
   settings:
     sync_remotes: true
     default_vcs: git
   
   repositories:
     - name: repo1
       url: https://github.com/user/repo1.git
       path: ~/code/repo1
       vcs: git
     
     - name: repo2
       url: https://github.com/user/repo2.git
       path: ~/code/repo2
       vcs: git
   
   includes:
     - ~/other-config.yaml
   ```

2. **Benefits**:
   - Simpler structure with fewer nesting levels
   - Consistent repository representation
   - Easier to parse and validate
   - More intuitive for users

### 2. Clear Schema Definition with Pydantic

1. **Formal Schema Definition**:
   ```python
   import typing as t
   from pathlib import Path
   import os
   from pydantic import BaseModel, Field, field_validator, ConfigDict
   
   class Repository(BaseModel):
       """Repository configuration model."""
       name: t.Optional[str] = None
       url: str
       path: str
       vcs: t.Optional[str] = None
       remotes: dict[str, str] = Field(default_factory=dict)
       rev: t.Optional[str] = None
       web_url: t.Optional[str] = None
       
       @field_validator('path')
       @classmethod
       def validate_path(cls, v: str) -> str:
           """Normalize repository path.
           
           Parameters
           ----
           v : str
               The path to normalize
               
           Returns
           ----
           str
               The normalized path
           """
           path_obj = Path(v).expanduser().resolve()
           return str(path_obj)
   
   class Settings(BaseModel):
       """Global settings model."""
       sync_remotes: bool = True
       default_vcs: t.Optional[str] = None
       depth: t.Optional[int] = None
   
   class VCSPullConfig(BaseModel):
       """Root configuration model."""
       settings: Settings = Field(default_factory=Settings)
       repositories: list[Repository] = Field(default_factory=list)
       includes: list[str] = Field(default_factory=list)
       
       model_config = ConfigDict(
           json_schema_extra={
               "examples": [
                   {
                       "settings": {
                           "sync_remotes": True,
                           "default_vcs": "git"
                       },
                       "repositories": [
                           {
                               "name": "example-repo",
                               "url": "https://github.com/user/repo.git",
                               "path": "~/code/repo",
                               "vcs": "git"
                           }
                       ],
                       "includes": [
                           "~/other-config.yaml"
                       ]
                   }
               ]
           }
       )
   ```

2. **Using TypeAdapter for Validation**:
   ```python
   import typing as t
   from pathlib import Path
   import yaml
   import json
   import os
   from pydantic import TypeAdapter
   
   # Define type adapters for optimized validation
   CONFIG_ADAPTER = TypeAdapter(VCSPullConfig)
   
   def load_config(config_path: t.Union[str, Path]) -> VCSPullConfig:
       """Load and validate configuration from a file.
       
       Parameters
       ----
       config_path : Union[str, Path]
           Path to the configuration file
           
       Returns
       ----
       VCSPullConfig
           Validated configuration model
           
       Raises
       ----
       FileNotFoundError
           If the configuration file doesn't exist
       ValidationError
           If the configuration is invalid
       """
       config_path = Path(config_path).expanduser().resolve()
       
       if not config_path.exists():
           raise FileNotFoundError(f"Configuration file not found: {config_path}")
       
       # Load raw configuration
       with open(config_path, 'r') as f:
           if config_path.suffix.lower() in ('.yaml', '.yml'):
               raw_config = yaml.safe_load(f)
           elif config_path.suffix.lower() == '.json':
               raw_config = json.load(f)
           else:
               raise ValueError(f"Unsupported file format: {config_path.suffix}")
       
       # Validate with type adapter
       return CONFIG_ADAPTER.validate_python(raw_config)
   ```

3. **Benefits**:
   - Formal schema definition provides clear documentation
   - Type hints make the configuration structure self-documenting
   - Validation ensures configuration correctness
   - JSON Schema can be generated for external documentation

### 3. Simplified File Resolution

1. **Consistent Path Handling**:
   ```python
   import typing as t
   import os
   from pathlib import Path
   
   def normalize_path(path: t.Union[str, Path]) -> Path:
       """Normalize a path by expanding user directory and resolving it.
       
       Parameters
       ----
       path : Union[str, Path]
           The path to normalize
           
       Returns
       ----
       Path
           The normalized path
       """
       return Path(path).expanduser().resolve()
   
   def find_config_files(search_paths: list[t.Union[str, Path]]) -> list[Path]:
       """Find configuration files in the specified search paths.
       
       Parameters
       ----
       search_paths : list[Union[str, Path]]
           List of paths to search for configuration files
           
       Returns
       ----
       list[Path]
           List of found configuration files
       """
       config_files = []
       for path in search_paths:
           path = normalize_path(path)
           
           if path.is_file() and path.suffix.lower() in ('.yaml', '.yml', '.json'):
               config_files.append(path)
           elif path.is_dir():
               for suffix in ('.yaml', '.yml', '.json'):
                   files = list(path.glob(f"*{suffix}"))
                   config_files.extend(files)
       
       return config_files
   ```

2. **Includes Resolution**:
   ```python
   import typing as t
   from pathlib import Path
   
   def resolve_includes(
       config: VCSPullConfig, 
       base_path: t.Union[str, Path]
   ) -> VCSPullConfig:
       """Resolve included configuration files.
       
       Parameters
       ----
       config : VCSPullConfig
           The base configuration
       base_path : Union[str, Path]
           The base path for resolving relative include paths
           
       Returns
       ----
       VCSPullConfig
           Configuration with includes resolved
       """
       base_path = Path(base_path).expanduser().resolve()
       
       if not config.includes:
           return config
       
       merged_config = config.model_copy(deep=True)
       
       # Process include files
       for include_path in config.includes:
           include_path = Path(include_path)
           
           # If path is relative, make it relative to base_path
           if not include_path.is_absolute():
               include_path = base_path / include_path
           
           include_path = include_path.expanduser().resolve()
           
           if not include_path.exists():
               continue
           
           # Load included config
           included_config = load_config(include_path)
           
           # Recursively resolve nested includes
           included_config = resolve_includes(included_config, include_path.parent)
           
           # Merge configs
           merged_config.repositories.extend(included_config.repositories)
           
           # Merge settings (more complex logic needed here)
           # Only override non-default values
           for field_name, field_value in included_config.settings.model_dump().items():
               if field_name not in merged_config.settings.model_fields_set:
                   setattr(merged_config.settings, field_name, field_value)
       
       # Clear includes to prevent circular references
       merged_config.includes = []
       
       return merged_config
   ```

3. **Benefits**:
   - Consistent path handling across the codebase
   - Clear resolution of included files
   - Prevention of circular includes
   - Proper merging of configurations

## Implementation Plan

1. **Phase 1: Schema Definition**
   - Define Pydantic models for configuration
   - Implement basic validation logic
   - Create schema documentation

2. **Phase 2: Configuration Handling**
   - Implement configuration loading functions
   - Add environment variable support
   - Create include resolution logic
   - Develop configuration merging functions

3. **Phase 3: Migration Tools**
   - Create tools to convert old format to new format
   - Add backward compatibility layer
   - Create migration guide for users

4. **Phase 4: Documentation & Examples**
   - Generate JSON schema documentation
   - Create example configuration files
   - Update user documentation with new format

## Benefits

1. **Improved Maintainability**: Clearer structure with single responsibility components
2. **Enhanced User Experience**: Simpler configuration format with better documentation
3. **Type Safety**: Pydantic models with type hints improve type checking
4. **Better Testing**: Simplified components are easier to test
5. **Automated Documentation**: JSON schema provides self-documenting configuration
6. **IDE Support**: Better integration with editors through JSON schema
7. **Environment Flexibility**: Consistent environment variable overrides

## Drawbacks and Mitigation

1. **Breaking Changes**:
   - Provide migration tools to convert old format to new format
   - Add backward compatibility layer during transition period
   - Comprehensive documentation on migration process

2. **Learning Curve**:
   - Improved documentation with examples
   - Clear schema definition for configuration
   - Migration guide for existing users

## Conclusion

The proposed configuration format simplifies the structure and handling of VCSPull configuration, reducing complexity and improving maintainability. By leveraging Pydantic models for validation and schema definition, we can provide better documentation and type safety throughout the codebase. 

The changes will require a transition period with backward compatibility to ensure existing users can migrate smoothly to the new format. However, the benefits of a clearer, more maintainable configuration system will significantly improve both the developer and user experience with VCSPull. 