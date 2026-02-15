(cli-search)=

# vcspull search

The `vcspull search` command looks up repositories across your vcspull
configuration with an rg-like query syntax. Queries are regex by default, can
scope to specific fields, and can emit structured JSON for automation.

## Command

```{eval-rst}
.. argparse::
    :module: vcspull.cli
    :func: create_parser
    :prog: vcspull
    :path: search
```

## Basic usage

Search all fields (name, path, url, workspace) with regex:

```vcspull-console
$ vcspull search django
• django → ~/code/django
```

## Field-scoped queries

Target specific fields with prefixes:

```vcspull-console
$ vcspull search name:django url:github
• django → ~/code/django
  url: git+https://github.com/django/django.git
```

Available field prefixes:
- `name:`
- `path:`
- `url:`
- `workspace:` (alias: `root:` or `ws:`)

## Literal matches

Use `-F/--fixed-strings` to match literal text instead of regex:

```console
$ vcspull search --fixed-strings 'git+https://github.com/org/repo.git'
```

## Case handling

`-i/--ignore-case` forces case-insensitive matching. `-S/--smart-case` matches
case-insensitively unless your query includes uppercase characters.

```console
$ vcspull search --smart-case Django
```

## Boolean matching

By default all terms must match. Use `--any` to match if *any* term matches:

```console
$ vcspull search --any django flask
```

Invert matches with `-v/--invert-match`:

```console
$ vcspull search --invert-match --fixed-strings github
```

## JSON output

Emit matches as JSON for automation:

```console
$ vcspull search --json django
```

Output format:

```json
[
  {
    "name": "django",
    "url": "git+https://github.com/django/django.git",
    "path": "~/code/django",
    "workspace_root": "~/code/",
    "matched_fields": ["name", "url"]
  }
]
```

Use NDJSON for streaming:

```console
$ vcspull search --ndjson django
```
