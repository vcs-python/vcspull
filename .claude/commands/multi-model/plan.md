---
description: Multi-model planning — get implementation plans from Claude, Gemini, and GPT, then synthesize the best plan
allowed-tools: Bash(git:*), Bash(gemini:*), Bash(codex:*), Bash(agent:*), Bash(which:*), Read, Grep, Glob, Task
---

# Multi-Model Plan

Get implementation plans from multiple AI models (Claude, Gemini, GPT) in parallel, then synthesize the best plan. This is a **read-only** command — no files are written or edited. The output is a finalized Claude Code plan ready for execution.

The task description comes from `$ARGUMENTS`. If no arguments are provided, ask the user what they want planned.

---

## Phase 1: Gather Context

**Goal**: Understand the project state and the planning request.

1. **Read CLAUDE.md / AGENTS.md** if present — project conventions constrain valid plans.

2. **Determine trunk branch**:
   ```bash
   git remote show origin | grep 'HEAD branch'
   ```

3. **Understand current branch state**:
   ```bash
   git diff origin/<trunk>...HEAD --stat
   git log origin/<trunk>..HEAD --oneline
   ```

4. **Capture the task**: Use `$ARGUMENTS` as the task description. If `$ARGUMENTS` is empty, ask the user what they want planned.

5. **Explore relevant code**: Read the files most relevant to the task to understand the existing architecture, patterns, and constraints. Use Grep/Glob/Read to build context.

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

**Resolution logic** for each external slot:
1. Native CLI found → use it
2. Else `agent` found → use `agent` with `--model` flag
3. Else → slot unavailable, note in report

Report which models will participate and which backend each uses.

---

## Phase 3: Get Plans from All Models in Parallel

**Goal**: Ask each model to produce an implementation plan for the task.

### Claude Plan (Task agent)

Launch a Task agent with `subagent_type: "general-purpose"` to create Claude's plan:

**Prompt for the Claude planning agent**:
> Create a detailed implementation plan for the following task. Read the codebase to understand the existing architecture, patterns, and conventions. Read CLAUDE.md/AGENTS.md for project standards.
>
> Task: <task description>
>
> Your plan must include:
> 1. **Files to create or modify** — list every file with what changes are needed
> 2. **Implementation sequence** — ordered steps with dependencies between them
> 3. **Architecture decisions** — justify key choices with reference to existing patterns
> 4. **Test strategy** — what tests to add/extend, using existing test patterns
> 5. **Risks and edge cases** — potential problems and mitigations
>
> Be specific — reference actual files, functions, and patterns from the codebase. Do NOT modify any files — plan only.

### Gemini Plan (if available)

**Planning prompt** (same for both backends):
> Create an implementation plan for the following task. Read relevant codebase files and AGENTS.md/CLAUDE.md for conventions. Do NOT modify any files.
>
> Task: <task description>
>
> Include: files to modify, implementation steps in order, architecture decisions, test strategy, and risks. Reference actual files and patterns from the codebase.

**Native (`gemini` CLI)**:
```bash
timeout 300 gemini -p "<planning prompt>"
```

**Fallback (`agent` CLI)**:
```bash
timeout 300 agent -p -f --model gemini-3-pro "<planning prompt>"
```

### GPT Plan (if available)

**Planning prompt** (same for both backends):
> Create an implementation plan for the following task. Read relevant codebase files and AGENTS.md/CLAUDE.md for conventions. Do NOT modify any files.
>
> Task: <task description>
>
> Include: files to modify, implementation steps in order, architecture decisions, test strategy, and risks. Reference actual files and patterns from the codebase.

**Native (`codex` CLI)**:
```bash
timeout 300 codex \
    --sandbox danger-full-access \
    --ask-for-approval never \
    -c model_reasoning_effort=medium \
    exec "<planning prompt>"
```

**Fallback (`agent` CLI)**:
```bash
timeout 300 agent -p -f --model gpt-5.2 "<planning prompt>"
```

### Execution Strategy

- Launch all models in parallel.
- If a model fails, note the failure and continue with remaining models.
- Set a 5-minute timeout for external CLI commands (`timeout 300`).

---

## Phase 4: Synthesize the Best Plan

**Goal**: Combine the strongest elements from all plans into a single, superior plan.

### Step 1: Compare Plans

For each model's plan, evaluate:
- **File coverage**: Which files does it identify for modification? Are any missing?
- **Sequence correctness**: Are dependencies between steps correct?
- **Pattern adherence**: Does it follow the project's existing patterns (from CLAUDE.md)?
- **Test strategy**: Does it extend existing tests or create new ones appropriately?
- **Risk awareness**: Does it identify realistic edge cases?
- **Unique approaches**: What novel ideas does this plan have that others don't?

### Step 2: Verify Claims

For each plan's claims about the codebase:
- **Read the referenced files** to confirm they exist and the plan's understanding is correct
- **Check function signatures** and APIs to verify the proposed integration points
- **Validate test patterns** — confirm that the test approach matches the project's conventions

### Step 3: Build the Synthesized Plan

1. **Start with the most architecturally sound plan** as the base
2. **Incorporate better file coverage** from other plans (if one model identified a file others missed)
3. **Adopt the strongest test strategy** — prefer the plan that best extends existing parametrized tests
4. **Merge unique risk mitigations** from each plan
5. **Resolve approach conflicts** — when models propose different architectures, pick the one that best fits existing patterns (verify by reading code)

### Step 4: Present the Final Plan

```markdown
# Implementation Plan

**Task**: <task description>

## Architecture Decision

<Chosen approach and why, referencing existing codebase patterns>

## Implementation Steps

### Step 1: <description>
- **Files**: `path/to/file.py`
- **Changes**: <specific changes>
- **Depends on**: (none / Step N)

### Step 2: <description>
- **Files**: `path/to/file.py`
- **Changes**: <specific changes>
- **Depends on**: Step 1

... (continue for all steps)

## Test Strategy

- **Extend**: `tests/test_foo.py` — add entries to `FooFixture` NamedTuple
- **New test**: `tests/test_bar.py::test_new_function` — for new functionality

## Risks and Mitigations

1. **Risk**: <description>
   - **Mitigation**: <approach>

---

## Model Contributions

**Base plan from**: <model>
**Incorporated from other models**:
- [Gemini] <what was taken from Gemini's plan>
- [GPT] <what was taken from GPT's plan>

**Rejected approaches**:
- [Model] <approach> — rejected because <reason with code reference>

**Models participated**: Claude, Gemini, GPT (or subset)
**Models unavailable/failed**: (if any)
```

---

## Rules

- Never modify any files — this is read-only planning
- Always verify each plan's claims by reading the actual codebase
- Always resolve conflicts by checking what the code actually does
- The final plan must follow project conventions from CLAUDE.md/AGENTS.md
- If only Claude is available, still produce a thorough plan and note the limitation
- Use `timeout 300` for external CLI commands
- Capture stderr from external tools to report failures clearly
- The output should be a concrete, actionable plan — not vague suggestions
