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

## Subcommands

### List

Show configured worktrees and their planned status without making changes:

```console
$ vcspull worktree list
```

Each worktree is displayed with a status symbol:

| Symbol | Action | Meaning |
|--------|--------|---------|
| `+` | CREATE | Worktree doesn't exist yet, will be created |
| `~` | UPDATE | Branch worktree exists, will pull latest |
| `✓` | UNCHANGED | Tag/commit worktree exists, already at target |
| `⚠` | BLOCKED | Worktree has uncommitted changes |
| `✗` | ERROR | Operation failed (ref not found, etc.) |

Filter to specific repositories:

```console
$ vcspull worktree list 'myproject'
```

### Sync

Create or update worktrees to match configuration:

```console
$ vcspull worktree sync '*'
```

Preview what would happen without making changes:

```console
$ vcspull worktree sync --dry-run '*'
```

The sync subcommand:
- Creates missing worktrees at the configured `dir`
- Pulls latest changes for `branch` worktrees
- Leaves `tag` and `commit` worktrees unchanged (they're immutable)
- Skips worktrees with uncommitted changes (BLOCKED)

### Prune

Remove worktrees that are no longer in your configuration:

```console
$ vcspull worktree prune '*'
```

Preview what would be removed:

```console
$ vcspull worktree prune --dry-run '*'
```

Prune scans all git worktrees registered with each matched repository and
removes any that don't appear in the current config. Repositories that have
had their `worktrees` config removed entirely are also scanned.

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
