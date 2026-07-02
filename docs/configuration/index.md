(configuration)=

# Configuration

::::{grid} 1 1 2 2
:gutter: 2 2 3 3

:::{grid-item-card} Config Generation
:link: generation
:link-type: doc
Import repos from forges and generate config automatically.
:::

::::

## URL Format

Repo type and address is [RFC3986](https://datatracker.ietf.org/doc/html/rfc3986) style URLs.
You may recognize this from [pip](https://pip.pypa.io/en/stable/)'s
[VCS URL] format.

[vcs url]: https://pip.pypa.io/en/latest/topics/vcs-support/

## Config locations

You can place the file in one of three places:

1. Home: _~/.vcspull.yaml_
2. [XDG] home directory: `$XDG_CONFIG_HOME/vcspull/`

   Example: _~/.config/vcspull/myrepos.yaml_

   `XDG_CONFIG_HOME` is often _~/.config/vcspull/_, but can vary on platform, to check:

   ```console
   $ echo $XDG_CONFIG_HOME
   ```

3. Anywhere (and trigger via `vcspull sync --file ./path/to/file.yaml [repo_name]`)

[xdg]: https://standards.freedesktop.org/basedir-spec/basedir-spec-latest.html

## Schema

```{warning}

This structure is subject to break in upcoming releases.
```

```yaml
~/workdir/:
  repo_name:
    remotes:
      origin: git_repo_url
```

### Examples

````{tab} Simple

```{literalinclude} ../../examples/remotes.yaml
:language: yaml

```

To pull _kaptan_:

```console
$ vcspull sync kaptan
```

````

````{tab} Complex

**Christmas tree**

config showing off every current feature and inline shortcut available.

```{literalinclude} ../../examples/christmas-tree.yaml
:language: yaml

```

````

````{tab} Open Source Student

**Code scholar**

This file is used to checkout and sync multiple open source
configs.

YAML:

```{literalinclude} ../../examples/code-scholar.yaml
:language: yaml

```

````

## Worktree configuration

Repositories can declare worktrees—additional checkouts of specific tags,
branches, or commits in separate directories. Worktrees are listed under the
`worktrees` key of a repository entry:

```{literalinclude} ../../examples/worktrees.yaml
:language: yaml
```

Each worktree entry requires:
- `dir`: Path for the worktree (relative to workspace root or absolute)
- Exactly one of `tag`, `branch`, or `commit`

Optional fields:
- `lock`: Lock the worktree to prevent accidental removal
- `lock_reason`: Reason for locking (implies `lock: true`)

See {ref}`cli-worktree` for full command documentation.

## Sync options

Per-repository sync behavior lives under an `options:` block alongside the
`repo` URL. The keys below tune how {ref}`cli-sync` clones and updates a
checkout. Mutation policy such as `pin` lives in the same block (see
{ref}`config-pin`).

### Revision pinning

`options.rev` pins a repository to a commit, tag, or branch, which
{ref}`cli-sync` checks out. This lets a config capture a reproducible snapshot
instead of tracking the branch tip. It is distinct from `options.pin` (see
{ref}`config-pin`), which guards the config entry from being overwritten rather
than pinning a [git](https://git-scm.com/) ref.

```yaml
~/code/:
  flask:
    repo: git+https://github.com/pallets/flask.git
    options:
      rev: v3.0.0
```

`vcspull add <path> --pin <ref>` and `vcspull discover <dir> --pin <ref>` record
this key when importing an existing checkout. See {ref}`cli-add` and
{ref}`cli-discover`.

### Shallow clones

`options.shallow: true` makes {ref}`cli-sync` clone the repository with
`--depth 1`, trading git history for disk and time—useful for workspaces with
many repositories.

```yaml
~/code/:
  flask:
    repo: git+https://github.com/pallets/flask.git
    options:
      shallow: true
```

`vcspull add` and `vcspull discover` detect an existing depth-1 checkout
automatically and record `options.shallow: true`; the `--shallow` flag forces it
on even for a full checkout.

### Clone depth

`options.depth: N` keeps a small window of history by cloning with `--depth N`.
Reach for it when `shallow: true` (depth 1) is too little—for example, a handful
of recent commits for `git log` or `git bisect`.

```yaml
~/code/:
  django:
    repo: git+https://github.com/django/django.git
    options:
      depth: 50
```

`vcspull add <path> --depth N` and `vcspull discover <dir> --depth N` record this
key. When importing an existing shallow checkout, both detect its depth: a
depth-1 checkout records `options.shallow: true` and a deeper window records
`options.depth: N`. `depth` takes precedence over `shallow` when both are set.

### Migrating from the top-level form

vcspull v1.61.0 accepted `rev:` and `shallow:` at the repository entry root.
Those keys still work but are deprecated in favor of the `options:` block, and
{ref}`cli-sync` warns when it reads them. Run {ref}`cli-migrate` to rewrite
existing configs in place:

```console
$ vcspull migrate --write
```

See {ref}`migration` for the deprecation note and {ref}`cli-migrate` for the
command reference.

(config-pin)=

## Repository pinning

Repositories can be **pinned** to prevent automated commands from modifying their
configuration entries. This is useful for pinned forks, company mirrors, or any
repository whose URL or config shape you manage by hand.

Here is a configuration showing all three pin forms side by side:

```yaml
~/code/:
  # Global pin — blocks ALL operations (import, add, discover, fmt, merge)
  internal-fork:
    repo: "git+git@github.com:myorg/internal-fork.git"
    options:
      pin: true
      pin_reason: "pinned to company fork — update manually"

  # Per-operation pin — only import and fmt are blocked
  my-framework:
    repo: "git+git@github.com:myorg/my-framework.git"
    options:
      pin:
        import: true
        fmt: true
      pin_reason: "URL managed manually; formatting intentional"

  # Shorthand — equivalent to pin: {import: true}
  stable-dep:
    repo: "git+https://github.com/upstream/stable-dep.git"
    options:
      allow_overwrite: false
```

### Pin all operations

Set `pin: true` inside `options` to block every mutation command. This is
the simplest form — no automated vcspull command can modify this entry:

```yaml
~/code/:
  internal-fork:
    repo: "git+git@github.com:myorg/internal-fork.git"
    options:
      pin: true
      pin_reason: "pinned to company fork — update manually"
```

### Pin specific operations

Pass a mapping instead of a boolean to pin only the operations you care about.
Unlisted keys default to `false` (unpinned):

```yaml
~/code/:
  my-framework:
    repo: "git+git@github.com:myorg/my-framework.git"
    options:
      pin:
        import: true
        fmt: true
      pin_reason: "URL managed manually; formatting intentional"
```

Available pin keys:

| Key        | Blocks                                                     |
|------------|-----------------------------------------------------------|
| `import`   | `vcspull import --sync` from replacing this URL            |
| `add`      | `vcspull add` from overwriting this entry                  |
| `discover` | `vcspull discover` from overwriting this entry             |
| `fmt`      | `vcspull fmt` from normalizing this entry                  |
| `merge`    | Duplicate-workspace-root merge from displacing this entry  |

### Shorthand: allow_overwrite

`allow_overwrite: false` is a convenience shorthand equivalent to
`pin: {import: true}`. It only guards against `vcspull import --sync`:

```yaml
~/code/:
  stable-dep:
    repo: "git+https://github.com/upstream/stable-dep.git"
    options:
      allow_overwrite: false
```

### Pin behavior

- **Defaults** — repositories are unpinned. All operations proceed normally
  unless a pin is explicitly set.
- **Boolean pin** — `pin: true` blocks all five operations (`import`, `add`,
  `discover`, `fmt`, `merge`).
- **Per-operation pin** — only the listed keys are blocked; unlisted keys
  default to `false` (unpinned).
- **pin_reason** — an optional human-readable string shown in log output when
  an operation is skipped. It is purely informational and does not imply
  `pin: true` on its own.
- **Advisory** — pins prevent automated commands from modifying the entry.
  You can still edit the configuration file by hand at any time.

Each command handles pins differently:

| Command | Pin effect | Log level |
|---------|------------|-----------|
| `vcspull import --sync` | Skips URL replacement | info |
| `vcspull add` | Skips with warning | warning |
| `vcspull discover` | Silently skips | debug |
| `vcspull fmt` | Preserves entry verbatim | (silent) |
| Workspace merge | Pinned entry wins conflict | info |

```{note}
The `pin` and `pin_reason` fields described here live under `options` and
guard the *configuration entry* against mutation by vcspull commands.

This is different from the worktree-level `lock` / `lock_reason` that lives
inside individual `worktrees` entries and passes `--lock` to
`git worktree add`. See {ref}`cli-worktree` for worktree locking.
```

## Import provenance

When repositories are imported with `--sync` or `--prune`, vcspull records
which service and owner the import came from. This is stored in a
`metadata.imported_from` field:

```yaml
~/code/:
  my-project:
    repo: "git+git@github.com:myorg/my-project.git"
    metadata:
      imported_from: "github:myorg"
```

The `metadata` block is managed by vcspull — you generally don't need to edit
it by hand. It is used to scope pruning: when re-importing with `--sync`,
only entries tagged with the matching source are candidates for removal.

See {ref}`cli-import` for full details on `--sync` and `--prune`.

## Caveats

(git-remote-ssh-git)=

### SSH Git URLs

For git remotes using SSH authorization such as `git+git@github.com:tony/kaptan.git` use `git+ssh`:

```console
git+ssh://git@github.com/tony/kaptan.git
```

```{toctree}
:hidden:

generation
```
