---
description: >
  Update the libvcs dependency in vcspull to the latest version with atomic,
  well-documented commits. Use when asked to "update libvcs", "bump libvcs",
  "upgrade libvcs", "check for libvcs updates", or "update libvcs dependency".
  Covers discovery, package bump, code adaptation, test updates, and CHANGES
  entries as separate commits.
user-invocable: true
allowed-tools: ["Bash", "Read", "Grep", "Glob", "Edit", "Write", "WebSearch", "Agent", "AskUserQuestion"]
argument-hint: "[--dry-run] [--no-pr]"
---

# Update libvcs in vcspull

Workflow for updating vcspull's primary dependency (libvcs) with separate, atomic commits following established project conventions.

Parse `$ARGUMENTS` for flags:

| Flag | Effect |
|------|--------|
| `--dry-run` | Analyze and report what would change without making modifications |
| `--no-pr` | Skip PR creation at the end |

## Phase 1: Discovery

**Goal**: Determine current and target versions, assess what changed.

### 1a. Check current state

Read `pyproject.toml` in vcspull and extract the `libvcs` version constraint from `dependencies`.

```bash
grep 'libvcs' pyproject.toml
```

Also check the installed and available versions:

```bash
uv pip show libvcs
```

### 1b. Ensure local libvcs clone is fresh

The local clone lives at `~/work/python/libvcs/`. Fetch and check tags:

```bash
cd ~/work/python/libvcs && git fetch --tags origin
git tag --sort=-v:refname | head -5
```

### 1c. Identify the target version

Compare the current pinned version (from pyproject.toml) with the latest tag from the local clone and PyPI. If already at latest, report "vcspull is already on the latest libvcs (vX.Y.Z)" and stop — unless `$ARGUMENTS` explicitly names a version.

### 1d. Study what changed

Read the libvcs CHANGES file between the current and target versions:

```bash
cd ~/work/python/libvcs && git log v<current>..v<target> --oneline
```

Read the CHANGES entries for the target version. Focus on:
- **Breaking changes** — require code updates in vcspull
- **New features** — may enable new functionality in vcspull
- **Bug fixes** — may fix issues vcspull worked around
- **API changes** — renamed classes, changed signatures, new return types

### 1e. Assess impact

Classify the update into one of three tiers:

| Tier | Description | Commits needed |
|------|-------------|----------------|
| **Simple bump** | No API changes, maintenance only | 2 (package + CHANGES) |
| **Adaptation** | API changes require code updates | 3-4 (package + code + tests + CHANGES) |
| **Feature integration** | New features to adopt in vcspull | 3-5 (package + code + tests + CHANGES, possibly split) |

Present findings to user and confirm before proceeding.

If `--dry-run`, report findings and stop here.

---

## Phase 2: Package Bump Commit

**Goal**: Update the version constraint and lock file.

### 2a. Create a branch

```bash
git checkout -b update-libvcs-<target-version>
```

### 2b. Update pyproject.toml

Change the `libvcs` dependency version. vcspull uses compatible-release constraints (`~=`):

```
"libvcs~=0.XX.0"
```

### 2c. Remove uv.sources override (if present)

Check `pyproject.toml` for a `[tool.uv.sources]` section pointing libvcs at a branch or local path. If found, remove it before locking — otherwise `uv lock` resolves to the override instead of PyPI.

### 2d. Update lock file

```bash
uv lock
```

### 2e. Verify installation

```bash
uv sync && uv run python -c "import libvcs; print(libvcs.__version__)"
```

### 2f. Commit

Stage only `pyproject.toml` and `uv.lock`. Commit message format:

```
py(deps) libvcs <old> -> <new>

See also: https://libvcs.git-pull.com/history.html#libvcs-<version-slug>
```

The version slug uses dashes: `0-39-0` for `0.39.0`.

**Exemplar** (from real history):
```
py(deps) libvcs 0.38.6 -> 0.39.0

See also: https://libvcs.git-pull.com/history.html#libvcs-0-39-0-2026-02-07
```

---

## Phase 3: Code Adaptation Commit (if needed)

**Goal**: Update vcspull source code for API changes.

Skip this phase entirely if the libvcs update has no breaking or API changes.

### 3a. Identify affected code

Search vcspull source for usage of changed libvcs APIs:

```bash
cd ~/work/python/vcspull
grep -r "from libvcs" src/
grep -r "import libvcs" src/
```

