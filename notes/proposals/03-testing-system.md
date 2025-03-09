# Testing System Proposal

> Restructuring the testing framework to improve maintainability, coverage, and reliability.

## Current Issues

The audit identified several issues with the current testing system:

1. **Large Test Files**: Some test files like `test_config.py` (520 lines) and `test_cli.py` (349 lines) are too large to maintain effectively.
2. **Lack of Test Isolation**: Many tests depend on global state or real filesystem access.
3. **Manual Test Fixtures**: Most test fixtures are manually created rather than using pytest's fixture system.
4. **Limited Coverage**: Significant parts of the codebase lack proper test coverage.
5. **Inconsistent Testing Approach**: Multiple approaches to testing (pytest, unittest style, manual) create confusion.
6. **Missing Property-Based and Doctest Testing**: No property-based tests or doctests for library functions.

## Proposed Changes

### 1. Test Organization

1. **Directory Structure Aligned with Source**:
   - Restructure test directories to mirror source directories
   - Split large test files into focused test modules

   ```
   tests/
   ├── conftest.py              # Main pytest fixtures
   ├── unit/                    # Unit tests
   │   ├── cli/                 # CLI tests (matching src structure)
   │   │   ├── test_sync.py
   │   │   └── test_detect.py
   │   ├── config/              # Config tests
   │   │   ├── test_loading.py
   │   │   ├── test_validation.py
   │   │   └── test_parsing.py
   │   └── vcs/                 # VCS tests
   │       ├── test_git.py
   │       ├── test_hg.py
   │       └── test_detect.py
   ├── integration/             # Integration tests
   │   ├── test_config_loading.py
   │   └── test_repo_operations.py
   ├── functional/              # End-to-end tests
   │   └── test_cli_commands.py
   ├── examples/                # Documented examples (used in doctests)
   │   ├── config/
   │   └── cli/
   └── fixtures/                # Test fixtures and data
       ├── configs/             # Example config files
       └── repositories/        # Test repo structures
   ```

2. **Naming Conventions**:
   - Unit tests: `test_<unit>_<behavior>.py` (e.g., `test_config_validation.py`)
   - Integration tests: `test_<component1>_<component2>.py` (e.g., `test_config_loading.py`)
   - Functional tests: `test_<feature>.py` (e.g., `test_cli_commands.py`)

### 2. Improved Fixtures System

