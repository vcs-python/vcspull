# VCSPull TODO List

This document outlines the tasks needed to improve the test coverage, type safety, and overall quality of the VCSPull codebase based on the test audit plan.

## 1. Type Safety Improvements

- [ ] **Enhance Exception Hierarchy**
  - [ ] Expand `exc.py` with specific exception types for different error scenarios
  - [ ] Add rich exception metadata (path, url, suggestions, risk level)
  - [ ] Add proper typing to all exception classes

- [ ] **Improve Type Definitions**
  - [ ] Revise `types.py` to use more specific types (avoid Any)
  - [ ] Create type aliases for complex types to improve readability
  - [ ] Add Protocols for structural typing where appropriate
  - [ ] Ensure all TypedDict definitions are complete and accurate

- [ ] **Type Annotation Completeness**
  - [ ] Audit all functions for missing type annotations
  - [ ] Add return type annotations to all functions
  - [ ] Use Optional and Union types appropriately
  - [ ] Properly annotate all class methods

- [ ] **Configure Strict Type Checking**
  - [ ] Set up `mypy.ini` with strict mode enabled
  - [ ] Enable all recommended type checking flags
  - [ ] Add CI checks for type validation

## 2. Test Coverage Improvements

- [ ] **Config Module**
  - [ ] Add tests for edge cases in config parsing
  - [ ] Test invalid configuration handling
  - [ ] Test environment variable expansion
  - [ ] Test relative path resolution

- [ ] **CLI Module**
  - [ ] Add tests for each CLI command
  - [ ] Test error handling and output formatting
  - [ ] Test interactive mode behaviors
  - [ ] Mock external dependencies for reliable testing

- [ ] **Sync Operations**
  - [ ] Create tests for sync operations with different VCS types
  - [ ] Mock VCS operations for predictable testing
  - [ ] Test error handling during sync operations
  - [ ] Test recovery mechanisms

- [ ] **Validator Module**
  - [ ] Add tests for each validation function
  - [ ] Test validation of malformed configurations
  - [ ] Ensure all validators throw appropriate exceptions

## 3. Test Infrastructure

- [ ] **Improve Test Fixtures**
  - [ ] Create reusable fixtures for common test scenarios
  - [ ] Implement typed fixtures using Protocols
  - [ ] Add fixtures for different repository types (git, svn, etc.)

- [ ] **Add Property-Based Testing**
  - [ ] Implement Hypothesis test strategies for configuration generation
  - [ ] Test config parsing with random valid and invalid inputs
  - [ ] Add property-based tests for path handling

- [ ] **Improve Test Organization**
  - [ ] Organize tests by module/feature
  - [ ] Add integration tests for end-to-end workflows
  - [ ] Separate unit tests from integration tests

## 4. Documentation

- [ ] **Docstring Improvements**
  - [ ] Ensure all public functions have complete docstrings
  - [ ] Add examples to docstrings where appropriate
  - [ ] Document possible exceptions and error conditions
  - [ ] Add type information to docstrings (NumPy format)

- [ ] **Add Type Documentation**
  - [ ] Document complex type behavior
  - [ ] Add clear explanations for TypedDict usage
  - [ ] Document Protocol implementations

## 5. Refactoring for Testability

- [ ] **Dependency Injection**
  - [ ] Refactor code to allow for dependency injection
  - [ ] Make external dependencies mockable
  - [ ] Create interfaces for key components

- [ ] **Pure Functions**
  - [ ] Extract pure functions from complex methods
  - [ ] Move side effects to dedicated functions
  - [ ] Improve function isolation

## 6. CI Integration

- [ ] **Test Automation**
  - [ ] Configure CI to run all tests
  - [ ] Add coverage reporting
  - [ ] Set up test matrix for different Python versions
  - [ ] Implement test results visualization

- [ ] **Type Checking in CI**
  - [ ] Add mypy checks to CI pipeline
  - [ ] Add annotations coverage reporting

## Prioritized Tasks

1. **Immediate Priorities**
   - Enhance exception hierarchy
   - Complete type annotations
   - Configure strict type checking
   - Add tests for core configuration functionality

2. **Medium-term Goals**
   - Improve test fixtures
   - Add tests for CLI operations
   - Improve docstrings
   - Refactor for better testability

3. **Long-term Objectives**
   - Implement property-based testing
   - Achieve 90%+ test coverage
   - Complete documentation overhaul
   - Integrate comprehensive CI checks

## Metrics and Success Criteria

- [ ] **Type Safety**
  - [ ] Pass mypy in strict mode with zero warnings
  - [ ] 100% of functions have type annotations
  - [ ] No usage of `Any` without explicit justification

- [ ] **Test Coverage**
  - [ ] Overall test coverage > 90%
  - [ ] Core modules coverage > 95%
  - [ ] All public APIs have tests

- [ ] **Documentation**
  - [ ] All public APIs documented
  - [ ] All complex types documented
  - [ ] Examples for all major features
