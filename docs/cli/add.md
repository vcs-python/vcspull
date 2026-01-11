(cli-add)=

# vcspull add

The `vcspull add` command registers a repository in your configuration by
pointing vcspull at a checkout on disk. The command inspects the directory,
merges duplicate workspace roots by default, and prompts before writing unless
you pass `--yes`.

```{note}
This command replaces the manual import functionality from `vcspull import`.
For bulk scanning of existing repositories, see {ref}`cli-discover`.
```

## Command

```{eval-rst}
.. argparse::
    :module: vcspull.cli
    :func: create_parser
    :prog: vcspull
    :path: add
```

## Basic usage

Point to an existing checkout to add it under its parent workspace:

```console
$ vcspull add ~/study/python/pytest-docker
Found new repository to import:
  + pytest-docker (https://github.com/avast/pytest-docker)
  • workspace: ~/study/python/
  ↳ path: ~/study/python/pytest-docker
? Import this repository? [y/N]: y
Successfully added 'pytest-docker' (git+https://github.com/avast/pytest-docker) to ~/.vcspull.yaml under '~/study/python/'.
```

The parent directory (`~/study/python/` in this example) becomes the workspace
root. vcspull shortens paths under `$HOME` to `~/...` in its log output so the
preview stays readable.

## Overriding detected information

### Choose a different name

Override the derived repository name with `--name` when the directory name
isn't the label you want stored in the configuration:

```console
$ vcspull add ~/study/python/pytest-docker --name docker-pytest
```

### Override the remote URL

vcspull reads the Git `origin` remote automatically. Supply `--url` when you
need to register a different remote or when the checkout does not have one yet:

```console
$ vcspull add ~/study/python/example --url https://github.com/org/example
```

URLs follow [pip's VCS format][pip vcs url]; vcspull inserts the `git+` prefix
for HTTPS URLs so the resulting configuration matches `vcspull fmt` output.

### Select a workspace explicitly

The workspace defaults to the checkout's parent directory. Pass
`--workspace`/`--workspace-root` to store the repository under a different
section:

```console
$ vcspull add ~/scratch/tmp-project --workspace ~/projects/python/
```

## Confirmation and dry runs

`vcspull add` asks for confirmation before writing. Use `--yes` to skip the
prompt in automation, or `--dry-run`/`-n` to preview the changes without
modifying any files:

```console
$ vcspull add ~/study/python/pytest-docker --dry-run
```

Dry runs still show duplicate merge diagnostics so you can see what would
change.

## Choosing configuration files

vcspull searches for configuration files in this order:

1. `./.vcspull.yaml`
2. `~/.vcspull.yaml`
3. `~/.config/vcspull/*.yaml`

Specify a file explicitly with `-f/--file`:

```console
$ vcspull add ~/study/python/pytest-docker -f ~/configs/python.yaml
```

## Handling duplicates

vcspull merges duplicate workspace sections before writing so existing
repositories stay intact. When it collapses multiple sections, the command logs
a summary of the merge. Prefer to inspect duplicates yourself? Add
`--no-merge` to keep every section untouched.

## After adding repositories

1. Run `vcspull fmt --write` to normalize your configuration (see
   {ref}`cli-fmt`).
2. Run `vcspull list` to verify the new entry (see {ref}`cli-list`).
3. Run `vcspull sync` to clone or update the working tree (see {ref}`cli-sync`).

## Migration from vcspull import

If you previously used `vcspull import <name> <url>`, switch to the path-first
workflow:

```diff
- $ vcspull import flask https://github.com/pallets/flask.git -c ~/.vcspull.yaml
+ $ vcspull add ~/code/flask --url https://github.com/pallets/flask.git -f ~/.vcspull.yaml
```

Key differences:

- `vcspull add` now derives the name from the filesystem unless you pass
  `--name`.
- The parent directory becomes the workspace automatically; use `--workspace`
  to override.
- Use `--url` to record a remote when the checkout does not have one.

[pip vcs url]: https://pip.pypa.io/en/stable/topics/vcs-support/
