(cli-add)=

# vcspull add

The `vcspull add` command registers a single repository in your
{ref}`configuration <configuration>`. Point it at a checkout on disk and it
reads the details out of the directory; give it a repository URL and it records
the entry without cloning anything, leaving the working tree to
{ref}`vcspull sync <cli-sync>`. Either way it merges duplicate workspace roots
by default and prompts before writing unless you pass `--yes`.

```{note}
This command replaces the old `vcspull import <name> <url>` from v1.36--v1.39.
For bulk scanning of local repositories, see {ref}`cli-discover`.
For bulk import from remote services ([GitHub](https://github.com),
[GitLab](https://gitlab.com), etc.), see {ref}`cli-import`.
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

```vcspull-console
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

## Declaring a repository you have not cloned

Pass a repository URL instead of a path when you want the entry in your
configuration but do not have the code yet:

```vcspull-console
$ vcspull add https://github.com/pallets/flask.git
Found new repository to import:
  + flask (https://github.com/pallets/flask.git)
  • workspace: ~/code/
  ↳ path: ~/code/flask
  • workspace roots in ~/.vcspull.yaml:
      1) ~/code/ (default)
      2) ~/study/python/
? Import this repository? [y/N/1-2]: y
✓ Successfully added 'flask' (git+https://github.com/pallets/flask.git) to ~/.vcspull.yaml under '~/code/'.
```

The repository name comes from the URL — `flask` here — unless you pass
`--name`. Nothing is fetched: the entry lands in your configuration and
{ref}`vcspull sync <cli-sync>` clones it the next time you run it.

Because there is no parent directory to infer a workspace from, vcspull offers
the workspace roots your configuration already declares. Answering `y` accepts
the default, answering with a number picks a different root, and `--workspace`
names one outright and skips the list. When the configuration declares no roots
yet, the current directory becomes the workspace.

A directory on disk always wins. If the argument names something that exists,
vcspull treats it as a path even when the same text would also parse as a URL.

## Overriding detected information

### Choose a different name

Override the derived repository name with `--name` when the directory name
isn't the label you want stored in the configuration:

```console
$ vcspull add ~/study/python/pytest-docker --name docker-pytest
```

### Override the remote URL

vcspull reads the [Git](https://git-scm.com/) `origin` remote automatically. Supply `--url` when you
need to register a different remote or when the checkout does not have one yet:

```console
$ vcspull add ~/study/python/example --url https://github.com/org/example
```

`--url` accompanies a path. When the argument is already a URL, pass it once and
leave `--url` off — supplying both is ambiguous, so vcspull stops rather than
guessing which one you meant.

URLs follow [pip's VCS format][pip vcs url]; vcspull inserts the `git+` prefix
for HTTPS URLs so the resulting configuration matches
{ref}`vcspull fmt <cli-fmt>` output.

### Select a workspace explicitly

The workspace defaults to the checkout's parent directory, or — when you add by
URL — to the first workspace root your configuration declares. Pass
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
$ vcspull add ~/study/python/pytest-docker \
    --file ~/configs/python.yaml
```

## Handling duplicates

vcspull merges duplicate workspace sections before writing so existing
repositories stay intact. When it collapses multiple sections, the command logs
a summary of the merge. Prefer to inspect duplicates yourself? Add
`--no-merge` to keep every section untouched.

## Pinned entries

Repositories whose configuration includes a {ref}`pin <config-pin>` on the
`add` operation are skipped with a warning. For example, given this configuration:

```yaml
~/code/:
  internal-fork:
    repo: "git+git@github.com:myorg/internal-fork.git"
    options:
      pin: true
      pin_reason: "pinned to company fork — update manually"
```

Attempting to add a repo that matches an existing pinned entry produces a
warning and leaves the entry untouched:

```vcspull-console
$ vcspull add ~/code/internal-fork
⚠ Repository 'internal-fork' is pinned (pinned to company fork — update manually) — skipping
```

Both `options.pin: true` (global) and `options.pin.add: true` (per-operation)
block the `add` command. The `pin_reason` (if set) is included in the warning.
See {ref}`config-pin` for full pin configuration.

## After adding repositories

1. Run {ref}`vcspull fmt <cli-fmt>` with `--write` to normalize your
   configuration.
2. Run {ref}`vcspull list <cli-list>` to verify the new entry.
3. Run {ref}`vcspull sync <cli-sync>` to clone or update the working tree.

## Migration from the old vcspull import

The `vcspull import <name> <url>` command from v1.36--v1.39 has been replaced
by `vcspull add`:

```diff
- $ vcspull import flask https://github.com/pallets/flask.git -c ~/.vcspull.yaml
+ $ vcspull add https://github.com/pallets/flask.git --file ~/.vcspull.yaml
```

Key differences:

- `vcspull add` derives the name from the URL, or from the directory when you
  add a checkout, unless you pass `--name`.
- The workspace comes from the checkout's parent directory, or from the
  workspace roots your configuration declares when you add by URL; use
  `--workspace` to override either.
- Use `--url` to record a remote when a checkout does not have one.

```{note}
Starting with v1.55, `vcspull import` is a *different* command that bulk-imports
repositories from remote services (GitHub, GitLab, etc.). See {ref}`cli-import`
for details.
```

[pip vcs url]: https://pip.pypa.io/en/stable/topics/vcs-support/
