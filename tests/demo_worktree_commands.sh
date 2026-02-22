#!/usr/bin/env bash
# Manual integration test for vcspull worktree CLI commands.
# Runs in an isolated HOME so the real user config is never touched.
#
# Usage:
#   bash tests/demo_worktree_commands.sh
set -euo pipefail

# ── Utility functions ─────────────────────────────────────────────

PASS=0
FAIL=0
ORIG_HOME="$HOME"
DEMO_HOME="/tmp/vcspull-demo-worktrees"

section() {
    printf '\n\033[1;36m══ %s ══\033[0m\n' "$1"
}

pass_test() {
    PASS=$((PASS + 1))
    printf '  \033[32m✓ PASS\033[0m %s\n' "$1"
}

fail_test() {
    FAIL=$((FAIL + 1))
    printf '  \033[31m✗ FAIL\033[0m %s\n' "$1"
}

assert_success() {
    local label="$1"; shift
    if "$@" >/dev/null 2>&1; then
        pass_test "$label"
    else
        fail_test "$label (command exited non-zero)"
    fi
}

assert_contains() {
    local label="$1" needle="$2" haystack="$3"
    if printf '%s' "$haystack" | grep -qF "$needle"; then
        pass_test "$label"
    else
        fail_test "$label — expected to find '$needle'"
    fi
}

assert_not_contains() {
    local label="$1" needle="$2" haystack="$3"
    if printf '%s' "$haystack" | grep -qF "$needle"; then
        fail_test "$label — should NOT contain '$needle'"
    else
        pass_test "$label"
    fi
}

assert_exists() {
    local label="$1" path="$2"
    if [ -e "$path" ]; then
        pass_test "$label"
    else
        fail_test "$label — path does not exist: $path"
    fi
}

assert_not_exists() {
    local label="$1" path="$2"
    if [ -e "$path" ]; then
        fail_test "$label — path should not exist: $path"
    else
        pass_test "$label"
    fi
}

cleanup() {
    export HOME="$ORIG_HOME"
    echo ""
    echo "Cleaning up $DEMO_HOME ..."
    rm -rf "$DEMO_HOME"
}
trap cleanup EXIT

# ── Step 0: Environment Setup ─────────────────────────────────────

section "Step 0: Environment Setup"

rm -rf "$DEMO_HOME"
mkdir -p "$DEMO_HOME"
export HOME="$DEMO_HOME"

git config --global user.name "Test"
git config --global user.email "test@test.com"

# Create first source repo
mkdir -p "$HOME/repos/myproject"
git -C "$HOME/repos/myproject" init -b main
echo "hello" > "$HOME/repos/myproject/README.md"
git -C "$HOME/repos/myproject" add .
git -C "$HOME/repos/myproject" commit -m "initial commit"
git -C "$HOME/repos/myproject" tag v1.0.0
git -C "$HOME/repos/myproject" tag v2.0.0
git -C "$HOME/repos/myproject" branch develop
git -C "$HOME/repos/myproject" branch feature-x
COMMIT_SHA=$(git -C "$HOME/repos/myproject" rev-parse HEAD)

# Create second source repo
mkdir -p "$HOME/repos/other-project"
git -C "$HOME/repos/other-project" init -b main
echo "other" > "$HOME/repos/other-project/README.md"
git -C "$HOME/repos/other-project" add .
git -C "$HOME/repos/other-project" commit -m "initial commit"
git -C "$HOME/repos/other-project" tag v1.0.0

echo "Created source repos, COMMIT_SHA=$COMMIT_SHA"

# ── Step 1: Write Main Config ─────────────────────────────────────

section "Step 1: Write Main Config"

cat > "$HOME/.vcspull.yaml" <<EOF
$HOME/repos/:
  myproject:
    repo: git+file://$HOME/repos/myproject
    worktrees:
      - dir: "../worktrees/myproject-v1"
        tag: "v1.0.0"
      - dir: "../worktrees/myproject-dev"
        branch: "develop"
      - dir: "../worktrees/myproject-pinned"
        commit: "$COMMIT_SHA"
EOF
echo "Wrote $HOME/.vcspull.yaml"

# ── S1: List Before Sync (empty state) ───────────────────────────

section "S1: List Before Sync (empty state)"

OUT=$(uv run vcspull worktree list --color never 2>&1) || true
echo "$OUT"

assert_contains "S1: output contains myproject"      "myproject"   "$OUT"
assert_contains "S1: output contains + (CREATE)"      "+"           "$OUT"
assert_contains "S1: output contains tag:v1.0.0"      "tag:v1.0.0"  "$OUT"
assert_contains "S1: output contains branch:develop"   "branch:develop" "$OUT"
assert_contains "S1: output contains 'will create'"     "will create"  "$OUT"