1. **Centralized Fixture Management**:
   - Create hierarchical fixtures in `conftest.py` files
   - Use fixture factories for parameterized fixtures
   - Provide isolated filesystem fixtures using `tmp_path`

   ```python
   import typing as t
   import os
   import pytest
   from pathlib import Path
   import yaml
   
   from vcspull import Repository
   from vcspull.config import ConfigFile
   
   # Path fixtures
   @pytest.fixture
   def config_dir(tmp_path: Path) -> Path:
       """Create a temporary directory for config files."""
       config_dir = tmp_path / "configs"
       config_dir.mkdir()
       return config_dir
   
   @pytest.fixture
   def repos_dir(tmp_path: Path) -> Path:
       """Create a temporary directory for repositories."""
       repos_dir = tmp_path / "repos"
       repos_dir.mkdir()
       return repos_dir
   
   # Configuration fixtures
   @pytest.fixture
   def sample_config_dict() -> dict:
       """Return a sample configuration dictionary."""
       return {
           "settings": {
               "sync_remotes": True,
               "default_vcs": "git"
           },
           "repositories": [
               {
                   "name": "repo1",
                   "url": "https://github.com/user/repo1.git",
                   "path": "~/code/repo1"
               },
               {
                   "name": "repo2",
                   "url": "https://github.com/user/repo2.git",
                   "path": "~/code/repo2",
                   "remotes": {
                       "upstream": "https://github.com/upstream/repo2.git"
                   }
               }
           ]
       }
   
   @pytest.fixture
   def sample_config_file(config_dir: Path, sample_config_dict: dict) -> Path:
       """Create a sample configuration file.
       
       Parameters
       ----------
       config_dir : Path
           Directory to place the config file
       sample_config_dict : dict
           Configuration dictionary to write
           
       Returns
       -------
       Path
           Path to the created config file
       """
       config_path = config_dir / "config.yaml"
       with open(config_path, "w") as f:
           yaml.safe_dump(sample_config_dict, f)
       return config_path
   
   @pytest.fixture
   def validated_config(sample_config_dict: dict) -> ConfigFile:
       """Return a validated configuration object.
       
       Parameters
       ----------
       sample_config_dict : dict
           Configuration dictionary to validate
           
       Returns
       -------
       ConfigFile
           Validated configuration object
       """
       return ConfigFile.model_validate(sample_config_dict)
   
   # Repository fixtures
   @pytest.fixture
   def sample_repository() -> Repository:
       """Return a sample repository object."""
       return Repository(
           name="test-repo",
           url="https://github.com/user/test-repo.git",
           path="~/code/test-repo"
       )
   
   # Mock repository fixtures
   @pytest.fixture
   def git_repo_factory(repos_dir: Path):
       """Factory for creating git repository test fixtures.
       
       Parameters
       ----------
       repos_dir : Path
           Base directory for repositories
           
       Returns
       -------
       Callable
           Function to create git repositories
       """
       def _create_git_repo(name: str, with_remote: bool = False) -> Path:
           """Create a git repository for testing.
           
           Parameters
           ----------
           name : str
               Repository name
           with_remote : bool, optional
               Whether to add a remote, by default False
               
           Returns
           -------
           Path
               Path to the repository
           """
           repo_path = repos_dir / name
           repo_path.mkdir(parents=True, exist_ok=True)
           
           # Git initialization
           os.system(f"git init {repo_path}")
           
           # Add some content
           readme = repo_path / "README.md"
           readme.write_text(f"# {name}\n\nTest repository")
           
           # Initial commit
           os.chdir(repo_path)
           os.system("git add README.md")
           os.system("git config user.email 'test@example.com'")
           os.system("git config user.name 'Test User'")
           os.system("git commit -m 'Initial commit'")
           
           # Add remote if requested
           if with_remote:
               os.system("git remote add origin https://github.com/user/test-repo.git")
           
           return repo_path
       
       return _create_git_repo
   ```

2. **Pydantic Model Testing Fixtures**:
   - Add fixtures for generating and validating models
   - Provide helpers for property-based testing
   - Support testing validation with bad input

   ```python
   import typing as t
   import pytest
   from pydantic import ValidationError
   from hypothesis import given, strategies as st
   from hypothesis.provisional import urls
   
   from vcspull.config import Repository, ConfigFile, Settings
   
   # Pydantic validation testing
   @pytest.fixture
   def assert_validation_error():
       """Fixture to assert that validation errors occur for bad input.
       
       Returns
       -------
       Callable
           Function to assert validation errors
       """
       def _assert_validation_error(model_cls, data: dict, expected_error_count: int = 1):
           """Assert that validation raises an error.
           
           Parameters
           ----------
           model_cls : Type[BaseModel]
               Pydantic model class to validate against
           data : dict
               Data to validate
           expected_error_count : int, optional
               Expected number of errors, by default 1
           """
           with pytest.raises(ValidationError) as excinfo:
               model_cls.model_validate(data)
           
           errors = excinfo.value.errors()
           assert len(errors) >= expected_error_count, \
               f"Expected at least {expected_error_count} error(s), got {len(errors)}"
       
       return _assert_validation_error
   
   # Hypothesis strategies for model generation
   @pytest.fixture
   def repository_strategy():
       """Strategy for generating valid Repository models.
       
       Returns
       -------
       SearchStrategy
           Hypothesis strategy for generating repositories
       """
       return st.builds(
           Repository,
           name=st.one_of(st.none(), st.text(min_size=1)),
           url=urls(),
           path=st.text(min_size=1),
           vcs=st.one_of(st.none(), st.just("git"), st.just("hg"), st.just("svn")),
           rev=st.one_of(st.none(), st.text()),
           remotes=st.dictionaries(
               keys=st.text(min_size=1),
               values=urls(),
               max_size=3
           )
       )
   
   @pytest.fixture
   def config_strategy(repository_strategy):
       """Strategy for generating valid ConfigFile models.
       
       Parameters
       ----------
       repository_strategy : SearchStrategy
           Strategy for generating repositories
           
       Returns
       -------
       SearchStrategy
           Hypothesis strategy for generating config files
       """
       return st.builds(
           ConfigFile,
           settings=st.builds(Settings),
           repositories=st.lists(repository_strategy, max_size=5),
           includes=st.lists(st.text(), max_size=3)
       )
   ```

