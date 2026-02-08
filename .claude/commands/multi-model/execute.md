---
description: Multi-model execute — run a task across Claude, Gemini, and GPT in git worktrees, then synthesize the best of all approaches
allowed-tools: Bash(git:*), Bash(uv run:*), Bash(gemini:*), Bash(codex:*), Bash(agent:*), Bash(which:*), Read, Grep, Glob, Edit, Write, Task
---

# Multi-Model Execute

Run a task across multiple AI models (Claude, Gemini, GPT), each working in its own **isolated git worktree**. After all models complete, **synthesize the best elements from all approaches** into a single, superior implementation. Unlike `/multi-model:prompt` (which picks one winner), this command cherry-picks the best parts from each model's work.

The task comes from `$ARGUMENTS`. If no arguments are provided, ask the user what they want implemented.

---

## Phase 1: Gather Context

**Goal**: Understand the project and prepare the task.

1. **Read CLAUDE.md / AGENTS.md** if present — project conventions constrain all implementations.

2. **Determine trunk branch**:
   ```bash
   git remote show origin | grep 'HEAD branch'
   ```

3. **Record the current branch and commit**:
   ```bash
   git branch --show-current
   git rev-parse HEAD
   ```
   Store these — all worktrees branch from this point.

4. **Capture the task**: Use `$ARGUMENTS` as the task. If `$ARGUMENTS` is empty, ask the user.

5. **Explore relevant code**: Read files relevant to the task to understand existing patterns, APIs, and test structure. This context helps evaluate model outputs later.

---

## Phase 2: Detect Available Models

**Goal**: Check which AI CLI tools are installed locally.

Run these checks in parallel:

```bash
which gemini 2>/dev/null && echo "gemini:available" || echo "gemini:missing"
which codex 2>/dev/null && echo "codex:available" || echo "codex:missing"
which agent 2>/dev/null && echo "agent:available" || echo "agent:missing"
```

### Model resolution (priority order)

| Slot | Priority 1 (native) | Priority 2 (agent fallback) | Agent model |
|------|---------------------|-----------------------------|-------------|
| **Claude** | Always available (this agent) | — | — |
| **Gemini** | `gemini` binary | `agent --model gemini-3-pro` | `gemini-3-pro` |
| **GPT** | `codex` binary | `agent --model gpt-5.2` | `gpt-5.2` |

Report which models will participate and which backend each uses.

---

## Phase 3: Create Isolated Worktrees

**Goal**: Set up an isolated git worktree for each available external model.

For each external model (Gemini, GPT — Claude works in the main tree):

```bash
git worktree add ../<repo-name>-mm-<model> -b mm/<model>/<timestamp>
```

Example:
```bash
git worktree add ../vcspull-mm-gemini -b mm/gemini/20260208-143022
git worktree add ../vcspull-mm-gpt -b mm/gpt/20260208-143022
```

Use the format `mm/<model>/<YYYYMMDD-HHMMSS>` for branch names.

---

## Phase 4: Run All Models in Parallel

**Goal**: Execute the task in each model's isolated environment.

### Claude Implementation (main worktree)

Launch a Task agent with `subagent_type: "general-purpose"` to implement in the main working tree:

**Prompt for the Claude agent**:
> Implement the following task in this codebase. Read CLAUDE.md/AGENTS.md for project conventions and follow them strictly.
>
> Task: <user's task>
>
> Follow project conventions: imports, docstrings, test patterns (functional tests, NamedTuple fixtures). Run quality gates after making changes: ruff check, ruff format, mypy, pytest.

### Gemini Implementation (worktree)

**Implementation prompt** (same for both backends):
> Implement the following task. Follow AGENTS.md/CLAUDE.md conventions. Run quality checks after: ruff check, ruff format, mypy, pytest.
>
> Task: <user's task>

**Native (`gemini` CLI)** — run in the worktree directory:
```bash
cd ../<repo-name>-mm-gemini && timeout 600 gemini -p "<implementation prompt>"
```

**Fallback (`agent` CLI)**:
```bash
cd ../<repo-name>-mm-gemini && timeout 600 agent -p -f --model gemini-3-pro "<implementation prompt>"
```

### GPT Implementation (worktree)

**Implementation prompt** (same for both backends):
> Implement the following task. Follow AGENTS.md/CLAUDE.md conventions. Run quality checks after: ruff check, ruff format, mypy, pytest.
>
> Task: <user's task>

**Native (`codex` CLI)** — run in the worktree directory:
```bash
cd ../<repo-name>-mm-gpt && timeout 600 codex \
    --sandbox danger-full-access \
    --ask-for-approval never \
    -c model_reasoning_effort=medium \
    exec "<implementation prompt>"
```

**Fallback (`agent` CLI)**:
```bash
cd ../<repo-name>-mm-gpt && timeout 600 agent -p -f --model gpt-5.2 "<implementation prompt>"
```

### Execution Strategy

- Launch all models in parallel.
- Use 10-minute timeout (`timeout 600`) since models are writing code.
- If a model fails, note the failure and continue with remaining models.

