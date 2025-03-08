# VCSPull Test Coverage Checklist

This document provides a comprehensive checklist of test coverage for the VCSPull codebase, identifying common use cases, uncommon scenarios, and edge cases that should be tested to ensure robust functionality.

## Core Modules and Their Testing Priorities

### 1. Configuration Management (config.py, _internal/config_reader.py)

#### Common Cases:
- [x] **Config File Loading:** Loading valid YAML/JSON files from common locations *(tests/test_config_file.py: test_dict_equals_yaml, test_find_config_files)*
  - [x] Home directory (~/.vcspull.yaml, ~/.vcspull.json) *(tests/test_config_file.py: test_find_config_include_home_config_files)*
  - [x] XDG config directory *(tests/test_utils.py: test_vcspull_configdir_xdg_config_dir)*
  - [x] Project-specific config files *(tests/test_config_file.py: test_in_dir)*
- [x] **Directory Expansion:** Resolving paths with tilde (~) and environment variables *(tests/test_config_file.py: test_expandenv_and_homevars, test_expand_shell_command_after)*
- [x] **Basic Configuration Format:** Standard repository declarations with required fields *(tests/test_config.py: test_simple_format)*
- [x] **Multiple Repositories:** Configurations with multiple repositories in different paths *(tests/test_config_file.py: test_dict_equals_yaml)*
- [x] **Filtering Repositories:** Basic pattern matching for repository names *(tests/test_repo.py: test_filter_name, test_filter_dir, test_filter_vcs)*
- [x] **Repository Extraction:** Converting raw configs to normalized formats *(tests/test_repo.py: test_to_dictlist)*

#### Uncommon Cases:
- [x] **Deeply Nested Configurations:** Multiple levels of directory nesting in config *(tests/test_config_file.py: test_dict_equals_yaml)*
- [x] **Configuration Merging:** Combining multiple configuration files *(tests/test_config_file.py: test_merge_nested_dict)*
- [ ] **Duplicate Detection:** Identifying and handling duplicate repositories
- [ ] **Conflicting Configurations:** When the same repository is defined differently in multiple files
- [x] **Relative Paths:** Config files using relative paths that need resolution *(tests/test_config.py: test_relative_dir)*
- [x] **Custom Config Locations:** Loading from non-standard locations *(tests/test_config_file.py: test_find_config_match_string, test_find_config_match_list)*

#### Edge Cases:
- [ ] **Empty Configuration Files:** Files with empty content or only comments
- [ ] **Malformed YAML/JSON:** Syntax errors in configuration files
- [ ] **Circular Path References:** Directory structures with circular references
- [ ] **Very Large Configurations:** Performance with hundreds of repositories
- [ ] **Case Sensitivity Issues:** Path case differences between config and filesystem
- [ ] **Unicode and Special Characters:** In repository names, paths, and URLs *(tests/test_validator.py: test_validate_path_with_special_characters - partially covered)*
- [ ] **Inaccessible Paths:** Referenced paths that exist but are not accessible
- [ ] **Path Traversal Attempts:** Paths attempting to use "../" to escape sandboxed areas
- [x] **Missing Config Files:** Behavior when specified config files don't exist *(tests/test_config_file.py: test_multiple_config_files_raises_exception)*
- [x] **Mixed VCS Types:** Configurations mixing git, hg, and svn repositories *(tests/test_repo.py: test_vcs_url_scheme_to_object)*
- [ ] **Invalid URLs:** URL schemes that don't match the specified VCS type

### 2. Validation (validator.py, schemas.py)

#### Common Cases:
- [x] **Basic Schema Validation:** Checking required fields in configurations *(tests/test_validator.py: test_validate_config_with_valid_config)*
- [x] **VCS Type Validation:** Validating supported VCS types (git, hg, svn) *(tests/test_validator.py: test_validate_repo_config_valid)*
- [x] **URL Validation:** Basic validation of repository URLs *(tests/test_validator.py: test_validate_repo_config_empty_values)*
- [x] **Path Validation:** Checking that paths are valid *(tests/test_validator.py: test_validate_path_valid, test_validate_path_invalid)*
- [x] **Git Remote Validation:** Validating git remote configurations *(tests/test_sync.py: test_updating_remote)*

