# $ vcspull &middot; [![Python Package](https://img.shields.io/pypi/v/vcspull.svg)](https://pypi.org/project/vcspull/) [![Docs](https://github.com/vcs-python/vcspull/workflows/docs/badge.svg)](https://github.com/vcs-python/vcspull/actions?query=workflow%3A%22docs%22) [![Build Status](https://github.com/vcs-python/vcspull/workflows/tests/badge.svg)](https://github.com/vcs-python/vcspull/actions?query=workflow%3A%22tests%22) [![Code Coverage](https://codecov.io/gh/vcs-python/vcspull/branch/master/graph/badge.svg)](https://codecov.io/gh/vcs-python/vcspull) [![License](https://img.shields.io/github/license/vcs-python/vcspull.svg)](https://github.com/vcs-python/vcspull/blob/master/LICENSE)

Synchronize repos in bulk from JSON or YAML file. Compare to
[myrepos](http://myrepos.branchable.com/). Built on [libvcs](https://github.com/vcs-python/libvcs)

Great if you use the same repos at the same locations across multiple
machines or want to clone / update a pattern of repos without having to
`cd` into each one.

- clone /update to the latest repos with `$ vcspull`
- use filters to specify a location, repo url or pattern in the
  manifest to clone / update
- supports svn, git, hg version control systems
- automatically checkout fresh repositories
- [Documentation](https://vcspull.git-pull.com/),
  [Configuration](https://vcspull.git-pull.com/configuration.html),
  and [Config generators](https://vcspull.git-pull.com/config-generation.html)
- supports [pip](https://pip.pypa.io/)-style URL's
  ([RFC3986](https://datatracker.ietf.org/doc/html/rfc3986)-based [url
  scheme](https://pip.pypa.io/en/latest/topics/vcs-support/))

# how to

## install

```console
$ pip install --user vcspull
```

### Developmental releases

You can test the unpublished version of vcspull before its released.

- [pip](https://pip.pypa.io/en/stable/):

  ```console
  $ pip install --user --upgrade --pre vcspull
  ```

- [pipx](https://pypa.github.io/pipx/docs/):

  ```console
  $ pipx install --suffix=@next 'vcspull' --pip-args '\--pre' --force
  ```

  Then use `vcspull@next sync [config]...`.

## configure

add repos you want vcspull to manage to `~/.vcspull.yaml`.

_vcspull does not currently scan for repos on your system, but it may in
the future_

```yaml
~/code/:
  flask: "git+https://github.com/mitsuhiko/flask.git"
~/study/c:
  awesome: "git+git://git.naquadah.org/awesome.git"
~/study/data-structures-algorithms/c:
  libds: "git+https://github.com/zhemao/libds.git"
  algoxy:
    repo: "git+https://github.com/liuxinyu95/AlgoXY.git"
    remotes:
      tony: "git+ssh://git@github.com/tony/AlgoXY.git"
```

(see the author's
[.vcspull.yaml](https://github.com/tony/.dot-config/blob/master/.vcspull.yaml),
more [configuration](https://vcspull.git-pull.com/configuration.html))

next, on other machines, copy your `$HOME/.vcspull.yaml` file or
`$HOME/.vcspull/` directory them and you can clone your repos
consistently. vcspull automatically handles building nested directories.
Updating already cloned/checked out repos is done automatically if they
already exist.

## clone / update your repos

```console
$ vcspull
```

keep nested VCS repositories updated too, lets say you have a mercurial
or svn project with a git dependency:

`external_deps.yaml` in your project root, (can be anything):

```yaml
./vendor/:
  sdl2pp: "git+https://github.com/libSDL2pp/libSDL2pp.git"
```

clone / update repos:

```console
$ vcspull sync -c external_deps.yaml
```

See the [Quickstart](https://vcspull.git-pull.com/quickstart.html) for
more.

## pulling specific repos

have a lot of repos?

you can choose to update only select repos through
[fnmatch](http://pubs.opengroup.org/onlinepubs/009695399/functions/fnmatch.html)
patterns. remember to add the repos to your `~/.vcspull.{json,yaml}`
first.

The patterns can be filtered by by directory, repo name or vcs url.

```console
// any repo starting with "fla"
$ vcspull sync "fla*"
// any repo with django in the name
$ vcspull sync "*django*"

// search by vcs + url
// since urls are in this format <vcs>+<protocol>://<url>
$ vcspull sync "git+*"

// any git repo with python in the vcspull
$ vcspull sync "git+*python*

// any git repo with django in the vcs url
$ vcspull sync "git+*django*"

// all repositories in your ~/code directory
$ vcspull sync "$HOME/code/*"
```

<img src="https://raw.githubusercontent.com/vcs-python/vcspull/master/docs/_static/vcspull-demo.gif" class="align-center" style="width:45.0%" alt="image" />

# Donations

Your donations fund development of new features, testing and support.
Your money will go directly to maintenance and development of the
project. If you are an individual, feel free to give whatever feels
right for the value you get out of the project.

See donation options at <https://git-pull.com/support.html>.

# More information

- Python support: >= 3.7, pypy
- VCS supported: git(1), svn(1), hg(1)
- Source: <https://github.com/vcs-python/vcspull>
- Docs: <https://vcspull.git-pull.com>
- Changelog: <https://vcspull.git-pull.com/history.html>
- API: <https://vcspull.git-pull.com/api.html>
- Issues: <https://github.com/vcs-python/vcspull/issues>
- Test Coverage: <https://codecov.io/gh/vcs-python/vcspull>
- pypi: <https://pypi.python.org/pypi/vcspull>
- Open Hub: <https://www.openhub.net/p/vcspull>
- License: [MIT](https://opensource.org/licenses/MIT).
