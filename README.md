# $ vcspull &middot; [![Python Package](https://img.shields.io/pypi/v/vcspull.svg)](https://pypi.org/project/vcspull/) [![License](https://img.shields.io/github/license/vcs-python/vcspull.svg)](https://github.com/vcs-python/vcspull/blob/master/LICENSE) [![Code Coverage](https://codecov.io/gh/vcs-python/vcspull/branch/master/graph/badge.svg)](https://codecov.io/gh/vcs-python/vcspull)

Manage and sync multiple git, svn, and mercurial repos via JSON or YAML file. Compare to
[myrepos], [mu-repo]. Built on [libvcs].

Great if you use the same repos at the same locations across multiple
machines or want to clone / update a pattern of repos without having to
`cd` into each one.

- clone / update to the latest repos with `$ vcspull`
- use filters to specify a location, repo url or pattern in the
  manifest to clone / update
- supports svn, git, hg version control systems
- automatically checkout fresh repositories
- supports [pip](https://pip.pypa.io/)-style URL's
  ([RFC3986](https://datatracker.ietf.org/doc/html/rfc3986)-based [url
  scheme](https://pip.pypa.io/en/latest/topics/vcs-support/))

See the [documentation](https://vcspull.git-pull.com/), [configuration](https://vcspull.git-pull.com/configuration/) examples, and [config generators](https://vcspull.git-pull.com/configuration/generation.html).

[myrepos]: http://myrepos.branchable.com/
[mu-repo]: http://fabioz.github.io/mu-repo/

# How to

## Install

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

## Configuration

Add your repos to `~/.vcspull.yaml`.

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

`$HOME/.vcspull.yaml` and `$XDG_CONFIG_HOME/vcspull/` (`~/.config/vcspull`) can
be used as a declarative manifest to clone you repos consistently across
machines. Subsequent syncs of nitialized repos will fetch the latest commits.

## Sync your repos

```console
$ vcspull sync
```

Keep nested VCS repositories updated too, lets say you have a mercurial
or svn project with a git dependency:

`external_deps.yaml` in your project root (any filename will do):

```yaml
./vendor/:
  sdl2pp: "git+https://github.com/libSDL2pp/libSDL2pp.git"
```

Clone / update repos via config file:

```console
$ vcspull sync -c external_deps.yaml
```

See the [Quickstart](https://vcspull.git-pull.com/quickstart.html) for
more.

## Pulling specific repos

Have a lot of repos?

you can choose to update only select repos through
[fnmatch](http://pubs.opengroup.org/onlinepubs/009695399/functions/fnmatch.html)
patterns. remember to add the repos to your `~/.vcspull.{json,yaml}`
first.

The patterns can be filtered by by directory, repo name or vcs url.

Any repo starting with "fla":

```console
$ vcspull sync "fla*"
```

Any repo with django in the name:

```console
$ vcspull sync "*django*"
```

Search by vcs + url, since urls are in this format <vcs>+<protocol>://<url>:

```console
$ vcspull sync "git+*"
```

Any git repo with python in the vcspull:

```console
$ vcspull sync "git+*python*
```

Any git repo with django in the vcs url:

```console
$ vcspull sync "git+*django*"
```

All repositories in your ~/code directory:

```console
$ vcspull sync "$HOME/code/*"
```

[libvcs]: https://github.com/vcs-python/libvcs

<img src="https://raw.githubusercontent.com/vcs-python/vcspull/master/docs/_static/vcspull-demo.gif" class="align-center" style="width:45.0%" alt="image" />

# Donations

Your donations fund development of new features, testing and support.
Your money will go directly to maintenance and development of the
project. If you are an individual, feel free to give whatever feels
right for the value you get out of the project.

See donation options at <https://git-pull.com/support.html>.

# More information

- Python support: >= 3.9, pypy
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

[![Docs](https://github.com/vcs-python/vcspull/workflows/docs/badge.svg)](https://vcspull.git-pull.com) [![Build Status](https://github.com/vcs-python/vcspull/workflows/tests/badge.svg)](https://github.com/vcs-python/vcspull/actions?query=workflow%3A%22tests%22)