#### Uncommon Cases:
- [x] **Nested Validation Errors:** Multiple validation issues in nested structures *(tests/test_validator.py: test_validate_config_nested_validation_errors)*
- [ ] **URL Scheme Mismatches:** When URL scheme doesn't match the VCS type
- [ ] **Advanced URL Validation:** SSH URLs, usernames in URLs, port specifications
- [x] **Custom Fields Validation:** Handling of non-standard fields in configs *(tests/test_validator.py: test_validate_repo_config_with_extra_fields)*
- [ ] **Shell Command Validation:** Validating shell commands in configs

#### Edge Cases:
- [x] **Pydantic Model Conversion:** Converting between raw and validated models *(tests/test_validator.py: test_format_pydantic_errors)*
- [ ] **Partial Configuration Validation:** Validating incomplete configurations
- [x] **Deeply Nested Errors:** Validation errors in deeply nested structures *(tests/test_validator.py: test_validate_config_nested_validation_errors)*
- [ ] **Custom Protocol Handling:** git+ssh://, git+https://, etc.
- [ ] **Invalid Characters:** Non-printable or control characters in fields
- [ ] **Very Long Field Values:** Fields with extremely long values
- [ ] **Mixed Case VCS Types:** "Git" vs "git" vs "GIT"
- [ ] **Conflicting Validation Rules:** When multiple validation rules conflict
- [x] **Empty vs. Missing Fields:** Distinction between empty and missing fields *(tests/test_validator.py: test_validate_repo_config_missing_keys, test_validate_repo_config_empty_values)*
- [ ] **Type Coercion Issues:** When field values are of unexpected types
- [ ] **Invalid URL Formats by VCS Type:** URLs that are valid in general but invalid for specific VCS

### 3. CLI Interface (cli/__init__.py, cli/sync.py)

#### Common Cases:
- [x] **Basic CLI Invocation:** Running commands with minimal arguments *(tests/test_cli.py: test_sync)*
- [x] **Repository Filtering:** Using patterns to select repositories *(tests/test_cli.py: test_sync_cli_filter_non_existent)*
- [x] **Config File Specification:** Using custom config files *(tests/test_cli.py: various test fixtures with config paths)*
- [x] **Default Behaviors:** Running with default options *(tests/test_cli.py: test_sync fixtures with default args)*
- [ ] **Help Command:** Displaying help information
- [ ] **Version Display:** Showing version information

#### Uncommon Cases:
- [x] **Multiple Filters:** Using multiple inclusion/exclusion patterns *(tests/test_cli.py: test_sync_cli_filter_non_existent with multiple args)*
- [ ] **Interactive Mode:** CLI behavior in interactive mode
- [ ] **Multiple Config Files:** Specifying multiple config files
- [ ] **Special Output Formats:** JSON, detailed, etc.
- [ ] **Custom Working Directory:** Running from non-standard working directories
- [ ] **Verbosity Levels:** Different verbosity settings

#### Edge Cases:
- [ ] **Invalid Arguments:** Handling of invalid command-line arguments
- [x] **Output Redirection:** Behavior when stdout/stderr are redirected *(tests/test_cli.py: uses capsys fixture in most tests)*
- [ ] **Terminal vs. Non-Terminal:** Behavior in different terminal environments
- [ ] **Signal Handling:** Response to interrupts and other signals
- [ ] **Unknown Commands:** Behavior with non-existing commands
- [ ] **Very Long Arguments:** Command line arguments with extreme length
- [ ] **Unicode in CLI Arguments:** International characters in arguments
- [ ] **Permission Issues:** Running with insufficient permissions
- [ ] **Environment Variable Overrides:** CLI behavior with environment variables
- [ ] **Parallel Execution:** Running multiple commands in parallel

### 4. Repository Operations (libvcs interaction)

