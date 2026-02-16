(cli-worktree-prune)=

# vcspull worktree prune

Remove worktrees that are no longer in your configuration.

## Command

```{eval-rst}
.. argparse::
    :module: vcspull.cli
    :func: create_parser
    :prog: vcspull
    :path: worktree prune
```

## Basic usage

Prune orphaned worktrees:

```console
$ vcspull worktree prune '*'
```

Prune scans all git worktrees registered with each matched repository and
removes any that don't appear in the current config. Repositories that have
had their `worktrees` config removed entirely are also scanned.

## Dry run

Preview what would be removed:

```console
$ vcspull worktree prune --dry-run '*'
```

## Filtering

Prune worktrees for specific repositories:

```console
$ vcspull worktree prune 'myproject'
```

## JSON output

```console
$ vcspull worktree prune --json '*'
```

## NDJSON output

```console
$ vcspull worktree prune --ndjson '*'
```
