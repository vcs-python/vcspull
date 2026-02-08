---
description: Fix multi-model review findings — validate, add test coverage, fix, and commit each as atomic changes
allowed-tools: Bash(git diff:*), Bash(git log:*), Bash(git branch:*), Bash(git status:*), Bash(git add:*), Bash(git commit:*), Bash(git checkout:*), Bash(uv run ruff:*), Bash(uv run mypy:*), Bash(uv run py.test:*), Bash(uv run pytest:*), Read, Grep, Glob, Edit, Write, Task
---

# Fix Review Findings

Process multi-model code review findings from the conversation context. Validate each finding independently against the actual codebase and project conventions, add test coverage where applicable, apply fixes as separate atomic commits, and ensure all quality gates pass before each commit.

---

## Phase 1: Parse and Prioritize Findings

**Goal**: Extract structured findings from the multi-model review report in the conversation.

**Actions**:

1. **Locate the review report** in the conversation context (output from `/multi-model:review` or similar)

2. **Extract each finding** into a numbered list with:
   - **Consensus level**: how many reviewers flagged it (3, 2, or 1)
   - **Severity**: Critical / Important / Suggestion (after consensus promotion)
   - **Reviewers**: which models flagged it (Claude, Gemini, GPT)
   - **File and line**: location in the codebase
   - **Description**: what the issue is
   - **Recommendation**: suggested fix

3. **Sort by priority** (process in this order):
   - Consensus Critical (3 reviewers) first
   - Consensus Critical (2 reviewers, promoted)
   - Consensus Important (2 reviewers, promoted)
   - Single-reviewer Important
   - Single-reviewer Suggestions

4. **Create a todo list** tracking each finding

5. **Read CLAUDE.md / AGENTS.md** for project conventions that apply to the fixes

---

## Phase 2: Validate Each Finding

**Goal**: Independently assess whether each finding is valid and actionable.

For EACH finding:

1. **Read the relevant code** — the exact lines referenced in the finding

2. **Check project conventions** — read CLAUDE.md/AGENTS.md to verify whether the finding aligns with project standards

3. **Review the project's own APIs** — read the function signatures, return types, and docstrings to understand the intended contract vs what the reviewers flagged

4. **Check existing test coverage** — search for tests that already cover this code path:
   ```
   Grep for the function/class name in tests/
   Read the relevant test file(s)
   ```

5. **Assess validity** using these criteria:
   - **Valid**: The finding identifies a real issue that aligns with project conventions
   - **Already addressed**: The issue was already fixed in a later commit
   - **Incorrect**: The reviewer misread the code or the suggestion would introduce a bug
   - **Out of scope**: Valid concern but not related to this branch's changes
   - **Pre-existing**: Valid but existed before this branch (not introduced by our changes)

6. **Document the verdict** for each finding:
   - If valid: note the planned fix AND test coverage strategy
   - If invalid: note the specific reason (cite code, tests, or conventions)

7. **Present the validation results** to the user before making changes:
   - List each finding with its verdict
   - For valid findings, describe: the fix + the test approach
   - **Wait for user confirmation** before proceeding to Phase 3

---

## Phase 3: Apply Fixes (One Commit Per Finding)

**Goal**: Apply each valid finding as a separate, atomic commit with test coverage.

**CRITICAL**: Process one finding at a time. Complete the full cycle for each before moving to the next.

For EACH valid finding:

### Step 1: Search for Existing Test Coverage

Before writing any code, search for existing tests that can be extended:

```
Grep for the affected function/module name in tests/
Read the test file structure — identify existing parametrized fixtures
Look for NamedTuple fixtures that can be extended with a new test case
```

**Priority order for test placement**:
1. **Extend existing parametrized test** — add a new entry to an existing `NamedTuple` fixture list (e.g., add a `SyncFixture` entry to `SYNC_REPO_FIXTURES`)
2. **Add a case to an existing test function** — if the test function already covers the component
3. **Create a new test function** in the existing test file — only if no existing test covers this area
4. **Create a new test file** — only as a last resort

### Step 2: Write/Extend Tests

Follow project test conventions strictly:

