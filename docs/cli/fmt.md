(cli-fmt)=

# vcspull fmt

`vcspull fmt` normalizes configuration files so directory keys and repository
entries stay consistent. By default the formatter prints the proposed changes to
stdout. Apply the updates in place with `--write`.

When duplicate workspace roots are encountered, the formatter merges them into a
single section so repositories are never dropped. Prefer to review duplicates
without rewriting them? Pass `--no-merge` to leave the original sections in
place while still showing a warning.

## Command

```{eval-rst}
.. argparse::
    :module: vcspull.cli
    :func: create_parser
    :prog: vcspull
    :path: fmt
```

## What gets formatted

The formatter performs four main tasks:

- Expands string-only entries into verbose dictionaries using the `repo` key.
- Converts legacy `url` keys to `repo` for consistency with the rest of the
  tooling.
- Sorts directory keys and repository names alphabetically to minimize diffs.
- Consolidates duplicate workspace roots into a single merged section while
  logging any conflicts.

For example:

```yaml
~/code/:
  libvcs: git+https://github.com/vcspull/libvcs.git
  vcspull:
    url: git+https://github.com/vcspull/vcspull.git
```

becomes:

```yaml
~/code/:
  libvcs:
    repo: git+https://github.com/vcspull/libvcs.git
  vcspull:
    repo: git+https://github.com/vcspull/vcspull.git
```

## Writing changes

Run the formatter in dry-run mode first to preview the adjustments:

```console
$ vcspull fmt --file ~/.vcspull.yaml
```

Then add `--write` to persist them back to disk:

```console
$ vcspull fmt \
    --file ~/.vcspull.yaml \
    --write
```

Use `--all` to iterate over the default search locations: the current working
directory, `~/.vcspull.*`, and the XDG configuration directory. Each formatted
file is reported individually.

```console
$ vcspull fmt --all --write
```

Pair the formatter with [`vcspull discover`](cli-discover) after scanning the file
system to keep newly added repositories ordered and normalized.
