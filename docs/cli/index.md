(cli)=

# Commands

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
        See :ref:`cli-sync`, :ref:`cli-add`, :ref:`cli-import`, :ref:`cli-discover`, :ref:`cli-list`, :ref:`cli-search`, :ref:`cli-status`, :ref:`cli-fmt`
```