- **Functional tests only** — standalone `test_*` functions, NOT classes
- **Use `typing.NamedTuple`** for parametrized tests:
  ```python
  class FixtureName(t.NamedTuple):
      test_id: str
      # ... fields matching test parameters
  ```
- **Use `pytest.mark.parametrize`** with `ids` from `test_id`:
  ```python
  @pytest.mark.parametrize(
      list(FixtureName._fields),
      FIXTURE_LIST,
      ids=[test.test_id for test in FIXTURE_LIST],
  )
  ```
- **Leverage existing pytest fixtures** from:
  - `conftest.py` — project-specific fixtures
  - libvcs pytest plugin — `create_git_remote_repo`, `git_repo`, `set_home`, `gitconfig`, etc.
- **Use `from __future__ import annotations`** at top
- **Use `import typing as t`** namespace style
- **Document mocks** with comments explaining WHAT and WHY

### Step 3: Apply the Fix

- Make the minimal change that addresses the finding
- Do not bundle unrelated changes
- Follow project conventions from CLAUDE.md:
  - `from __future__ import annotations` at top of files
  - `import typing as t` namespace style
  - NumPy docstring style
  - Functional tests only (no test classes)

### Step 4: Run Quality Gates

Run ALL quality gates and ensure they pass:

```bash
uv run ruff check . --fix --show-fixes
uv run ruff format .
uv run mypy
uv run py.test --reruns 0 -vvv
```

- If any gate fails, fix the issue before proceeding
- If a test fails due to the change, either:
  - Adjust the fix to be correct, OR
  - Update the test if the finding changes expected behavior
- ALL FOUR gates must pass before committing

### Step 5: Commit

Stage only the files changed for this specific finding:

```bash
git add <specific-files>
```

Use the project commit message format with HEREDOC:

```bash
git commit -m "$(cat <<'EOF'
Component(fix[subcomponent]) Brief description addressing review finding

why: Address multi-model review finding — <what the reviewers flagged>
what:
- <specific change 1>
- <specific change 2>
- Add/extend test coverage for <what was tested>
EOF
)"
```

**Commit type guidance**:
- `fix` for bug fixes, type annotation corrections, or logic errors
- `refactor` for code clarity, naming improvements, or structural changes
- `test` for test-only additions or improvements
- `docs` for documentation, docstring, or changelog updates

### Step 6: Verify Clean State

After committing, confirm:
```bash
git status
git diff
```

No uncommitted changes should remain before moving to the next finding.

---

## Phase 4: Summary

After processing all valid findings, present a summary:

1. **Applied fixes**: List each committed fix with its commit hash and consensus level
2. **Tests added/extended**: List test coverage improvements per finding
3. **Skipped findings**: List each invalid/out-of-scope finding with the reason
4. **Final verification**: Run the full quality gate one last time:
   ```bash
   uv run ruff check . --fix --show-fixes
   uv run ruff format .
   uv run mypy
   uv run py.test --reruns 0 -vvv
   ```
5. Report the final pass/fail status
6. Show the commit log for the session:
   ```bash
   git log --oneline -<N>
   ```

---

## Recovery: Quality Gate Failure

If quality gates fail after applying a fix:

1. **Identify** which gate failed and why
2. **Fix** the issue (adjust the change, not bypass the gate)
3. **Re-run** all four gates
4. If the fix cannot be made to pass all gates after 2 attempts:
   - Revert the change: `git checkout -- <files>`
   - Mark the finding as "valid but could not apply cleanly"
   - Move to the next finding
   - Report the issue in the Phase 4 summary

---

## Rules

- Never skip quality gates
- Never bundle multiple findings into one commit
- Never modify code that isn't related to the finding being addressed
- Always wait for user confirmation after Phase 2 validation
- Always use project commit message conventions
- Always search for existing tests before creating new test functions
- Always prefer extending existing parametrized NamedTuple fixtures over creating new tests
- If a finding requires changes in multiple files, that is still ONE commit (one logical change)
- Process consensus findings before single-reviewer findings
- If a finding is pre-existing (not from this branch), note it but still fix if the user approved it
