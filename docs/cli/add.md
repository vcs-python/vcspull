(cli-add)=

# vcspull add

The `vcspull add` command adds a single repository to your vcspull configuration.
Provide a repository name and URL, and vcspull will append it to your config file
with the appropriate workspace root.

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
    :nodescription:
```

## Basic usage

Add a repository by name and URL:

```console
$ vcspull add flask https://github.com/pallets/flask.git
Successfully added 'flask' to ./.vcspull.yaml under './'
```

By default, the repository is added to the current directory's workspace root (`./`).

## Specifying workspace root

Use `-w/--workspace` or `--workspace-root` to control where the repository will be checked out:

```console
$ vcspull add flask https://github.com/pallets/flask.git -w ~/code/
Successfully added 'flask' to ~/.vcspull.yaml under '~/code/'
```

All three flag names work identically:

```console
$ vcspull add django https://github.com/django/django.git --workspace ~/code/
$ vcspull add requests https://github.com/psf/requests.git --workspace-root ~/code/
```

## Custom repository path

Override the inferred path with `--path` when the repository already exists on disk:

```console
$ vcspull add my-lib https://github.com/example/my-lib.git \
    --path ~/code/libraries/my-lib
```

The `--path` flag is useful when:
- Migrating existing local repositories
- Using non-standard directory layouts
- The repository name doesn't match the desired directory name

You can also point `vcspull add` at an existing checkout. Supplying a path such
as `vcspull add ~/projects/example` infers the repository name, inspects its
`origin` remote, and prompts before writing. Add `--yes` when you need to skip
the confirmation in scripts.

## Choosing configuration files

By default, vcspull looks for the first YAML configuration file in:
1. Current directory (`.vcspull.yaml`)
2. Home directory (`~/.vcspull.yaml`)
3. XDG config directory (`~/.config/vcspull/`)

If no config exists, a new `.vcspull.yaml` is created in the current directory.

Specify a custom config file with `-f/--file`:

```console
$ vcspull add vcspull https://github.com/vcs-python/vcspull.git \
    -f ~/projects/.vcspull.yaml
```

## Dry run mode

Preview changes without modifying your configuration with `--dry-run` or `-n`:

```console
$ vcspull add flask https://github.com/pallets/flask.git -w ~/code/ --dry-run
Would add 'flask' (https://github.com/pallets/flask.git) to ~/.vcspull.yaml under '~/code/'
```

This is useful for:
- Verifying the workspace root is correct
- Checking which config file will be modified
- Testing path inference

## URL formats

Repositories use [pip VCS URL][pip vcs url] format with a scheme prefix:

- Git: `git+https://github.com/user/repo.git`
- Mercurial: `hg+https://bitbucket.org/user/repo`
- Subversion: `svn+http://svn.example.org/repo/trunk`

The URL scheme determines the VCS type. For Git, the `git+` prefix is required.

## Examples

Add to default location:

```console
$ vcspull add myproject https://github.com/myuser/myproject.git
```

Add to specific workspace:

```console
$ vcspull add django-blog https://github.com/example/django-blog.git \
    -w ~/code/django/
```

Add with custom path:

```console
$ vcspull add dotfiles https://github.com/myuser/dotfiles.git \
    --path ~/.dotfiles
```

Preview before adding:

```console
$ vcspull add flask https://github.com/pallets/flask.git \
    -w ~/code/ --dry-run
```

Add to specific config file:

```console
$ vcspull add tooling https://github.com/company/tooling.git \
    -f ~/company/.vcspull.yaml \
    -w ~/work/
```

## Handling duplicates

vcspull merges duplicate workspace sections by default so existing repositories
stay intact. When conflicts appear, the command logs what it kept. Prefer to
resolve duplicates yourself? Pass `--no-merge` to leave every section untouched
while still surfacing warnings.

## After adding repositories

After adding repositories, consider:

1. Running `vcspull fmt --write` to normalize and sort your configuration (see {ref}`cli-fmt`)
2. Running `vcspull list` to verify the repository was added correctly (see {ref}`cli-list`)
3. Running `vcspull sync` to clone the repository (see {ref}`cli-sync`)

## Migration from vcspull import

If you previously used `vcspull import <name> <url>`:

```diff
- $ vcspull import flask https://github.com/pallets/flask.git -c ~/.vcspull.yaml
+ $ vcspull add flask https://github.com/pallets/flask.git -f ~/.vcspull.yaml
```

Changes:
- Command name: `import` → `add`
- Config flag: `-c` → `-f`
- Same functionality otherwise

[pip vcs url]: https://pip.pypa.io/en/stable/topics/vcs-support/
