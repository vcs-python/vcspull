(cli-list)=

# vcspull list

The `vcspull list` command displays configured repositories from your vcspull
configuration files. Use this introspection command to verify your configuration,
filter repositories by patterns, and export structured data for automation.

## Command

```{eval-rst}
.. argparse::
    :module: vcspull.cli
    :func: create_parser
    :prog: vcspull
    :path: list
    :nodescription:
```

## Basic usage

List all configured repositories:

```console
$ vcspull list
• tiktoken → /home/d/study/ai/tiktoken
• GeographicLib → /home/d/study/c++/GeographicLib
• flask → /home/d/code/flask
```

## Filtering repositories

Filter repositories using fnmatch-style patterns:

```console
$ vcspull list 'flask*'
• flask → /home/d/code/flask
• flask-sqlalchemy → /home/d/code/flask-sqlalchemy
```

Multiple patterns are supported:

```console
$ vcspull list django flask
```

## Tree view

Group repositories by workspace root with `--tree`:

```console
$ vcspull list --tree

~/study/ai/
  • tiktoken → /home/d/study/ai/tiktoken

~/study/c++/
  • GeographicLib → /home/d/study/c++/GeographicLib
  • anax → /home/d/study/c++/anax

~/code/
  • flask → /home/d/code/flask
```

## JSON output

Export repository information as JSON for automation and tooling:

```console
$ vcspull list --json
```

Output format:

```json
[
  {
    "name": "tiktoken",
    "url": "git+https://github.com/openai/tiktoken.git",
    "path": "/home/d/study/ai/tiktoken",
    "workspace_root": "~/study/ai/"
  },
  {
    "name": "flask",
    "url": "git+https://github.com/pallets/flask.git",
    "path": "/home/d/code/flask",
    "workspace_root": "~/code/"
  }
]
```

The `workspace_root` field shows which configuration section the repository
belongs to, matching the keys in your `.vcspull.yaml` file.

Filter JSON output with tools like [jq]:

```console
$ vcspull list --json | jq '.[] | select(.workspace_root | contains("study"))'
```

## NDJSON output

For streaming and line-oriented processing, use `--ndjson`:

```console
$ vcspull list --ndjson
{"name":"tiktoken","url":"git+https://github.com/openai/tiktoken.git","path":"/home/d/study/ai/tiktoken","workspace_root":"~/study/ai/"}
{"name":"flask","url":"git+https://github.com/pallets/flask.git","path":"/home/d/code/flask","workspace_root":"~/code/"}
```

Each line is a complete JSON object, making it ideal for:
- Processing large configurations line-by-line
- Streaming data to other tools
- Parsing with simple line-based tools

```console
$ vcspull list --ndjson | grep 'study' | jq -r '.name'
```

## Choosing configuration files

By default, vcspull searches for config files in standard locations
(`~/.vcspull.yaml`, `./.vcspull.yaml`, and XDG config directories).

Specify a custom config file with `-f/--file`:

```console
$ vcspull list -f ~/projects/.vcspull.yaml
```

## Workspace filtering

Filter repositories by workspace root with `-w/--workspace/--workspace-root`:

```console
$ vcspull list -w ~/code/
• flask → /home/d/code/flask
• requests → /home/d/code/requests
```

Globbing is supported, so you can target multiple related workspaces:

```console
$ vcspull list --workspace '*/work/*'
```

The workspace filter combines with pattern filters and structured output flags,
allowing you to export subsets of your configuration quickly.

## Color output

Control colored output with `--color`:

- `--color auto` (default): Use colors if outputting to a terminal
- `--color always`: Always use colors
- `--color never`: Never use colors

The `NO_COLOR` environment variable is also respected.

[jq]: https://stedolan.github.io/jq/