---

## Phase 5: Analyze All Implementations

**Goal**: Deep-compare every model's implementation to identify the best elements from each.

### Step 1: Gather All Diffs

For each model that completed:

**Claude** (main worktree):
```bash
git diff HEAD
```

**External models** (worktrees):
```bash
git -C ../<repo-name>-mm-<model> diff HEAD
```

### Step 2: Run Quality Gates on Each

```bash
# In each worktree/tree
uv run ruff check . 2>&1
uv run ruff format --check . 2>&1
uv run mypy 2>&1
uv run py.test --reruns 0 -x 2>&1
```

Record pass/fail status for each gate and model.

### Step 3: File-by-File Comparison

For each file that was modified by any model:

1. **Read all versions** — the original plus each model's version
2. **Compare approaches** — how did each model solve this part?
3. **Rate each approach** on:
   - Correctness (does it work?)
   - Convention adherence (does it match project patterns?)
   - Code quality (readability, naming, structure)
   - Completeness (edge cases, error handling)
   - Test coverage (if a test file)

4. **Select the best approach per file** — this may come from different models for different files

### Step 4: Present Analysis to User

```markdown
# Multi-Model Implementation Analysis

**Task**: <user's task>

## Quality Gate Results

| Model | ruff | mypy | pytest | Overall |
|-------|------|------|--------|---------|
| Claude | ✅/❌ | ✅/❌ | ✅/❌ | ✅/❌ |
| Gemini | ✅/❌ | ✅/❌ | ✅/❌ | ✅/❌ |
| GPT | ✅/❌ | ✅/❌ | ✅/❌ | ✅/❌ |

## File-by-File Best Approach

| File | Best From | Why |
|------|-----------|-----|
| `src/foo.py` | Claude | Better error handling, follows project patterns |
| `src/bar.py` | Gemini | More complete implementation, covers edge case X |
| `tests/test_foo.py` | GPT | Better use of existing NamedTuple fixtures |

## Synthesis Plan

1. Take `src/foo.py` from Claude's implementation
2. Take `src/bar.py` from Gemini's implementation
3. Take `tests/test_foo.py` from GPT's implementation
4. Combine and verify quality gates pass
```

**Wait for user confirmation** before applying the synthesis.

---

## Phase 6: Synthesize the Best Implementation

**Goal**: Combine the best elements from all models into the main working tree.

### Step 1: Start Fresh

Discard Claude's changes to start from a clean state:
```bash
git checkout -- .
```

### Step 2: Apply Best-of-Breed Changes

For each file, apply the best model's version:

- **If from Claude**: Re-apply Claude's changes (from the diff captured earlier)
- **If from an external model**: Read the file from the worktree and apply it:
  ```bash
  # Read the external model's version
  git -C ../<repo-name>-mm-<model> show HEAD:<filepath>
  ```
  Then use Edit/Write to apply those changes to the main tree.

### Step 3: Integrate and Adjust

After applying best-of-breed changes:
1. **Read the combined result** — verify all pieces fit together
2. **Fix integration issues** — imports, function signatures, or API mismatches between files from different models
3. **Ensure consistency** — naming conventions, docstring style, import style from CLAUDE.md

### Step 4: Run Quality Gates

```bash
uv run ruff check . --fix --show-fixes
uv run ruff format .
uv run mypy
uv run py.test --reruns 0 -vvv
```

All four gates must pass. If they fail, fix the integration issues and re-run.

### Step 5: Cleanup Worktrees

Remove all multi-model worktrees and branches:

```bash
git worktree remove ../<repo-name>-mm-gemini --force 2>/dev/null
git worktree remove ../<repo-name>-mm-gpt --force 2>/dev/null
git branch -D mm/gemini/<timestamp> 2>/dev/null
git branch -D mm/gpt/<timestamp> 2>/dev/null
```

---

## Phase 7: Summary

Present the final result:

```markdown
# Synthesis Complete

**Task**: <user's task>

## What was synthesized

| File | Source Model | Key Contribution |
|------|-------------|-----------------|
| `src/foo.py` | Claude | <what it contributed> |
| `src/bar.py` | Gemini | <what it contributed> |
| `tests/test_foo.py` | GPT | <what it contributed> |

## Quality Gates

- ruff check: ✅
- ruff format: ✅
- mypy: ✅
- pytest: ✅

## Models participated: Claude, Gemini, GPT
## Models unavailable/failed: (if any)
```

The changes are now in the working tree, unstaged. The user can review and commit them.

---

## Rules

- Always create isolated worktrees — never let models interfere with each other
- Always run quality gates on each implementation before comparing
- Always present the synthesis plan to the user and wait for confirmation before applying
- Always clean up worktrees and branches after synthesis
- The synthesis must pass all quality gates before being considered complete
- If only Claude is available, skip worktree creation and just implement directly
- Use `timeout 600` for external CLI commands
- If a model fails, clearly report why and continue with remaining models
- Branch names use `mm/<model>/<YYYYMMDD-HHMMSS>` format
- Never commit the synthesized result — leave it unstaged for user review
