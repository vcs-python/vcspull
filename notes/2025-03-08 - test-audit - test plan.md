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
     
     class NetworkError(VCSPullException):
         """Network-related errors."""
     
     class AuthenticationError(NetworkError):
         """Authentication failures."""
     
     class RepositoryStateError(VCSPullException):
         """Error with repository state."""
     ```

2. **Refactor Validator Module**
   - Update `src/vcspull/validator.py` to use the specific exception types
   - Add detailed error messages with context information
   - Add validation for URL schemes, special characters, and path traversal

3. **Enhance Error Reporting**
   - Add context information to all exceptions (file/line, operation in progress)
   - Include recovery suggestions in error messages
   - Add error codes for programmatic handling

### B. Add Testability Hooks

1. **Dependency Injection**
   - Refactor VCS operations to accept injectable dependencies:
     ```python
     def update_repo(repo, vcs_factory=None, network_manager=None):
         vcs_factory = vcs_factory or default_vcs_factory
         network_manager = network_manager or default_network_manager
         # Use these injected dependencies for better testing
     ```

2. **Add State Inspection Methods**
   - Add methods to inspect repository state:
     ```python
     def get_repository_state(repo_path):
         """Return detailed repository state information."""
     
     def is_detached_head(repo_path):
         """Check if repository is in detached HEAD state."""
     ```

3. **Add Test Mode Flag**
   - Add a test mode flag to enable special behaviors for testing:
     ```python
     def sync_repositories(repos, test_mode=False):
         """Sync repositories with test mode support.
         
         In test mode, additional logging and safeguards are enabled.
         """
     ```

### C. Separate Concerns for Better Testability

1. **Extract Network Operations**
   - Create a separate module for network operations:
     ```python
     # src/vcspull/_internal/network.py
     def perform_request(url, auth=None, retry_strategy=None):
         """Perform HTTP request with configurable retry strategy."""
     ```

2. **Extract Shell Command Execution**
   - Create a separate module for shell command execution:
     ```python
     # src/vcspull/_internal/shell.py
     def execute_command(command, env=None, cwd=None, timeout=None):
         """Execute shell command with configurable parameters."""
     ```

3. **Extract Filesystem Operations**
   - Create a separate module for filesystem operations:
     ```python
     # src/vcspull/_internal/fs.py
     def ensure_directory(path, mode=0o755):
         """Ensure directory exists with proper permissions."""
     ```

### D. Add Simulation Capabilities

1. **Add Network Simulation**
   - Add capability to simulate network conditions:
     ```python
     # src/vcspull/_internal/testing/network.py
     def simulate_network_condition(condition_type, duration=None):
         """Simulate network condition (latency, outage, etc.)."""
     ```

2. **Add Repository State Simulation**
   - Add capability to simulate repository states:
     ```python
     # src/vcspull/_internal/testing/repo.py
     def simulate_repository_state(repo_path, state_type):
         """Simulate repository state (detached HEAD, merge conflict, etc.)."""
     ```

## 2. Additional Tests to Add

### A. Configuration and Validation Tests

1. **Malformed Configuration Tests**
   - Test with invalid YAML syntax
   - Test with invalid JSON syntax
   - Test with incorrect indentation in YAML
   - Test with duplicate keys

2. **URL Validation Tests**
   - Test with invalid URL schemes
   - Test with missing protocol prefixes
   - Test with special characters in URLs
   - Test with extremely long URLs

3. **Path Validation Tests**
   - Test with path traversal attempts (`../../../etc/passwd`)
   - Test with invalid characters in paths
   - Test with unicode characters in paths
   - Test with extremely long paths

### B. VCS-Specific Operation Tests

1. **Git Branch and Tag Tests**
   - Test checkout of specific branches
   - Test checkout of specific tags
   - Test checkout of specific commits
   - Test handling of non-existent branches/tags

2. **Git Submodule Tests**
   - Test repositories with submodules
   - Test submodule initialization and update
   - Test handling of missing submodules
   - Test nested submodules

3. **Repository State Tests**
   - Test handling of detached HEAD state
   - Test handling of merge conflicts
   - Test handling of uncommitted changes
   - Test handling of untracked files

4. **Authentication Tests**
   - Test SSH key authentication
   - Test username/password authentication
   - Test token authentication
   - Test authentication failures and recovery

### C. Error Handling and Recovery Tests

1. **Network Error Tests**
   - Test temporary network outages
   - Test permanent network failures
   - Test slow connections and timeouts
   - Test rate limiting scenarios

2. **Operation Interruption Tests**
   - Test interruption during clone
   - Test interruption during pull
   - Test interruption during checkout
   - Test recovery after interruption

3. **Resource Constraint Tests**
   - Test with disk space limitations
   - Test with memory constraints
   - Test with file descriptor limitations
   - Test with permission restrictions

### D. Platform-Specific Tests

1. **Windows-Specific Tests**
   - Test Windows path handling
   - Test with Windows line endings (CRLF)
   - Test with Windows file locking
   - Test with Windows shell commands

2. **Unicode and Internationalization Tests**
   - Test with non-ASCII repository names
   - Test with non-ASCII file paths
   - Test with non-ASCII branch names
   - Test with non-ASCII commit messages

### E. Performance and Concurrency Tests

1. **Large Repository Tests**
   - Test with large repositories (>1GB)
   - Test with repositories with many files
   - Test with repositories with deep history
   - Test with repositories with large binaries

2. **Concurrent Operation Tests**
   - Test multiple simultaneous operations
   - Test resource contention scenarios
   - Test locking mechanisms
   - Test progress reporting during long operations

### F. CLI Advanced Feature Tests

1. **Interactive Mode Tests**
   - Test interactive prompts with mock inputs
   - Test confirmation dialogs
   - Test error recovery prompts
   - Test with various user input scenarios

2. **Output Format Tests**
   - Test JSON output format
   - Test YAML output format
   - Test different verbosity levels
   - Test machine-readable output

3. **Dry Run Mode Tests**
   - Test preview functionality without changes
   - Verify expected vs. actual changes
   - Test reporting of what would be done
   - Test with various repository states

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
