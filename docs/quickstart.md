(quickstart)=

# Quickstart

## Installation

For latest official version:

```console
$ pip install --user vcspull
```

Upgrading:

```console
$ pip install --user --upgrade vcspull
```

(developmental-releases)=

### Developmental releases

New versions of vcspull are published to PyPI as alpha, beta, or release candidates.
In their versions you will see notfication like `a1`, `b1`, and `rc1`, respectively.
`1.10.0b4` would mean the 4th beta release of `1.10.0` before general availability.

- [pip]\:

  ```console
  $ pip install --user --upgrade --pre vcspull
  ```

- [pipx]\:

  ```console
  $ pipx install --suffix=@next 'vcspull' --pip-args '\--pre' --force
  ```

  Then use `vcspull@next sync [config]...`.

via trunk (can break easily):

- [pip]\:

  ```console
  $ pip install --user -e git+https://github.com/vcs-python/vcspull.git#egg=vcspull
  ```

- [pipx]\:

  ```console
  $ pipx install --suffix=@master 'vcspull @ git+https://github.com/vcs-python/vcspull.git@master' --force
  ```

[pip]: https://pip.pypa.io/en/stable/
[pipx]: https://pypa.github.io/pipx/docs/

## Configuration

```{seealso}

{ref}`configuration` and {ref}`config-generation`.

```

We will check out the source code of [flask][flask] to `~/code/flask`.

Prefer JSON? Create a `~/.vcspull.json` file:

```{code-block} json

{
  "~/code/": {
    "flask": "git+https://github.com/mitsuhiko/flask.git"
  }
}

```

YAML? Create a `~/.vcspull.yaml` file:

```{code-block} yaml

~/code/:
    "flask": "git+https://github.com/mitsuhiko/flask.git"

```

The `git+` in front of the repository URL. Mercurial repositories use
`hg+` and Subversion will use `svn+`. Repo type and address is
specified in [pip vcs url][pip vcs url] format.

Now run the command, to pull all the repositories in your
`.vcspull.yaml` / `.vcspull.json`.

```console

$ vcspull

```

Also, you can sync arbitrary projects, lets assume you have a mercurial
repo but need a git dependency, in your project add `.deps.yaml` (can
be any name):

```{code-block} yaml

./vendor/:
  sdl2pp: 'git+https://github.com/libSDL2pp/libSDL2pp.git'

```

Use `-c` to specify a config.

```console

$ vcspull sync -c .deps.yaml

```

You can also use [fnmatch][fnmatch] to pull repositories from your config in
various fashions, e.g.:

```console

$ vcspull sync django
$ vcspull sync django\*
# or
$ vcspull sync "django*"

```

Filter by vcs URL

Any repo beginning with `http`, `https` or `git` will be look up
repos by the vcs url.

```console

# pull / update repositories I have with github in the repo url
$ vcspull sync "git+https://github.com/yourusername/*"

# pull / update repositories I have with bitbucket in the repo url
$ vcspull sync "git+https://*bitbucket*"

```

Filter by the path of the repo on your local machine:

Any repo beginning with `/`, `./`, `~` or `$HOME` will scan
for patterns of where the project is on your system:

```console

# pull all the repos I have inside of ~/study/python
$ vcspull sync "$HOME/study/python"

# pull all the repos I have in directories on my config with "python"
$ vcspull sync ~/*python*"

```

[pip vcs url]: http://www.pip-installer.org/en/latest/logic.html#vcs-support
[flask]: http://flask.pocoo.org/
[fnmatch]: http://pubs.opengroup.org/onlinepubs/009695399/functions/fnmatch.html
