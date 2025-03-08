# VCSPull TODO List

This document outlines the tasks needed to improve the test coverage, type safety, and overall quality of the VCSPull codebase based on the test audit plan.

## Progress Update (2025-03-08)

- ⬜ Initiated Pydantic integration for improved type safety and validation
  - Plan to replace TypedDict with Pydantic models
  - Will use Pydantic validators instead of manual validation functions
  - Will leverage Pydantic's built-in error handling

- ⬜ Enhanced test coverage for the validator module
  - Will add tests for edge cases and complex configurations
  - Will ensure all tests pass with mypy in strict mode
  - Need to update tests to work with Pydantic models

## 1. Type Safety Improvements

- [ ] **Implement Pydantic Models**
  - [ ] Replace TypedDict definitions with Pydantic models
  - [ ] Add field validators with meaningful error messages
  - [ ] Use Pydantic's built-in error handling
  - [ ] Create model hierarchies for nested configurations

- [ ] **Enhance Exception Hierarchy**
  - [ ] Expand `exc.py` with specific exception types for different error scenarios
  - [ ] Add rich exception metadata (path, url, suggestions, risk level)
  - [ ] Integrate exceptions with Pydantic validation errors

- [ ] **Improve Type Definitions**
  - [ ] Revise `types.py` to use Pydantic models instead of TypedDict
  - [ ] Create model aliases for complex types to improve readability
  - [ ] Add Protocol interfaces for structural typing where appropriate

- [ ] **Type Annotation Completeness**
  - [ ] Audit all functions for missing type annotations
  - [ ] Add return type annotations to all functions
  - [ ] Use Optional and Union types appropriately
  - [ ] Properly annotate all class methods

- [ ] **Configure Strict Type Checking**
  - [ ] Strict mode enabled in `pyproject.toml` under `[tool.mypy]`
  - [ ] Recommended type checking flags enabled
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
  - [ ] Update validator tests to use Pydantic models
  - [ ] Add tests for each validation function and validator
  - [ ] Test validation of malformed configurations
  - [ ] Ensure all validators throw appropriate exceptions

## 3. Test Infrastructure

- [ ] **Improve Test Fixtures**
  - [ ] Create reusable fixtures for common test scenarios
  - [ ] Implement typed fixtures using Protocols and Pydantic models
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

- [ ] **Add Pydantic Model Documentation**
  - [ ] Document model schemas and field constraints
  - [ ] Add examples of model usage
  - [ ] Document validation logic and error messages
  - [ ] Create API documentation for Pydantic models

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
   - [ ] Implement base Pydantic models for configuration
   - [ ] Integrate Pydantic validation with existing validation logic
   - [ ] Configure strict type checking
   - [ ] Update validator tests to work with Pydantic models

2. **Medium-term Goals**
   - [ ] Improve test fixtures
   - [ ] Add tests for CLI operations
   - [ ] Improve docstrings
   - [ ] Refactor for better testability

3. **Long-term Objectives**
   - [ ] Implement property-based testing
   - [ ] Achieve 90%+ test coverage
   - [ ] Complete documentation overhaul
   - [ ] Integrate comprehensive CI checks

## Next Steps

1. **Create Pydantic Models**
   - Create base models for RawConfigDict and ConfigDict
   - Add validators for required fields and constraints
   - Implement serialization and deserialization methods

2. **Update Validation Logic**
   - Replace manual validators with Pydantic validators
   - Integrate Pydantic error handling with existing exceptions
   - Update validation tests to use Pydantic models

3. **Update Config Processing**
   - Update config processing to use Pydantic models
   - Ensure backward compatibility with existing code
   - Add tests for model-based config processing

## Metrics and Success Criteria

- [ ] **Type Safety**
  - [ ] Pass mypy in strict mode with zero warnings
  - [ ] 100% of functions have type annotations
  - [ ] All configuration types defined as Pydantic models

- [ ] **Test Coverage**
  - [ ] Overall test coverage > 90%
  - [ ] Core modules coverage > 95%
  - [ ] All public APIs have tests

- [ ] **Documentation**
  - [ ] All public APIs documented
  - [ ] All Pydantic models documented
  - [ ] Examples for all major features
