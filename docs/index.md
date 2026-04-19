---
hide-toc: true
---

(index)=

# vcspull

CLI workspace manager for VCS repos. Sync, organize, and manage multiple
git (and hg/svn) repositories from a single YAML config.

::::{grid} 1 2 3 3
:gutter: 2 2 3 3

:::{grid-item-card} Quickstart
:link: quickstart
:link-type: doc
Install and sync your first repos.
:::

:::{grid-item-card} CLI Reference
:link: cli/index
:link-type: doc
Every command, flag, and option.
:::

:::{grid-item-card} Configuration
:link: configuration/index
:link-type: doc
Config format, locations, schema, and examples.
:::

::::

::::{grid} 1 1 2 2
:gutter: 2 2 3 3

:::{grid-item-card} Internals
:link: internals/index
:link-type: doc
Internal Python API for contributors.
:::

:::{grid-item-card} Contributing
:link: project/index
:link-type: doc
Development setup, code style, and release process.
:::

::::

## Install

```console
$ pip install vcspull
```

```console
$ uv tool install vcspull
```

```console
$ pipx install vcspull
```

See [Quickstart](quickstart.md) for all installation methods and first steps.

## At a glance

```yaml
~/code/:
  flask: "git+https://github.com/pallets/flask.git"
  django: "git+https://github.com/django/django.git"
~/study/:
  linux: "git+https://github.com/torvalds/linux.git"
```

```console
$ vcspull sync
```

```{image} _static/vcspull-demo.gif
:width: 100%
:loading: lazy
```

```{toctree}
:hidden:

quickstart
cli/index
configuration/index
api/index
internals/index
project/index
history
migration
GitHub <https://github.com/vcs-python/vcspull>
```
