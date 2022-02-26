(quickstart)=

# Quickstart

## Installation

First, install vcspull.

For latest official version:

```{code-block} bash

$ pip install --user vcspull

```

Development version:

```{code-block} bash

$ pip install --user -e git+https://github.com/vcs-python/vcspull.git#egg=vcspull

```

## Configuration

```{seealso}

{ref}`configuration`.

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

```{code-block} bash

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

```{code-block} bash

$ vcspull -c .deps.yaml

```

You can also use [fnmatch][fnmatch] to pull repositories from your config in
various fashions, e.g.:

```{code-block} bash

$ vcspull django
$ vcspull django\*
# or
$ vcspull "django*"

```

Filter by vcs URL

Any repo beginning with `http`, `https` or `git` will be look up
repos by the vcs url.

```{code-block} bash

# pull / update repositories I have with github in the repo url
$ vcspull "git+https://github.com/yourusername/*"

# pull / update repositories I have with bitbucket in the repo url
$ vcspull "git+https://*bitbucket*"

```

Filter by the path of the repo on your local machine:

Any repo beginning with `/`, `./`, `~` or `$HOME` will scan
for patterns of where the project is on your system:

```{code-block} bash

# pull all the repos I have inside of ~/study/python
$ vcspull "$HOME/study/python"

# pull all the repos I have in directories on my config with "python"
$ vcspull ~/*python*"

```

[pip vcs url]: http://www.pip-installer.org/en/latest/logic.html#vcs-support
[flask]: http://flask.pocoo.org/
[fnmatch]: http://pubs.opengroup.org/onlinepubs/009695399/functions/fnmatch.html
