(cli-discover)=

# vcspull discover

The `vcspull discover` command scans directories for existing Git repositories
and adds them to your vcspull configuration. This is ideal for importing existing
workspaces or migrating from other tools.

## Command

```{eval-rst}
.. argparse::
    :module: vcspull.cli
    :func: create_parser
    :prog: vcspull
    :path: discover
```

## Basic usage

Scan a directory for Git repositories:

```vcspull-console
$ vcspull discover ~/code
Found 2 repositories in ~/code

Repository: vcspull
  Path: ~/code/vcspull
  Remote: git+https://github.com/vcs-python/vcspull.git
  Workspace: ~/code/

? Add to configuration? [y/N]: y
Successfully added 'vcspull' to ~/.vcspull.yaml

Repository: libvcs
  Path: ~/code/libvcs
  Remote: git+https://github.com/vcs-python/libvcs.git
  Workspace: ~/code/

? Add to configuration? [y/N]: y
Successfully added 'libvcs' to ~/.vcspull.yaml

Scan complete: 2 repositories added, 0 skipped
```

The command prompts for each repository before adding it to your configuration.
When a matching workspace section already exists, vcspull merges the new entry
into it so previously tracked repositories stay intact. Prefer to review
duplicates yourself? Add `--no-merge` to keep every section untouched while
still seeing a warning.

## Recursive scanning

Search nested directories with `--recursive` or `-r`:

```console
$ vcspull discover ~/code --recursive
```

This scans all subdirectories for Git repositories, making it ideal for:
- Workspaces with project categories (e.g., `~/code/python/`, `~/code/rust/`)
- Nested organization structures
- Home directory scans

## Unattended mode

Skip prompts and add all repositories with `--yes` or `-y`:

```vcspull-console
$ vcspull discover ~/code --recursive --yes
Found 15 repositories in ~/code
Added 15 repositories to ~/.vcspull.yaml
```

This is useful for:
- Automated workspace setup
- Migration scripts
- CI/CD environments

## Dry run mode

Preview what would be added without modifying your configuration:

```console
$ vcspull discover ~/code --dry-run
```

Output shows:

```vcspull-output
Would add: vcspull (~/code/)
  Remote: git+https://github.com/vcs-python/vcspull.git

Would add: libvcs (~/code/)
  Remote: git+https://github.com/vcs-python/libvcs.git

Dry run complete: 2 repositories would be added
```

Combine with `--recursive` to preview large scans:

```console
$ vcspull discover ~/ --recursive --dry-run
```

## Workspace root override

Force all discovered repositories to use a specific workspace root:

```console
$ vcspull discover ~/company/projects --workspace-root ~/work/ --yes
```

By default, vcspull infers the workspace root from the repository's location.
The `--workspace-root` override is useful when:

- Consolidating repos from multiple locations
- Standardizing workspace organization
- The inferred workspace root doesn't match your desired structure

Example - scanning home directory but organizing by workspace:

```console
$ vcspull discover ~ --recursive --workspace-root ~/code/ --yes
```

## Choosing configuration files

Specify a custom config file with `-f/--file`:

```console
$ vcspull discover ~/company --recursive -f ~/company/.vcspull.yaml
```

If the config file doesn't exist, it will be created.

## Repository detection

`vcspull discover` identifies Git repositories by looking for `.git` directories.

For each repository found:
1. The directory name becomes the repository name
2. The `origin` remote URL is extracted (if available)
3. The workspace root is inferred from the repository's location
4. You're prompted to confirm adding it

### Repositories without remotes

Repositories without an `origin` remote are detected but logged as a warning:

```vcspull-console
$ vcspull discover ~/code
WARNING: Could not determine remote URL for ~/code/local-project (no origin remote)
Skipping local-project
```

These repositories are skipped by default. You can add them manually with
`vcspull add` if needed.

## Examples

Scan current directory:

```console
$ vcspull discover .
```

Scan recursively with confirmation:

```console
$ vcspull discover ~/code --recursive
```

Bulk import without prompts:

```console
$ vcspull discover ~/code --recursive --yes
```

Preview a large scan:

```console
$ vcspull discover ~/code --recursive --dry-run
```

Scan with custom workspace:

```console
$ vcspull discover /tmp/checkouts --workspace-root ~/code/ --yes
```

Scan to specific config:

```console
$ vcspull discover ~/company/repos \
    --recursive \
    --yes \
    -f ~/company/.vcspull.yaml
```

## After discovering repositories

After discovering repositories, consider:

1. Running `vcspull fmt --write` to normalize and sort your configuration (see {ref}`cli-fmt`)
2. Running `vcspull list --tree` to verify the workspace organization (see {ref}`cli-list`)
3. Running `vcspull status` to confirm all repositories are tracked (see {ref}`cli-status`)

## Handling existing entries

If a repository already exists in your configuration, vcspull will detect it:

```vcspull-console
Repository: flask
  Path: ~/code/flask
  Remote: git+https://github.com/pallets/flask.git
  Workspace: ~/code/

Note: Repository 'flask' already exists in ~/code/
? Add anyway? [y/N]: n
Skipped flask (already exists)
```

You can choose to skip or overwrite the existing entry.

## Migration from vcspull import --scan

If you previously used `vcspull import --scan`:

```diff
- $ vcspull import --scan ~/code --recursive -c ~/.vcspull.yaml --yes
+ $ vcspull discover ~/code --recursive -f ~/.vcspull.yaml --yes
```

Changes:
- Command: `import --scan` → `discover`
- Config flag: `-c` → `-f`
- `--scan` flag removed (discover always scans)
- Same functionality otherwise

## Use cases

**Initial workspace setup:**

Discover all repositories:

```console
$ vcspull discover ~/code --recursive --yes
```

Then format and sort the configuration:

```console
$ vcspull fmt --write
```

**Migrate from another tool:**

Preview what would be discovered:

```console
$ vcspull discover ~/projects --recursive --dry-run
```

Then apply the changes:

```console
$ vcspull discover ~/projects --recursive --yes
```

**Add company repos to separate config:**

```console
$ vcspull discover ~/company \
    --recursive \
    -f ~/company/.vcspull.yaml \
    --workspace-root ~/work/ \
    --yes
```

**Audit what's on disk:**

```console
$ vcspull discover ~/code --recursive --dry-run | grep "Would add"
```
