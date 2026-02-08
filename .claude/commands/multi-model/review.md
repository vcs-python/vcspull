---
description: Multi-model code review — runs Claude, Gemini, and Codex reviews in parallel, then synthesizes findings
allowed-tools: Bash(git diff:*), Bash(git log:*), Bash(git branch:*), Bash(git status:*), Bash(git remote:*), Bash(gemini:*), Bash(codex:*), Bash(which:*), Read, Grep, Glob, Task
---

# Multi-Model Code Review

Run code review using up to three AI models (Claude, Gemini, Codex) in parallel, then synthesize their findings into a unified report with consensus-weighted confidence.

---

## Phase 1: Gather Context

**Goal**: Understand the branch state and determine the trunk branch.

1. **Determine trunk branch**:
   ```bash
   git remote show origin | grep 'HEAD branch'
   ```
   Fall back to `master` if detection fails.

2. **Get the diff stats**:
   ```bash
   git diff origin/<trunk>...HEAD --stat
   ```

3. **Get commit history for this branch**:
   ```bash
   git log origin/<trunk>..HEAD --oneline
   ```

4. **Read AGENTS.md / CLAUDE.md** if present at the repo root — these contain project conventions the review should enforce.

---

## Phase 2: Detect Available Reviewers

**Goal**: Check which AI CLI tools are installed locally.

Run these checks in parallel:

```bash
which gemini 2>/dev/null && echo "gemini:available" || echo "gemini:missing"
which codex 2>/dev/null && echo "codex:available" || echo "codex:missing"
```

Claude (this agent) is always available. Build a list of available reviewers:
- **Claude** — always available
- **Gemini** — available if `gemini` binary is found
- **Codex** — available if `codex` binary is found

Report which reviewers will participate. If only Claude is available, proceed with Claude-only review and note the missing tools.

---

## Phase 3: Launch Reviews in Parallel

**Goal**: Run all available reviewers simultaneously.

### Claude Review (Task agent)

Launch a Task agent with `subagent_type: "general-purpose"` to perform Claude's own code review:

**Prompt for the Claude review agent**:
> Perform a thorough code review of the changes on this branch compared to origin/<trunk>.
>
> Run `git diff origin/<trunk>...HEAD` to see all changes.
> Read the CLAUDE.md or AGENTS.md file at the repo root for project conventions.
>
> Review for:
> 1. **Bugs and logic errors** — incorrect behavior, edge cases, off-by-one errors
> 2. **Security issues** — injection, XSS, unsafe deserialization, secrets in code
> 3. **Project convention violations** — check against CLAUDE.md/AGENTS.md
> 4. **Code quality** — duplication, unclear naming, missing error handling
> 5. **Test coverage gaps** — new code paths without tests
>
> For each issue found, report:
> - **Severity**: Critical / Important / Suggestion
> - **File and line**: exact location
> - **Description**: what the issue is
> - **Recommendation**: how to fix it
>
> Assign a confidence score (0-100) to each issue. Only report issues with confidence >= 70.

### Gemini Review (if available)

Run Gemini CLI in non-interactive mode. Execute via Bash:

```bash
gemini -p "You are a code reviewer. Analyze the changes since the trunk in this branch, consider AGENTS.md.

Run git diff origin/<trunk>...HEAD to see the changes. Read AGENTS.md or CLAUDE.md for project conventions.

For each issue, report: severity (Critical/Important/Suggestion), file and line, description, and recommendation. Focus on bugs, logic errors, security issues, and convention violations."
```

**Important**: Use the actual trunk branch name detected in Phase 1 in the prompt. Capture the full stdout output.

### Codex Review (if available)

Run Codex CLI with full sandbox access. Execute via Bash:

```bash
codex \
    --sandbox danger-full-access \
    --ask-for-approval never \
    -c model_reasoning_effort=medium \
    exec "You are a code reviewer - Analyze the changes since the trunk in this branch, consider AGENTS.md.

Run git diff origin/<trunk>...HEAD to see the changes. Read AGENTS.md or CLAUDE.md for project conventions.

For each issue, report: severity (Critical/Important/Suggestion), file and line, description, and recommendation. Focus on bugs, logic errors, security issues, and convention violations."
```

**Important**: Use the actual trunk branch name detected in Phase 1 in the prompt. Capture the full stdout output.

### Execution Strategy

- Launch the Claude Task agent and the Gemini/Codex Bash commands in parallel where possible.
- If a reviewer fails (timeout, crash, API error), note the failure and continue with the remaining reviewers.
- Set a 5-minute timeout for Gemini and Codex commands (`timeout 300`).

---

## Phase 4: Synthesize Findings

**Goal**: Combine all reviewer outputs into a unified, consensus-weighted report.

### Step 1: Parse Each Reviewer's Output

Read through each reviewer's output and extract individual findings. Normalize each finding to:
- **Reviewer**: which model found it
- **Severity**: Critical / Important / Suggestion
- **File**: file path and line number (if provided)
- **Description**: the issue
- **Recommendation**: suggested fix

### Step 2: Cross-Reference and Deduplicate

Group findings that refer to the same issue (same file, similar description). For each unique issue:

- **Consensus count**: how many reviewers flagged it (1, 2, or 3)
- **Consensus boost**: Issues flagged by multiple reviewers get higher confidence
  - 1 reviewer: use reported severity as-is
  - 2 reviewers: promote severity by one level (Suggestion → Important, Important → Critical)
  - 3 reviewers: mark as Critical regardless

### Step 3: Generate Unified Report

Present the synthesized report in this format:

```markdown
# Multi-Model Code Review Report

**Reviewers**: Claude, Gemini, Codex (or whichever participated)
**Branch**: <branch-name>
**Compared against**: origin/<trunk>
**Files changed**: <count>

## Consensus Issues (flagged by multiple reviewers)

### Critical
- [Claude + Gemini + Codex] **file.py:42** — Description of issue
  - Recommendation: ...

### Important
- [Claude + Gemini] **file.py:15** — Description of issue
  - Recommendation: ...

## Single-Reviewer Issues

### Critical
- [Claude] **file.py:88** — Description
  - Recommendation: ...

### Important
- [Gemini] **file.py:23** — Description
  - Recommendation: ...

### Suggestions
- [Codex] **file.py:55** — Description
  - Recommendation: ...

## Reviewer Disagreements

List any cases where reviewers explicitly contradicted each other, noting both positions.

## Summary

- **Total issues**: X
- **Consensus issues**: Y (flagged by 2+ reviewers)
- **Critical**: Z
- **Reviewers participated**: Claude, Gemini, Codex
- **Reviewers unavailable/failed**: (if any)
```

---

## Phase 5: Recommendations

After presenting the report:

1. **Prioritize consensus issues** — these have the highest confidence since multiple independent models agree
2. **Flag reviewer disagreements** — where one model says it's fine and another says it's a bug, note both perspectives for the user to decide
3. **Suggest next steps**:
   - Fix critical consensus issues first
   - Address single-reviewer critical issues
   - Consider important issues
   - Optionally address suggestions

---

## Rules

- Never modify code — this is a read-only review
- Always attempt to run all available reviewers, even if one fails
- Always clearly attribute which reviewer(s) found each issue
- Consensus issues take priority over single-reviewer issues
- If no external reviewers are available, fall back to Claude-only review and note the limitation
- Use `timeout 300` for external CLI commands to prevent hangs
- Capture stderr from external tools to report failures clearly
