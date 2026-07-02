(quickstart)=

# Quickstart

vcspull syncs a workspace of [git](https://git-scm.com/),
[mercurial](https://www.mercurial-scm.org/), and
[subversion](https://subversion.apache.org/) repositories from one
[YAML](https://yaml.org/) or JSON configuration file. Install it, declare
your repositories, and pull everything with a single command.

## Installation

For the latest official version:

```console
$ pip install --user vcspull
```

Or using uv:

```console
$ uv tool install vcspull
```

For one-time use without installation:

```console
$ uvx vcspull
```

Upgrading:

```console
$ pip install --user --upgrade vcspull
```

Or with uv:

```console
$ uv tool upgrade vcspull
```

(developmental-releases)=

### Developmental releases

New versions of vcspull are published to [PyPI](https://pypi.org/) as alpha,
beta, or release candidates. Their versions carry suffixes like `a1`, `b1`,
and `rc1`, respectively.
`1.10.0b4` would mean the 4th beta release of `1.10.0` before general availability.

- [pip]\:

  ```console
  $ pip install --user --upgrade --pre vcspull
  ```

- [pipx]\:

  ```console
  $ pipx install \
      --suffix=@next \
      --pip-args '\--pre' \
      --force \
      'vcspull'
  ```

  The suffixed command is then available as `vcspull@next sync [config]`.

- [uv tool install][uv-tools]\:

  ```console
  $ uv tool install --prerelease allow vcspull
  ```

- [uv]\:

  ```console
  $ uv add vcspull --prerelease allow
  ```

- [uvx]\:

  ```console
  $ uvx --from 'vcspull' --prerelease allow vcspull
  ```

via trunk (can break easily):

- [pip]\:

  ```console
  $ pip install --user -e git+https://github.com/vcs-python/vcspull.git#egg=vcspull
  ```

- [pipx]\:

  ```console
  $ pipx install \
      --suffix=@master \
      --force \
      'vcspull @ git+https://github.com/vcs-python/vcspull.git@master'
  ```

- [uv]\:

  ```console
  $ uv tool install vcspull --from git+https://github.com/vcs-python/vcspull.git
  ```

[pip]: https://pip.pypa.io/en/stable/
[pipx]: https://pypa.github.io/pipx/docs/
[uv]: https://docs.astral.sh/uv/
[uv-tools]: https://docs.astral.sh/uv/concepts/tools/
[uvx]: https://docs.astral.sh/uv/guides/tools/

## Configuration

```{seealso}
{ref}`configuration` and {ref}`cli-import`.
```

You'll check out the source code of [flask][flask] to `~/code/flask`.

Prefer JSON? Create a `~/.vcspull.json` file:

```json
{
  "~/code/": {
    "flask": "git+https://github.com/mitsuhiko/flask.git"
  }
}
```

YAML? Create a `~/.vcspull.yaml` file:

```yaml
~/code/:
  "flask": "git+https://github.com/mitsuhiko/flask.git"
```

Already have repositories cloned locally? Use
`vcspull discover ~/code --recursive` to detect existing Git checkouts and
append them to your configuration. See {ref}`cli-discover` for more details and
options such as `--workspace-root` and `--yes` for unattended runs. After editing or
discovering repositories, run `vcspull fmt --write` (documented in {ref}`cli-fmt`) to
normalize keys and keep your configuration tidy.

The `git+` prefix tells vcspull the repository type. Mercurial repositories
use `hg+`; Subversion uses `svn+`. Repository type and address are specified
in [pip VCS URL][pip vcs url] format.

Now run the command to pull all the repositories in your
`.vcspull.yaml` / `.vcspull.json`:

```console
$ vcspull sync --all
```

Want to manage multiple branches or tags of the same repository?
See {ref}`cli-worktree` for declarative worktree support.

You can also sync arbitrary projects. Let's say you have a mercurial
repository but need a git dependency — add a `.deps.yaml` to your project
(any name works):

```yaml
./vendor/:
  sdl2pp: "git+https://github.com/libSDL2pp/libSDL2pp.git"
```

Use `-f/--file` to specify a config.

```console
$ vcspull sync --file .deps.yaml --all
```

You can also use {mod}`fnmatch` patterns to pull repositories from your
config in various fashions:

```console
$ vcspull sync django
```

```console
$ vcspull sync django\*
```

```console
$ vcspull sync "django*"
```

Filter by VCS URL:

Any repo term beginning with `http`, `https`, or `git` looks up
repositories by their VCS URL.

Pull / update repositories you have with github in the repo url:

```console
$ vcspull sync "git+https://github.com/yourusername/*"
```

Pull / update repositories you have with bitbucket in the repo url:

```console
$ vcspull sync "git+https://*bitbucket*"
```

Filter by the path of the repo on your local machine:

Any repo term beginning with `/`, `./`, `~`, or `$HOME` matches against
the project's path on your system.

Pull all repos inside of _~/study/python_:

```console
$ vcspull sync "$HOME/study/python"
```

Pull all the repos in your config under directories containing "python":

```console
$ vcspull sync ~/*python*
```

[pip vcs url]: https://pip.pypa.io/en/stable/topics/vcs-support/
[flask]: https://flask.palletsprojects.com/
