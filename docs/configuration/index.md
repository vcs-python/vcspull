(configuration)=

# Configuration

Configuration maps workspace roots to repository entries. A workspace root is
where repositories live on disk, and each entry tells vcspull which VCS URL to
clone or update when you run {ref}`vcspull sync <cli-sync>`.

Most users can start with one `~/.vcspull.yaml` file:

```yaml
~/code/:
  flask:
    repo: git+https://github.com/pallets/flask.git
```

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

3. Anywhere (and trigger via {ref}`vcspull sync <cli-sync>` with
   `--file ./path/to/file.yaml [repo_name]`)

[xdg]: https://standards.freedesktop.org/basedir-spec/basedir-spec-latest.html

## Schema

Editors can complete configuration fields and catch invalid options using
[the published JSON Schema](https://vcspull.git-pull.com/_static/schemas/vcspull.schema.json).
Add its directive at the top of your YAML file:

```yaml
# yaml-language-server: $schema=https://vcspull.git-pull.com/_static/schemas/vcspull.schema.json
~/code/:
  flask:
    repo: git+https://github.com/pallets/flask.git
    git:
      filter: blob:none
```

The loader validates settings independently before sync starts.

Integer configuration fields use the exact JSON integer range through
`9007199254740991`. Native Git filter strings retain the full uint64 range;
for example, `filter: "tree:18446744073709551615"`.

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

## Backend options

Repository entries use one backend block matching their URL: `git`, `hg`,
or `svn`. Unknown keys, wrong-backend blocks, and malformed values fail when
loading, with the file, workspace, repository, and field in the error.
Supplied legacy values must be valid even when a canonical field overrides
them. Numeric integer fields accept `2.0` as `2`; booleans and fractional
values fail. Metadata contains JSON-compatible values with string keys.

| Block | Options |
| --- | --- |
| `git` | `depth`, `filter`, `tls_verify` |
| `hg` | `ssh`, `remote_cmd`, `pull`, `stream`, `tls_verify` |
| `svn` | `username`, `password`, `depth`, `trust_server_cert`, `ignore_externals` |

Git `depth` is a positive history length. Subversion `depth` is one of
`empty`, `files`, `immediates`, or `infinity`. TLS verification defaults to
`true` for Git and Mercurial. Subversion uses its client's certificate checks
unless `trust_server_cert` is enabled.

### Partial clones

`git.filter: blob:none` retains commit history while leaving historical file
contents on the remote until Git needs them. Checkout downloads the contents
needed by the current working tree.

```yaml
~/code/:
  git:
    repo: git+https://github.com/git/git.git
    git:
      filter: blob:none
  monorepo:
    repo: git+https://example.com/monorepo.git
    git:
      filter:
        - blob:limit=1m
        - kind: tree
          depth: 3
```

Filters accept atomic native strings, kind-tagged mappings, or nonempty lists.
Use a mapping or nested list for a combined filter, without percent encoding:

```yaml
git:
  filter:
    kind: combine
    filters:
      - blob:none
      - tree:3
```

Native `combine:` strings are rejected in configuration; `vcspull migrate`
converts them to this structured form. Combinations may nest up to 32 levels.
`auto` requires a Git version that supports it and cannot be combined with
other filters or forwarded to submodule initialization. libvcs validates
filter syntax before running Git. The remote must enable partial-clone
filtering; Git may otherwise warn and transfer all objects.

### History depth and revisions

Use `git.depth: 1` for a shallow clone, or a larger positive integer for a
history window. `working_copy.rev` selects a native revision expression.

```yaml
~/code/:
  flask:
    repo: git+https://github.com/pallets/flask.git
    working_copy:
      rev: v3.0.0
    git:
      depth: 50
```

Depth and filter options apply to the initial clone and its submodules.
Changing either setting leaves an existing checkout's history and filter
unchanged. Revision selection is independent of the entry's mutation policy
under `pin`.

Legacy `options`, top-level `rev`/`shallow`/`depth`, and `<vcs>_options` blocks
still load with a warning. Run {ref}`cli-migrate` to rewrite them in one pass:

```console
$ vcspull migrate --write
```

See {ref}`migration` for precedence and the upgrade example.

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
    pin: true
    pin_reason: "pinned to company fork — update manually"

  # Per-operation pin — only import and fmt are blocked
  my-framework:
    repo: "git+git@github.com:myorg/my-framework.git"
    pin:
      import: true
      fmt: true
    pin_reason: "URL managed manually; formatting intentional"

  # Shorthand — equivalent to pin: {import: true}
  stable-dep:
    repo: "git+https://github.com/upstream/stable-dep.git"
    allow_overwrite: false
```

### Pin all operations

Set `pin: true` at the repository entry level to block every mutation command. This is
the simplest form — no automated vcspull command can modify this entry:

```yaml
~/code/:
  internal-fork:
    repo: "git+git@github.com:myorg/internal-fork.git"
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
    pin:
      import: true
      fmt: true
    pin_reason: "URL managed manually; formatting intentional"
```

Available pin keys:

| Key        | Blocks                                                     |
|------------|-----------------------------------------------------------|
| `import`   | {ref}`vcspull import <cli-import>` with `--sync` from replacing this URL |
| `add`      | {ref}`vcspull add <cli-add>` from overwriting this entry                 |
| `discover` | {ref}`vcspull discover <cli-discover>` from overwriting this entry       |
| `fmt`      | {ref}`vcspull fmt <cli-fmt>` from normalizing this entry                 |
| `merge`    | Duplicate-workspace-root merge from displacing this entry  |

### Shorthand: allow_overwrite

`allow_overwrite: false` is a convenience shorthand equivalent to
`pin: {import: true}`. It only guards against
{ref}`vcspull import <cli-import>` with `--sync`:

```yaml
~/code/:
  stable-dep:
    repo: "git+https://github.com/upstream/stable-dep.git"
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
| {ref}`vcspull import <cli-import>` with `--sync` | Skips URL replacement | info |
| {ref}`vcspull add <cli-add>` | Skips with warning | warning |
| {ref}`vcspull discover <cli-discover>` | Silently skips | debug |
| {ref}`vcspull fmt <cli-fmt>` | Preserves entry verbatim | (silent) |
| Workspace merge | Pinned entry wins conflict | info |

```{note}
The `pin` and `pin_reason` fields live at the repository entry level and
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

```text
git+ssh://git@github.com/tony/kaptan.git
```

```{toctree}
:hidden:

generation
```
