(cli-status)=

# vcspull status

The `vcspull status` command checks the health of configured repositories,
showing which repositories exist on disk, which are missing, and their Git status.
This introspection command helps verify your local workspace matches your configuration.

## Command

```{eval-rst}
.. argparse::
    :module: vcspull.cli
    :func: create_parser
    :prog: vcspull
    :path: status
```

## Basic usage

Check the status of all configured repositories:

```vcspull-console
$ vcspull status
✗ django-extensions: missing
✗ tiktoken: missing
✓ flask: up to date
✓ django: up to date

Summary: 4 repositories, 2 exist, 2 missing
```

The command shows:
- Repository name
- Whether the checkout exists on disk (`missing`)
- The working-tree state for git checkouts (`up to date`, `dirty`)

## Filtering repositories

Filter repositories using fnmatch-style patterns:

```vcspull-console
$ vcspull status 'django*'
✗ django-extensions: missing
✓ django: up to date

Summary: 2 repositories, 1 exist, 1 missing
```

Multiple patterns are supported:

```console
$ vcspull status django flask requests
```

## Detailed status

Show additional information with `--detailed` or `-d`:

```vcspull-console
$ vcspull status --detailed
✗ django-extensions: missing
  Path: ~/code/django-extensions
✗ tiktoken: missing
  Path: ~/study/ai/tiktoken
✓ django: dirty
  Path: ~/code/django
  Branch: main
  Ahead/Behind: 0/0
✓ flask: up to date
  Path: ~/code/flask
  Branch: main
  Ahead/Behind: 0/0

Summary: 4 repositories, 2 exist, 2 missing
```

This mode shows the full path, active branch, and divergence counters (`ahead`
and `behind`) relative to the tracked upstream. If the working tree has
uncommitted changes the headline reports `dirty` and the JSON payloads set
`clean` to `false`.

## JSON output

Export status information as JSON for automation and monitoring:

```console
$ vcspull status --json flask tiktoken
```

Output format:

```json
[
  {
    "reason": "status",
    "name": "tiktoken",
    "path": "~/study/ai/tiktoken",
    "workspace_root": "~/study/ai/",
    "exists": false,
    "is_git": false,
    "clean": null,
    "branch": null,
    "ahead": null,
    "behind": null
  },
  {
    "reason": "status",
    "name": "flask",
    "path": "~/code/flask",
    "workspace_root": "~/code/",
    "exists": true,
    "is_git": true,
    "clean": true,
    "branch": null,
    "ahead": null,
    "behind": null
  },
  {
    "reason": "summary",
    "total": 2,
    "exists": 1,
    "missing": 1,
    "clean": 1,
    "dirty": 0,
    "duration_ms": 4
  }
]
```

Each status entry includes:
- `reason`: Always `"status"` for repository entries, `"summary"` for the final summary
- `name`: Repository name
- `path`: Full filesystem path
- `workspace_root`: Configuration section this repo belongs to
- `exists`: Whether the directory exists
- `is_git`: Whether it's a Git repository
- `clean`: Git working tree status (`null` if not a git repo or missing)
- `branch`: Current branch (populated only with `--detailed`, otherwise `null`)
- `ahead`, `behind`: Divergence counts relative to the upstream branch
  (populated only with `--detailed`, otherwise `null`)

Combine `--json` with `--detailed` to fill in `branch`, `ahead`, and `behind`.

Filter with [jq] to find missing repositories:

```console
$ vcspull status --json \
    | jq '.[] | select(.reason == "status" and .exists == false)'
```

Or extract just the summary:

```console
$ vcspull status --json | jq '.[] | select(.reason == "summary")'
```

## NDJSON output

For streaming output, use `--ndjson`:

```console
$ vcspull status --ndjson flask tiktoken
{"reason": "status", "name": "tiktoken", "path": "~/study/ai/tiktoken", "workspace_root": "~/study/ai/", "exists": false, "is_git": false, "clean": null, "branch": null, "ahead": null, "behind": null}
{"reason": "status", "name": "flask", "path": "~/code/flask", "workspace_root": "~/code/", "exists": true, "is_git": true, "clean": true, "branch": null, "ahead": null, "behind": null}
{"reason": "summary", "total": 2, "exists": 1, "missing": 1, "clean": 1, "dirty": 0, "duration_ms": 4}
```

Process line-by-line:

```console
$ vcspull status --ndjson | grep '"exists":false' | jq -r '.name'
```

## Use cases

Monitor missing repositories:

```console
$ vcspull status --json \
    | jq -r '.[] | select(.reason == "status" and .exists == false) | .name'
```

Check which repositories need syncing:

```console
$ vcspull status --json \
    | jq -r '.[] | select(.reason == "status" and .exists == false) | .name' \
    | xargs vcspull sync
```

Generate reports:

```console
$ vcspull status --json > workspace-status-$(date +%Y%m%d).json
```

## Choosing configuration files

Specify a custom config file with `-f/--file`:

```console
$ vcspull status --file ~/projects/.vcspull.yaml
```

## Workspace filtering

Filter repositories by workspace root with `-w/--workspace` or `--workspace-root`:

```console
$ vcspull status --workspace ~/code/
```

## Color output

Control colored output with `--color`:

- `--color auto` (default): Use colors if outputting to a terminal
- `--color always`: Always use colors
- `--color never`: Never use colors

The `NO_COLOR` environment variable is also respected.

[jq]: https://stedolan.github.io/jq/
