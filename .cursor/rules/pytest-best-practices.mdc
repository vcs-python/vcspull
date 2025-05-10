---
description: 
globs: tests/**/*.py
alwaysApply: false
---
# Ground Rules for Writing vcspull Tests

## 1. Study First, Be Homogenous
- **Analyze Existing Tests:** Before writing new tests, study `tests/test_sync.py`, `tests/test_config.py`, and other relevant test files to understand existing patterns, fixture usage, and assertion styles.
- **Maintain Consistency:** Strive for homogeneity in test structure, naming conventions, and overall style.
- **Project Conventions:** Adhere to project-specific conventions like using `typing as t` and `pathlib.Path` for all path manipulations.

## 2. Fixture Prioritization and Usage
- **`libvcs` Fixtures First:** For any VCS-related operations (creating repos, committing, checking status), **always** prioritize using fixtures from `libvcs.pytest_plugin` (available via `vcspull/conftest.py`). Examples:
    - `create_git_remote_repo`, `create_svn_remote_repo`, `create_hg_remote_repo` (and their `mercurial`/`subversion` counterparts if using those directly) for setting up test repositories.
    - `git_repo`, `svn_repo`, `hg_repo` for pre-configured `Sync` objects.
    - `git_commit_envvars` for environment variables needed for git commits.
- **Pytest Built-in Fixtures:** Utilize standard `pytest` fixtures like `tmp_path` for temporary files and directories.
- **Custom Project Fixtures:**
    - For common non-VCS setup (e.g., mocked home/CWD, config file setup), use or create well-defined fixtures.
    - Place shared fixtures in `vcspull/conftest.py` or `vcspull/tests/conftest.py`. Module-specific fixtures can reside in the test file itself.
    - Example: `home_path`, `cwd_path` (refactored to use `monkeypatch`), `setup_teardown_test_config_dir`.
- **`autouse=True`:** Use sparingly, only for fixtures that genuinely apply to *all* tests within their scope.

## 3. Mocking Strategy: `monkeypatch` vs. `mocker`
- **`monkeypatch` (pytest built-in):**
    - **Environment & Globals:** Use for modifying global settings, environment variables (`monkeypatch.setenv()`, `monkeypatch.delenv()`), the current working directory (`monkeypatch.chdir()`), or `sys.path`.
    - **Patching Attributes/Builtins:** Use `monkeypatch.setattr()` to modify attributes of classes/objects (e.g., `pathlib.Path.home`) or to replace functions/methods in external libraries or Python builtins. When needing to control the home directory, prefer using established project fixtures like `user_path`, `home_path`, or `config_path`. These fixtures are responsible for correctly mocking `pathlib.Path.home()` internally, typically using `monkeypatch.setattr()`. Avoid direct `monkeypatch.setattr(pathlib.Path, "home", ...)` in individual tests if a suitable project fixture exists.
    - **Dictionary Items:** Use `monkeypatch.setitem()` and `monkeypatch.delitem()` for modifying dictionaries.
    - Refer to [Pytest Monkeypatch Documentation](mdc:.dot-config/https:/docs.pytest.org/en/stable/how-to/monkeypatch.html).
- **`mocker` (from `pytest-mock`):**
    - **Application Code:** Primarily use for patching functions, methods, or objects *within the `vcspull` application code itself* (e.g., `mocker.patch('vcspull.cli.add.some_function')`).
    - **Assertions:** Use `mocker` when you need to assert how a mock was called, its return values, or to simulate side effects for your application's internal logic.
- **Clarity in Mocking (CRITICAL):**
    - For **every** use of `mocker.patch()`, `mocker.patch.object()`, `monkeypatch.setattr()`, `monkeypatch.setenv()`, etc., include comments explaining:
        - **`# WHAT:`**: What specific function, method, attribute, or environment variable is being simulated or altered.
        - **`# WHY:`**: The reason for the mock – what behavior is being controlled or isolated for the test's purpose.

## 4. Test Structure and Assertions
- **Atomic Tests:** Each test function should verify a single, specific piece of functionality or scenario.
- **Clear Naming:** Test functions and fixtures should have descriptive names (e.g., `test_add_repo_new_config_cwd`).
- **Docstrings:** Test functions should have a concise docstring explaining what is being tested.
- **Plain Assertions:** Use standard `assert` statements for verifications.
- **Logging:** Use the `caplog` fixture to assert specific log messages when testing command output or internal logging.
- **Error Handling:** Explicitly test for expected exceptions using `pytest.raises()`.

### Parameterized Test Structure
For tests involving multiple scenarios managed by `@pytest.mark.parametrize`, use `typing.NamedTuple` to define the structure of each test case. This promotes readability and consistency.
- Include a `test_id: str` field in the `NamedTuple` for clear test identification in pytest output.
- Define a list of these `NamedTuple` instances for your test scenarios.
- Use `pytest.mark.parametrize` with `ids=lambda tc: tc.test_id` (or similar) for descriptive test names.