### 3. Testing Approaches

1. **Unit Testing with pytest**:
   - Test each component in isolation
   - Use proper mocking and fixtures
   - Focus on good test coverage

   ```python
   import typing as t
   import pytest
   from pathlib import Path
   
   from vcspull.config import load_config_file, ConfigError
   
   def test_load_config_file_yaml(config_dir: Path):
       """Test loading YAML configuration.
       
       Parameters
       ----------
       config_dir : Path
           Temporary directory for config files
       """
       # Arrange
       config_path = config_dir / "config.yaml"
       with open(config_path, "w") as f:
           f.write("repositories:\n  - name: test\n    url: https://github.com/test/test.git\n    path: ~/test")
       
       # Act
       config = load_config_file(config_path)
       
       # Assert
       assert config == {
           "repositories": [
               {
                   "name": "test", 
                   "url": "https://github.com/test/test.git", 
                   "path": "~/test"
               }
           ]
       }
   
   def test_load_config_file_error(config_dir: Path):
       """Test handling of invalid configuration files.
       
       Parameters
       ----------
       config_dir : Path
           Temporary directory for config files
       """
       # Arrange
       config_path = config_dir / "invalid.yaml"
       with open(config_path, "w") as f:
           f.write("invalid: yaml: content")
       
       # Act & Assert
       with pytest.raises(ConfigError) as excinfo:
           load_config_file(config_path)
       
       assert "Failed to parse" in str(excinfo.value)
   ```

2. **Property-Based Testing with Hypothesis**:
   - Use property-based testing for validation and serialization
   - Test invariants and properties rather than specific examples

   ```python
   import typing as t
   import pytest
   from hypothesis import given, strategies as st
   
   from vcspull.config import Repository
   
   @given(
       url=urls(),
       path=st.text(min_size=1)
   )
   def test_repository_path_normalization(url: str, path: str):
       """Test that path normalization works for any valid input.
       
       Parameters
       ----------
       url : str
           Repository URL (generated)
       path : str
           Repository path (generated)
       """
       # Arrange & Act
       repo = Repository(url=url, path=path)
       
       # Assert
       assert repo.path is not None
       # Path should never end with path separator
       assert not repo.path.endswith("/")
       assert not repo.path.endswith("\\")
   
   @given(st.data())
   def test_repository_model_roundtrip(data):
       """Test model serialization/deserialization roundtrip.
       
       Parameters
       ----------
       data : st.DataObject
           Hypothesis data object
       """
       # Arrange
       repo_strategy = data.draw(repository_strategy())
       
       # Act
       repo_dict = repo_strategy.model_dump()
       new_repo = Repository.model_validate(repo_dict)
       new_dict = new_repo.model_dump()
       
       # Assert
       assert repo_dict == new_dict, "Serialization roundtrip failed"
   ```

3. **Integration Testing**:
   - Test multiple components working together
   - Use test fixtures to simulate real-world usage
   - Focus on boundaries between components

   ```python
   import typing as t
   import pytest
   from pathlib import Path
   
   from vcspull.config import process_configuration
   
   def test_process_configuration_with_includes(config_dir: Path):
       """Test processing configuration with includes.
       
       Parameters
       ----------
       config_dir : Path
           Temporary directory for config files
       """
       # Arrange
       main_config = config_dir / "main.yaml"
       with open(main_config, "w") as f:
           f.write("""
           settings:
             sync_remotes: true
           repositories:
             - name: repo1
               url: https://github.com/user/repo1.git
               path: ~/code/repo1
           includes:
             - {}
           """.format(str(config_dir / "included.yaml")))
       
       included_config = config_dir / "included.yaml"
       with open(included_config, "w") as f:
           f.write("""
           repositories:
             - name: repo2
               url: https://github.com/user/repo2.git
               path: ~/code/repo2
           """)
       
       # Act
       config = process_configuration([main_config])
       
       # Assert
       assert len(config.repositories) == 2
       assert config.repositories[0].name == "repo1"
       assert config.repositories[1].name == "repo2"
       assert config.settings.sync_remotes is True
   ```