#### Common Cases:
- [x] **Repository Cloning:** Basic cloning of repositories *(tests/test_sync.py: test_makes_recursive)*
- [x] **Repository Update:** Updating existing repositories *(tests/test_sync.py: test_updating_remote)*
- [x] **Remote Management:** Adding/updating remotes for Git *(tests/test_sync.py: test_updating_remote with remotes)*
- [ ] **Status Checking:** Checking repository status
- [x] **Success and Error Handling:** Managing operation outcomes *(tests/test_cli.py: test_sync_broken)*

#### Uncommon Cases:
- [ ] **Repository Authentication:** Cloning/updating repos requiring auth
- [x] **Custom Remote Configurations:** Non-standard remote setups *(tests/test_sync.py: UPDATING_REMOTE_FIXTURES with has_extra_remotes=True)*
- [ ] **Repository Hooks:** Pre/post operation hooks
- [x] **Shell Commands:** Executing shell commands after operations *(tests/test_config_file.py: test_expand_shell_command_after)*
- [ ] **Repository Recovery:** Recovering from failed operations

#### Edge Cases:
- [ ] **Network Failures:** Behavior during network interruptions
- [ ] **Interrupted Operations:** Handling of operations interrupted mid-way
- [ ] **Repository Corruption:** Dealing with corrupted repositories
- [ ] **Large Repositories:** Performance with very large repositories
- [ ] **Repository Lock Files:** Handling existing lock files
- [ ] **Concurrent Operations:** Multiple operations on the same repository
- [ ] **Shallow Clones:** Behavior with shallow clone operations
- [ ] **Submodule Handling:** Repositories with submodules
- [ ] **Unknown VCS Versions:** Operating with uncommon VCS versions
- [ ] **Custom Protocol Handlers:** git+ssh://, svn+https://, etc.
- [ ] **Path Collisions:** When different configurations target the same path

### 5. Utilities and Helpers (util.py, log.py)

#### Common Cases:
- [x] **Path Manipulation:** Basic path operations *(tests/test_config_file.py: test_expand_shell_command_after, test_expandenv_and_homevars)*
- [x] **Dictionary Updates:** Merging and updating configuration dictionaries *(tests/test_config_file.py: test_merge_nested_dict)*
- [ ] **Logging Configuration:** Basic logging setup and usage
- [ ] **Process Execution:** Running external commands

#### Uncommon Cases:
- [x] **Complex Path Resolution:** Resolving complex path references *(tests/test_config_file.py: test_expandenv_and_homevars)*
- [ ] **Advanced Logging:** Logging with different levels and formats
- [ ] **Process Timeouts:** Handling command execution timeouts
- [x] **Environment Variable Expansion:** In various contexts *(tests/test_utils.py: test_vcspull_configdir_env_var, test_vcspull_configdir_xdg_config_dir)*

#### Edge Cases:
- [ ] **Path Edge Cases:** Unicode, very long paths, special characters
- [ ] **Dictionary Merging Conflicts:** When merge keys conflict
- [ ] **Logging Under Load:** Behavior with high-volume logging
- [ ] **Process Execution Failures:** When commands fail or return errors
- [ ] **Environment with Special Characters:** Environment variables with unusual values
- [ ] **Shell Command Injection Prevention:** Security of process execution
- [ ] **Resource Limitations:** Behavior under resource constraints

## Pydantic Model Testing

As part of the transition to Pydantic models, these specific areas need thorough testing:

### Common Cases:
- [x] **Model Creation:** Creating models from valid data *(tests/test_validator.py: test_validate_config_with_valid_config)*
- [x] **Model Validation:** Basic validation of required fields *(tests/test_validator.py: test_validate_repo_config_missing_keys)*
- [ ] **Model Serialization:** Converting models to dictionaries
- [ ] **Field Type Coercion:** Automatic type conversion for compatible types

### Uncommon Cases:
- [ ] **Model Inheritance:** Behavior of model inheritance
- [ ] **Custom Validators:** Advanced field validators
- [ ] **Model Composition:** Models containing other models
- [x] **Validation Error Handling:** Managing and reporting validation errors *(tests/test_validator.py: test_format_pydantic_errors)*