```python
# Example of Parameterized Test Structure
import typing as t
import pytest

class MyTestScenario(t.NamedTuple):
    test_id: str
    input_arg: str
    expected_output: str
    # ... other relevant parameters

TEST_SCENARIOS: list[MyTestScenario] = [
    MyTestScenario(test_id="case_alpha", input_arg="foo", expected_output="bar"),
    MyTestScenario(test_id="case_beta", input_arg="baz", expected_output="qux"),
]

@pytest.mark.parametrize(
    MyTestScenario._fields,
    TEST_SCENARIOS,
    ids=[tc.test_id for tc in TEST_SCENARIOS] # Or ids=lambda tc: tc.test_id
)
def test_my_feature(
    input_arg: str, expected_output: str, # Corresponds to NamedTuple fields (test_id usually not passed)
    # ... other fixtures ...
    test_id: str, # if you need test_id inside the test, otherwise omit from signature
) -> None:
    # ... test logic using input_arg and asserting against expected_output ...
    actual_output = f"processed_{input_arg}" # Replace with actual function call
    assert actual_output == expected_output
    # Note: test_id is automatically unpacked by parametrize if present in NamedTuple fields
    # and also passed as an argument if included in the test function signature.
```

### Asserting CLI Output
When testing CLI commands using `capsys` (for stdout/stderr) or `caplog` (for log messages), define expected output clearly. A common pattern is to check for the presence (or absence) of a list of substring "needles" within the captured output.

```python
# Example of Asserting CLI Output
# (within a test function that uses capsys or caplog)

# Assuming your NamedTuple for parameters includes:
# expected_in_out: t.Optional[t.Union[str, list[str]]] = None
# expected_not_in_out: t.Optional[t.Union[str, list[str]]] = None

# Example: Capturing stdout
# captured_stdout = capsys.readouterr().out
# output_to_check = captured_stdout

# Example: Capturing log messages
# output_to_check = \"\\n\".join(rec.message for rec in caplog.records)


# Generic checking logic:
# if expected_in_out is not None:
#     needles = [expected_in_out] if isinstance(expected_in_out, str) else expected_in_out
#     for needle in needles:
#         assert needle in output_to_check, f"Expected '{needle}' in output"

# if expected_not_in_out is not None:
#     needles = [expected_not_in_out] if isinstance(expected_not_in_out, str) else expected_not_in_out
#     for needle in needles:
#         assert needle not in output_to_check, f"Did not expect '{needle}' in output"
```

## 5. Code Coverage and Quality
- **100% Coverage:** Aim for 100% test coverage for all new or modified code in `cli/add.py` and `cli/add_from_fs.py` (and any other modules).
- **Test All Paths:** Ensure tests cover success cases, failure cases, edge conditions, and all logical branches within the code.
- **Development Workflow:** Adhere to the project's quality assurance process:
    ```
    uv run ruff check . --fix
    uv run ruff format .
    uv run mypy
    uv run py.test --cov -v
    ```
  (Run these commands locally to verify changes).

## 6. `vcspull`-Specific Considerations
- **Configuration Files:**
    - When testing config loading, mock `find_home_config_files` appropriately.
    - **Always** use the project's helper functions (e.g., `vcspull.tests.helpers.write_config` or the higher-level `vcspull.tests.helpers.save_config_yaml`) to create temporary `.vcspull.yaml` files within your tests (typically in `tmp_path` or `config_path`). Avoid direct `yaml.dump` and `file.write_text` for config file creation to maintain consistency and reduce boilerplate.
- **Path Expansion:** Be mindful of `expand_dir`. If testing logic that depends on its behavior, provide controlled mocks for it or ensure `home_path` / `cwd_path` fixtures correctly influence its resolution.
- **Avoid Manual VCS Subprocesses:**
    - **Do not** use `subprocess.run(["git", ...])` or similar direct VCS command calls for setting up repository states in tests if a `libvcs` fixture or library function can achieve the same result.
    - The only exception is when testing a function that *itself* directly uses `subprocess` (e.g., `get_git_origin_url`).
    - Refactor tests like `test_add_from_fs_integration_with_libvcs` to use `create_git_remote_repo` from `libvcs` instead of manual `git init` calls via `subprocess`.

### Filesystem State Management and `shutil`
- **`tmp_path` is Primary:** Rely on `pytest` fixtures like `tmp_path` (and derived fixtures such as `user_path`, `config_path`) for creating and managing temporary files and directories needed by tests. Pytest automatically handles the cleanup of these resources.
- **Avoid Manual Cleanup of `tmp_path` Resources:** Manual cleanup of files/directories created within `tmp_path` using `shutil` (e.g., `shutil.rmtree()`) should generally be unnecessary, as pytest's fixture management handles this.
- **`shutil` for Pre-conditions:** However, `shutil` operations (or standard library functions like `os.remove`, `pathlib.Path.unlink`, `pathlib.Path.mkdir`) can be legitimately used *during the setup phase of a test (before the code under test is executed)*. This is appropriate when you need to establish specific filesystem pre-conditions *within* the `tmp_path` environment that are crucial for the test scenario.
    - **Example:** Ensuring a directory does *not* exist before testing an operation that is expected to create it, or ensuring a specific file *does* exist. The usage of `if my_git_repo.is_dir(): shutil.rmtree(my_git_repo)` in `tests/test_cli.py` (within `test_sync_broken`) is an example of setting such a pre-condition: it ensures that the target directory for a repository is removed before `vcspull sync` is called, allowing tests to consistently observe cloning behavior.

By following these rules, we can ensure that new tests are robust, maintainable, consistent with the existing test suite, and effectively leverage the capabilities of `pytest` and `libvcs`.