# ── S2: First Sync (creates all 3 worktrees) ─────────────────────

section "S2: First Sync (creates all 3 worktrees)"

OUT=$(uv run vcspull worktree sync --color never 2>&1) || true
echo "$OUT"

assert_contains "S2: summary has +3 created"          "+3 created"  "$OUT"
assert_exists   "S2: myproject-v1 dir exists"          "$HOME/worktrees/myproject-v1"
assert_exists   "S2: myproject-dev dir exists"         "$HOME/worktrees/myproject-dev"
assert_exists   "S2: myproject-pinned dir exists"      "$HOME/worktrees/myproject-pinned"

# Verify refs
V1_TAG=$(git -C "$HOME/worktrees/myproject-v1" describe --exact-match --tags HEAD 2>&1) || true
assert_contains "S2: v1 tag is v1.0.0"                "v1.0.0"      "$V1_TAG"

DEV_BRANCH=$(git -C "$HOME/worktrees/myproject-dev" branch --show-current 2>&1) || true
assert_contains "S2: dev branch is develop"            "develop"     "$DEV_BRANCH"

PINNED_SHA=$(git -C "$HOME/worktrees/myproject-pinned" rev-parse HEAD 2>&1) || true
assert_contains "S2: pinned SHA matches"               "$COMMIT_SHA" "$PINNED_SHA"

# ── S3: List After Sync (shows status) ───────────────────────────

section "S3: List After Sync (shows status)"

OUT=$(uv run vcspull worktree list --color never 2>&1) || true
echo "$OUT"

assert_contains "S3: output contains exists"           "exists"      "$OUT"

# ── S4: Re-Sync (update branch, unchanged tag/commit) ────────────

section "S4: Re-Sync (update branch, unchanged tag/commit)"

OUT=$(uv run vcspull worktree sync --color never 2>&1) || true
echo "$OUT"

assert_contains "S4: summary has ~1 updated"           "~1 updated"  "$OUT"
assert_contains "S4: summary has +0 created"           "+0 created"  "$OUT"

# ── S5: Dirty Worktree Detection (BLOCKED) ───────────────────────

section "S5: Dirty Worktree Detection (BLOCKED)"

echo "dirty" > "$HOME/worktrees/myproject-dev/dirty.txt"

OUT=$(uv run vcspull worktree sync --color never 2>&1) || true
echo "$OUT"

assert_contains "S5: output contains blocked indicator" "blocked"    "$OUT"

rm -f "$HOME/worktrees/myproject-dev/dirty.txt"

# ── S6: Missing Ref (ERROR) ──────────────────────────────────────

section "S6: Missing Ref (ERROR)"

cat > "$HOME/test-missing-ref.yaml" <<EOF
$HOME/repos/:
  myproject:
    repo: git+file://$HOME/repos/myproject
    worktrees:
      - dir: "../worktrees/myproject-bad-ref"
        tag: "v99.99.99"
EOF

OUT=$(uv run vcspull worktree sync -f "$HOME/test-missing-ref.yaml" --color never 2>&1) || true
echo "$OUT"

assert_contains   "S6: output contains error symbol"   "not found"   "$OUT"
assert_not_exists "S6: bad-ref dir does not exist"      "$HOME/worktrees/myproject-bad-ref"
assert_contains   "S6: summary has errors"              "errors"      "$OUT"

# ── S7: Dry-Run Sync ─────────────────────────────────────────────

section "S7: Dry-Run Sync"

cat > "$HOME/test-dryrun.yaml" <<EOF
$HOME/repos/:
  myproject:
    repo: git+file://$HOME/repos/myproject
    worktrees:
      - dir: "../worktrees/wt-dryrun"
        tag: "v2.0.0"
EOF

OUT=$(uv run vcspull worktree sync -f "$HOME/test-dryrun.yaml" --dry-run --color never 2>&1) || true
echo "$OUT"

assert_contains   "S7: output contains Would sync"     "Would sync"  "$OUT"
assert_contains   "S7: output contains dry-run tip"     "without --dry-run" "$OUT"
assert_not_exists "S7: wt-dryrun dir does not exist"    "$HOME/worktrees/wt-dryrun"

# ── S8: Path Types (relative, absolute, tilde) ───────────────────

section "S8: Path Types (relative, absolute, tilde)"