Cross-reference with the breaking changes identified in Phase 1d.

### 3b. Make code changes

Adapt imports, type annotations, function calls, and error handling to match the new libvcs API.

### 3c. Run type checking

```bash
uv run mypy
```

### 3d. Run tests

```bash
uv run pytest
```

Fix any failures that stem from API changes (not test-specific issues — those go in Phase 4).

### 3e. Commit

Stage only `src/` files. Commit message format uses the affected module as scope:

```
<module>(fix|feat[detail]): description of adaptation

why: libvcs <new> changed <what>
what:
- Specific change 1
- Specific change 2
```

**Exemplar**:
```
cli/sync(fix[update_repo]) Widen return type to GitSync | HgSync | SvnSync

why: libvcs 0.39.0 changed update_repo() to return SyncResult
what:
- Update return type annotation on update_repo wrapper
- Handle SyncResult.errors in sync summary
```

---

## Phase 4: Test Adaptation Commit (if needed)

**Goal**: Update test code for API or behavior changes.

Skip if no test changes are required.

### 4a. Run full test suite

```bash
uv run pytest
```

### 4b. Fix test failures

Address failures caused by:
- Changed libvcs fixtures (e.g., new fixture parameters)
- Changed behavior (e.g., different output format)
- New features needing coverage

### 4c. Commit

Stage only `tests/` and `conftest.py` files. Commit message format:

```
tests(fix|feat[detail]): description

why: Explanation tied to the libvcs update
what:
- Specific test changes
```

**Exemplar**:
```
tests(fix[test_cli]) Add skip markers to HG/SVN errored tests

why: libvcs 0.39.0 SyncResult changes behavior of errored syncs
what:
- Add skip_if_binaries_missing for hg/svn tests
- Update expected error messages for new SyncError format
```

---

## Phase 5: CHANGES Entry Commit

**Goal**: Document the update in the changelog.

### 5a. Determine section

For libvcs bumps, the entry goes under `### Breaking changes` in the unreleased section. This is the established convention — even minor bumps use this section because they change the minimum dependency version.

### 5b. Write the entry

Format depends on the tier:

**Simple bump** — single bullet:
```markdown
### Breaking changes

- Bump minimum libvcs from v<old> -> v<new> (#???)
```

**Adaptation / Feature integration** — bullet with description:
```markdown
### Breaking changes

- Bump minimum libvcs from v<old> -> v<new> (#???)

  Brief description of what the new version brings.
```

If there are also code/feature changes from Phases 3-4, add corresponding sections for those (Features, Bug fixes, Tests) following the CHANGES conventions. Consult the commit pattern exemplars below for examples.

### 5c. Insert into CHANGES

Find the insertion point after the placeholder comment:
```
<!-- END PLACEHOLDER - ADD NEW CHANGELOG ENTRIES BELOW THIS LINE -->
```

Insert the entry after this line. If the placeholder is not found, insert after the first `## ` heading in the unreleased section (e.g., `## vcspull v1.59.x (unreleased)`).

### 5d. Commit

Stage only `CHANGES`. Commit message:

```
docs(CHANGES) Note libvcs v<new> bump
```

If additional feature/fix entries were added:
```
docs(CHANGES) libvcs v<new> bump, <brief summary of other entries>
```

**Exemplar**:
```
docs(CHANGES) Note libvcs v0.39.0 bump
```

---

## Phase 6: Verification

**Goal**: Ensure everything works before pushing.

### 6a. Full quality check

```bash
uv run ruff format .
uv run ruff check . --fix --show-fixes
uv run mypy
uv run pytest
```

All four must pass. If any fail, fix and amend the appropriate commit (not the CHANGES commit).

### 6b. Review commits

```bash
git log --oneline origin/master..HEAD
```

Verify the commit sequence matches the expected pattern:
1. `py(deps) libvcs X -> Y`
2. (optional) code adaptation commit(s)
3. (optional) test adaptation commit(s)
4. `docs(CHANGES) Note libvcs vY bump`

---

## Phase 7: PR (unless --no-pr)

**Goal**: Push and open a pull request.

### 7a. Push

```bash
git push -u origin update-libvcs-<target-version>
```

### 7b. Create PR

```bash
gh pr create --title "py(deps) libvcs <old> -> <new>" --body "$(cat <<'EOF'
## Summary

- Bump libvcs from <old> to <new>
- [List any code/test adaptations]

See libvcs CHANGES: https://libvcs.git-pull.com/history.html#libvcs-<version-slug>

## Test plan

- [ ] `uv run pytest` passes
- [ ] `uv run mypy` passes
- [ ] `uv run ruff check .` passes
EOF
)"
```

