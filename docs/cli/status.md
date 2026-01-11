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
✗ tiktoken: missing
✓ flask: up to date
✓ django: up to date

Summary: 3 repositories, 2 exist, 1 missing
```

The command shows:
- Repository name and path
- Whether the repository exists on disk
- If it's a Git repository
- Basic cleanliness status

## Filtering repositories

Filter repositories using fnmatch-style patterns:

```vcspull-console
$ vcspull status 'django*'
• django → ~/code/django (exists, clean)
• django-extensions → ~/code/django-extensions (missing)
```

Multiple patterns are supported:

```console
$ vcspull status django flask requests
```

## Detailed status

Show additional information with `--detailed` or `-d`:

```vcspull-console
$ vcspull status --detailed
✓ flask: up to date
  Path: ~/code/flask
  Branch: main
  Ahead/Behind: 0/0
```

This mode shows the full path, active branch, and divergence counters (`ahead`
and `behind`) relative to the tracked upstream. If the working tree has
uncommitted changes the headline reports `dirty` and the JSON payloads set
`clean` to `false`.

## JSON output

Export status information as JSON for automation and monitoring:

```console
$ vcspull status --json
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
    "branch": "main",
    "ahead": 0,
    "behind": 0
  },
  {
    "reason": "summary",
    "total": 2,
    "exists": 1,
    "missing": 1,
    "clean": 1,
    "dirty": 0
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
- `branch`: Current branch (when detailed information is available)
- `ahead`, `behind`: Divergence counts relative to the upstream branch

Filter with [jq]:

```console
$ vcspull status --json | jq '.[] | select(.reason == "status" and .exists == false)'
$ vcspull status --json | jq '.[] | select(.reason == "summary")'
```

## NDJSON output

For streaming output, use `--ndjson`:

```console
$ vcspull status --ndjson
{"reason":"status","name":"tiktoken","path":"~/study/ai/tiktoken","workspace_root":"~/study/ai/","exists":false,"is_git":false,"clean":null}
{"reason":"status","name":"flask","path":"~/code/flask","workspace_root":"~/code/","exists":true,"is_git":true,"clean":true}
{"reason":"summary","total":2,"exists":1,"missing":1,"clean":1,"dirty":0}
```

Process line-by-line:

```console
$ vcspull status --ndjson | grep '"exists":false' | jq -r '.name'
```

## Use cases

Monitor missing repositories:

```console
$ vcspull status --json | jq -r '.[] | select(.reason == "status" and .exists == false) | .name'
```

Check which repositories need syncing:

```console
$ vcspull status --json | jq -r '.[] | select(.reason == "status" and .exists == false) | .name' | xargs vcspull sync
```

Generate reports:

```console
$ vcspull status --json > workspace-status-$(date +%Y%m%d).json
```

## Choosing configuration files

Specify a custom config file with `-f/--file`:

```console
$ vcspull status -f ~/projects/.vcspull.yaml
```

## Workspace filtering

Filter repositories by workspace root (planned feature):

```console
$ vcspull status -w ~/code/
```

## Color output

Control colored output with `--color`:

- `--color auto` (default): Use colors if outputting to a terminal
- `--color always`: Always use colors
- `--color never`: Never use colors

The `NO_COLOR` environment variable is also respected.

## Future enhancements

The status command will be expanded to include:
- Detailed Git status (ahead/behind remote, current branch)
- Dirty working tree detection
- Remote URL mismatches
- Submodule status

[jq]: https://stedolan.github.io/jq/
