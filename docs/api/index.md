(api)=

# API Reference

Most readers only need the {ref}`CLI <cli>` — this section documents
vcspull's Python modules for the rarer cases where you script against your
configuration from Python.

:::{seealso}
For granular control see the [libvcs documentation](https://libvcs.git-pull.com/en/latest/)---especially the sections on [commands](https://libvcs.git-pull.com/en/latest/usage/commands.html) and [projects](https://libvcs.git-pull.com/en/latest/usage/projects.html).
:::

::::{grid} 1 2 3 3
:gutter: 2 2 3 3

:::{grid-item-card} Config
:link: config
:link-type: doc
{mod}`vcspull.config` loads configuration and extracts repositories.
:::

:::{grid-item-card} Exceptions
:link: exc
:link-type: doc
{mod}`vcspull.exc` defines the exception hierarchy.
:::

:::{grid-item-card} Logging
:link: log
:link-type: doc
{mod}`vcspull.log` formats CLI and file logging.
:::

:::{grid-item-card} Validation
:link: validator
:link-type: doc
{mod}`vcspull.validator` checks parsed configuration shape.
:::

:::{grid-item-card} Utilities
:link: util
:link-type: doc
{mod}`vcspull.util` collects shared helpers.
:::

:::{grid-item-card} Types
:link: types
:link-type: doc
{mod}`vcspull.types` documents configuration data shapes.
:::

::::

```{toctree}
:hidden:

config
exc
log
validator
util
types
```