Report the PR URL.

---

## Commit Pattern Exemplars

Real commit sequences from vcspull's git history, organized by update tier.

### Tier 1: Simple Bump (2 commits)

When libvcs has no API changes — maintenance, internal refactors, or bug fixes that don't affect vcspull's code.

**Example: v0.38.2 -> v0.38.3 (v1.50.1)**

Commit 1 — Package bump:
```
py(deps) libvcs 0.38.2 -> 0.38.3

See also: https://libvcs.git-pull.com/history.html#libvcs-0-38-3-2026-01-25
```
Files: `pyproject.toml`, `uv.lock`

Commit 2 — CHANGES:
```
docs(CHANGES) Note libvcs v0.38.3 bump
```
Files: `CHANGES`

CHANGES entry:
```markdown
### Breaking changes

- Bump minimum libvcs from v0.38.2 -> v0.38.3 (#505)
```

### Tier 2: Adaptation (3-4 commits)

When libvcs has API changes that require updates to vcspull source or tests.

**Example: v0.38.6 -> v0.39.0 (v1.52.0)**

This is the gold-standard example — libvcs 0.39.0 introduced `SyncResult` return types, requiring code and test changes.

Commit 1 — Package bump:
```
py(deps) libvcs 0.38.6 -> 0.39.0

See also: https://libvcs.git-pull.com/history.html#libvcs-0-39-0-2026-02-07
```
Files: `pyproject.toml`, `uv.lock`

Commit 2 — CHANGES (initial):
```
docs(CHANGES) Note libvcs v0.39.0 bump
```
CHANGES entry:
```markdown
### Breaking changes

- Bump minimum libvcs from v0.38.6 -> v0.39.0 (#512)

  Adds `SyncResult` and various other bug fixes to syncing.
```

Commit 3 — Code adaptation:
```
cli/sync(feat[update_repo]) Detect and report errored git syncs
cli/sync(fix[summary]) Separate unmatched patterns from repo total in sync summary
cli/sync(feat[exit-on-error]) Exit non-zero on unmatched patterns with --exit-on-error
cli/sync(fix[update_repo]) Widen return type to GitSync | HgSync | SvnSync
```

Commit 4 — Test adaptation:
```
tests(refactor[test_cli]) Use libvcs factory fixtures for SVN/HG errored tests
tests(fix[test_cli]) Add skip markers to HG/SVN errored tests
```

Commit 5 — CHANGES expansion (after code/test work):
```
docs(CHANGES) Add feature, bug fix, and test entries for #512
```

### Tier 3: Feature Integration (2-5 commits)

When vcspull adopts new libvcs features.

**Example: v0.35.1 -> v0.36.0 (v1.35.0)**

Commit 1 — Package bump:
```
py(deps) libvcs 0.35.1 -> 0.36.0
```

Commit 2 — CHANGES:
```markdown
### Development

- libvcs 0.35.1 -> 0.36.0 (#467)

  Improved Git URL detection
```

Note: Simpler feature updates that don't require vcspull code changes may only need 2 commits. The CHANGES entry goes under "Development" rather than "Breaking changes" when there's no minimum-version constraint change.

---

## Commit Message Conventions

**Package bump**: `py(deps) libvcs <old> -> <new>` — body has "See also" link, files: `pyproject.toml` + `uv.lock`

**Code adaptation**: `<module>(fix|feat[detail]): description` — body has `why:` and `what:`, files: `src/` only

**Test adaptation**: `tests(fix|feat[detail]): description` — files: `tests/` and optionally `conftest.py`

**CHANGES**: `docs(CHANGES) <brief description>` — no PR number, no version suffix, files: `CHANGES` only

## CHANGES Entry Conventions

| Update type | CHANGES section |
|-------------|----------------|
| Minimum version bump | `### Breaking changes` |
| New features adopted | `### Features` or `### What's new` |
| Bug fixes from libvcs | `### Bug fixes` |
| Test changes | `### Tests` |
| Maintenance-only bump | `### Development` |

Version slug format for links: `0.39.0` → `libvcs-0-39-0-2026-02-07` (with release date).

PR number handling: Use `(#???)` as placeholder if no PR exists yet. CHANGES entries reference PRs; commit messages do not.
