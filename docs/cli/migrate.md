(cli-migrate)=

# vcspull migrate

`vcspull migrate` rewrites {ref}`configuration files <configuration>` into
checkout targets, backend options, and entry policy. It previews changes by
default; `--write` saves them.

## Command

```{eval-rst}
.. argparse::
    :module: vcspull.cli
    :func: create_parser
    :prog: vcspull
    :path: migrate
```

## What gets migrated

| Legacy setting | Destination |
| --- | --- |
| `rev` or `options.rev` | `working_copy.rev` |
| `depth` or `options.depth` | `git.depth` |
| `shallow: true` or `options.shallow: true` | `git.depth: 1` |
| `git_options`, `hg_options`, `svn_options` | `git`, `hg`, `svn` |
| `options.pin`, `options.pin_reason`, `options.allow_overwrite` | Entry level |

Canonical values win over legacy values. Within legacy settings, backend
blocks win over `options`, which wins over top-level tuning. An explicit
depth wins over shallow cloning. A canonical target replaces the legacy
target as a whole, so migration cannot add a second ref selector.

Unknown `options` keys stop migration and name the configuration file,
workspace root, repository entry, and key. The file remains unchanged.

Given:

```yaml
~/code/:
  flask:
    repo: git+https://github.com/pallets/flask.git
    rev: v3.0.0
    shallow: true
```

`vcspull migrate --write` produces:

```yaml
~/code/:
  flask:
    repo: git+https://github.com/pallets/flask.git
    working_copy:
      rev: v3.0.0
    git:
      depth: 1
```

## Writing changes

Preview the rewrite first:

```console
$ vcspull migrate --file ~/.vcspull.yaml
```

Then add `--write` to persist it:

```console
$ vcspull migrate \
    --file ~/.vcspull.yaml \
    --write
```

Use `--all` to iterate over the default search locations: the current working
directory, `~/.vcspull.*`, and the
[XDG](https://standards.freedesktop.org/basedir-spec/basedir-spec-latest.html)
configuration directory.

```console
$ vcspull migrate --all --write
```

One pass rewrites every legacy location. Repeating migration makes no changes.

## See also

- {ref}`configuration` — checkout targets and backend options.
- {ref}`migration` — upgrade examples.
