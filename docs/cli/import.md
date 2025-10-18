(cli-import)=

# vcspull import

The `vcspull import` command registers existing repositories with your vcspull
configuration. You can either provide a single repository name and URL or scan
directories for Git repositories that already live on disk.

## Command

```{eval-rst}
.. argparse::
    :module: vcspull.cli
    :func: create_parser
    :prog: vcspull
    :path: import
    :nodescription:
```

## Manual import

Provide a repository name and remote URL to append an entry to your
configuration. Use `--path` when you already have a working tree on disk so the
configured base directory matches its location. Override the inferred base
directory with `--dir` when you need a specific configuration key.

```console
$ vcspull import my-lib https://github.com/example/my-lib.git --path ~/code/my-lib
```

With no `-c/--config` flag vcspull looks for the first YAML configuration file
under `~/.config/vcspull/` or the current working directory. When none exist a
new `.vcspull.yaml` is created next to where you run the command.

## Filesystem scanning

`vcspull import --scan` discovers Git repositories that already exist on disk
and writes them to your configuration. The command prompts before adding each
repository, showing the inferred name, directory key, and origin URL (when
available).

```console
$ vcspull import --scan ~/code --recursive
? Add ~/code/vcspull (dir: ~/code/)? [y/N]: y
? Add ~/code/libvcs (dir: ~/code/)? [y/N]: y
```

- `--recursive`/`-r` searches nested directories.
- `--base-dir-key` forces all discovered repositories to use the same base
  directory key, overriding the automatically expanded directory.
- `--yes`/`-y` accepts every suggestion, which is useful for unattended
  migrations.

When vcspull detects a Git remote named `origin` it records the remote URL in
the configuration. Repositories without a remote are still added, allowing you
to fill the `repo` key later.

## Choosing configuration files

Pass `-c/--config` to import into a specific YAML file:

```console
$ vcspull import --scan ~/company --recursive --config ~/company/.vcspull.yaml
```

Use `--all` with the [`vcspull fmt`](cli-fmt) command after a large scan to keep
configuration entries sorted and normalized.
