(cli-worktree)=

# vcspull worktree

The `vcspull worktree` command manages [git worktrees] declaratively from your
vcspull configuration. Instead of manually running `git worktree add` for each
branch or tag, you declare the desired worktrees in YAML and let vcspull
create, update, and prune them.

[git worktrees]: https://git-scm.com/docs/git-worktree

## Command

```{eval-rst}
.. argparse::
    :module: vcspull.cli
    :func: create_parser
    :prog: vcspull
    :path: worktree
    :nosubcommands:
    :nodescription:
```

Choose a subcommand for details:

- {ref}`cli-worktree-list` — show configured worktrees and their status
- {ref}`cli-worktree-sync` — create or update worktrees
- {ref}`cli-worktree-prune` — remove worktrees not in configuration

```{toctree}
:maxdepth: 1
:hidden:

list
sync
prune
```

## Configuration

Worktrees are configured as a list under a repository entry. Each worktree
requires a `dir` (relative to workspace root or absolute) and exactly one
ref type: `tag`, `branch`, or `commit`.

```yaml
~/code/:
  myproject:
    url: "git+https://github.com/myorg/myproject.git"
    worktrees:
      # Pin a stable release (detached HEAD)
      - dir: "../myproject-v2.0"
        tag: "v2.0.0"
        lock: true
        lock_reason: "production reference"

      # Track a development branch (updatable)
      - dir: "../myproject-dev"
        branch: "develop"

      # Pin a specific commit (detached HEAD)
      - dir: "../myproject-bisect"
        commit: "abc1234"
```

### Fields

| Field | Required | Description |
|-------|----------|-------------|
| `dir` | yes | Worktree path (relative to workspace root or absolute) |
| `tag` | one of | Tag to checkout (creates detached HEAD) |
| `branch` | one of | Branch to checkout (can be updated/pulled) |
| `commit` | one of | Commit SHA to checkout (creates detached HEAD) |
| `lock` | no | Lock the worktree to prevent accidental removal |
| `lock_reason` | no | Reason for locking (implies `lock: true`) |

Exactly one of `tag`, `branch`, or `commit` must be specified per entry.

## Integration with vcspull sync

The `vcspull sync` command can sync worktrees alongside repositories using the
`--include-worktrees` flag:

```console
$ vcspull sync --include-worktrees '*'
```

Preview the combined operation:

```console
$ vcspull sync --include-worktrees --dry-run '*'
```

This first syncs (clones/updates) the repository itself, then processes its
configured worktrees.

## JSON output

All subcommands support `--json` for structured output:

```console
$ vcspull worktree list --json 'myproject'
```

Each worktree entry emits:

```json
{
  "worktree_path": "~/code/myproject-v2.0",
  "ref_type": "tag",
  "ref_value": "v2.0.0",
  "action": "unchanged",
  "exists": true,
  "is_dirty": false,
  "detail": "tag worktree already exists",
  "error": null
}
```

### NDJSON output

Stream events line-by-line with `--ndjson`:

```console
$ vcspull worktree list --ndjson 'myproject'
```

Each line is a self-contained JSON object, suitable for piping to [jq] or
log aggregation.

[jq]: https://stedolan.github.io/jq/

## Safety

vcspull applies several safety checks before modifying worktrees:

**Dirty worktrees are BLOCKED.** If a worktree has uncommitted changes, vcspull
will not update or remove it. Commit or stash your changes first.

**Missing refs are ERROR.** If a configured tag, branch, or commit doesn't exist
in the repository, the entry is marked as an error. Fetch from the remote to
make the ref available.

**Lock support.** Worktrees created with `lock: true` or `lock_reason` are
locked via `git worktree lock`, preventing accidental removal with
`git worktree remove`.

## Pattern filtering

Filter which repositories are processed using fnmatch-style patterns:

```console
$ vcspull worktree list 'django*'
```

```console
$ vcspull worktree sync 'myproject' 'another-repo'
```

Use `'*'` to match all repositories with worktrees configured.

## Workspace filtering

Filter by workspace root directory:

```console
$ vcspull worktree list --workspace ~/code/
```

## Configuration file selection

Specify a custom config file:

```console
$ vcspull worktree list --file ~/projects/.vcspull.yaml
```

## Color output

Control colored output with `--color`:

- `--color auto` (default): Use colors if outputting to a terminal
- `--color always`: Always use colors
- `--color never`: Never use colors

The `NO_COLOR` environment variable is also respected.

## Use cases

### LLM / agentic workflows

Clone a repository trunk and pin multiple release tags for reference:

```yaml
~/code/:
  cpython:
    url: "git+https://github.com/python/cpython.git"
    worktrees:
      - dir: "../cpython-3.12"
        tag: "v3.12.0"
      - dir: "../cpython-3.13"
        tag: "v3.13.0"
```

This gives agents read-only snapshots of specific versions alongside the
main checkout.

### Parallel development across branches

Work on multiple feature branches without switching:

```yaml
~/code/:
  webapp:
    url: "git+https://github.com/myorg/webapp.git"
    worktrees:
      - dir: "../webapp-feature-auth"
        branch: "feature/auth"
      - dir: "../webapp-feature-billing"
        branch: "feature/billing"
```

### Maintaining versioned reference copies

Lock stable releases to prevent accidental modification:

```yaml
~/code/:
  library:
    url: "git+https://github.com/myorg/library.git"
    worktrees:
      - dir: "../library-v1"
        tag: "v1.0.0"
        lock: true
        lock_reason: "legacy API reference"
      - dir: "../library-v2"
        tag: "v2.0.0"
        lock: true
        lock_reason: "current stable reference"
```
