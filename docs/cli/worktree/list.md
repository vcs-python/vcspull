(cli-worktree-list)=

# vcspull worktree list

Show configured worktrees and their planned status without making changes.

## Command

```{eval-rst}
.. argparse::
    :module: vcspull.cli
    :func: create_parser
    :prog: vcspull
    :path: worktree list
```

## Basic usage

List all configured worktrees:

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

## Filtering

Filter to specific repositories:

```console
$ vcspull worktree list 'myproject'
```

Use fnmatch-style patterns:

```console
$ vcspull worktree list 'django*'
```

## JSON output

```console
$ vcspull worktree list --json 'myproject'
```

## NDJSON output

```console
$ vcspull worktree list --ndjson 'myproject'
```