4. **Doctests for Examples**:
   - Add doctests to key functions for documentation
   - Create examples that serve as both docs and tests
   - Focus on showing how to use the library

   ```python
   def normalize_path(path_str: str) -> str:
       """Normalize path to string representation.
       
       Expands user home directory (~) and environment variables.
       Returns an absolute path.
       
       Parameters
       ----------
       path_str : str
           Path string to normalize
           
       Returns
       -------
       str
           Normalized path as string
           
       Examples
       --------
       >>> from vcspull.utils.path import normalize_path
       >>> import os
       
       Normalize home directory:
       
       >>> path = normalize_path("~/projects")
       >>> path.startswith(os.path.expanduser("~"))
       True
       
       Normalize environment variables:
       
       >>> os.environ["TEST_DIR"] = "/tmp/test"
       >>> normalize_path("$TEST_DIR/project")
       '/tmp/test/project'
       """
       path = Path(os.path.expandvars(path_str)).expanduser()
       return str(path.resolve() if path.exists() else path.absolute())
   ```

### 4. Continuous Testing Setup

1. **Test Watcher Configuration**:
   - Set up `pytest-watcher` for continuous testing during development
   - Configure different watch modes for different test types

   ```ini
   # pyproject.toml
   [tool.pytest.ini_options]
   testpaths = ["tests"]
   python_files = ["test_*.py"]
   doctest_optionflags = ["NORMALIZE_WHITESPACE", "IGNORE_EXCEPTION_DETAIL"]
   
   [tool.ptw]
   runner = "pytest"
   ```

2. **CI Pipeline Integration**:
   - Configure CI to run tests, coverage, and linting
   - Structure tests to run in logical groupings (unit, integration, functional)
   - Generate and publish coverage reports

### 5. Focused Test Coverage Strategy

1. **Coverage Goals**:
   - Aim for 90%+ coverage on core modules
   - Focus on critical paths and error handling
   - Identify and prioritize under-tested components

2. **Coverage Reports**:
   - Generate coverage reports as part of CI
   - Track coverage trends over time
   - Highlight areas needing attention

## Implementation Plan

1. **Phase 1: Test Structure Reorganization**
   - Restructure test directories to match source structure
   - Split large test files into focused modules
   - Add missing conftest.py files with basic fixtures

2. **Phase 2: Fixture Development**
   - Create comprehensive test fixtures
   - Implement property-based test strategies
   - Add support for isolated filesystem testing

3. **Phase 3: Test Coverage Improvement**
   - Identify under-tested components from coverage reports
   - Write tests for critical functionality
   - Focus on error handling and edge cases

4. **Phase 4: Documentation and Examples**
   - Add doctests to key functions
   - Create example code in tests/examples
   - Update documentation with examples

5. **Phase 5: Continuous Testing Setup**
   - Configure test watcher for development
   - Set up CI pipeline integration
   - Create reporting and monitoring for test results

## Benefits

1. **Improved Maintainability**: Better organized tests are easier to understand and extend
2. **Higher Test Coverage**: Comprehensive testing of all components improves reliability
3. **Better Documentation**: Doctests provide both documentation and verification
4. **Faster Development**: Continuous testing catches issues early
5. **Clearer Requirements**: Tests document expected behavior clearly
6. **Easier Refactoring**: Comprehensive tests make refactoring safer
7. **Improved Onboarding**: New developers can understand the code through tests

## Drawbacks and Mitigation

1. **Initial Implementation Effort**:
   - Implement changes gradually, focusing on most critical components first
   - Automate test organization where possible
   - Consider tools for helping generate initial tests

2. **Potential Over-Testing**:
   - Focus on value-adding tests rather than test count
   - Use code coverage to guide testing efforts
   - Balance unit, integration, and property-based tests

## Conclusion

The proposed testing system will significantly improve the maintainability and reliability of the VCSPull codebase. By organizing tests to match the source structure, improving fixtures, and using multiple testing approaches, we can ensure comprehensive test coverage and make the codebase more robust. The addition of property-based testing and doctests will also improve documentation and catch more edge cases.

This proposal aligns with the broader goal of streamlining the VCSPull codebase, making it more maintainable and intuitive. The improved testing system will support other proposals by providing a safety net for refactoring and ensuring new components meet quality standards. 