cat > "$HOME/test-paths.yaml" <<EOF
$HOME/repos/:
  myproject:
    repo: git+file://$HOME/repos/myproject
    worktrees:
      - dir: "../worktrees/wt-relative"
        tag: "v1.0.0"
      - dir: "$HOME/worktrees/wt-absolute"
        tag: "v1.0.0"
      - dir: "~/worktrees/wt-tilde"
        tag: "v1.0.0"
EOF

OUT=$(uv run vcspull worktree sync -f "$HOME/test-paths.yaml" --color never 2>&1) || true
echo "$OUT"

assert_exists "S8: wt-relative dir exists"              "$HOME/worktrees/wt-relative"
assert_exists "S8: wt-absolute dir exists"              "$HOME/worktrees/wt-absolute"
assert_exists "S8: wt-tilde dir exists"                 "$HOME/worktrees/wt-tilde"

# ── S9: Lock + Lock Reason ────────────────────────────────────────

section "S9: Lock + Lock Reason"

cat > "$HOME/test-lock.yaml" <<EOF
$HOME/repos/:
  myproject:
    repo: git+file://$HOME/repos/myproject
    worktrees:
      - dir: "../worktrees/wt-locked"
        tag: "v1.0.0"
        lock: true
        lock_reason: "Production"
EOF

OUT=$(uv run vcspull worktree sync -f "$HOME/test-lock.yaml" --color never 2>&1) || true
echo "$OUT"

LOCK_INFO=$(git -C "$HOME/repos/myproject" worktree list --porcelain 2>&1) || true
echo "$LOCK_INFO"

assert_contains "S9: worktree is locked"                "locked"      "$LOCK_INFO"
assert_contains "S9: lock reason is Production"          "Production"  "$LOCK_INFO"

# ── S10: Pattern Filtering ────────────────────────────────────────

section "S10: Pattern Filtering"

cat > "$HOME/test-filter.yaml" <<EOF
$HOME/repos/:
  myproject:
    repo: git+file://$HOME/repos/myproject
    worktrees:
      - dir: "../worktrees/filter-mp"
        tag: "v1.0.0"
  other-project:
    repo: git+file://$HOME/repos/other-project
    worktrees:
      - dir: "../worktrees/filter-op"
        tag: "v1.0.0"
EOF

OUT=$(uv run vcspull worktree list -f "$HOME/test-filter.yaml" "myproject" --color never 2>&1) || true
echo "$OUT"

assert_contains     "S10: myproject filter shows myproject"      "myproject"      "$OUT"
assert_not_contains "S10: myproject filter hides other-project"  "other-project"  "$OUT"

OUT=$(uv run vcspull worktree list -f "$HOME/test-filter.yaml" "other*" --color never 2>&1) || true
echo "$OUT"

assert_contains     "S10: other* filter shows other-project"    "other-project"  "$OUT"

# ── S11: JSON Output ─────────────────────────────────────────────

section "S11: JSON Output"

OUT=$(uv run vcspull worktree list --json --color never 2>&1) || true
echo "$OUT"

# JSON mode output should be valid JSON
if echo "$OUT" | python3 -m json.tool >/dev/null 2>&1; then
    pass_test "S11: output is valid JSON"
else
    fail_test "S11: output is NOT valid JSON"
fi

assert_contains "S11: JSON has ref_type"                "ref_type"    "$OUT"
assert_contains "S11: JSON has action"                  "action"      "$OUT"

# ── S12: NDJSON Output ───────────────────────────────────────────

section "S12: NDJSON Output"

OUT=$(uv run vcspull worktree list --ndjson --color never 2>&1) || true
echo "$OUT"

NDJSON_VALID=true
while IFS= read -r line; do
    if [ -n "$line" ] && ! echo "$line" | python3 -m json.tool >/dev/null 2>&1; then
        NDJSON_VALID=false
        break
    fi
done <<< "$OUT"

if $NDJSON_VALID; then
    pass_test "S12: each NDJSON line is valid JSON"
else
    fail_test "S12: NDJSON has invalid JSON lines"
fi

# ── S13: vcspull sync --include-worktrees ─────────────────────────

section "S13: vcspull sync --include-worktrees"

cat > "$HOME/test-include-wt.yaml" <<EOF
$HOME/repos/:
  myproject:
    repo: git+file://$HOME/repos/myproject
    worktrees:
      - dir: "../worktrees/wt-via-sync"
        tag: "v2.0.0"
EOF

OUT=$(uv run vcspull sync --all -f "$HOME/test-include-wt.yaml" --include-worktrees --color never 2>&1) || true
echo "$OUT"

assert_contains "S13: output contains Synced myproject" "Synced"      "$OUT"
assert_contains "S13: output mentions worktree"          "worktree"    "$OUT"
assert_exists   "S13: wt-via-sync dir exists"            "$HOME/worktrees/wt-via-sync"

