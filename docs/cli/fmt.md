(cli-fmt)=

# vcspull fmt

`vcspull fmt` normalizes configuration files so directory keys and repository
entries stay consistent. By default the formatter prints the proposed changes to
stdout. Apply the updates in place with `--write`.

## Command

```{eval-rst}
.. argparse::
    :module: vcspull.cli
    :func: create_parser
    :prog: vcspull
    :path: fmt
    :nodescription:
```

## What gets formatted

The formatter performs three main tasks:

- Expands string-only entries into verbose dictionaries using the `repo` key.
- Converts legacy `url` keys to `repo` for consistency with the rest of the
  tooling.
- Sorts directory keys and repository names alphabetically to minimize diffs.

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

Run the formatter in dry-run mode first to preview the adjustments, then add
`--write` (or `-w`) to persist them back to disk:

```console
$ vcspull fmt --file ~/.vcspull.yaml
$ vcspull fmt --file ~/.vcspull.yaml --write
```

Short form:

```console
$ vcspull fmt -f ~/.vcspull.yaml
$ vcspull fmt -f ~/.vcspull.yaml -w
```

Use `--all` to iterate over the default search locations: the current working
directory, `~/.vcspull.*`, and the XDG configuration directory. Each formatted
file is reported individually.

```console
$ vcspull fmt --all --write
```

Pair the formatter with [`vcspull discover`](cli-discover) after scanning the file
system to keep newly added repositories ordered and normalized.
