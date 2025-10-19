(cli-import)=

# vcspull import

```{warning}
**This command has been removed** as of vcspull 1.38.0.

The `import` command has been split into two focused commands:
- Use {ref}`cli-add` to add single repositories manually
- Use {ref}`cli-discover` to scan directories for existing repositories

See the {ref}`migration guide <migration>` for detailed upgrade instructions.
```

## Historical Documentation

The `vcspull import` command previously registered existing repositories with your vcspull
configuration. You could either provide a single repository name and URL or scan
directories for Git repositories that already lived on disk.

## Manual import

Provide a repository name and remote URL to append an entry to your
configuration. Use `--path` when you already have a working tree on disk so the
inferred workspace root matches its location. Override the detected workspace
root with `--workspace-root` when you need to target a specific directory.

```console
$ vcspull import my-lib https://github.com/example/my-lib.git --path ~/code/my-lib
$ vcspull import another-lib https://github.com/example/another-lib.git \
    --workspace-root ~/code
```

With no `-c/--config` flag vcspull looks for the first YAML configuration file
under `~/.config/vcspull/` or the current working directory. When none exist a
new `.vcspull.yaml` is created next to where you run the command.

## Filesystem scanning

`vcspull import --scan` discovers Git repositories that already exist on disk
and writes them to your configuration. The command prompts before adding each
repository, showing the inferred name, workspace root, and origin URL (when
available).

```console
$ vcspull import --scan ~/code --recursive
? Add ~/code/vcspull (workspace root: ~/code/)? [y/N]: y
? Add ~/code/libvcs (workspace root: ~/code/)? [y/N]: y
```

- `--recursive`/`-r` searches nested directories.
- `--workspace-root` forces all discovered repositories to use the same
  workspace root, overriding the directory inferred from their location.
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

## Migration Guide

### Manual import → add

```diff
- $ vcspull import myproject https://github.com/user/myproject.git -c ~/.vcspull.yaml
+ $ vcspull add myproject https://github.com/user/myproject.git -f ~/.vcspull.yaml
```

Changes:
- Command name: `import` → `add`
- Config flag: `-c/--config` → `-f/--file`

See {ref}`cli-add` for full documentation.

### Filesystem scanning → discover

```diff
- $ vcspull import --scan ~/code --recursive -c ~/.vcspull.yaml --yes
+ $ vcspull discover ~/code --recursive -f ~/.vcspull.yaml --yes
```

Changes:
- Command: `import --scan` → `discover`
- Config flag: `-c/--config` → `-f/--file`
- `--scan` flag removed (discover always scans)

See {ref}`cli-discover` for full documentation.
