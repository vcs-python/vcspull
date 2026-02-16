(cli-worktree-sync)=

# vcspull worktree sync

Create or update worktrees to match configuration.

## Command

```{eval-rst}
.. argparse::
    :module: vcspull.cli
    :func: create_parser
    :prog: vcspull
    :path: worktree sync
```

## Basic usage

Sync all configured worktrees:

```console
$ vcspull worktree sync '*'
```

The sync subcommand:
- Creates missing worktrees at the configured `dir`
- Pulls latest changes for `branch` worktrees
- Leaves `tag` and `commit` worktrees unchanged (they're immutable)
- Skips worktrees with uncommitted changes (BLOCKED)

## Dry run

Preview what would happen without making changes:

```console
$ vcspull worktree sync --dry-run '*'
```

## Filtering

Sync worktrees for specific repositories:

```console
$ vcspull worktree sync 'myproject'
```

Use fnmatch-style patterns:

```console
$ vcspull worktree sync 'django*'
```

## JSON output

```console
$ vcspull worktree sync --json '*'
```

## NDJSON output

```console
$ vcspull worktree sync --ndjson '*'
```
