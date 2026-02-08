---
description: Multi-model prompt — run a prompt across Claude, Gemini, and GPT in isolated git worktrees, then pick the best approach
allowed-tools: Bash(git diff:*), Bash(git log:*), Bash(git branch:*), Bash(git status:*), Bash(git remote:*), Bash(git worktree:*), Bash(git checkout:*), Bash(git merge:*), Bash(git cherry-pick:*), Bash(git stash:*), Bash(gemini:*), Bash(codex:*), Bash(agent:*), Bash(which:*), Bash(ls:*), Bash(cat:*), Bash(rm:*), Read, Grep, Glob, Edit, Write, Task
---

# Multi-Model Prompt

Run a prompt across multiple AI models (Claude, Gemini, GPT), each working in its own **isolated git worktree**. After all models complete, compare their implementations and **pick the single best approach** to bring back to the main working tree. This command is for prompts where the user wants to see competing implementations and choose.

The prompt comes from `$ARGUMENTS`. If no arguments are provided, ask the user what they want implemented.

---

## Phase 1: Gather Context

**Goal**: Understand the project and prepare the prompt.

1. **Read CLAUDE.md / AGENTS.md** if present — project conventions apply to all implementations.

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

4. **Capture the prompt**: Use `$ARGUMENTS` as the implementation prompt. If `$ARGUMENTS` is empty, ask the user.

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

Use the format `mm/<model>/<YYYYMMDD-HHMMSS>` for branch names to avoid collisions.

**Important**: All worktrees branch from the current HEAD, so all models start with identical code.

---

## Phase 4: Run All Models in Parallel

**Goal**: Execute the prompt in each model's isolated environment.

### Claude Implementation (main worktree)

Launch a Task agent with `subagent_type: "general-purpose"` to implement in the main working tree:

**Prompt for the Claude agent**:
> Implement the following task in this codebase. Read CLAUDE.md/AGENTS.md for project conventions and follow them strictly.
>
> Task: <user's prompt>
>
> Follow project conventions: imports, docstrings, test patterns (functional tests, NamedTuple fixtures). Run quality gates after making changes: ruff check, ruff format, mypy, pytest.

### Gemini Implementation (worktree)

**Implementation prompt** (same for both backends):
> Implement the following task. Follow AGENTS.md/CLAUDE.md conventions. Run quality checks after: ruff check, ruff format, mypy, pytest.
>
> Task: <user's prompt>

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
> Task: <user's prompt>

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

## Phase 5: Compare Implementations

**Goal**: Evaluate each model's implementation to pick the best one.

### Step 1: Gather Diffs

For each model that completed, examine the changes:

**Claude** (main worktree):
```bash
git diff HEAD
```

**External models** (worktrees):
```bash
git -C ../<repo-name>-mm-<model> diff HEAD
```

### Step 2: Run Quality Gates on Each

For each implementation, run quality gates in its worktree:

```bash
cd <worktree-path>
uv run ruff check . 2>&1
uv run ruff format --check . 2>&1
uv run mypy 2>&1
uv run py.test --reruns 0 -x 2>&1
```

Record pass/fail status for each gate and each model.

### Step 3: Evaluate and Compare

For each implementation, assess:
- **Quality gate results**: Does it pass ruff, mypy, and pytest?
- **Correctness**: Does it actually solve the task?
- **Pattern adherence**: Does it follow project conventions from CLAUDE.md?
- **Code quality**: Readability, naming, structure
- **Test coverage**: Did it add/extend tests appropriately?
- **Scope discipline**: Did it make only the requested changes (no unnecessary refactoring)?

### Step 4: Present Comparison to User

```markdown
# Multi-Model Implementation Comparison

**Task**: <user's prompt>

## Results

| Model | Quality Gates | Correctness | Convention Adherence | Files Changed |
|-------|--------------|-------------|---------------------|---------------|
| Claude | ✅/❌ ruff, mypy, pytest | ✅/❌ | ✅/❌ | N files |
| Gemini | ✅/❌ ruff, mypy, pytest | ✅/❌ | ✅/❌ | N files |
| GPT | ✅/❌ ruff, mypy, pytest | ✅/❌ | ✅/❌ | N files |

## Recommendation

**Best implementation**: <model> — <reason>

## Key Differences

- <Model A> did X while <Model B> did Y — <which is better and why>
- ...
```

**Wait for user to pick** which implementation to adopt, or accept the recommendation.

---

## Phase 6: Adopt the Chosen Implementation

**Goal**: Bring the chosen implementation into the main working tree.

### If Claude's implementation was chosen:
- Changes are already in the main tree — nothing to do.
- Clean up external worktrees (see cleanup below).

### If an external model's implementation was chosen:
1. **Discard Claude's changes** in the main tree:
   ```bash
   git checkout -- .
   ```
2. **Cherry-pick or merge** the external model's commit(s):
   ```bash
   git merge mm/<model>/<timestamp> --no-ff
   ```
   Or if there are conflicts, cherry-pick individual commits.

### Cleanup Worktrees

Remove all multi-model worktrees and branches:

```bash
git worktree remove ../<repo-name>-mm-gemini --force 2>/dev/null
git worktree remove ../<repo-name>-mm-gpt --force 2>/dev/null
git branch -D mm/gemini/<timestamp> 2>/dev/null
git branch -D mm/gpt/<timestamp> 2>/dev/null
```

---

## Rules

- Always create isolated worktrees — never let models interfere with each other
- Always run quality gates on each implementation before comparing
- Always present the comparison to the user and let them choose (or accept recommendation)
- Always clean up worktrees and branches after adoption
- If only Claude is available, skip worktree creation and just implement directly
- Use `timeout 600` for external CLI commands (longer timeout since models are coding)
- If a model fails, clearly report why and continue with remaining models
- Branch names use `mm/<model>/<YYYYMMDD-HHMMSS>` format