### Edge Cases:
- [ ] **Conversion Between Raw and Validated Models:** Edge cases in model conversion
- [ ] **Circular References:** Handling models with circular references
- [x] **Optional vs. Required Fields:** Behavior with different field requirements *(tests/test_validator.py: test_validate_repo_config_missing_keys)*
- [ ] **Default Values:** Complex default value scenarios
- [ ] **Union Types:** Fields accepting multiple types
- [ ] **Field Constraints:** Min/max length, regex patterns, etc.
- [ ] **Custom Error Messages:** Override of validation error messages
- [ ] **JSON Schema Generation:** Accuracy of generated schemas
- [ ] **Recursive Models:** Self-referential model structures
- [ ] **Discriminated Unions:** Type discrimination in unions

## Data-Driven and Property-Based Testing Opportunities

### Property-Based Testing:
- [ ] **Configuration Structure Invariants:** Properties that should hold for all valid configs
- [ ] **Model Conversion Roundtrips:** Converting between models and back preserves data
- [ ] **Path Normalization:** Properties of normalized paths
- [ ] **URL Parsing:** Properties of parsed and validated URLs
- [ ] **Repository Configuration Consistency:** Internal consistency of repository configs

### Data Generation Strategies:
- [ ] **Random Valid Configurations:** Generating syntactically valid configurations
- [ ] **Random Invalid Configurations:** Generating configurations with specific issues
- [ ] **Repository URL Generation:** Creating varied repository URLs
- [ ] **Path Generation:** Creating diverse filesystem paths
- [ ] **VCS Type Combinations:** Various combinations of VCS types and configurations

## Test Infrastructure Improvements

### Fixtures:
- [x] **Repository Fixtures:** Pre-configured repositories of different types *(tests/fixtures/example.py)*
- [x] **Configuration Fixtures:** Sample configurations of varying complexity *(tests/fixtures/example.py)*
- [ ] **File System Fixtures:** Mock file systems with different characteristics
- [ ] **Network Fixtures:** Mock network responses for repository operations
- [ ] **VCS Command Fixtures:** Mock VCS command execution

### Mocking:
- [x] **File System Mocking:** Simulating file system operations *(tests/helpers.py: EnvironmentVarGuard, tmp_path fixtures)*
- [ ] **Network Mocking:** Simulating network operations
- [x] **Process Execution Mocking:** Simulating command execution *(tests/test_cli.py: various monkeypatch uses)*
- [ ] **Time Mocking:** Controlling time-dependent operations

### Test Categories:
- [x] **Unit Tests:** Testing individual functions and methods *(most tests in the codebase)*
- [x] **Integration Tests:** Testing interactions between components *(tests/test_sync.py, tests/test_cli.py)*
- [ ] **End-to-End Tests:** Testing full workflows
- [ ] **Property Tests:** Testing invariant properties
- [ ] **Performance Tests:** Testing operation speed and resource usage
- [ ] **Security Tests:** Testing security properties

## Test Coverage Goals

### Overall Coverage Targets:
- [ ] **High-Risk Modules:** 95%+ coverage (config.py, validator.py)
- [ ] **Medium-Risk Modules:** 90%+ coverage (CLI modules, schema modules)
- [ ] **Low-Risk Modules:** 80%+ coverage (utility modules)

### Coverage Types:
- [ ] **Statement Coverage:** Executing all statements in the code
- [ ] **Branch Coverage:** Executing all branches in the code
- [ ] **Condition Coverage:** Testing all boolean sub-expressions
- [ ] **Path Coverage:** Testing all possible paths through the code

### Functional Coverage:
- [ ] **Configuration Loading:** 100% of configuration loading code paths
- [ ] **Validation:** 100% of validation code paths
- [ ] **Repository Operations:** 95% of operation code paths
- [ ] **CLI Interface:** 90% of CLI code paths
- [ ] **Error Handling:** 95% of error handling code paths
