(cli-sync)=

(vcspull-sync)=

# vcspull sync

The `vcspull sync` command clones and updates repositories defined in your
vcspull {ref}`configuration <configuration>`. It's the primary command for keeping your local workspace
synchronized with remote repositories.

```{image} ../_static/demos/asciinema/vcspull-sync.gif
:alt: vcspull sync cloning a workspace of repositories
:width: 100%
:loading: lazy
```

## Command

```{eval-rst}
.. argparse::
    :module: vcspull.cli
    :func: create_parser
    :prog: vcspull
    :path: sync
```

## Filtering repos

Running `vcspull sync` with no patterns syncs nothing and prints the generated
help text. You always say which repositories to touch, with patterns or
`--all`.

### Sync all repos

Sync everything with the `*` pattern:

```console
$ vcspull sync '*'
```

Depending on how your shell expands the [wild card / asterisk], you may not
need to quote `*`.

[wild card / asterisk]: https://tldp.org/LDP/abs/html/special-chars.html#:~:text=wild%20card%20%5Basterisk%5D.

### Filtering

Filter repos starting with "django-":

```console
$ vcspull sync 'django-*'
```

### Multiple terms

Name several repositories exactly:

```console
$ vcspull sync 'django-anymail' 'django-guardian'
```

## Configuration file selection

Specify a custom config file with `-f/--file`:

```console
$ vcspull sync --file ~/projects/.vcspull.yaml '*'
```

By default, vcspull searches for config files in:
1. Current directory (`.vcspull.yaml`)
2. Home directory (`~/.vcspull.yaml`)
3. [XDG](https://standards.freedesktop.org/basedir-spec/basedir-spec-latest.html)
   config directory (`~/.config/vcspull/`)

## Workspace filtering

Filter repositories by workspace root with `-w/--workspace` or `--workspace-root`:

```console
$ vcspull sync --workspace ~/code/ '*'
```

This syncs only repositories in the specified workspace root, useful for:
- Selective workspace updates
- Multi-workspace setups
- Targeted sync operations

The `-w`, `--workspace`, and `--workspace-root` spellings work identically:

```console
$ vcspull sync --workspace-root ~/code/ '*'
```

## Error handling

### Repos not found in config

If a repo term has no match in your configurations, vcspull shows a warning:

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

Sync terms act as a filter rather than a lookup, so the message is a
warning — it does not stop the run, even with `--exit-on-error`.

### Continuing past errors

When syncing multiple repositories, vcspull continues to the next repository
if one fails.

Pass `--exit-on-error` / `-x` to stop the whole run at the first failing
repository instead:

```console
$ vcspull sync --exit-on-error grako django
```

Print traceback for errored repos:

```console
$ vcspull --log-level DEBUG sync --exit-on-error grako django
```

## Dry run mode

Preview what would be synchronized without making changes:

```vcspull-console
$ vcspull sync --dry-run '*'
Plan: 2 to clone (+), 0 to update (~), 2 unchanged (✓), 0 blocked (⚠), 0 errors (✗)

~/code/
  + django-extensions  ~/code/django-extensions  missing

~/study/ai/
  + tiktoken  ~/study/ai/tiktoken  missing
Tip: run without --dry-run to apply. Use --show-unchanged to include ✓ rows.
```

Use `--dry-run` or `-n` to:
- Verify your configuration before syncing
- Check which repositories would be updated
- Test pattern filters
- Preview operations in CI/CD

## JSON output

Export sync operations as JSON for automation:

```console
$ vcspull sync --dry-run --json 'flask' 'tiktoken'
```

Output:

```json
[
  {
    "format_version": "1",
    "type": "operation",
    "name": "tiktoken",
    "path": "~/study/ai/tiktoken",
    "workspace_root": "~/study/ai/",
    "action": "clone",
    "detail": "missing",
    "url": "git+https://github.com/openai/tiktoken.git"
  },
  {
    "format_version": "1",
    "type": "summary",
    "clone": 1,
    "update": 0,
    "unchanged": 1,
    "blocked": 0,
    "errors": 0,
    "total": 2,
    "duration_ms": 8
  }
]
```

Each event emitted during the run includes:

- `format_version`: Schema version of the event stream (currently `"1"`)
- `type`: `"operation"` for repository events, `"summary"` for the final
  summary
- `name`, `path`, `workspace_root`, `url`: Repository metadata from your
  config
- `action`: `"clone"`, `"update"`, `"unchanged"`, `"blocked"`, or `"error"`
- `detail`: Short explanation of the action, when available
- `branch`, `ahead`, `behind`, `dirty`: Working-tree state for existing
  checkouts

Use `--json` without `--dry-run` to capture actual sync executions—successful
and failed repositories are emitted with their final state.

## NDJSON output

Stream sync events line-by-line with `--ndjson`:

```console
$ vcspull sync --dry-run --ndjson 'flask' 'tiktoken'
```

```vcspull-output
{"format_version": "1", "type": "operation", "name": "tiktoken", "path": "~/study/ai/tiktoken", "workspace_root": "~/study/ai/", "action": "clone", "detail": "missing", "url": "git+https://github.com/openai/tiktoken.git"}
{"format_version": "1", "type": "summary", "clone": 1, "update": 0, "unchanged": 1, "blocked": 0, "errors": 0, "total": 2, "duration_ms": 7}
```

Each line is a JSON object representing a sync event, ideal for:
- Real-time processing
- Progress monitoring
- Log aggregation

## Color output

Control colored output with `--color`:

- `--color auto` (default): Use colors if outputting to a terminal
- `--color always`: Always use colors
- `--color never`: Never use colors

The [`NO_COLOR`](https://no-color.org/) environment variable is also
respected.
