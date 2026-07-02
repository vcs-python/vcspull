(cli-migrate)=

# vcspull migrate

`vcspull migrate` rewrites {ref}`configuration files <configuration>` to the
current schema, moving the
per-repository `rev`, `shallow`, and `depth` keys from the entry root into the
`options:` block. By default it prints the proposed changes; apply them in place
with `--write`.

These keys shipped at the entry root in vcspull v1.61.0. They are still read,
but {ref}`cli-sync` warns when it encounters them. Migrating clears the warning
and keeps configs on the supported shape.

## Command

```{eval-rst}
.. argparse::
    :module: vcspull.cli
    :func: create_parser
    :prog: vcspull
    :path: migrate
```

## What gets migrated

For each repository entry, a top-level `rev`, `shallow`, or `depth` key is moved
under `options:`. A value already present under `options:` wins, and `depth`
takes precedence over `shallow`. Entries already on the `options:` form, string
shorthands, and unrelated keys are left untouched.

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
    options:
      rev: v3.0.0
      shallow: true
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

Migration is idempotent—running it again on an already-migrated file makes no
changes.

## See also

- {ref}`configuration` — the `options:` block and its sync-tuning keys.
- {ref}`migration` — the deprecation note for the top-level form.
