(cli)=

(commands)=

# CLI Reference

::::{grid} 1 2 3 3
:gutter: 2 2 3 3

:::{grid-item-card} vcspull sync
:link: sync
:link-type: doc
Pull / clone repositories from config.
:::

:::{grid-item-card} vcspull add
:link: add
:link-type: doc
Add a repository to your config file.
:::

:::{grid-item-card} vcspull list
:link: list
:link-type: doc
List configured repositories.
:::

:::{grid-item-card} vcspull search
:link: search
:link-type: doc
Search repos by name, path, or URL.
:::

:::{grid-item-card} vcspull status
:link: status
:link-type: doc
Show working-tree status for each repo.
:::

:::{grid-item-card} vcspull discover
:link: discover
:link-type: doc
Scan directories for existing repos.
:::

:::{grid-item-card} vcspull fmt
:link: fmt
:link-type: doc
Normalize and format config files.
:::

:::{grid-item-card} vcspull import
:link: import/index
:link-type: doc
Import repos from GitHub, GitLab, and more.
:::

:::{grid-item-card} vcspull worktree
:link: worktree/index
:link-type: doc
Manage git worktrees declaratively.
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

    subparser_name : @replace
        See :ref:`cli-sync`, :ref:`cli-add`, :ref:`cli-import`, :ref:`cli-discover`, :ref:`cli-list`, :ref:`cli-search`, :ref:`cli-status`, :ref:`cli-worktree`, :ref:`cli-fmt`
```
