---
description: Multi-model question — ask Claude, Gemini, and GPT the same question in parallel, then synthesize the best answer
allowed-tools: Bash(git:*), Bash(gemini:*), Bash(codex:*), Bash(agent:*), Bash(which:*), Read, Grep, Glob, Task
---

# Multi-Model Ask

Ask a question across multiple AI models (Claude, Gemini, GPT) in parallel, then synthesize the best answer from all responses. This is a **read-only** command — no files are written or edited.

The question comes from `$ARGUMENTS`. If no arguments are provided, ask the user what they want to know.

---

## Phase 1: Gather Context

**Goal**: Understand the project and prepare the question.

1. **Read CLAUDE.md / AGENTS.md** if present — project conventions inform better answers.

2. **Determine trunk branch** (for questions about branch changes):
   ```bash
   git remote show origin | grep 'HEAD branch'
   ```

3. **Capture the question**: Use `$ARGUMENTS` as the user's question. If `$ARGUMENTS` is empty, ask the user what question they want answered.

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

## Phase 3: Ask All Models in Parallel

**Goal**: Send the same question to all available models simultaneously.

### Claude Answer (Task agent)

Launch a Task agent with `subagent_type: "general-purpose"` to answer the question:

**Prompt for the Claude agent**:
> Answer the following question about this codebase. Read any relevant files to give a thorough, accurate answer. Read CLAUDE.md/AGENTS.md for project conventions.
>
> Question: <user's question>
>
> Provide a clear, well-structured answer. Cite specific files and line numbers where relevant. Do NOT modify any files — this is research only.

### Gemini Answer (if available)

**Question prompt** (same for both backends):
> Answer this question about the codebase. Read relevant files and AGENTS.md/CLAUDE.md for conventions. Do NOT modify any files.
>
> Question: <user's question>
>
> Provide a clear answer citing specific files where relevant.

**Native (`gemini` CLI)**:
```bash
timeout 300 gemini -p "<question prompt>"
```

**Fallback (`agent` CLI)**:
```bash
timeout 300 agent -p -f --model gemini-3-pro "<question prompt>"
```

### GPT Answer (if available)

**Question prompt** (same for both backends):
> Answer this question about the codebase. Read relevant files and AGENTS.md/CLAUDE.md for conventions. Do NOT modify any files.
>
> Question: <user's question>
>
> Provide a clear answer citing specific files where relevant.

**Native (`codex` CLI)**:
```bash
timeout 300 codex \
    --sandbox danger-full-access \
    --ask-for-approval never \
    -c model_reasoning_effort=medium \
    exec "<question prompt>"
```

**Fallback (`agent` CLI)**:
```bash
timeout 300 agent -p -f --model gpt-5.2 "<question prompt>"
```

### Execution Strategy

- Launch the Claude Task agent and external CLI commands in parallel.
- If a model fails (timeout, crash, API error), note the failure and continue with remaining models.
- Set a 5-minute timeout for external CLI commands (`timeout 300`).

---

## Phase 4: Synthesize Best Answer

**Goal**: Combine all model responses into the single best answer.

### Step 1: Compare Responses

For each model's response, note:
- **Key points**: What facts, files, or explanations did it provide?
- **Unique insights**: What did this model mention that others didn't?
- **Accuracy**: Does the answer match the actual codebase? (Verify claims by reading files.)
- **Completeness**: Did it answer all parts of the question?

### Step 2: Build Synthesized Answer

Combine the best elements from all responses:

1. **Start with the most complete and accurate answer** as the base
2. **Add unique insights** from other models that are verified as correct
3. **Resolve contradictions** by checking the actual codebase — cite the file and line that proves which model is correct
4. **Remove inaccuracies** — if a model hallucinated a file or function, drop that claim

### Step 3: Present the Answer

```markdown
# Answer

<Synthesized best answer here, citing files and lines>

---

## Model Agreement

**All models agreed on**: <key points of consensus>

**Unique insights from individual models**:
- [Claude] <insight not mentioned by others>
- [Gemini] <insight not mentioned by others>
- [GPT] <insight not mentioned by others>

**Contradictions resolved**: <any disagreements and how they were resolved>

**Models participated**: Claude, Gemini, GPT (or subset)
**Models unavailable/failed**: (if any)
```

---

## Rules

- Never modify any files — this is read-only research
- Always verify model claims against the actual codebase before including in the synthesis
- Always cite specific files and line numbers when possible
- If models contradict each other, check the code and state which is correct
- If only Claude is available, still provide a thorough answer and note the limitation
- Use `timeout 300` for external CLI commands
- Capture stderr from external tools to report failures clearly
