(cli-sync)=

(vcspull-sync)=

# vcspull sync

The `vcspull sync` command clones and updates repositories defined in your
vcspull configuration. It's the primary command for keeping your local workspace
synchronized with remote repositories.

## Command

```{eval-rst}
.. argparse::
    :module: vcspull.cli
    :func: create_parser
    :prog: vcspull
    :path: sync
```

## Dry run mode

Preview what would be synchronized without making changes:

```vcspull-console
$ vcspull sync --dry-run '*'
Would sync flask at ~/code/flask
Would sync django at ~/code/django
Would sync requests at ~/code/requests
```

Use `--dry-run` or `-n` to:
- Verify your configuration before syncing
- Check which repositories would be updated
- Test pattern filters
- Preview operations in CI/CD

## JSON output

Export sync operations as JSON for automation:

```console
$ vcspull sync --dry-run --json '*'
[
  {
    "reason": "sync",
    "name": "flask",
    "path": "~/code/flask",
    "workspace_root": "~/code/",
    "status": "preview"
  },
  {
    "reason": "summary",
    "total": 3,
    "synced": 0,
    "previewed": 3,
    "failed": 0
  }
]
```

Each event emitted during the run includes:

- `reason`: `"sync"` for repository events, `"summary"` for the final summary
- `name`, `path`, `workspace_root`: Repository metadata from your config
- `status`: `"synced"`, `"preview"`, or `"error"` (with an `error` field)

Use `--json` without `--dry-run` to capture actual sync executions—successful
and failed repositories are emitted with their final state.

## NDJSON output

Stream sync events line-by-line with `--ndjson`:

```console
$ vcspull sync --dry-run --ndjson '*'
{"reason":"sync","name":"flask","path":"~/code/flask","workspace_root":"~/code/","status":"preview"}
{"reason":"summary","total":3,"synced":0,"previewed":3,"failed":0}
```

Each line is a JSON object representing a sync event, ideal for:
- Real-time processing
- Progress monitoring
- Log aggregation

## Configuration file selection

Specify a custom config file with `-f/--file`:

```console
$ vcspull sync -f ~/projects/.vcspull.yaml '*'
```

By default, vcspull searches for config files in:
1. Current directory (`.vcspull.yaml`)
2. Home directory (`~/.vcspull.yaml`)
3. XDG config directory (`~/.config/vcspull/`)

## Workspace filtering

Filter repositories by workspace root with `-w/--workspace` or `--workspace-root`:

```console
$ vcspull sync -w ~/code/ '*'
```

This syncs only repositories in the specified workspace root,  useful for:
- Selective workspace updates
- Multi-workspace setups
- Targeted sync operations

All three flag names work identically. Using `--workspace`:

```console
$ vcspull sync --workspace ~/code/ '*'
```

Or using `--workspace-root`:

```console
$ vcspull sync --workspace-root ~/code/ '*'
```

## Color output

Control colored output with `--color`:

- `--color auto` (default): Use colors if outputting to a terminal
- `--color always`: Always use colors
- `--color never`: Never use colors

The `NO_COLOR` environment variable is also respected.

## Filtering repos

As of 1.13.x, `$ vcspull sync` with no args passed will show a help dialog:

```console
$ vcspull sync
Usage: vcspull sync [OPTIONS] [REPO_TERMS]...
```

### Sync all repos

Depending on how your terminal works with shell escapes for expands such as the [wild card / asterisk], you may not need to quote `*`.

```console
$ vcspull sync '*'
```

[wild card / asterisk]: https://tldp.org/LDP/abs/html/special-chars.html#:~:text=wild%20card%20%5Basterisk%5D.

### Filtering

Filter all repos start with "django-":

```console
$ vcspull sync 'django-*'
```

### Multiple terms

Filter all repos start with "django-":

```console
$ vcspull sync 'django-anymail' 'django-guardian'
```

## Error handling

### Repos not found in config

As of 1.13.x, if you enter a repo term (or terms) that aren't found throughout
your configurations, it will show a warning:

```vcspull-console
$ vcspull sync non_existent_repo
No repo found in config(s) for "non_existent_repo"
```

```vcspull-console
$ vcspull sync non_existent_repo existing_repo
No repo found in config(s) for "non_existent_repo"
```

```vcspull-console
$ vcspull sync non_existent_repo existing_repo another_repo_not_in_config
No repo found in config(s) for "non_existent_repo"
No repo found in config(s) for "another_repo_not_in_config"
```

Since syncing terms are treated as a filter rather than a lookup, the message is
considered a warning, so will not exit even if `--exit-on-error` flag is used.

### Syncing

As of 1.13.x, vcspull will continue to the next repo if an error is encountered when syncing multiple repos.

To imitate the old behavior, the `--exit-on-error` / `-x` flag:

```console
$ vcspull sync --exit-on-error grako django
```

Print traceback for errored repos:

```console
$ vcspull --log-level DEBUG sync --exit-on-error grako django
```
