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
   from pydantic import BaseModel, Field, field_validator

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
           """Normalize repository path."""
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
       
       model_config = {
           "json_schema_extra": {
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
                               "path": "~/code/repo"
                           }
                       ]
                   }
               ]
           }
       }
   ```

2. **Benefits**:
   - Clear schema definition that can be used for validation
   - Automatic documentation generation
   - IDE autocompletion support
   - Type checking with mypy
   - Examples included in the schema

### 3. Unified Configuration Handling

1. **Centralized Configuration Module**:
   ```python
   import typing as t
   from pathlib import Path
   import yaml
   import os
   from .schemas import VCSPullConfig, Repository

   def find_configs() -> list[Path]:
       """Find configuration files in standard locations.
       
       Returns
       ----
       list[Path]
           List of found configuration file paths
       """
       # Standard locations for configuration files
       locations = [
           Path.cwd() / ".vcspull.yaml",
           Path.home() / ".vcspull.yaml",
           Path.home() / ".config" / "vcspull" / "config.yaml",
           # Environment variable location if set
           os.environ.get("VCSPULL_CONFIG", None)
       ]
       
       return [p for p in locations if p and Path(p).exists()]
   
   def load_config(path: t.Union[str, Path]) -> dict:
       """Load configuration from a YAML file.
       
       Parameters
       ----
       path : Union[str, Path]
           Path to the configuration file
           
       Returns
       ----
       dict
           Loaded configuration data
           
       Raises
       ----
       FileNotFoundError
           If the configuration file does not exist
       yaml.YAMLError
           If the configuration file has invalid YAML
       """
       path_obj = Path(path)
       if not path_obj.exists():
           raise FileNotFoundError(f"Configuration file not found: {path}")
       
       with open(path_obj, 'r') as f:
           try:
               return yaml.safe_load(f)
           except yaml.YAMLError as e:
               raise yaml.YAMLError(f"Invalid YAML in configuration file: {e}")
   
   def validate_config(config_data: dict) -> VCSPullConfig:
       """Validate configuration data using Pydantic models.
       
       Parameters
       ----
       config_data : dict
           Raw configuration data
           
       Returns
       ----
       VCSPullConfig
           Validated configuration object
       """
       return VCSPullConfig.model_validate(config_data)
   
   def load_and_validate_config(path: t.Union[str, Path]) -> VCSPullConfig:
       """Load and validate configuration from a file.
       
       Parameters
       ----
       path : Union[str, Path]
           Path to the configuration file
           
       Returns
       ----
       VCSPullConfig
           Validated configuration object
       """
       config_data = load_config(path)
       return validate_config(config_data)
   
   def merge_configs(configs: list[VCSPullConfig]) -> VCSPullConfig:
       """Merge multiple configuration objects.
       
       Parameters
       ----
       configs : list[VCSPullConfig]
           List of configuration objects to merge
           
       Returns
       ----
       VCSPullConfig
           Merged configuration object
       """
       if not configs:
           return VCSPullConfig()
       
       # Start with the first config
       base_config = configs[0]
       
       # Merge remaining configs
       for config in configs[1:]:
           # Merge settings
           for key, value in config.settings.model_dump().items():
               if value is not None:
                   setattr(base_config.settings, key, value)
           
           # Merge repositories (avoiding duplicates by URL)
           existing_urls = {repo.url for repo in base_config.repositories}
           for repo in config.repositories:
               if repo.url not in existing_urls:
                   base_config.repositories.append(repo)
                   existing_urls.add(repo.url)
       
       return base_config
   ```

2. **Benefits**:
   - Single responsibility for each function
   - Clear validation and loading flow
   - Explicit error handling
   - Type hints for better IDE support and mypy validation

### 4. Environment Variable Support

1. **Environment Variable Overrides**:
   ```python
   import os
   from pydantic import BaseModel, Field
   
   class EnvironmentSettings(BaseModel):
       """Environment variable configuration settings."""
       config_path: t.Optional[str] = Field(default=None, validation_alias="VCSPULL_CONFIG")
       log_level: t.Optional[str] = Field(default=None, validation_alias="VCSPULL_LOG_LEVEL")
       disable_includes: bool = Field(default=False, validation_alias="VCSPULL_DISABLE_INCLUDES")
       
       @classmethod
       def from_env(cls) -> "EnvironmentSettings":
           """Create settings object from environment variables.
           
           Returns
           ----
           EnvironmentSettings
               Settings loaded from environment variables
           """
           return cls.model_validate(dict(os.environ))
   
   def apply_env_overrides(config: VCSPullConfig) -> VCSPullConfig:
       """Apply environment variable overrides to configuration.
       
       Parameters
       ----
       config : VCSPullConfig
           Base configuration object
           
       Returns
       ----
       VCSPullConfig
           Configuration object with environment overrides applied
       """
       env_settings = EnvironmentSettings.from_env()
       
       # Apply log level override if set
       if env_settings.log_level:
           config.settings.log_level = env_settings.log_level
       
       # Apply other overrides as needed
       
       return config
   ```

2. **Benefits**:
   - Clear separation of environment variable handling
   - Consistent override mechanism
   - Self-documenting through Pydantic model

### 5. Includes Handling

1. **Simplified Include Resolution**:
   ```python
   import typing as t
   from pathlib import Path
   
   def resolve_includes(config: VCSPullConfig, base_dir: t.Optional[Path] = None) -> VCSPullConfig:
       """Resolve and process included configuration files.
       
       Parameters
       ----
       config : VCSPullConfig
           Base configuration object with includes
       base_dir : Optional[Path]
           Base directory for resolving relative paths (defaults to cwd)
           
       Returns
       ----
       VCSPullConfig
           Configuration with includes processed
       """
       if not config.includes:
           return config
       
       # Use current directory if base_dir not provided
       base_dir = base_dir or Path.cwd()
       
       included_configs = []
       for include_path in config.includes:
           path_obj = Path(include_path)
           
           # Make relative paths absolute from base_dir
           if not path_obj.is_absolute():
               path_obj = base_dir / path_obj
           
           # Expand user home directory
           path_obj = path_obj.expanduser()
           
           # Load and process the included config
           if path_obj.exists():
               included_config = load_and_validate_config(path_obj)
               # Process nested includes recursively
               included_config = resolve_includes(included_config, path_obj.parent)
               included_configs.append(included_config)
       
       # Merge all configs together
       all_configs = [config] + included_configs
       return merge_configs(all_configs)
   ```

2. **Benefits**:
   - Recursive include resolution
   - Clear handling of relative paths
   - Proper merging of included configurations

### 6. JSON Schema Generation

1. **Automatic Documentation Generation**:
   ```python
   import json
   from pydantic import BaseModel
   
   def generate_json_schema(output_path: t.Optional[str] = None) -> dict:
       """Generate JSON schema for configuration.
       
       Parameters
       ----
       output_path : Optional[str]
           Path to save the schema file (if None, just returns the schema)
           
       Returns
       ----
       dict
           JSON schema for configuration
       """
       schema = VCSPullConfig.model_json_schema()
       
       if output_path:
           with open(output_path, 'w') as f:
               json.dump(schema, f, indent=2)
       
       return schema
   ```

2. **Benefits**:
   - Automatic schema documentation
   - Can be used for validation in editors
   - Facilitates configuration integration with IDEs

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