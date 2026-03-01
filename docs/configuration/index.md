(configuration)=

# Configuration

## URL Format

Repo type and address is [RFC3986](https://datatracker.ietf.org/doc/html/rfc3986) style URLs.
You may recognize this from `pip`'s [VCS URL] format.

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

3. Anywhere (and trigger via `vcspull sync -c ./path/to/file.yaml sync [repo_name]`)

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

(config-lock)=

## Repository locking

Repositories can be **locked** to prevent automated commands from modifying their
configuration entries. This is useful for pinned forks, company mirrors, or any
repository whose URL or config shape you manage by hand.

Here is a configuration showing all three lock forms side by side:

```yaml
~/code/:
  # Global lock — blocks ALL operations (import, add, discover, fmt, merge)
  internal-fork:
    repo: "git+git@github.com:myorg/internal-fork.git"
    options:
      lock: true
      lock_reason: "pinned to company fork — update manually"

  # Per-operation lock — only import and fmt are blocked
  my-framework:
    repo: "git+git@github.com:myorg/my-framework.git"
    options:
      lock:
        import: true
        fmt: true
      lock_reason: "URL managed manually; formatting intentional"

  # Shorthand — equivalent to lock: {import: true}
  stable-dep:
    repo: "git+https://github.com/upstream/stable-dep.git"
    options:
      allow_overwrite: false
```

### Lock all operations

Set `lock: true` inside `options` to block every mutation command. This is
the simplest form — no automated vcspull command can modify this entry:

```yaml
~/code/:
  internal-fork:
    repo: "git+git@github.com:myorg/internal-fork.git"
    options:
      lock: true
      lock_reason: "pinned to company fork — update manually"
```

### Lock specific operations

Pass a mapping instead of a boolean to lock only the operations you care about.
Unlisted keys default to `false` (unlocked):

```yaml
~/code/:
  my-framework:
    repo: "git+git@github.com:myorg/my-framework.git"
    options:
      lock:
        import: true
        fmt: true
      lock_reason: "URL managed manually; formatting intentional"
```

Available lock keys:

| Key        | Blocks                                                     |
|------------|-----------------------------------------------------------|
| `import`   | `vcspull import --overwrite` from replacing this URL       |
| `add`      | `vcspull add` from overwriting this entry                  |
| `discover` | `vcspull discover` from overwriting this entry             |
| `fmt`      | `vcspull fmt` from normalizing this entry                  |
| `merge`    | Duplicate-workspace-root merge from displacing this entry  |

### Shorthand: allow_overwrite

`allow_overwrite: false` is a convenience shorthand equivalent to
`lock: {import: true}`. It only guards against `vcspull import --overwrite`:

```yaml
~/code/:
  stable-dep:
    repo: "git+https://github.com/upstream/stable-dep.git"
    options:
      allow_overwrite: false
```

### Lock behavior

- **Defaults** — repositories are unlocked. All operations proceed normally
  unless a lock is explicitly set.
- **Boolean lock** — `lock: true` blocks all five operations (`import`, `add`,
  `discover`, `fmt`, `merge`).
- **Per-operation lock** — only the listed keys are blocked; unlisted keys
  default to `false` (unlocked).
- **lock_reason** — an optional human-readable string shown in log output when
  an operation is skipped. It is purely informational and does not imply
  `lock: true` on its own.
- **Advisory** — locks prevent automated commands from modifying the entry.
  You can still edit the configuration file by hand at any time.

Each command handles locks differently:

| Command | Lock effect | Log level |
|---------|-------------|-----------|
| `vcspull import --overwrite` | Skips URL replacement | info |
| `vcspull add` | Skips with warning | warning |
| `vcspull discover` | Silently skips | debug |
| `vcspull fmt` | Preserves entry verbatim | (silent) |
| Workspace merge | Locked entry wins conflict | info |

```{note}
The `lock` and `lock_reason` fields described here live under `options` and
guard the *configuration entry* against mutation by vcspull commands.

This is different from the worktree-level `lock` / `lock_reason` that lives
inside individual `worktrees` entries and passes `--lock` to
`git worktree add`. See {ref}`cli-worktree` for worktree locking.
```

## Caveats

(git-remote-ssh-git)=

### SSH Git URLs

For git remotes using SSH authorization such as `git+git@github.com:tony/kaptan.git` use `git+ssh`:

```console
git+ssh://git@github.com/tony/kaptan.git
```
