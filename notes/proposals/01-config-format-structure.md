# Config Format and Structure Proposal

> Streamlining and simplifying the VCSPull configuration system to make it more intuitive and maintainable.

## Current Issues

Based on the audit, the current configuration system has several problems:

1. **Complex Configuration Sources**: Multiple config file sources with complex merging logic
2. **Path Handling Complexity**: Redundant path expansion, normalization, and validation across modules
3. **Duplicate Detection**: Inefficient O(n²) algorithm for detecting duplicates
4. **Complex Loading Pipeline**: Multi-stage transformation from raw config to validated model with intermediate steps

## Proposed Changes

### 1. Simplified Configuration Format

**Current Format**:
```yaml
/home/user/myproject/:  # Path acts as both key and destination
  git+https://github.com/user/myrepo.git:  # URL acts as both key and source location
    remotes:
      upstream: https://github.com/upstream/myrepo.git
```

**Proposed Format**:
```yaml
repositories:
  - name: "myrepo"  # Explicit name for the repository (optional, defaults to repo name)
    url: "git+https://github.com/user/myrepo.git"  # Primary source location
    path: "/home/user/myproject/"  # Destination path
    remotes:  # Optional remotes
      upstream: "https://github.com/upstream/myrepo.git"
    vcs: "git"  # Optional, can be inferred from URL
    rev: "main"  # Optional revision/branch to checkout
    web_url: "https://github.com/user/myrepo"  # Optional web URL
```

Benefits:
- Explicit fields with clear meanings
- No overloading of keys as paths or URLs
- Simpler to parse and validate
- More extensible for additional properties
- Easier to merge from multiple config files
- Aligns with common YAML/JSON patterns used in other tools

### 2. Configuration File Structure

1. **Single Root Format**:
   - Use a single root object with explicit sections
   - Avoid deep nesting of configuration files

2. **Configuration Sections**:
   ```yaml
   # Global settings applied to all repositories
   settings:
     sync_remotes: true
     default_vcs: "git"
     depth: 1
   
   # Repository definitions
   repositories:
     - name: "myrepo"
       url: "git+https://github.com/user/myrepo.git"
       path: "/home/user/myproject/"
     
     - name: "another-repo"
       url: "git+https://github.com/user/another-repo.git"
       path: "/home/user/projects/another-repo"
   
   # Include other config files (optional)
   includes:
     - "~/.config/vcspull/work.yaml"
     - "~/.config/vcspull/personal.yaml"
   ```

3. **Environment Variable Expansion**:
   - Support for environment variables in paths and URLs
   - Example: `path: "${HOME}/projects/myrepo"`

### 3. Configuration Loading Pipeline

1. **Simplified Loading Process**:
   - Load all config files (including includes) in a single pass
   - Parse YAML/JSON to dictionaries
   - Transform to a single unified format
   - Validate against schema
   - Resolve duplicates
   - Expand paths and environment variables

2. **Efficient Duplicate Detection**:
   - Use a hash-based approach instead of O(n²) nested loops
   - Consider repositories duplicates if they have the same path or same URL
   - Provide clear warnings about duplicates
   - Use a more sophisticated merging strategy for conflicting repositories

### 4. Path Handling

1. **Centralized Path Utilities**:
   - Create a dedicated path module
   - Leverage pathlib more extensively
   - Consistent approach to path normalization, expansion, and validation

2. **Path Resolution Rules**:
   - Relative paths are resolved relative to the config file location
   - Environment variables are expanded
   - User home directories are expanded
   - Paths are normalized to platform-specific format
   - Validation ensures paths are valid for the platform

### 5. Migration Strategy

1. **Backward Compatibility**:
   - Support both old and new formats for a transition period
   - Provide utility to convert from old format to new format
   - Default to new format for new configurations

2. **Command Line Migration Tool**:
   - Add a `vcspull migrate` command to convert config files
   - Include a `--check` option to validate current config files against new format
   - Provide clear error messages for incompatible configurations

## Implementation Plan

1. **Phase 1: Path Utilities**
   - Create a centralized path module
   - Update all path handling to use the new utilities
   - Add comprehensive tests for path handling edge cases

2. **Phase 2: New Configuration Format**
   - Define Pydantic models for new format
   - Implement parser for new format
   - Maintain backward compatibility with old format

3. **Phase 3: Configuration Loading Pipeline**
   - Implement new loading process
   - Improve duplicate detection
   - Add clear error messages and logging

4. **Phase 4: Migration Tools**
   - Create migration utility
   - Update documentation
   - Add examples for new format

## Benefits

1. **Simplicity**: Clearer configuration format with explicit fields
2. **Maintainability**: Reduced complexity in configuration loading
3. **Performance**: Improved duplicate detection algorithm
4. **Extensibility**: Easier to add new fields and features
5. **Testability**: Simplified path handling and configuration loading make testing easier
6. **User Experience**: More intuitive configuration format

## Drawbacks and Mitigation

1. **Breaking Changes**:
   - Migrate gradually with backward compatibility
   - Provide clear migration guides and tools

2. **Learning Curve**:
   - Improved documentation with examples
   - Clear error messages for invalid configurations
   - Migration utilities to assist users

## Conclusion

The proposed changes to the configuration format and structure will significantly reduce complexity in the VCSPull codebase. By adopting a more explicit and standardized configuration format, we can eliminate many of the issues identified in the codebase audit while improving the user experience and maintainability of the system. 