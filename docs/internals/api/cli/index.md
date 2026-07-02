(api_cli)=

(api_commands)=

# CLI

```{toctree}
:caption: General commands
:maxdepth: 1

sync
add
import
discover
list
search
status
worktree
fmt
migrate
```

## vcspull CLI - `vcspull.cli`

{mod}`vcspull.cli` assembles the argument parser and dispatches each
subcommand to its module — start here to trace how a command line becomes a
function call.

```{eval-rst}
.. automodule:: vcspull.cli
   :members:
   :show-inheritance:
   :undoc-members:
```
