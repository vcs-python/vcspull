(cli)=

(commands)=

# CLI Reference

::::{grid} 1 2 3 3
:gutter: 2 2 3 3

:::{grid-item-card} Sync
:link: sync
:link-type: doc
{ref}`vcspull sync <cli-sync>` pulls and clones repositories from config.
:::

:::{grid-item-card} Add
:link: add
:link-type: doc
{ref}`vcspull add <cli-add>` records one repository in your config file.
:::

:::{grid-item-card} List
:link: list
:link-type: doc
{ref}`vcspull list <cli-list>` shows configured repositories.
:::

:::{grid-item-card} Search
:link: search
:link-type: doc
{ref}`vcspull search <cli-search>` searches repos by name, path, or URL.
:::

:::{grid-item-card} Status
:link: status
:link-type: doc
{ref}`vcspull status <cli-status>` checks working-tree status.
:::

:::{grid-item-card} Discover
:link: discover
:link-type: doc
{ref}`vcspull discover <cli-discover>` scans directories for existing repos.
:::

:::{grid-item-card} Format
:link: fmt
:link-type: doc
{ref}`vcspull fmt <cli-fmt>` normalizes config files.
:::

:::{grid-item-card} Migrate
:link: migrate
:link-type: doc
{ref}`vcspull migrate <cli-migrate>` moves sync options under `options:`.
:::

:::{grid-item-card} Import
:link: import/index
:link-type: doc
{ref}`vcspull import <cli-import>` imports repos from GitHub, GitLab, and more.
:::

:::{grid-item-card} Worktrees
:link: worktree/index
:link-type: doc
{ref}`vcspull worktree <cli-worktree>` manages git worktrees declaratively.
:::

:::{grid-item-card} Completion
:link: completion
:link-type: doc
Shell completions for bash, zsh, and fish.
:::

::::

```{toctree}
:caption: General commands
:maxdepth: 1

sync
add
import/index
discover
list
search
status
worktree/index
fmt
migrate
```

```{toctree}
:caption: Completion
:maxdepth: 1

completion
```

(cli-main)=

(vcspull-main)=

## Command: `vcspull`

```{eval-rst}
.. argparse::
    :module: vcspull.cli
    :func: create_parser
    :prog: vcspull
    :nosubcommands:
    :no-description:

    subparser_name : @replace
        See :ref:`cli-sync`, :ref:`cli-add`, :ref:`cli-import`, :ref:`cli-discover`, :ref:`cli-list`, :ref:`cli-search`, :ref:`cli-status`, :ref:`cli-worktree`, :ref:`cli-fmt`, :ref:`cli-migrate`
```
