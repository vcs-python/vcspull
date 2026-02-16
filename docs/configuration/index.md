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

## Caveats

(git-remote-ssh-git)=

### SSH Git URLs

For git remotes using SSH authorization such as `git+git@github.com:tony/kaptan.git` use `git+ssh`:

```console
git+ssh://git@github.com/tony/kaptan.git
```
