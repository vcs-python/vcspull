#!/usr/bin/env bash
# Build the sandbox the demo tapes record against.
#
# Everything lives under /tmp/vcspull-demo, which the tapes point HOME and
# XDG_CONFIG_HOME at. That keeps the recordings off the real home directory and
# makes every path on screen render as ~/code/... instead of a developer's
# actual layout.
#
# Idempotent: wipes and rebuilds. Re-run before re-rendering any tape.
set -euo pipefail

DEMO_DIR=/tmp/vcspull-demo

# Resolve the vcspull under test. Override with VCSPULL_BIN to record against a
# working tree rather than an installed release.
REAL_VCSPULL="${VCSPULL_BIN:-$(command -v vcspull || true)}"
if [ -z "$REAL_VCSPULL" ]; then
  echo "error: vcspull not found on PATH; set VCSPULL_BIN to its location" >&2
  exit 1
fi

rm -rf "$DEMO_DIR"
mkdir -p "$DEMO_DIR/.config/vcspull" "$DEMO_DIR/bin"

# The tapes put $DEMO_DIR/bin first on PATH, so `vcspull` resolves here without
# any absolute developer path appearing in a committed tape.
printf '#!/usr/bin/env bash\nexec %q "$@"\n' "$REAL_VCSPULL" > "$DEMO_DIR/bin/vcspull"
chmod +x "$DEMO_DIR/bin/vcspull"

# ---------------------------------------------------------------- main config
# Eight widely-recognized public repositories, grouped by language. The three
# Python entries pin depth: 1 so the sync demo clones shallowly and finishes
# inside a watchable window.
cat > "$DEMO_DIR/.vcspull.yaml" <<'YAML'
~/code/python/:
  click:
    url: git+https://github.com/pallets/click.git
    options:
      depth: 1
  flask:
    url: git+https://github.com/pallets/flask.git
    options:
      depth: 1
    worktrees:
      - dir: ../flask-3.x
        tag: "3.0.0"
      - dir: ../flask-dev
        branch: main
  httpx:
    url: git+https://github.com/encode/httpx.git
    options:
      depth: 1
~/code/go/:
  bubbletea: git+https://github.com/charmbracelet/bubbletea.git
  fzf: git+https://github.com/junegunn/fzf.git
  gin: git+https://github.com/gin-gonic/gin.git
~/code/c/:
  jq: git+https://github.com/jqlang/jq.git
  tmux: git+https://github.com/tmux/tmux.git
YAML

# -------------------------------------------------------------- legacy config
# Pre-v1.62 shape, with rev/shallow/depth at the entry root. Feeds `migrate`.
cat > "$DEMO_DIR/legacy.yaml" <<'YAML'
~/code/python/:
  click:
    url: git+https://github.com/pallets/click.git
    shallow: true
  flask:
    url: git+https://github.com/pallets/flask.git
    depth: 1
    rev: "3.0.0"
YAML

# -------------------------------------------------------------- cloned repos
# Three of the eight are present on disk; the rest stay missing so `status`
# shows a mix rather than a uniform column of checkmarks.
mkdir -p "$DEMO_DIR/code/python" "$DEMO_DIR/code/rust"
for r in "pallets/click" "pallets/flask" "encode/httpx"; do
  git clone --quiet --depth 1 "https://github.com/$r.git" \
    "$DEMO_DIR/code/python/${r#*/}" 2>/dev/null
done

# `worktree list` plans a tag worktree. A --depth 1 clone carries no tags, so
# without this fetch the tag fails to resolve and libvcs prints the absolute
# sandbox path inside the error -- putting /tmp/vcspull-demo on screen.
git -C "$DEMO_DIR/code/python/flask" fetch --quiet --depth 1 origin tag 3.0.0

# One dirty tree, so `status` and `sync` have a non-clean state to report.
echo "scratch" >> "$DEMO_DIR/code/python/flask/README.md"

# On disk but absent from the config, which gives `add` and `discover`
# something real to find.
git init --quiet "$DEMO_DIR/code/rust/ripgrep"
git -C "$DEMO_DIR/code/rust/ripgrep" remote add origin \
  https://github.com/BurntSushi/ripgrep.git
git -C "$DEMO_DIR/code/rust/ripgrep" \
  -c user.email=demo@example.com -c user.name=demo \
  commit --quiet --allow-empty -m "init"

# ------------------------------------------------------------------- restore
# Mutative demos (add, sync, fmt, migrate) reset from these between takes.
cp "$DEMO_DIR/.vcspull.yaml" "$DEMO_DIR/.vcspull.yaml.bak"
cp "$DEMO_DIR/legacy.yaml" "$DEMO_DIR/legacy.yaml.bak"
tar -C "$DEMO_DIR" -czf "$DEMO_DIR/code.tar.gz" code

echo "sandbox ready: $DEMO_DIR ($(du -sh "$DEMO_DIR/code" | cut -f1))"