# ── S14: vcspull sync --include-worktrees --dry-run ───────────────

section "S14: vcspull sync --include-worktrees --dry-run"

cat > "$HOME/test-include-wt-dryrun.yaml" <<EOF
$HOME/repos/:
  myproject:
    repo: git+file://$HOME/repos/myproject
    worktrees:
      - dir: "../worktrees/wt-via-sync-dryrun"
        tag: "v2.0.0"
EOF

OUT=$(uv run vcspull sync --all -f "$HOME/test-include-wt-dryrun.yaml" --include-worktrees --dry-run --color never 2>&1) || true
echo "$OUT"

assert_contains   "S14: output contains worktree plan"  "worktree"    "$OUT"
assert_not_exists "S14: wt-via-sync-dryrun not created"  "$HOME/worktrees/wt-via-sync-dryrun"

# ── S15: Dry-Run Prune ───────────────────────────────────────────

section "S15: Dry-Run Prune"

# First ensure myproject-v1 worktree exists (from S2)
assert_exists "S15: myproject-v1 exists before prune"    "$HOME/worktrees/myproject-v1"

# Config that does NOT include myproject-v1 (only dev and pinned)
cat > "$HOME/test-prune-dryrun.yaml" <<EOF
$HOME/repos/:
  myproject:
    repo: git+file://$HOME/repos/myproject
    worktrees:
      - dir: "../worktrees/myproject-dev"
        branch: "develop"
      - dir: "../worktrees/myproject-pinned"
        commit: "$COMMIT_SHA"
EOF

OUT=$(uv run vcspull worktree prune -f "$HOME/test-prune-dryrun.yaml" --dry-run --color never 2>&1) || true
echo "$OUT"

assert_contains "S15: output contains Would prune"      "Would prune" "$OUT"
assert_contains "S15: output mentions myproject-v1"      "myproject-v1" "$OUT"
assert_exists   "S15: myproject-v1 still exists"         "$HOME/worktrees/myproject-v1"

# ── S16: Actual Prune ────────────────────────────────────────────

section "S16: Actual Prune"

OUT=$(uv run vcspull worktree prune -f "$HOME/test-prune-dryrun.yaml" --color never 2>&1) || true
echo "$OUT"

assert_contains   "S16: output contains Pruned"          "Pruned"      "$OUT"
assert_not_exists "S16: myproject-v1 is gone"             "$HOME/worktrees/myproject-v1"
assert_exists     "S16: myproject-dev still exists"       "$HOME/worktrees/myproject-dev"
assert_exists     "S16: myproject-pinned still exists"    "$HOME/worktrees/myproject-pinned"

# ── S17: Prune with Empty Config (orphan detection) ──────────────

section "S17: Prune with Empty Config (orphan detection)"

# Config with NO worktrees key — all remaining worktrees are orphans
cat > "$HOME/test-orphan.yaml" <<EOF
$HOME/repos/:
  myproject:
    repo: git+file://$HOME/repos/myproject
EOF

OUT=$(uv run vcspull worktree prune -f "$HOME/test-orphan.yaml" --color never 2>&1) || true
echo "$OUT"

assert_contains "S17: output mentions pruned worktrees"  "Pruned"      "$OUT"

# ── S18: Verify Clean Git State ──────────────────────────────────

section "S18: Verify Clean Git State"

WORKTREE_LIST=$(git -C "$HOME/repos/myproject" worktree list 2>&1) || true
echo "$WORKTREE_LIST"

# Count lines — should be just the main worktree
LINE_COUNT=$(echo "$WORKTREE_LIST" | wc -l | tr -d ' ')
if [ "$LINE_COUNT" -le 1 ]; then
    pass_test "S18: only main worktree remains"
else
    # Some worktrees may linger from path/lock tests — check that the core
    # worktrees from S2 are gone
    if echo "$WORKTREE_LIST" | grep -q "myproject-dev"; then
        fail_test "S18: myproject-dev worktree still registered"
    elif echo "$WORKTREE_LIST" | grep -q "myproject-pinned"; then
        fail_test "S18: myproject-pinned worktree still registered"
    else
        pass_test "S18: core worktrees pruned (some path/lock test worktrees may remain)"
    fi
fi

# ── Epilogue ─────────────────────────────────────────────────────

echo ""
echo "════════════════════════════════════════════════"
printf 'RESULTS: \033[32m%d passed\033[0m, \033[31m%d failed\033[0m\n' "$PASS" "$FAIL"
echo "════════════════════════════════════════════════"
[ "$FAIL" -eq 0 ] || exit 1
